"""Restyle Guns, Gore and Cannoli sprite parts into 重彩 Chinese ink painting.

Design decisions
----------------
* **Keep the drawing, change the pigment.** The first attempt rebuilt the line
  art from region borders and destroyed every facial feature: eyes, brows and
  moustache merged into one blob. The original already contains hand-drawn
  1-3px strokes, so those pixels *are* the ink layer. We recolor around them and
  only thicken the silhouette, which preserves recognisability at 60-100px.
* **Thin dark = stroke, thick dark = garment.** ``erosion_depth`` separates the
  two: a stroke dies after one erosion, a filled coat survives several. This is
  what lets Vinnie's near-black suit become 石青 instead of being read as ink.
* **青绿 layering.** Traditional 重彩 builds blue-green drapery as 石绿 under
  石青. The suit's own shading bands (found by k-means) are assigned
  石青/石绿 alternately, so the two pigments follow the artist's shading rather
  than a noisy per-pixel threshold -- and the pigment ratio is controllable.
* **Semantic slots.** A blind hue shift paints hair and suit the same blue.
  Each sprite slot declares what it is (garment / skin / hat / tie / weapon /
  brass) and the mapping follows the meaning.
* **Silhouette is sacred.** Alpha is carried over untouched; collision boxes and
  animation pivots were authored against it.

CLI
---
    python restyle_ink.py preview      # representative parts -> contact sheet
    python restyle_ink.py batch        # all parts + baked frames
"""
import json
import os
import sys

import numpy as np
from PIL import Image, ImageFilter

PROJECT = r"D:\AI\DAIGuns, Gore and Cannoli from WB"

# ------------------------------------------------------------------ pigments
# name: (base sRGB, deep-tone multiplier, light-tone multiplier)
PIGMENTS = {
    "朱红": ((176, 52, 40), (140, 44, 32), (206, 96, 70)),
    "石青": ((34, 98, 138), (20, 60, 90), (56, 106, 134)),
    "石绿": ((48, 108, 78), (26, 68, 50), (86, 138, 100)),
    "赭石": ((152, 96, 58), (108, 64, 38), (198, 158, 124)),
    "藤黄": ((196, 146, 38), (148, 104, 26), (222, 182, 92)),
    "花青": ((42, 58, 92), (24, 34, 62), (78, 94, 128)),
    "墨": ((34, 31, 28), (19, 17, 15), (74, 68, 62)),
    "纸": ((243, 235, 220), (226, 214, 192), (252, 248, 240)),
}
# flesh is not the same as 赭石 earth pigment: skin needs its own light ramp or
# every face comes out muddy brown
SKIN_TONE = ((196, 148, 106), (142, 94, 62), (232, 202, 170))
INK_RGB = np.array([28, 25, 23], dtype=np.float32)
PAPER_RGB = np.array([243, 235, 220], dtype=np.float32)

# reference hue of each chromatic pigment (degrees)
PIG_HUE = {"朱红": 8, "赭石": 30, "藤黄": 46, "石绿": 146, "石青": 202, "花青": 226}

# what a grey/neutral region of each kind of part should become
ACHROMA = {"garment": "花青", "skin": "赭石", "hat": "墨", "tie": "墨",
           "shoe": "墨", "weapon": "墨", "brass": "藤黄", "glass": "纸",
           "explosive": "墨"}

# the only pigments a given kind of part is allowed to use -- this is what stops
# a black hat turning tan and a steel revolver turning brown
ALLOWED = {
    "garment":   ["石青", "石绿", "花青", "纸"],
    "skin":      ["赭石", "纸", "朱红"],
    "hat":       ["墨", "花青", "朱红"],
    "tie":       ["朱红", "墨"],
    "shoe":      ["墨", "朱红"],
    "weapon":    ["墨", "赭石", "花青"],
    "brass":     ["藤黄", "赭石"],
    "glass":     ["石绿", "石青", "纸"],
    "explosive": ["石绿", "墨", "朱红"],
}

