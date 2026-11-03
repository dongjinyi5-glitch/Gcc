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

import factions

PROJECT = r"D:\AI\Guns, Gore and Cannoli from WB"

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
# A corpse cannot share the living flesh ramp -- 赭石 straight off the dish
# gives a zombie a healthy tan. Dead flesh loses chroma and picks up a green
# cast, which is exactly what 赭石 mixed with 石绿 looks like on paper.
SKIN_TONE_FACTION = {
    "人类": SKIN_TONE,
    "僵尸": ((160, 146, 114), (102, 96, 78), (202, 194, 168)),
}
# Rat fur is warm grey-brown, not 赭石 straight from the dish. The survey
# measured 花青 0.512 on the rat, but that number is a classifier artefact:
# desaturated grey-brown is CIELAB-nearest to 花青 among six mineral pigments.
# Painting it 花青 produced a navy-blue dog. Fur needs its own ramp.
FUR_TONE = ((124, 108, 90), (80, 70, 58), (162, 148, 128))

# 军装色是**混色**，没有一个矿物颜料直接落在那里。
#   石绿 straight from the dish = forest green, which is not olive drab;
#   赭石 straight from the dish = terracotta, which is not 国防色土黄.
# Same failure mode as the rat's fur (see FUR_TONE): a pigment name is not a
# colour. These two ramps are the 重彩 reading of the real fabric tones.
HBT_TONE = ((104, 106, 72), (62, 66, 46), (152, 152, 112))     # 美制 HBT 橄榄绿
KHAKI_TONE = ((134, 116, 80), (86, 74, 50), (178, 164, 126))   # 日军国防色土黄

# role -> pigment -> ramp, applied to GARMENT parts only. 赭石 on a face must
# keep the flesh ramp; only cloth takes the fabric ramp.
ROLE_RAMP = {
    "远征军":   {"石绿": HBT_TONE},
    "日军将官": {"赭石": KHAKI_TONE},
    "日军佐官": {"赭石": KHAKI_TONE},
    "日军士兵": {"赭石": KHAKI_TONE},
}
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
    # flesh must never be left as blank paper: 留白 belongs in fabric folds and
    # background, not in a face. Letting 纸 in here punched pale cream patches
    # into Vinnie's cheek wherever the original highlight was bright enough.
    "skin":      ["赭石", "朱红"],
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
    # "bite" frames are NOT a blood decal -- they are the whole HEAD posed with
    # its mouth open (113x126, exactly the head sprite's size). Routing them to
    # `gore` painted an entire face 朱红 and turned the zombie into a red mask.
    # They are skin; the blood on them is found by hue, region by region.
    ("bite",       ("skin",    "赭石", None)),
    ("tail",       ("skin",    "赭石", None)),
]
DEFAULT_RULE = ("garment", "石青", "石绿")

# Slots whose *dark* band is a separate object worth its own accent pigment.
# The crotch sprite is a leather belt plus a buckle; 朱红革带 is the classic
# 重彩 accent, and it also gives the figure the red note it otherwise lacks.
DARK_ACCENT = {"crotch": "朱红"}


# ------------------------------------------------------------ faction palettes
# A slot name describes *geometry* ("this is the torso"), not material. What the
# torso is made of depends on the faction: a gangster's torso is a wool suit, a
# zombie's is a torn shirt over a ribcage, a rat's is fur. So the slot rule
# decides the kind, and the faction decides which pigment that kind gets.
#
# kind -> (primary, secondary, allowed pigments)
# ``None`` means "keep whatever SLOT_RULES already decided". That matters: the
# shoe slot deliberately splits into 朱红 toe-cap and 墨 heel, and a faction
# table that forced one primary would flatten that two-tone shoe. Only the
# entries that genuinely differ per faction are filled in.
# Factions that actually have human flesh. Only they get the `skinlike` guard
# that keeps a face/neck/hand from being recoloured by the garment hue; a rat is
# fur from nose to tail, so the guard must not fire there.
FLESH_FACTIONS = {"人类", "僵尸"}

# Factions whose "garment" is cloth, so it can take a 石绿 underlayer. A rat's
# torso is fur: laying 石绿 underneath it painted a green animal (石绿 0.641 on
# one torso). 青绿积染 is a drapery technique, not a general one -- the rat gets
# a 花青 shadow layer instead, which is what fur in shadow looks like.
GREEN_LAYER_FACTIONS = {"人类", "僵尸"}
SHADOW_LAYER_FACTIONS = {"人类", "僵尸", "鼠怪"}

