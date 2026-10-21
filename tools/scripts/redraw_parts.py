"""Redraw pipeline (plan B): replace part art with newly drawn sprites.

Why this exists
---------------
``restyle_ink.py`` recolours pixels. It can turn a navy coat olive, but it can
never turn a fedora into a helmet -- the silhouette is the input, not the output.
Plan B needs new *drawing*, so the artwork has to come from a generative model.

The hard constraint is mechanical, not artistic: the prefab assembles ~42
separate sprites by Transform. If the new art does not land exactly where the
old art did, the character comes apart. So this pipeline never lets the model
decide geometry:

    1. build a 1:1 native canvas from the ORIGINAL parts   (--canvas)
    2. generate one full-body concept in the same pose     (external)
    3. fit the concept to the original silhouette bbox,
       then read every part back out of it through that
       part's own alpha mask                               (--slice)
    4. every part keeps its exact canvas size, pivot and
       alpha, so the assembly is bit-compatible

What that buys and what it costs
--------------------------------
Bought: garment *forms* can change -- a fedora crown can be drawn as a helmet
dome, lapels as a stand collar, a trench hem as a field blouse -- because the
model redraws inside the outline instead of mapping colours onto it.

Cost: the outline itself is still the old outline. A helmet cannot be wider
than the fedora was. Growing the silhouette means changing alpha, which changes
what the acceptance gate measures and needs a fresh collision review. That is a
deliberate second step, not something to slip in silently.

Usage
-----
    python redraw_parts.py Vinnie --canvas
    python redraw_parts.py Vinnie --slice art/vinnie_parts/_concept.png
"""
import io
import json
import math
import os
import sys

import numpy as np
from PIL import Image

from ggc_assets import AssetDB, PROJECT, tn

CHAR = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("--") \
    else "Vinnie"
BASE = os.path.join(PROJECT, "art", CHAR.lower() + "_parts")
ORIG = os.path.join(BASE, "original")
REDRAW = os.path.join(BASE, "redraw")
PLACEMENT = os.path.join(BASE, "placement.json")

BACKUP = os.path.join(PROJECT, "backup")
PRISTINE = {f: os.path.join(BACKUP, f)
            for f in os.listdir(BACKUP) if f.endswith(".assets")} \
    if os.path.isdir(BACKUP) else {}

# Canvas scale. 200 is the ppu most parts use, so the overwhelming majority of
# parts are copied 1:1 and never resampled. The handful at 210 lose 5%.
PPU = 200.0
PAD = 8
# strength of the khaki->olive hue correction on cloth parts
OLIVE_K = 0.30
OLIVE_TARGET = 100.0
# How many pixels to grow the ink stroke by.
#
# A dark garment already carries a lot of dark area, so 1 px is enough for
# Vinnie's navy coat (ink_ratio 0.285). A light khaki uniform carries far less:
# the same drawing measures 0.193, under the shared 0.2 floor, purely because
# 国防色 is a light colour. Thickening to 2 px brings it to 0.218 and still
# reads as brushwork rather than as a thick outline. The table is per role
# because it follows the garment's value, not the character.
INK_PX_BY_ROLE = {
    "日军士兵": 2, "日军佐官": 2, "日军将官": 2,
    "日本海军": 2, "日军军医": 2,
    "日本平民·浅色": 2,
}
INK_PX = int(sys.argv[sys.argv.index("--ink") + 1]) if "--ink" in sys.argv else None


def part_png(p):
    return os.path.join(ORIG, p["file"])