# --------------------------------------------------------------- slot semantics
# prefix -> (kind, primary, secondary)
#   kind: garment | skin | hat | tie | shoe | weapon | brass | glass | explosive
SLOT_RULES = [
    ("tie",        ("tie",     "朱红", None)),
    ("hat",        ("hat",     "墨",   None)),
    ("head",       ("skin",    "赭石", None)),
    ("neckpiece",  ("skin",    "赭石", None)),
    ("hand",       ("skin",    "赭石", None)),
    ("foottip",    ("shoe",    "朱红", None)),
    ("footheel",   ("shoe",    "墨",   None)),
    ("coat",       ("garment", "石青", "石绿")),
    ("torso",      ("garment", "石青", "石绿")),
    ("crotch",     ("garment", "石青", "石绿")),
    ("leg",        ("garment", "石青", "石绿")),
    ("arm",        ("garment", "石青", "石绿")),
    ("bullet",     ("brass",   "藤黄", None)),
    ("shell",      ("brass",   "藤黄", None)),
    ("ammo",       ("brass",   "藤黄", None)),
    ("grenade",    ("explosive", "石绿", None)),
    ("molotov",    ("glass",   "石绿", None)),
    ("gas",        ("glass",   "石绿", None)),
    ("bazooka",    ("weapon",  "墨",   None)),
    ("flame",      ("weapon",  "墨",   None)),
    ("fuel",       ("weapon",  "墨",   None)),
    ("hose",       ("weapon",  "墨",   None)),
    ("gun",        ("weapon",  "墨",   None)),
    ("pistol",     ("weapon",  "墨",   None)),
    ("revolver",   ("weapon",  "墨",   None)),
    ("shotgun",    ("weapon",  "墨",   None)),
    ("magnum",     ("weapon",  "墨",   None)),
    ("lupara",     ("weapon",  "墨",   None)),
    ("tommygun",   ("weapon",  "墨",   None)),
]
DEFAULT_RULE = ("garment", "石青", "石绿")

# Slots whose *dark* band is a separate object worth its own accent pigment.
# The crotch sprite is a leather belt plus a buckle; 朱红革带 is the classic
# 重彩 accent, and it also gives the figure the red note it otherwise lacks.
DARK_ACCENT = {"crotch": "朱红"}


def rule_for(slot):
    s = (slot or "").lower()
    for prefix, rule in SLOT_RULES:
        if prefix in s:
            return rule
    return DEFAULT_RULE


# ------------------------------------------------------------------- utilities
def luminance(rgb):
    return 0.2126 * rgb[..., 0] + 0.7152 * rgb[..., 1] + 0.0722 * rgb[..., 2]


def rgb_to_hsv(rgb):
    a = rgb / 255.0
    mx = a.max(axis=-1)
    mn = a.min(axis=-1)
    df = mx - mn
    s = np.where(mx > 0, df / np.maximum(mx, 1e-9), 0.0)
    h = np.zeros_like(mx)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    nz = df > 1e-9
    i = nz & (mx == r)
    h[i] = ((g[i] - b[i]) / df[i]) % 6
    i = nz & (mx == g)
    h[i] = (b[i] - r[i]) / df[i] + 2
    i = nz & (mx == b)
    h[i] = (r[i] - g[i]) / df[i] + 4
    return h * 60.0, s, mx


def smooth_noise(h, w, cells, rng):
    gh = max(2, int(cells))
    gw = max(2, int(cells * w / max(1, h)))
    grid = (rng.random((gh, gw)) * 255).astype(np.uint8)
    img = Image.fromarray(grid, mode="L").resize((w, h), Image.BICUBIC)
    a = np.array(img, dtype=np.float32) / 255.0
    lo, hi = float(a.min()), float(a.max())
    return (a - lo) / max(1e-6, hi - lo)


def high_freq(h, w, rng, blur=0.6):
    a = (rng.random((h, w)) * 255).astype(np.uint8)
    img = Image.fromarray(a, mode="L").filter(ImageFilter.GaussianBlur(blur))
    return np.array(img, dtype=np.float32) / 255.0


def erode(mask, size=3):
    im = Image.fromarray((mask * 255).astype(np.uint8), mode="L")
    return np.array(im.filter(ImageFilter.MinFilter(size))) > 127


def dilate(mask, size=3):
    im = Image.fromarray((mask * 255).astype(np.uint8), mode="L")
    return np.array(im.filter(ImageFilter.MaxFilter(size))) > 127


def erosion_depth(mask, max_iter=10):
    depth = np.zeros(mask.shape, dtype=np.int16)
    cur = mask.copy()
    for k in range(1, max_iter + 1):
        nxt = erode(cur)
        if not nxt.any():
            break
        depth[nxt] = k
        cur = nxt
    return depth