FACTION_KIND = {
    "人类": {
        # slot rules already say 石青/石绿 for cloth; only the whitelist differs
        "garment":   (None, None, ["石青", "石绿", "花青", "纸"]),
        "skin":      (None, None, ["赭石", "朱红"]),
        "hat":       (None, None, ["墨", "花青", "朱红"]),
        "tie":       (None, None, ["朱红", "墨"]),
        "shoe":      (None, None, ["墨", "朱红"]),
        "weapon":    (None, None, ["墨", "赭石", "花青"]),
        "brass":     (None, None, ["藤黄", "赭石"]),
        "glass":     (None, None, ["石绿", "石青", "纸"]),
        "explosive": (None, None, ["石绿", "墨", "朱红"]),
        "gore":      (None, None, ["朱红", "墨"]),
    },
    "僵尸": {
        # rags, not tailoring: indigo wash with malachite mould, no azurite
        "garment":   ("花青", "石绿", ["花青", "石绿", "赭石", "纸"]),
        # decayed flesh: ochre base, malachite for the rot, vermilion for raw
        "skin":      (None, None, ["赭石", "石绿", "朱红"]),
        "hat":       (None, None, ["墨", "花青"]),
        "tie":       (None, None, ["朱红", "墨"]),
        "shoe":      (None, None, ["墨", "赭石"]),
        "weapon":    (None, None, ["墨", "赭石"]),
        "brass":     (None, None, ["藤黄", "赭石"]),
        "glass":     (None, None, ["石绿", "纸"]),
        "explosive": (None, None, ["石绿", "墨", "朱红"]),
        # the bite frames are mostly blood -- measured 朱红 0.226 across the
        # faction, so vermilion is a main colour here, not an accent
        "gore":      (None, None, ["朱红", "墨", "赭石"]),
    },
    "鼠怪": {
        # Fur. The survey measured 花青 0.512 here, which looks like a licence
        # to paint the rat indigo -- but that number is a classifier artefact:
        # desaturated grey-brown is CIELAB-nearest to 花青 among six mineral
        # pigments. Painting it 花青 produced a navy-blue dog. Fur is 赭石 laid
        # through a dedicated grey-brown ramp (FUR_TONE), with 花青 in the
        # shadow and 石绿 for the sickliness.
        "garment":   ("赭石", "花青", ["赭石", "花青", "石绿"]),
        # A rat has no "skin" slot in the human sense -- head, hands and all
        # fourteen tail segments are FUR.
        "skin":      ("赭石", "花青", ["赭石", "花青", "石绿"]),
        "hat":       (None, None, ["墨", "花青"]),
        "tie":       (None, None, ["朱红", "墨"]),
        "shoe":      (None, None, ["墨", "赭石"]),
        "weapon":    (None, None, ["墨", "赭石"]),
        "brass":     (None, None, ["藤黄", "赭石"]),
        "glass":     (None, None, ["石绿", "纸"]),
        "explosive": (None, None, ["石绿", "墨"]),
        "gore":      (None, None, ["朱红", "墨"]),
    },
}


# 兵种层（CBI 题材）。faction 回答「这是不是活人肉体」，role 回答「穿什么」。
# 两层正交：日军士兵丧尸和日军士兵本人共用同一套军服配色，皮肤一个走活人
# 肉色、一个走尸斑灰。role 优先于 faction——兵种比生死更具体地决定布料颜色。
SHADOW_LAYER_ROLES = {"日军士兵"}
# 用户明确标注「不变」的兵种类（鼠怪）。命中则原样返回，不做任何像素改写。
UNCHANGED_ROLES = {"鼠怪"}


def _role_kind_table(role):
    if not role:
        return None
    try:
        import theme_cbi
    except ImportError:          # 旧题材下没有这个模块，退回 faction
        return None
    return theme_cbi.ROLE_KIND.get(role)


def rule_for(slot, faction=None, role=None):
    """(kind, primary, secondary) for a slot, resolved against role then faction."""
    s = (slot or "").lower()
    rule = DEFAULT_RULE
    for prefix, r in SLOT_RULES:
        if prefix in s:
            rule = r
            break
    kind, primary, secondary = rule
    table = _role_kind_table(role) or FACTION_KIND.get(faction or "人类", {})
    if kind in table:
        fp, fs, _allowed = table[kind]
        if fp is not None:
            primary = fp
        if fs is not None:
            secondary = fs
    return kind, primary, secondary