def build_canvas():
    """Composite the active parts at native scale; record where each one lands."""
    if not PRISTINE:
        raise SystemExit("backup/ missing -- refusing to build a pose reference "
                         "from already-patched game files")
    db = AssetDB(file_map=PRISTINE)
    go = db.find_go(CHAR)
    if go is None:
        raise SystemExit(f"{CHAR} not found")

    # the extraction manifest already named every part file; map back through
    # the sprite key so the redrawn PNGs overwrite the right originals
    with io.open(os.path.join(BASE, "manifest.json"), encoding="utf-8") as fh:
        man = json.load(fh)
    file_of = {(p["sprite_file"], p["sprite_path_id"]): p["file"]
               for p in man["parts"]}
    slot_of = {(p["sprite_file"], p["sprite_path_id"]): p["slot"]
               for p in man["parts"]}

    resolved = []
    minx = miny = 1e9
    maxx = maxy = -1e9
    for p in db.walk(go):
        if not p.active:
            continue
        sp = db.resolve(p.sprite, p.ctx)
        if tn(sp) != "Sprite":
            continue
        meta = db.sprite_meta(sp)
        if not meta or "image" not in meta:
            continue
        img = meta["image"]
        ppu = meta["ppu"]
        lx = p.x - (meta["pivot_x"] / ppu) * p.sx
        ly = p.y - (meta["pivot_y"] / ppu) * p.sy
        ux = lx + (img.width / ppu) * p.sx
        uy = ly + (img.height / ppu) * p.sy
        minx, maxx = min(minx, lx), max(maxx, ux)
        miny, maxy = min(miny, ly), max(maxy, uy)
        resolved.append({
            "slot": slot_of.get((meta["sprite_file"], meta["sprite_path_id"]),
                                p.go_name or ""),
            "file": file_of.get((meta["sprite_file"], meta["sprite_path_id"])),
            "go_path": p.go_path,
            "order": p.order,
            "depth": p.depth,
            "sprite_file": meta["sprite_file"],
            "sprite_path_id": meta["sprite_path_id"],
            "size": [img.width, img.height],
            "ppu": ppu,
            "rect": [lx, ly, ux, uy],
            "img": img,
        })

    W = int(math.ceil((maxx - minx) * PPU)) + PAD * 2
    H = int(math.ceil((maxy - miny) * PPU)) + PAD * 2
    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))

    # draw back-to-front: the prefab's sorting order, then hierarchy depth
    resolved.sort(key=lambda r: (r["order"], -r["depth"]))
    out = []
    for r in resolved:
        lx, ly, ux, uy = r["rect"]
        px = int(round((lx - minx) * PPU)) + PAD
        py = int(round((maxy - uy) * PPU)) + PAD
        pw = max(1, int(round((ux - lx) * PPU)))
        ph = max(1, int(round((uy - ly) * PPU)))
        canvas.alpha_composite(r["img"].resize((pw, ph), Image.LANCZOS), (px, py))
        out.append({k: v for k, v in r.items() if k != "img"} |
                   {"canvas_rect": [px, py, pw, ph]})

    os.makedirs(BASE, exist_ok=True)
    canvas.save(os.path.join(BASE, "_native_canvas.png"))
    with io.open(PLACEMENT, "w", encoding="utf-8") as fh:
        json.dump({"char": CHAR, "ppu": PPU, "pad": PAD,
                   "canvas": [W, H], "origin": [minx, miny], "parts": out},
                  fh, indent=1, ensure_ascii=False)

    # a padded, paper-backed copy is what the image model gets to look at
    pad = 24
    ref = Image.new("RGBA", (W + pad * 2, H + pad * 2), (243, 235, 220, 255))
    ref.alpha_composite(canvas, (pad, pad))
    ref.convert("RGB").save(os.path.join(BASE, "_pose_reference.png"))

    print(f"canvas {W}x{H}, {len(out)} active parts -> _native_canvas.png")
    print(f"pose reference -> _pose_reference.png")


def _fit(concept, target_box):
    """Scale + translate the concept so its opaque bbox matches target_box."""
    a = np.array(concept.convert("RGBA"))
    ys, xs = np.nonzero(a[..., 3] > 24)
    if len(xs) == 0:
        raise SystemExit("concept image is fully transparent")
    cb = (xs.min(), ys.min(), xs.max() + 1, ys.max() + 1)
    tb = target_box
    sx = (tb[2] - tb[0]) / max(1, cb[2] - cb[0])
    sy = (tb[3] - tb[1]) / max(1, cb[3] - cb[1])
    # one uniform factor: a non-uniform fit would shear the figure and the
    # parts would no longer register with the pivots
    s = min(sx, sy)
    nw, nh = max(1, int(round(concept.width * s))), max(1, int(round(concept.height * s)))
    scaled = concept.resize((nw, nh), Image.LANCZOS)
    # centre it on the target box
    tx = int(round((tb[0] + tb[2]) / 2 - nw / 2 - cb[0] * s))
    ty = int(round((tb[1] + tb[3]) / 2 - nh / 2 - cb[1] * s))
    fitted = Image.new("RGBA", (concept.width, concept.height), (0, 0, 0, 0))
    fitted.paste(scaled, (tx, ty))
    return fitted, s