def kmeans(pixels, k, rng, iters=16):
    n = pixels.shape[0]
    k = min(k, max(1, n))
    centers = [pixels[rng.integers(n)]]
    for _ in range(k - 1):
        d2 = np.min(((pixels[:, None, :] - np.array(centers)[None, :, :]) ** 2)
                    .sum(axis=2), axis=1)
        p = d2 / max(1e-9, d2.sum())
        centers.append(pixels[rng.choice(n, p=p)])
    C = np.array(centers, dtype=np.float32)
    labels = np.zeros(n, dtype=np.int32)
    for _ in range(iters):
        labels = ((pixels[:, None, :] - C[None, :, :]) ** 2).sum(axis=2).argmin(axis=1)
        for i in range(k):
            m = labels == i
            if m.any():
                C[i] = pixels[m].mean(axis=0)
    return labels, C


def shade_color(ramp, t):
    """Lay pigment with continuous density: t in [0,1] is the normalised
    luminance of the original pixel. Keeps every fold and highlight the artist
    drew, which a per-region flat fill cannot do."""
    base, deep, light = (np.array(v, dtype=np.float32) for v in ramp)
    t = np.asarray(t, dtype=np.float32).ravel()
    factor = (0.55 + 0.66 * t)[:, None]
    col = base[None, :] * factor
    # hue character also shifts: deeper pigment in shadow, warmer in light
    w_deep = (0.38 * (1.0 - t))[:, None]
    w_light = (0.30 * t)[:, None]
    col = col * (1 - w_deep) + deep[None, :] * factor * w_deep
    col = col * (1 - w_light) + light[None, :] * factor * w_light
    return np.clip(col, 0, 255)


def pigment_shade(name, rel, ramp=None):
    """Pick base/deep/light tone of a pigment from a relative lightness array."""
    base, deep, light = (np.array(v, dtype=np.float32)
                         for v in (ramp or PIGMENTS[name]))
    rel = np.asarray(rel, dtype=np.float32).ravel()
    t_deep = np.clip((rel + 0.90) / 0.55, 0, 1)[:, None]
    t_light = np.clip((rel - 0.30) / 0.55, 0, 1)[:, None]
    base_b = np.repeat(base[None, :], rel.shape[0], axis=0)
    deep_col = deep[None, :] * (1 - t_deep) + base_b * t_deep
    light_col = base_b * (1 - t_light) + light[None, :] * t_light
    col = np.where((rel < -0.35)[:, None], deep_col, base_b)
    col = np.where((rel > 0.30)[:, None], light_col, col)
    return col