def allowed_for(kind, faction=None, role=None):
    """Pigments a kind of part may use under a role (falling back to faction)."""
    table = _role_kind_table(role)
    if table and kind in table:
        return table[kind][2]
    fk = FACTION_KIND.get(faction or "人类", {})
    if kind in fk:
        return fk[kind][2]
    return ALLOWED.get(kind, ["墨"])


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


def shade_color(ramp, t, lo=0.55, hi=0.66, light_w=0.30):
    """Lay pigment with continuous density: t in [0,1] is the normalised
    luminance of the original pixel. Keeps every fold and highlight the artist
    drew, which a per-region flat fill cannot do.

    ``lo`` / ``hi`` / ``light_w`` control the tonal spread. The default
    (0.55 / 0.66 / 0.30) lets a mineral pigment run from 55% to 121% of its
    base value — that wide range is what makes 石青 read as a loaded glaze.
    Skin must NOT use it: flesh is an earth tone (赭石) with a naturally narrow
    range, and a wide one turns a face into a pale mask over a dark jaw. Skin
    uses a raised floor and a capped ceiling instead.
    """
    base, deep, light = (np.array(v, dtype=np.float32) for v in ramp)
    t = np.asarray(t, dtype=np.float32).ravel()
    factor = (lo + hi * t)[:, None]
    col = base[None, :] * factor
    # hue character also shifts: deeper pigment in shadow, warmer in light
    w_deep = (0.38 * (1.0 - t))[:, None]
    w_light = (light_w * t)[:, None]
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
def restyle(img, slot="", seed=0, cfg=None, faction=None, role=None):
    cfg = cfg or {}
    rng = np.random.default_rng(seed)

    # 「不变」必须是可执行的，不能靠批处理脚本里手写 if 来记得
    if role in UNCHANGED_ROLES:
        return img.copy()

    arr = np.array(img.convert("RGBA"), dtype=np.float32)
    h, w = arr.shape[:2]
    rgb = arr[..., :3]
    alpha = arr[..., 3]
    opaque = alpha > 8
    if opaque.sum() < 12:
        return img.copy()

    L = luminance(rgb)
    H, S, V = rgb_to_hsv(rgb)
    kind, primary, secondary = rule_for(slot, faction, role)

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
    flesh = np.zeros_like(opaque)   # face/hand pixels, excluded from 皴擦 later
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

    allowed = allowed_for(kind, faction, role)

    # 青绿积染 needs 石绿 specifically. Under the role layer the secondary is
    # often 墨 or 藤黄 (khaki, navy, white), and laying those as an "underlayer"
    # would just muddy the garment -- so the technique is gated on the pigment,
    # not only on the faction.
    green_layer = bool(
        secondary == "石绿"
        and (role in SHADOW_LAYER_ROLES if role
             else (faction or "人类") in SHADOW_LAYER_FACTIONS))
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
        #
        # This guard exists to protect *flesh*. A rat has none -- its head,
        # hands and tail are fur -- so firing it there forced 赭石 onto 38% of
        # the body and turned the rat terracotta. Faction decides.
        skinlike = (faction in FLESH_FACTIONS
                    and (cH <= 50 or cH >= 340) and 0.15 <= cS <= 0.65
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
        elif cL >= 228 and cS <= 0.30 and kind == "skin":
            # 画人点睛，眼白留纸 -- an eye white is bare paper in 国画, not flesh.
            # Strictly the brightest neutral, so a cheek highlight (Vinnie's
            # measured L* 168) can never be mistaken for one. This is the one
            # exception to "a face may not contain 纸".
            pig = "纸"
        elif cS < 0.15:
            if cL > 200 and "纸" in allowed:
                pig = "纸"
            elif cL < 42 and "墨" in allowed:
                pig = "墨"
            else:
                pig = ACHROMA.get(kind, allowed[0])
        elif kind == "skin" and faction in FLESH_FACTIONS:
            # Flesh is an earth tone, and nearest-hue matching does not know
            # that: a corpse's cold grey face (H 249) sits closer to 石绿
            # (H 146) than to 赭石 (H 30), so the classifier speckled green
            # over a face. Decide by meaning instead -- green is rot, red was
            # already caught above as blood, everything else is flesh.
            pig = ("石绿" if (90 <= cH <= 200 and cS > 0.22
                              and "石绿" in allowed) else "赭石")
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
            # On a `skin` PART, 赭石 *is* flesh -- no hue test needed. Requiring
            # a warm hue meant a corpse's grey face fell through to the raw
            # 赭石 mineral ramp and came out dark brown, while a living face got
            # the pale flesh ramp. Same pigment, two very different results.
            is_skin = (pig == "赭石" and (r["skinlike"] or kind == "skin"))
            is_fur = (faction == "鼠怪" and pig == "赭石")
            fabric = (ROLE_RAMP.get(role or "", {}).get(pig)
                      if kind == "garment" else None)
            if is_fur:
                ramp = FUR_TONE
            elif is_skin:
                ramp = SKIN_TONE_FACTION.get(faction or "人类", SKIN_TONE)
            elif fabric is not None:
                ramp = fabric
            else:
                ramp = PIGMENTS[pig]
            # flesh and fur are soft materials, not mineral glazes: raise the
            # floor and cap the ceiling, or the form reads as a pale mask over
            # a dark jaw
            col = (shade_color(ramp, t, lo=0.74, hi=0.26, light_w=0.14)
                   if (is_skin or is_fur) else shade_color(ramp, t))

        # 青绿 layering: the shadow side of the main garment is laid in 石绿
        # underneath the 石青 glaze. Doing it inside one region (rather than by
        # picking a second cluster) keeps the band spatially coherent.
        #
        # It must be a SOFT weight, not a quantile split. A binary cut on
        # luminance drew a hard horizontal green bar across the zombie's waist
        # and knees -- visible in review, invisible to every numeric gate.
        if (rank == 0 and kind == "garment" and green_layer
                and m.sum() > 0.10 * opaque.sum()):
            dev = L[m] - r["L"]
            sd = float(dev.std())
            if sd > 2.5:
                thr = np.quantile(dev, float(cfg.get("green_split", 0.45)))
                span = max(1.5, sd * 0.9)
                # gamma < 1 so the green rises quickly out of the split point.
                # A linear ramp left almost the whole coat a 石青/石绿 average,
                # which the classifier reads as 石青 -- 石绿 collapsed to 0.022
                # and the 青绿 layering became invisible.
                gw = np.clip((thr - dev) / span, 0.0, 1.0) ** 0.45
            else:
                yy = np.nonzero(m)[0].astype(np.float32)
                yy = (yy - yy.min()) / max(1e-6, yy.max() - yy.min())
                gw = np.clip((yy - (1.0 - float(cfg.get("green_split", 0.45))))
                             / 0.30, 0.0, 1.0) ** 0.45
            if 0.02 < gw.mean() < 0.85:
                g = shade_color(PIGMENTS[secondary], t)
                col = col * (1.0 - gw)[:, None] + g * gw[:, None]

        # 重彩 sits on sized paper, so pigment never reaches full chroma
        col = col * float(cfg.get("pigment_gain", 0.95)) + \
            PAPER_RGB[None, :] * float(cfg.get("paper_mix", 0.06))
        out_rgb[m] = col
        if pig == "赭石" and (r["skinlike"] or kind == "skin"):
            flesh[m] = True

    # ---- 3d. blood is a pigment, not a region ------------------------------
    # A wound is a few hundred pixels inside a shirt of thousands, so k-means
    # merges it into the shirt and the red vanishes -- the zombie's measured
    # 朱红 fell from 0.106 (original) to 0.007. Red has to be judged per PIXEL.
    # Blood is exempt from the per-kind pigment whitelist: if the original is
    # red, it is blood, whatever part it sits on. Gating this on `allowed`
    # silently dropped it, because a zombie's garment palette is
    # 花青/石绿/赭石 -- no 朱红 at all -- so the wounds vanished.
    if kind not in ("glass", "brass"):
        # Blood must be DARK red. Cartoon flesh sits at S~0.55 with hue ~17, so
        # a saturation-only test painted Vinnie's whole face vermilion. Blood
        # is also dark (L 32-70 in this game), skin is bright (L > 150).
        blood = (fill & (S > 0.62) & ((H < 20) | (H > 340))
                 & (L > 25) & (L < 120))
        if blood.any():
            tb = np.clip((L[blood] - 25.0) / 60.0, 0.0, 1.0)
            out_rgb[blood] = shade_color(PIGMENTS["朱红"], tb)

    # pixels the k-means dropped (tiny islands) inherit the primary tone
    left = fill & (labels < 0)
    if left.any():
        out_rgb[left] = np.array(PIGMENTS[primary][0], dtype=np.float32) * 0.9 + \
            PAPER_RGB * 0.1

    # ---- 4. paper grain + 皴擦 ----------------------------------------------
    # 皴擦 belongs on cloth, rock and bark. A painter renders flesh smooth
    # (渲染), so putting the same texture on a face turned the cheek into a
    # mottled patch -- that was the "flat pale mask" the first pass had.
    grain_amp = float(cfg.get("grain", 7.0))
    grain = (high_freq(h, w, rng, 0.85) - 0.5) * 2 * grain_amp
    fiber = (smooth_noise(h, w, 26.0, rng) - 0.5) * 2 * grain_amp * 0.7
    body = fill & ~darkfill & ~flesh
    out_rgb += (grain + fiber)[..., None] * body[..., None]
    # flesh keeps a trace of paper tooth so it does not read as CG airbrush
    out_rgb += (grain * 0.20)[..., None] * (fill & ~darkfill & flesh)[..., None]

    if cfg.get("cun", True):
        rough = smooth_noise(h, w, 9.0, rng)
        cun = (rough > 0.86) & body
        out_rgb[cun] *= 0.90

    # 渲染: with the texture removed, flesh needs its volume back. A painter
    # models a face with a smooth directional wash (light from upper left), not
    # with grain -- this is the step that replaces 皴擦 on skin.
    if flesh.any():
        ys, xs = np.nonzero(flesh)
        y0, y1, x0, x1 = ys.min(), ys.max(), xs.min(), xs.max()
        yy = (np.arange(h, dtype=np.float32)[:, None] - y0) / max(1.0, y1 - y0)
        xx = (np.arange(w, dtype=np.float32)[None, :] - x0) / max(1.0, x1 - x0)
        model = 1.0 - float(cfg.get("flesh_model", 0.20)) * np.clip(
            0.62 * yy + 0.38 * xx, 0.0, 1.3)
        out_rgb *= np.where(flesh[..., None], model[..., None], 1.0)

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
    #
    # The weight has to be chosen by PART SIZE, not applied flat. A flat 1px
    # growth is 0.25% of a 400px coat but 1% of a 100px head, and the zombie
    # head is already 36% dark linework, so the contour has to stay fine there.
    # NOTE: dilate()/erode() take a KERNEL SIZE (odd), not an iteration count.
    _area = int(opaque.sum())
    brush = 5 if _area >= 45000 else 3
    thick = dilate(rim_ink, brush) & opaque & ~ink
    if _area >= 45000:
        thick |= dilate(thick, brush) & opaque & ~ink
    # A part that is ALREADY ink-dominated must not be thickened again. The
    # zombie head is 36% dark linework; bleeding every stroke by 1px pushed it
    # to 55% and the face collapsed into a black mask. A painter in that
    # situation thins the brush, not loads it.
    dark_ratio = float(dark.sum()) / max(1, _area)
    if dark_ratio < 0.30:
        thick |= dilate(ink, brush) & opaque & ~ink & (L < 150)
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
    mode = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("--") \
        else "preview"

    def opt(flag, default=None):
        return sys.argv[sys.argv.index(flag) + 1] if flag in sys.argv else default

    char = opt("--char", "Vinnie")
    faction = opt("--faction") or factions.faction_of(char)
    if faction not in FACTION_KIND:
        raise SystemExit(f"unknown faction {faction!r}; "
                         f"expected one of {list(FACTION_KIND)}")
    role = opt("--role")
    if role is None:
        try:
            import theme_cbi
            role = theme_cbi.role_of(char)
        except ImportError:
            role = None

    src = os.path.join(PROJECT, "art", f"{char.lower()}_parts", "original")
    dst = os.path.join(PROJECT, "art", f"{char.lower()}_parts", "restyled")
    if not os.path.isdir(src):
        raise SystemExit(f"no parts for {char} -- run extract_parts.py {char} first")
    os.makedirs(dst, exist_ok=True)

    files = [f for f in sorted(os.listdir(src))
             if f.lower().endswith(".png") and not f.startswith("_")]
    if mode == "preview":
        want = ["24_Head", "13_TorsoChest", "19_Crotch", "31_Hat",
                "52_Tommygun", "47_Magnum", "16_LegLowBack", "08_Molotov"]
        picked = [f for f in files if any(f.startswith(p) for p in want)]
        files = picked or files[:8]

    print(f"[{char} / {faction} / {role}] {len(files)} part(s) -> {dst}", flush=True)
    for i, f in enumerate(files):
        img = Image.open(os.path.join(src, f))
        slot = f.split("_")[1] if "_" in f else f
        res = restyle(img, slot=slot, seed=i * 7919 + 13,
                      faction=faction, role=role)
        res.save(os.path.join(dst, f))
        print(f"[{i + 1}/{len(files)}] {f}", flush=True)

    print(f"wrote {len(files)} files to {dst}")


if __name__ == "__main__":
    main()