def _bleed_colors(img, iters=160):
    """Spread painted colour into the transparent area, outward from the edges.

    Without this the slice is black. The old coat occupies a large alpha region
    that the new costume does not fill, so those pixels are transparent in the
    concept -- and forcing the original alpha on them makes (0,0,0) opaque
    black. The first composite came out with a black hump behind the head and a
    black skirt around the legs for exactly this reason.

    Bleeding keeps the nearest painted colour instead, so an area the new
    costume does not cover continues the adjacent fabric rather than turning
    into a hole.
    """
    a = np.array(img.convert("RGBA"))
    rgb = a[..., :3].astype(np.float32)
    known = a[..., 3] > 16
    if not known.any():
        return img
    # seed unknown pixels with the mean of the painted area, so anything the
    # bleed cannot reach degrades to a plausible tone instead of black
    rgb[~known] = rgb[known].mean(axis=0)
    for _ in range(iters):
        if known.all():
            break
        acc = np.zeros_like(rgb)
        cnt = np.zeros(known.shape, np.float32)
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            src = np.roll(known, (dy, dx), (0, 1))
            srgb = np.roll(rgb, (dy, dx), (0, 1))
            if dy == 1:
                src[0, :] = False
            elif dy == -1:
                src[-1, :] = False
            if dx == 1:
                src[:, 0] = False
            elif dx == -1:
                src[:, -1] = False
            acc += srgb * src[..., None]
            cnt += src
        grow = (~known) & (cnt > 0)
        rgb[grow] = acc[grow] / cnt[grow][:, None]
        known = known | grow
    out = a.copy()
    out[..., :3] = np.clip(rgb, 0, 255).astype(np.uint8)
    return Image.fromarray(out)


def _register(concept, canvas, ds=2):
    """Find the scale+offset that maximises silhouette IoU with the original.

    A bbox fit is not enough. The generated figure has narrower legs than the
    cartoon, so matching bounding boxes left the head ~30 px to the right and
    the parts sampled the wrong regions -- the toe caps came out 100% black.
    IoU registration locks the body mass instead of the extents, which is what
    the per-part alpha masks actually depend on.

    Search is done on a downscaled alpha mask; the winning transform is then
    applied to the full-resolution image.
    """
    W, H = canvas.size
    tgt = (np.array(canvas)[..., 3] > 8)

    best = (0.0, 1.0, 0, 0)
    # NOTE: the scaled image has to be PASTED into a W x H canvas. An earlier
    # version did resize((nw,nh)).resize((W,H)), which returns to the original
    # size -- the loop then only varied blur, not scale, and picked s=0.76
    # because a blurred mask happened to overlap the fat original silhouette
    # best. The whole figure came out two-thirds size.
    def probe(s, dx, dy, ds):
        base = _apply(concept, canvas, 0.0, s, dx, dy)
        m = (np.array(base)[..., 3] > 8)[::ds, ::ds]
        t = tgt[::ds, ::ds]
        inter = np.logical_and(m, t).sum()
        if inter == 0:
            return 0.0
        return inter / np.logical_or(m, t).sum()

    for s in [0.86 + 0.03 * i for i in range(11)]:
        for dy in range(-18, 19, 6):
            for dx in range(-18, 19, 6):
                iou = probe(s, dx, dy, 4)
                if iou > best[0]:
                    best = (iou, s, dx, dy)
    # refine around the coarse winner
    _, s0, dx0, dy0 = best
    for s in [s0 - 0.04 + 0.02 * i for i in range(5)]:
        for dy in range(dy0 - 5, dy0 + 6, 2):
            for dx in range(dx0 - 5, dx0 + 6, 2):
                iou = probe(s, dx, dy, 2)
                if iou > best[0]:
                    best = (iou, s, dx, dy)
    return best


