"""Put real brushwork on a restyled component without touching its shape.

Why this exists
---------------
Image-to-image redraw of this game's art fails, and the failure is structural,
not a tuning problem: the components are 77-99% dark, so a diffusion model has
almost no signal to work from.  Asked to restyle a night quay wall it returns a
bright paper illustration with the layout moved -- the brick ends up somewhere
else and every dark area becomes white.  Two attempts, two different models,
same outcome.

So the model is not asked to redraw anything.  It is asked for the one thing it
is good at and cannot get wrong: a **seamless patch of pigment and brushwork**.
That patch is then used as a modulation field over the restyled component, which
keeps the silhouette, the light map and the composition exactly where they were.

How the modulation works
------------------------
The brush patch is z-scored before use.  A raw luminance multiply would shift
the component's overall tone (a bright patch would lighten the whole wall); a
zero-mean field adds stroke contrast and leaves the mean alone.  The modulation
is then gated to mid-tones, because the lamp halos and the near-black areas are
the baked light map -- `restyle_scene` treats L* as a hard constraint and this
step must not break it.

Output keeps the original alpha bit-for-bit.
"""
import io
import json
import os
import sys

import numpy as np
from PIL import Image, ImageFilter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ggc_assets import PROJECT  # noqa: E402

ART = os.path.join(PROJECT, "art")
RESTYLED = os.path.join(ART, "scene_restyle", "all")
BRUSH = os.path.join(ART, "gen", "brush")
INV = os.path.join(ART, "scene_inventory.json")


def srgb_to_lab(rgb):
    c = rgb.astype(np.float32) / 255.0
    c = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    m = np.array([[0.4124, 0.3576, 0.1805],
                  [0.2126, 0.7152, 0.0722],
                  [0.0193, 0.1192, 0.9505]], np.float32)
    xyz = c.reshape(-1, 3) @ m.T
    xyz /= np.array([0.95047, 1.0, 1.08883], np.float32)
    f = np.where(xyz > 0.008856, np.cbrt(xyz), 7.787 * xyz + 16 / 116)
    return (116 * f[:, 1] - 16, 500 * (f[:, 0] - f[:, 1]),
            200 * (f[:, 1] - f[:, 2]))


def lab_to_srgb(L, a, b):
    fy = (L + 16) / 116
    fx = fy + a / 500
    fz = fy - b / 200
    f = np.stack([fx, fy, fz], 1)
    xyz = np.where(f ** 3 > 0.008856, f ** 3, (f - 16 / 116) / 7.787)
    xyz = xyz * np.array([0.95047, 1.0, 1.08883], np.float32)
    m = np.array([[3.2406, -1.5372, -0.4986],
                  [-0.9689, 1.8758, 0.0415],
                  [0.0557, -0.2040, 1.0570]], np.float32)
    c = np.clip(xyz @ m.T, 0, 1)
    c = np.where(c <= 0.0031308, c * 12.92, 1.055 * c ** (1 / 2.4) - 0.055)
    return (c * 255).round().astype(np.uint8)


def field(patch, shape, amp=1.0, soft=1.6):
    """Brush patch -> zero-mean modulation field, resized to the target."""
    g = np.array(patch.convert("L").resize((shape[1], shape[0]),
                                           Image.LANCZOS), np.float32) / 255.0
    g = np.array(Image.fromarray((g * 255).astype(np.uint8))
                 .filter(ImageFilter.GaussianBlur(soft)), np.float32) / 255.0
    z = (g - g.mean()) / (g.std() + 1e-6)
    return np.clip(z / 2.2, -1, 1) * amp


def apply(restyled, brush, amp=0.16, chroma=0.10):
    rgba = restyled.convert("RGBA")
    arr = np.array(rgba)
    h, w = arr.shape[:2]
    L, a, b = srgb_to_lab(arr[..., :3])
    L = L.reshape(h, w)
    a = a.reshape(h, w)
    b = b.reshape(h, w)

    f = field(brush, (h, w), amp)
    # 中间调权重：纯黑与高光（灯晕）不动，L* 是烘焙好的光图
    gate = np.clip((L - 8) / 22, 0, 1) * np.clip((92 - L) / 22, 0, 1)

    L2 = L * (1 + f * gate)
    a2 = a + f * gate * 12 * chroma
    b2 = b + f * gate * 12 * chroma

    rgb = lab_to_srgb(L2.reshape(-1), a2.reshape(-1), b2.reshape(-1))\
        .reshape(h, w, 3)
    out = np.dstack([rgb, arr[..., 3]])          # alpha 原样保留
    return Image.fromarray(out, "RGBA")


def composite_lstar(orig, gen, detail=0.45, floor=0.30):
    """Generated pigment + the *original* light map.

    The point of this function is that the model never has to get the darkness
    right.  It is fed a gamma-lifted copy (so it has signal to work with) and
    returns a bright illustration; here its **chroma** is kept and its
    luminance is thrown away, replaced by the original's L*.  The night comes
    back, the lamp halos stay exactly where the artist put them, and the white
    paper the model invents for transparent areas is cut away by the original
    alpha.

    Chroma is attenuated with darkness (`floor` .. 1.0 across L* 0..38): real
    mineral pigment reads as colour in light and as 墨 in shadow, and without
    this the dark half of every level turns into muddy orange.
    """
    from restyle_scene import box_blur

    o = np.array(orig.convert("RGBA"))
    h, w = o.shape[:2]
    g = np.array(gen.convert("RGB").resize((w, h), Image.LANCZOS))

    Lo = srgb_to_lab(o[..., :3])[0].reshape(h, w)
    Lg, ag, bg = srgb_to_lab(g)
    Lg, ag, bg = Lg.reshape(h, w), ag.reshape(h, w), bg.reshape(h, w)

    hp = Lg - box_blur(Lg, 6)
    gate = np.clip((Lo - 8) / 22, 0, 1) * np.clip((92 - Lo) / 22, 0, 1)
    L2 = Lo + hp * detail * gate

    cs = np.clip(Lo / 38.0, floor, 1.0)
    rgb = lab_to_srgb(L2.reshape(-1), (ag * cs).reshape(-1),
                      (bg * cs).reshape(-1)).reshape(h, w, 3)
    return Image.fromarray(np.dstack([rgb, o[..., 3]]), "RGBA")


def main():
    inv = {r["texture"]: r for r in
           json.load(io.open(INV, encoding="utf-8"))}
    jobs = sys.argv[1:] or ["Quay_05", "Crane-small_01"]
    warm = Image.open(os.path.join(BRUSH, "brush_warm_21.png"))
    cool = Image.open(os.path.join(BRUSH, "brush_cool_22.png"))
    os.makedirs(os.path.join(ART, "gen", "paint"), exist_ok=True)

    for name in jobs:
        r = inv[name]
        k = "%s__%d" % (r["file"], r["path_id"])
        src = os.path.join(RESTYLED, k + ".png")
        if not os.path.exists(src):
            print("缺 restyle:", name)
            continue
        base = Image.open(src)
        # 暖冷两张按原图自身的暖度混合
        arr = np.array(base.convert("RGB"), np.float32)
        warmth = float((arr[..., 0].mean() - arr[..., 2].mean()) / 128.0)
        mix = float(np.clip(0.5 + warmth, 0.15, 0.85))
        patch = Image.blend(cool, warm, mix)
        out = apply(base, patch)
        p = os.path.join(ART, "gen", "paint", name + "_painted.png")
        out.save(p)
        print("%-18s warmth=%.2f  -> %s" % (name, warmth, p))


if __name__ == "__main__":
    main()