# ------------------------------------------------------------------ the restyle
def restyle(img, slot="", seed=0, cfg=None):
    cfg = cfg or {}
    rng = np.random.default_rng(seed)

    arr = np.array(img.convert("RGBA"), dtype=np.float32)
    h, w = arr.shape[:2]
    rgb = arr[..., :3]
    alpha = arr[..., 3]
    opaque = alpha > 8
    if opaque.sum() < 12:
        return img.copy()

    L = luminance(rgb)
    H, S, V = rgb_to_hsv(rgb)
    kind, primary, secondary = rule_for(slot)

    # ---- 1. separate stroke from dark fill -----------------------------------
    dark = opaque & (L < 30)
    depth = erosion_depth(dark, max_iter=10) if dark.any() else np.zeros((h, w), np.int16)
    ink = dark & (depth <= int(cfg.get("ink_depth", 1)))
    darkfill = dark & (depth > int(cfg.get("ink_depth", 1)))
    # A tie is only 3-5px wide, so the stroke detector swallows the whole part
    # and paints it black. For parts that ARE a thin object, only the contour
    # counts as ink and the body takes its declared pigment.
    if kind in ("tie", "shoe"):
        ink = ink & ~erode(opaque, 3)
    fill = opaque & ~ink

    # ---- 2. segment the fills ------------------------------------------------
    K = int(cfg.get("k", 6))
    labels = np.full((h, w), -1, dtype=np.int32)
    if fill.any():
        lab, centers = kmeans(rgb[fill], K, rng)
        labels[fill] = lab
    else:
        centers = np.zeros((0, 3), dtype=np.float32)

    # ---- 3. classify every region -------------------------------------------
    out_rgb = np.zeros_like(rgb)
    regions = []
    for i in range(len(centers)):
        m = labels == i
        if m.sum() < 4:
            continue
        cL = float(L[m].mean())
        cS = float(S[m].mean())
        cH = float(np.median(H[m]))
        dark_frac = float(darkfill[m].mean())
        regions.append({"idx": i, "mask": m, "area": int(m.sum()), "L": cL,
                        "S": cS, "H": cH, "dark_frac": dark_frac})
    regions.sort(key=lambda r: -r["area"])

    allowed = ALLOWED.get(kind, ALLOWED["garment"])
    chromatic = [p for p in allowed if p in PIG_HUE]

    def hue_dist(hue, pig):
        d = abs(hue - PIG_HUE[pig]) % 360
        return min(d, 360 - d)

    # ---- 3a. decide a pigment per region (geometry only) --------------------
    for rank, r in enumerate(regions):
        cL, cS, cH = r["L"], r["S"], r["H"]

        # skin on a garment part (neck, face on the torso sprite) must stay
        # flesh, otherwise it picks the nearest allowed garment hue and turns
        # green -- a real failure seen in review
        # NOTE: cL is 0-255 luminance, not CIELAB L*, so the window is wide
        skinlike = ((cH <= 50 or cH >= 340) and 0.15 <= cS <= 0.65
                    and 90 <= cL <= 225 and kind in ("garment", "skin"))

        accent = None
        for k, v in DARK_ACCENT.items():
            if k in (slot or "").lower() and r["dark_frac"] > 0.5:
                accent = v
                break

        if accent:
            pig = accent
        elif rank == 0 and not skinlike:
            pig = primary
        elif skinlike:
            pig = "赭石"
        elif rank == 1 and kind == "garment" and secondary:
            pig = secondary
        elif cS > 0.45 and (cH < 25 or cH >= 335):
            pig = "朱红"          # blood, the neck piece, strong red accents
        elif kind == "skin" and ((cH > 160 and cS > 0.20)
                                 or (cL < 85 and cS < 0.30)):
            # hair and its cold highlights belong to ink, not to flesh
            pig = "墨" if cL < 110 else "花青"
        elif cS < 0.15:
            if cL > 200 and "纸" in allowed:
                pig = "纸"
            elif cL < 42 and "墨" in allowed:
                pig = "墨"
            else:
                pig = ACHROMA.get(kind, allowed[0])
        elif chromatic:
            # nearest allowed hue, biased towards the part's declared pigment
            pig = min(chromatic,
                      key=lambda p: hue_dist(cH, p) + (0 if p == primary else 12))
        else:
            pig = ACHROMA.get(kind, allowed[0])

        r["pig"] = pig
        r["skinlike"] = skinlike

    # ---- 3b. one tonal range per pigment -----------------------------------
    # Skin, hair and cloth occupy different luminance ranges. A single
    # part-wide range stretched the shadowed cheek into the highlight end and
    # erased the modelling; each pigment needs its own floor and ceiling.
    _chunks = {}
    for r in regions:
        _chunks.setdefault(r["pig"], []).append(L[r["mask"]])
    bounds = {}
    for pig, chunks in _chunks.items():
        v = np.concatenate(chunks)
        lo, hi = (float(x) for x in np.percentile(v, [4, 96]))
        bounds[pig] = (lo, max(hi, lo + 10.0))

    # ---- 3c. lay the pigment ------------------------------------------------
    for rank, r in enumerate(regions):
        m = r["mask"]
        pig = r["pig"]
        lo, hi = bounds[pig]

        # continuous 罩染: the region decides WHICH pigment, the original
        # luminance decides how densely it is laid
        t = np.clip((L[m] - lo) / max(1e-6, hi - lo), 0.0, 1.0)
        if pig == "纸":
            # unpainted paper keeps its value; the grain pass adds the life
            col = np.repeat(np.array(PIGMENTS["纸"][0], dtype=np.float32)[None, :],
                            len(t), axis=0)
        else:
            ramp = SKIN_TONE if (pig == "赭石" and r["skinlike"]) else PIGMENTS[pig]
            col = shade_color(ramp, t)

        # 青绿 layering: the shadow side of the main garment is laid in 石绿
        # underneath the 石青 glaze. Doing it inside one region (rather than by
        # picking a second cluster) keeps the band spatially coherent.
        if (rank == 0 and kind == "garment" and secondary
                and m.sum() > 0.10 * opaque.sum()):
            dev = L[m] - r["L"]
            sd = float(dev.std())
            if sd > 2.5:
                thr = np.quantile(dev, float(cfg.get("green_split", 0.35)))
                shadow = dev <= thr
            else:
                yy = np.nonzero(m)[0].astype(np.float32)
                yy = (yy - yy.min()) / max(1e-6, yy.max() - yy.min())
                shadow = yy > (1.0 - float(cfg.get("green_split", 0.35)))
            if 0.02 < shadow.mean() < 0.85:
                col[shadow] = shade_color(PIGMENTS[secondary], t[shadow])

        # 重彩 sits on sized paper, so pigment never reaches full chroma
        col = col * float(cfg.get("pigment_gain", 0.95)) + \
            PAPER_RGB[None, :] * float(cfg.get("paper_mix", 0.06))
        out_rgb[m] = col

    # pixels the k-means dropped (tiny islands) inherit the primary tone
    left = fill & (labels < 0)
    if left.any():
        out_rgb[left] = np.array(PIGMENTS[primary][0], dtype=np.float32) * 0.9 + \
            PAPER_RGB * 0.1

    # ---- 4. paper grain + 皴擦 ----------------------------------------------
    grain_amp = float(cfg.get("grain", 7.0))
    grain = (high_freq(h, w, rng, 0.85) - 0.5) * 2 * grain_amp
    fiber = (smooth_noise(h, w, 26.0, rng) - 0.5) * 2 * grain_amp * 0.7
    out_rgb += (grain + fiber)[..., None] * (fill & ~darkfill)[..., None]

    if cfg.get("cun", True):
        rough = smooth_noise(h, w, 9.0, rng)
        cun = (rough > 0.86) & fill & ~darkfill
        out_rgb[cun] *= 0.90

    # ---- 5. ink layer --------------------------------------------------------
    # original strokes keep their geometry; tone follows original darkness
    ink_rel = np.clip((L - 12.0) / 60.0, 0, 1)
    ink_tone = 0.72 + 0.9 * ink_rel
    ink_rgb = INK_RGB[None, None, :] * ink_tone[..., None]
    out_rgb[ink] = ink_rgb[ink]

    # Two brush weights, like a real figure painting: the silhouette is a heavy
    # loaded stroke, interior detail keeps the original fine line. Thickening
    # the interior is what destroyed faces in the first attempt.
    rim_ink = ink & ~erode(opaque, 3)
    # scale-aware brush weight: a large form takes a loaded contour, a 20px
    # detail keeps a fine line (this is how a painter sizes the brush)
    thick = dilate(rim_ink, 3) & opaque & ~ink
    if opaque.sum() > 12000:
        thick |= dilate(thick, 3) & opaque & ~ink
    # a single px of bleed on interior strokes keeps them from looking wiry
    thick |= dilate(ink, 3) & opaque & ~ink & (L < 150)
    out_rgb[thick] = INK_RGB[None, None, :] * 0.95

    # warm 洇 halo just inside the contour
    halo = (~ink) & (~thick) & dilate(ink | thick, 3) & fill
    if halo.any():
        out_rgb[halo] = out_rgb[halo] * 0.93 + PAPER_RGB[None, :] * 0.07

    # ---- 6. composite --------------------------------------------------------
    out = np.zeros_like(arr)
    out[..., :3] = np.clip(out_rgb, 0, 255)
    out[..., 3] = alpha
    res = Image.fromarray(out.astype(np.uint8), mode="RGBA")
    res = res.filter(ImageFilter.UnsharpMask(radius=0.8, percent=28, threshold=3))
    a2 = np.array(res, dtype=np.uint8)
    a2[..., 3] = alpha.astype(np.uint8)
    return Image.fromarray(a2, mode="RGBA")


# ---------------------------------------------------------------------- driver
def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "preview"
    char = "vinnie"
    src = os.path.join(PROJECT, "art", f"{char}_parts", "original")
    dst = os.path.join(PROJECT, "art", f"{char}_parts", "restyled")
    os.makedirs(dst, exist_ok=True)

    files = [f for f in sorted(os.listdir(src))
             if f.lower().endswith(".png") and not f.startswith("_")]
    if mode == "preview":
        want = ["24_Head", "13_TorsoChest", "19_Crotch", "31_Hat",
                "52_Tommygun", "47_Magnum", "16_LegLowBack", "08_Molotov"]
        files = [f for f in files if any(f.startswith(p) for p in want)] or files[:8]

    for i, f in enumerate(files):
        img = Image.open(os.path.join(src, f))
        slot = f.split("_")[1] if "_" in f else f
        res = restyle(img, slot=slot, seed=i * 7919 + 13)
        res.save(os.path.join(dst, f))
        print(f"[{i + 1}/{len(files)}] {f}", flush=True)

    print(f"wrote {len(files)} files to {dst}")


if __name__ == "__main__":
    main()