def _apply(concept, canvas, iou, s, dx, dy):
    W, H = canvas.size
    base = concept.convert("RGBA").resize((W, H), Image.LANCZOS)
    nw, nh = max(1, int(W * s)), max(1, int(H * s))
    scaled = base.resize((nw, nh), Image.LANCZOS)
    out = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    out.paste(scaled, ((W - nw) // 2 + dx, (H - nh) // 2 + dy))
    return out


# Weapons and props are NOT redrawn.
#
# Two reasons. The generated concept puts its gun somewhere slightly different
# from the original, so slicing it into the gun parts laid a second weapon over
# the first -- two Thompsons at once. And there is nothing to gain: the game's
# weapon already IS a Thompson M1928A1, which is exactly what a Chinese
# Expeditionary Force soldier carried. They keep their route-A palette art.
_PROP = ("gun", "pistol", "revolver", "shotgun", "magnum", "lupara", "tommygun",
         "bazooka", "maxim", "teslacoil", "actionpump", "molotov", "gas",
         "grenade", "bullet", "shell", "ammo", "hose", "fuel", "flame")


def _is_prop(slot):
    s = (slot or "").lower()
    return any(k in s for k in _PROP)


# Slots whose material is cloth, so a hue correction toward olive is legitimate.
# A face is not: shifting skin hue turns a man green. Matched by prefix.
_CLOTH = ("coat", "torso", "crotch", "leg", "arm", "hat", "neckpiece", "tie")

# The head group. These sprites are stacked at one pivot, so they must be
# placed by a single shared transform -- see _group_transform.
HEAD_SLOTS = ("hat", "head", "neckpiece", "headlips")


def _olive_shift(img, k=0.30):
    """Nudge khaki-brown cloth toward olive, keeping every bit of drawn detail.

    The model painted the uniform as warm khaki; the spec calls for HBT olive.
    Running restyle_ink over the redrawn art to force the palette was tried and
    is the wrong tool -- it segments by k-means, which is built for flat cartoon
    fills, and it shattered the pouches and the helmet net into speckle.

    A bounded hue rotation is safe here because it is a tone curve, not a
    segmentation: luminance and saturation structure survive untouched, so the
    drawing stays exactly as generated and only its temperature moves.
    """
    a = np.array(img.convert("RGBA"))
    rgb = a[..., :3].astype(np.float32) / 255.0
    mx = rgb.max(axis=-1)
    mn = rgb.min(axis=-1)
    df = mx - mn
    s = np.where(mx > 0, df / np.maximum(mx, 1e-9), 0.0)
    h = np.zeros_like(mx)
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    nz = df > 1e-6
    i = nz & (mx == r)
    h[i] = ((g[i] - b[i]) / df[i]) % 6
    i = nz & (mx == g)
    h[i] = (b[i] - r[i]) / df[i] + 2
    i = nz & (mx == b)
    h[i] = (r[i] - g[i]) / df[i] + 4
    h = h * 60.0

    band = (h >= 15) & (h <= 62) & (s > 0.10) & (a[..., 3] > 8)
    h2 = np.where(band, h + k * (OLIVE_TARGET - h), h)

    # back to RGB via the same HSV triple
    hh = (h2 / 60.0) % 6.0
    c = mx * s
    x = c * (1 - np.abs(hh % 2 - 1))
    m = mx - c
    out = np.zeros_like(rgb)
    zero = np.zeros_like(c)
    # NOTE: these must be half-open ranges, not cumulative `<` tests. Written as
    # `hh < 1`, `hh < 2`, ... every pixel matches every branch and the last one
    # wins -- which painted the whole uniform magenta (R and B swapped) while
    # the maths looked right.
    conds = [((hh >= 0) & (hh < 1), (c, x, zero)),
             ((hh >= 1) & (hh < 2), (x, c, zero)),
             ((hh >= 2) & (hh < 3), (zero, c, x)),
             ((hh >= 3) & (hh < 4), (zero, x, c)),
             ((hh >= 4) & (hh < 5), (x, zero, c)),
             ((hh >= 5) & (hh < 6), (c, zero, x))]
    for cond, (rr, gg, bb) in conds:
        out[..., 0][cond] = rr[cond]
        out[..., 1][cond] = gg[cond]
        out[..., 2][cond] = bb[cond]
    out = (out + m[..., None]) * 255.0

    res = a.copy()
    res[..., :3] = np.clip(np.where(band[..., None], out, a[..., :3]), 0, 255)
    return Image.fromarray(res.astype(np.uint8))


def _thicken_ink(img, px=1, weight=0.85):
    """Grow the dark stroke by a pixel or two.

    The generated art draws with a fine line; 重彩 wants 中等笔触, and the
    measured ink coverage came out 0.244 against a 0.28 floor. Thickening the
    existing dark pixels is the honest fix -- widening the floor would have
    accepted thin vector linework as brushwork.
    """
    a = np.array(img.convert("RGBA"))
    rgb = a[..., :3].astype(np.float32)
    L = 0.2126 * rgb[..., 0] + 0.7152 * rgb[..., 1] + 0.0722 * rgb[..., 2]
    dark = (L < 50) & (a[..., 3] > 8)
    if not dark.any():
        return img
    grown = dark.copy()
    for _ in range(px):
        g = grown.copy()
        g[1:, :] |= grown[:-1, :]
        g[:-1, :] |= grown[1:, :]
        g[:, 1:] |= grown[:, :-1]
        g[:, :-1] |= grown[:, 1:]
        grown = g
    edge = grown & ~dark
    if not edge.any():
        return img
    # darken toward the neighbouring stroke colour rather than flat black
    ink = np.array([28.0, 25.0, 23.0], dtype=np.float32)
    rgb[edge] = rgb[edge] * (1 - weight) + ink * weight
    out = a.copy()
    out[..., :3] = np.clip(rgb, 0, 255).astype(np.uint8)
    return Image.fromarray(out)


def _group_box(parts, want):
    """Union canvas bbox of the parts whose slot satisfies want."""
    rects = [p["canvas_rect"] for p in parts if want(p.get("slot"))]
    if not rects:
        return None
    x0 = min(r[0] for r in rects)
    y0 = min(r[1] for r in rects)
    x1 = max(r[0] + r[2] for r in rects)
    y1 = max(r[1] + r[3] for r in rects)
    return (x0, y0, x1, y1)


def _group_transform(filled, canvas, box, pad=22, ds=1):
    """One transform for a whole group of parts, applied together.

    The head needs its own transform. The generated head sits lower and a bit
    smaller than the hand-drawn one, so a single body-wide fit paints the face
    onto the neck. But the parts of the group must move TOGETHER: aligning them
    one at a time (each part against its own alpha) is what put the helmet over
    the face, because every part then had a different idea of where the head
    was. A shared transform keeps the assembly intact, which is the whole point
    of this pipeline.

    Returns (transformed_window, (wx0, wy0)).
    """
    wx0 = max(0, box[0] - pad)
    wy0 = max(0, box[1] - pad)
    wx1 = min(filled.width, box[2] + pad)
    wy1 = min(filled.height, box[3] + pad)
    win = filled.crop((wx0, wy0, wx1, wy1))
    tgt = canvas.crop((wx0, wy0, wx1, wy1)).copy()
    iou, s, dx, dy = _register(win, tgt, ds=ds)
    print(f"  group fit: IoU {iou:.3f} at scale {s:.2f} offset ({dx},{dy})")
    return _apply(win, tgt, iou, s, dx, dy), (wx0, wy0)


def _head_slot(slot):
    """Head group: the hat, the skull/face sprite and every expression variant.

    Kept as a group because they are stacked at the same pivot -- move one
    without the others and the face separates from the hat.
    """
    return (slot or "").lower().startswith(HEAD_SLOTS)


def slice_concept(path):
    with io.open(PLACEMENT, encoding="utf-8") as fh:
        man = json.load(fh)
    W, H = man["canvas"]
    canvas = Image.open(os.path.join(BASE, "_native_canvas.png")).convert("RGBA")
    concept = Image.open(path).convert("RGBA")

    a = np.array(canvas)
    ys, xs = np.nonzero(a[..., 3] > 8)
    target = (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1)
    fitted, s = _fit(concept, target)
    print(f"concept bbox-fitted to {target} at scale {s:.3f}")

    # ink stroke width follows the garment's value, not the operator's memory
    ink_px = INK_PX
    if ink_px is None:
        try:
            import theme_cbi
            role = theme_cbi.role_of(CHAR)
        except Exception:
            role = None
        ink_px = INK_PX_BY_ROLE.get(role, 1)
        print(f"ink stroke: {ink_px}px (role {role})")

    iou, rs, rdx, rdy = _register(concept, canvas)
    print(f"registration: IoU {iou:.3f} at scale {rs:.2f} offset ({rdx},{rdy})")
    fitted = _apply(concept, canvas, iou, rs, rdx, rdy)

    # if the model drew on a solid background, drop it: only keep what sits
    # inside the character silhouette, everything else would be painted into
    # the gaps between limbs
    fa = np.array(fitted)
    solid = float((fa[..., 3] > 200).mean())
    if solid > 0.98:
        print("[warn] concept has no transparency -- background cannot be "
              "removed reliably; slicing will carry it into the parts")

    filled = _bleed_colors(fitted)

    os.makedirs(REDRAW, exist_ok=True)

    # One texture can be placed many times: the hand sprite alone is used at
    # four different hand positions, and the two foot sprites at two each. If
    # the slice loop wrote the file once per placement, the last placement won
    # and the hand came out as four copies of one wrong pose stacked on top of
    # each other. Slice each FILE once, from the placement that shows the most
    # of it, and let the game reuse it the way it always did.
    canonical = {}
    for p in man["parts"]:
        f = p.get("file")
        if not f:
            continue
        area = p["canvas_rect"][2] * p["canvas_rect"][3]
        prev = canonical.get(f)
        if prev is None or area > prev[0]:
            canonical[f] = (area, p)

    os.makedirs(REDRAW, exist_ok=True)

    # The head gets its own shared transform. Everything else uses the global
    # one. The two are independent by design: the head is where the generated
    # figure deviates most, and forcing it onto the body's transform is what
    # painted the face onto the neck.
    head_img = head_off = None
    head_box = _group_box(man["parts"], _head_slot)
    if head_box:
        head_img, head_off = _group_transform(filled, canvas, head_box)

    kept = 0
    props = 0
    for f, (area, p) in canonical.items():
        if _is_prop(p.get("slot")):
            props += 1
            continue
        src = os.path.join(ORIG, f)
        if not os.path.isfile(src):
            continue
        orig = Image.open(src).convert("RGBA")
        px, py, pw, ph = p["canvas_rect"]
        if head_img is not None and _head_slot(p.get("slot")):
            lx, ly = px - head_off[0], py - head_off[1]
            crop = head_img.crop((lx, ly, lx + pw, ly + ph))
        else:
            crop = filled.crop((px, py, px + pw, py + ph))
        if crop.size != orig.size:
            crop = crop.resize(orig.size, Image.LANCZOS)

        alt_path = os.path.join(BASE, "restyled", f)
        alt = (Image.open(alt_path).convert("RGBA")
               if os.path.isfile(alt_path) else orig)
        if alt.size != orig.size:
            alt = alt.resize(orig.size, Image.LANCZOS)

        # trust the redraw only where the aligned concept actually has paint;
        # everywhere else keep the route-A palette art, so an area the new
        # costume does not reach continues the old drawing instead of smearing
        w = np.array(crop)[..., 3].astype(np.float32) / 255.0
        w = w[..., None]

        ca = np.array(crop).astype(np.float32)
        ba = np.array(alt).astype(np.float32)
        mixed = ca * w + ba * (1.0 - w)
        oa = np.array(orig)
        mixed[..., 3] = oa[..., 3]
        part = Image.fromarray(np.clip(mixed, 0, 255).astype(np.uint8))
        if any((p.get("slot") or "").lower().startswith(k) for k in _CLOTH):
            part = _olive_shift(part, k=OLIVE_K)
            part = _thicken_ink(part, px=ink_px)
        part.save(os.path.join(REDRAW, f))
        kept += 1

    # props keep their palette art, so the folder is a complete override set
    copied = 0
    for f in os.listdir(ORIG):
        if not f.lower().endswith(".png") or f.startswith("_"):
            continue
        dst = os.path.join(REDRAW, f)
        if os.path.isfile(dst):
            continue
        alt = os.path.join(BASE, "restyled", f)
        if os.path.isfile(alt):
            Image.open(alt).save(dst)
            copied += 1

    print(f"redrew {kept} body parts, {props} props kept from palette "
          f"({copied} files carried over) -> {REDRAW}")


def main():
    if "--canvas" in sys.argv:
        build_canvas()
    if "--slice" in sys.argv:
        slice_concept(sys.argv[sys.argv.index("--slice") + 1])
    if "--canvas" not in sys.argv and "--slice" not in sys.argv:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()
