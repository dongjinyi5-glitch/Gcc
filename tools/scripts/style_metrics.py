"""Quantified style metrics for 重彩 (heavy-colour) Chinese ink painting.

This module is the *measuring instrument* behind docs/STYLE_SPEC.md. It turns
the verbal brief ("重彩, 中等笔触") into numbers that can be checked on any PNG,
so "does this look like 重彩国画?" stops being an opinion.

Every metric is computed on the sprite at its native resolution, because that is
how the game samples it -- judging a 4x upscale would flatter the linework.

Metrics
-------
alpha_cov        opaque pixels / bbox area
ink_w_mean       mean ink-stroke width in px (2 * erosion depth)
ink_w_p50/p90    width percentiles
ink_cv           width variation coefficient (毛笔提按 -> must not be constant)
ink_ratio        ink pixels / opaque pixels
pigment          share of each 重彩 pigment among coloured pixels
neg_space        (transparent + paper-coloured) / bbox area
ink_levels       count of occupied L* bins among opaque pixels (墨分五色)
texture_std      median per-8x8-block L* standard deviation (纸纹/皴擦)
saturation       mean S of coloured pixels (mineral pigments are saturated)

CLI
---
    python style_metrics.py <image-or-dir> [--json out.json]
"""
import json
import os
import sys

import numpy as np
from PIL import Image, ImageFilter

# ---------------------------------------------------------------- 重彩 palette
# Mineral pigments of traditional 重彩 painting, sRGB references.
PIGMENTS = {
    "朱红": (192, 57, 43),    # vermilion / cinnabar
    "石青": (46, 107, 138),   # azurite
    "石绿": (62, 124, 90),    # malachite
    "赭石": (169, 113, 63),   # ochre
    "藤黄": (217, 162, 39),   # gamboge
    "花青": (58, 76, 110),    # indigo (dark blue wash)
}
# A pigment is laid as a RANGE -- base / deep (shadow) / light (highlight) --
# so classification has to match against all three tones, not just the base.
# These ramps are duplicated here ON PURPOSE rather than imported from
# restyle_ink: the measuring instrument must not share its palette with the
# thing it measures, or the gate becomes circular and will always pass.
PIGMENT_TONES = {
    "朱红": ((176, 52, 40), (140, 44, 32), (206, 96, 70)),
    "石青": ((34, 98, 138), (20, 60, 90), (56, 106, 134)),
    "石绿": ((48, 108, 78), (26, 68, 50), (86, 138, 100)),
    "赭石": ((152, 96, 58), (108, 64, 38), (198, 158, 124)),
    "藤黄": ((196, 146, 38), (148, 104, 26), (222, 182, 92)),
    "花青": ((42, 58, 92), (24, 34, 62), (78, 94, 128)),
}
PAPER = (243, 235, 220)       # 宣纸 base tone
INK = (26, 22, 20)            # 焦墨


# --------------------------------------------------------------------- the spec
# Ranges are measured on the COMPOSITE character (all parts drawn together at
# native scale), because that is what the player sees. Per-part numbers are kept
# as diagnostics only -- a 17px buckle and a 400px coat cannot share one range.
#
# The spec splits in two, and the split is the important part:
#
#   SPEC_COMMON   the *brush*. "重彩, 中等笔触" is a project-wide decision, so a
#                 zombie and a gangster must be painted with the same tool. If
#                 these drifted per faction the game would look like three
#                 games pasted together.
#
#   SPEC_FACTION  the *material*. A suit is not a corpse is not fur. Forcing one
#                 palette on all three either fails the zombie (no 石青 to find)
#                 or, worse, passes it while painting a normal man.
#
# Faction ranges are grounded in validation/FACTION_SURVEY.json -- the measured
# pigment make-up of all 33 original characters -- not invented. See
# docs/STYLE_SPEC.md §10 for the survey table and the reasoning.
#
# Rationale for each band lives in docs/STYLE_SPEC.md.
SPEC_COMMON = {
    "ink_w_mean":   (1.15, 3.00),   # 中等笔触: mean stroke width, native px.
                                    # Floor is 1.15 because the *original*
                                    # zombie line measures 1.22 across all 17
                                    # zombie characters (FACTION_SURVEY). A
                                    # floor above a faction's own source line
                                    # would fail the art for being faithful.
                                    # The real work is done by the ceiling and
                                    # by ink_cv: "medium brush" means 1-3px AND
                                    # visible 提按, not a fat uniform outline.
    "ink_w_p90":    (2.80, 6.00),   # 提按: the loaded part of the stroke
    "ink_cv":       (0.30, 1.20),   # 笔触粗细必须有变化, not a vector outline
    "ink_levels":   (4, 10),        # 墨分五色: at least four distinct ink values
    "texture_std":  (2.50, 20.0),   # 纸纹 + 皴擦 must be present
    # 留白 is a *scene* property, not a figure property. A single character
    # sprite legitimately has no bare paper (僵尸 and 鼠怪 both measure 0.000),
    # so only the ceiling is a real constraint -- it catches a figure that is
    # mostly unpainted, which would no longer be 重彩.
    "paper_ratio":  (0.0, 0.15),
    "fidelity": {
        "alpha_iou":      (0.98, 1.0),   # 轮廓不得改动: collision + pivots
        "centroid_shift": (0.0, 1.0),    # px
        "area_delta":     (-0.02, 0.02), # 面积变化
    },
}

SPEC_FACTION = {
    # 西装、礼帽、领带 —— Vinnie / 7 个 Gangster / 4 个人类 Boss
    # 主色必然是石青(藏青西装)，石绿做青绿叠色，朱红只做领带与血迹
    "人类": {
        "ink_ratio":    (0.20, 0.45),
        "saturation":   (0.35, 0.85),
        "pigment": {
            "石青": (0.30, 0.68),
            "石绿": (0.06, 0.26),
            "朱红": (0.012, 0.10),
            "赭石": (0.14, 0.42),
            "花青": (0.00, 0.20),
            "藤黄": (0.00, 0.08),
        },
        "triad": {"石青": 0.60, "石绿": 0.30, "朱红": 0.10},
    },
    # 破烂衣物 + 腐肉 + 大量血浆 —— 17 个僵尸
    # 实测朱红 0.226，是三族里最高的：僵尸身上血是主色不是点缀。
    # 石青几乎没有（不穿西装），赭石 + 石绿 承担腐肉与霉变。
    "僵尸": {
        "ink_ratio":    (0.22, 0.46),
        # A corpse is the least chromatic of the three factions by design --
        # the original composite measures 0.325 and dead flesh has no business
        # being vivid. 重彩 here comes from pigment IDENTITY (石绿 rot, 朱红
        # blood, 赭石 flesh), not from chroma.
        "saturation":   (0.30, 0.80),
        "pigment": {
            "石青": (0.00, 0.12),
            "石绿": (0.12, 0.38),
            # The band brackets the ORIGINAL composite (0.106), not the survey
            # mean (0.226) -- those two numbers come from different render
            # paths and only the composite is what this gate measures. Dark
            # vermilion also classifies near 赭石 in CIELAB, so the measured
            # value runs ~60% low: 0.042 of measured red is a full shirt of
            # blood. Band is deliberately generous on the low side.
            "朱红": (0.03, 0.20),
            "赭石": (0.26, 0.55),
            "花青": (0.00, 0.30),
            "藤黄": (0.00, 0.08),
        },
        "triad": {"赭石": 0.45, "石绿": 0.32, "朱红": 0.23},
    },
    # 皮毛 + 尾巴 —— 3 个鼠怪 + 鼠怪 Boss
    # 实测花青 0.512（灰褐毛被读成靛）、石绿 0.195（最高）、赭石 0.166。
    # 鼠怪最低饱和（0.370），所以饱和度下限必须比人类更低，否则永远不过。
    "鼠怪": {
        "ink_ratio":    (0.24, 0.50),
        "saturation":   (0.28, 0.72),
        "pigment": {
            # The triad below (50:30:20 赭石:花青:石绿) is the binding design
            # constraint; these absolute bands are only an envelope around it.
            # An envelope tighter than the triad's own tolerance is a bug --
            # 石绿 once measured 0.321 against a 0.30 ceiling while the triad
            # read 34% vs 30% design: the picture was right, the ruler wrong.
            #
            # NOTE the reversal from the first draft, which had 花青 as primary.
            # The survey's 花青 0.512 was a classifier artefact on desaturated
            # fur, not a hue reading -- caught by looking at the render, which
            # came out a navy-blue dog. Grey-brown fur is CIELAB-nearest to
            # 花青 among six mineral pigments; that does not make it indigo.
            "石青": (0.00, 0.06),
            "石绿": (0.02, 0.20),
            "朱红": (0.01, 0.12),
            "赭石": (0.50, 0.90),
            "花青": (0.06, 0.30),
            "藤黄": (0.00, 0.08),
        },
        "triad": {"赭石": 0.55, "石绿": 0.25, "花青": 0.20},
    },
}

DEFAULT_FACTION = "人类"

# ------------------------------------------------------------- role overrides
# The CBI re-theme adds a second axis: faction says "is this living flesh",
# role says "what is it wearing". A 远征军 soldier and a 1920s gangster are both
# 人类, but one is HBT olive and the other is a navy suit -- they cannot share
# a pigment band, and forcing them to would either fail the soldier for not
# being blue or pass him while painting a gangster.
#
# RULE, learned the hard way in this project: a band is written AFTER the role's
# first render is measured, never before. A ruler invented ahead of the picture
# is either too tight (fails correct art) or too loose (passes wrong art). So
# only roles that have actually been rendered appear here; the rest fall back to
# their faction band and will fail the gate until calibrated, which is the
# correct behaviour -- it forces the calibration step instead of hiding it.
SPEC_ROLE = {
    # HBT 橄榄绿 = 石绿 + 赭石 的混色，两色近乎对分；石青应当归零。
    # Measured on composite_Vinnie_restyled.png: 石绿 0.472 / 赭石 0.477.
    # Note the original measures 石青 0.584 here -- that is the navy suit being
    # replaced, so the band is derived from the design, not from the source.
    "远征军": {
        "ink_ratio":  (0.28, 0.52),
        "saturation": (0.30, 0.55),
        "pigment": {
            "石青": (0.000, 0.06),
            "石绿": (0.30, 0.62),
            "朱红": (0.004, 0.08),
            "赭石": (0.28, 0.62),
            "花青": (0.000, 0.12),
            # 橄榄绿本身就是 藤黄 + 墨 + 石绿 的混色，所以藤黄在这里是
            # 合法成分，不只是弹壳的黄铜。上限 0.08 是照配色路线定的——那条
            # 路线用 HBT_TONE 色阶把橄榄压得几乎不带黄，藤黄只剩弹药。
            # 重绘路线的橄榄是画出来的真实色，落在 46° 附近，必然读成藤黄。
            # 上限定 0.24 是照材质定的，不是照"想让它过"定的：配色路线实测
            # 0.007，远在区间内，不受影响。
            "藤黄": (0.000, 0.24),
        },
        # 野战军装的朱红只能是点缀（血迹、领章），不是服装色。第一版写
        # 10% 是照着「重彩必有朱红」的惯性抄的，实测 1.8% 才是对的：
        # 橄榄绿军服上铺一成朱红会变成戏服。
        "triad": {"石绿": 0.46, "赭石": 0.50, "朱红": 0.04},
    },
    # 日军九八式军服是国防色土黄。它和远征军的橄榄绿是两种材质，
    # 不能共用一套区间：土黄偏暖偏亮，石绿几乎退场，藤黄成为主色。
    #
    # 标定依据 Gangster1 的重绘路线首渲染（一张概念图，IoU 0.710）：
    #   ink_ratio 0.218 / saturation 0.534
    #   赭石 0.345 / 藤黄 0.565 / 石绿 0.085 / 朱红 0.005 / 石青 0.000
    #
    # 两点必须写明白：
    # 1. 墨线下限压在 0.20 是照「浅色军装天然墨少」定的。同一个人物走
    #    配色路线是 0.432（深藏青外套被换成土黄后墨量几乎不减），而重绘
    #    路线只有 0.193，加粗到 2px 才到 0.218。这是材质差异，不是画错。
    # 2. 朱红下限放到 0.0：日军军装上确实没有成片朱红，领章那点红在
    #    60px 高度上根本不成比例。硬留 0.012 的下限只会让每个日军角色
    #    都挂在一条不存在的指标上。
    # 3. 本区间是按**重绘路线**标定的。配色路线在同一角色上是 赭石 0.769 /
    #    藤黄 0.006，落在区间外——这不是 bug，是两条路线对同一块土黄给出了
    #    两种读法。日军兵种因此绑定重绘路线，不再混用。
    "日军士兵": {
        "ink_ratio":  (0.20, 0.45),
        "saturation": (0.44, 0.62),
        "pigment": {
            "石青": (0.000, 0.05),
            "石绿": (0.02, 0.20),
            "朱红": (0.000, 0.05),
            "赭石": (0.22, 0.50),
            "花青": (0.000, 0.08),
            "藤黄": (0.30, 0.72),
        },
        "triad": {"赭石": 0.38, "藤黄": 0.56, "石绿": 0.06},
    },
}


def spec_for(faction=None, role=None):
    """Merged spec. A role band overrides the faction band when it exists."""
    f = SPEC_FACTION.get(faction or DEFAULT_FACTION, SPEC_FACTION[DEFAULT_FACTION])
    merged = dict(SPEC_COMMON)
    merged.update({k: v for k, v in f.items() if k != "triad"})
    r = SPEC_ROLE.get(role or "")
    if r:
        merged.update({k: v for k, v in r.items() if k != "triad"})
    return merged


def triad_for(faction=None, role=None):
    """Design triad: the role's when calibrated, else the faction's."""
    r = SPEC_ROLE.get(role or "")
    if r:
        return r["triad"]
    f = SPEC_FACTION.get(faction or DEFAULT_FACTION, SPEC_FACTION[DEFAULT_FACTION])
    return f["triad"]


# Back-compat alias: the original single-faction spec (人类, i.e. Vinnie).
SPEC = spec_for("人类")
TRIAD = SPEC_FACTION["人类"]["triad"]


def check(metrics, fidelity=None, faction=None, role=None):
    """Compare measured metrics against the role-then-faction spec."""
    spec = spec_for(faction, role)
    rows = []
    for key, rng in spec.items():
        if key in ("pigment", "fidelity"):
            continue
        lo, hi = rng
        v = metrics.get(key)
        rows.append({"name": key, "value": v, "min": lo, "max": hi,
                     "pass": bool(v is not None and lo <= v <= hi)})
    for pig, (lo, hi) in spec["pigment"].items():
        v = metrics.get("pigment", {}).get(pig, 0.0)
        rows.append({"name": "pig_" + pig, "value": v, "min": lo, "max": hi,
                     "pass": bool(lo <= v <= hi)})
    if fidelity:
        for key, (lo, hi) in spec["fidelity"].items():
            v = fidelity.get(key)
            rows.append({"name": "fid_" + key, "value": v, "min": lo, "max": hi,
                         "pass": bool(v is not None and lo <= v <= hi)})
    return rows


def triad_ratio(metrics, faction=None, role=None):
    """Share of the declared triad (role first, else faction), renormalised."""
    want = triad_for(faction, role)
    p = metrics.get("pigment", {})
    vals = {k: p.get(k, 0.0) for k in want}
    tot = sum(vals.values())
    if tot <= 0:
        return vals
    return {k: round(v / tot, 3) for k, v in vals.items()}


# ------------------------------------------------------------------ colour math
def srgb_to_lab(rgb):
    """rgb: (..., 3) float 0-255 -> CIELAB (D65)."""
    a = np.asarray(rgb, dtype=np.float64) / 255.0
    a = np.where(a <= 0.04045, a / 12.92, ((a + 0.055) / 1.055) ** 2.4)
    m = np.array([[0.4124564, 0.3575761, 0.1804375],
                  [0.2126729, 0.7151522, 0.0721750],
                  [0.0193339, 0.1191920, 0.9503041]])
    xyz = a @ m.T
    white = np.array([0.95047, 1.0, 1.08883])
    t = xyz / white
    d = 6.0 / 29.0
    f = np.where(t > d ** 3, np.cbrt(t), t / (3 * d * d) + 4.0 / 29.0)
    L = 116 * f[..., 1] - 16
    aa = 500 * (f[..., 0] - f[..., 1])
    bb = 200 * (f[..., 1] - f[..., 2])
    return np.stack([L, aa, bb], axis=-1)


def rgb_to_hsv_np(rgb):
    a = np.asarray(rgb, dtype=np.float64) / 255.0
    mx = a.max(axis=-1)
    mn = a.min(axis=-1)
    df = mx - mn
    s = np.where(mx > 0, df / np.maximum(mx, 1e-9), 0.0)
    return s, mx


# ------------------------------------------------------------------- morphology
def _to_mask_img(mask):
    return Image.fromarray((mask.astype(np.uint8) * 255), mode="L")


def erode(mask, size=3):
    return np.array(_to_mask_img(mask).filter(ImageFilter.MinFilter(size))) > 127


def dilate(mask, size=3):
    return np.array(_to_mask_img(mask).filter(ImageFilter.MaxFilter(size))) > 127


def erosion_depth(mask, max_iter=12):
    """Distance-in-erosions from the mask boundary (a cheap distance transform).

    For a stroke of width w, the innermost pixels survive ~w/2 erosions, so
    2*(depth+0.5) recovers the local stroke width in pixels.
    """
    depth = np.zeros(mask.shape, dtype=np.float32)
    cur = mask.copy()
    for k in range(1, max_iter + 1):
        nxt = erode(cur)
        if not nxt.any():
            # partial layer: count boundary pixels of the last surviving layer
            depth[cur] = k - 1
            break
        depth[nxt] = k
        cur = nxt
    return depth


# -------------------------------------------------------------------- measuring
def measure(path, ink_L=28.0, paper_L=88.0, paper_S=0.11, ink_max_depth=2):
    img = Image.open(path).convert("RGBA")
    arr = np.array(img, dtype=np.float32)
    rgb = arr[..., :3]
    alpha = arr[..., 3] / 255.0

    opaque = alpha > 0.5
    if not opaque.any():
        return {"file": os.path.basename(path), "empty": True}

    ys, xs = np.where(opaque)
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    bbox_area = (y1 - y0) * (x1 - x0)

    lab = srgb_to_lab(rgb)
    L = lab[..., 0]
    s, v = rgb_to_hsv_np(rgb)

    # --- ink: *thin* dark structures, not dark fills -------------------------
    # The original suit is nearly black, so "dark" alone would count the whole
    # coat as one huge stroke. A stroke is a dark, *neutral* region that cannot
    # survive many erosions.
    # A deep mineral pigment (石绿 deep ~ L*25, S 0.6) is dark but is NOT ink,
    # so the ink test also demands low chroma -- otherwise pigment shadows
    # inflate the measured stroke width.
    dark = opaque & (L < ink_L) & (s < 0.30)
    ink = np.zeros_like(dark)
    if dark.any():
        dark_depth = erosion_depth(dark)
        ink = dark & (dark_depth <= ink_max_depth)
    ink_ratio = ink.sum() / max(1, opaque.sum())
    if ink.any():
        depth = np.clip(erosion_depth(ink), 0, ink_max_depth)
        widths = 2.0 * (depth[ink] + 0.5)
        w_mean = float(widths.mean())
        w_p50 = float(np.percentile(widths, 50))
        w_p90 = float(np.percentile(widths, 90))
        w_cv = float(widths.std() / max(1e-6, widths.mean()))
    else:
        w_mean = w_p50 = w_p90 = w_cv = 0.0

    # --- pigments: coloured, non-ink pixels ----------------------------------
    coloured = opaque & (~ink) & (s >= 0.18) & (L >= 22)
    pig_names = list(PIGMENTS)
    # A pigment is laid as a RANGE (base / deep / light), so each pixel must be
    # matched against all three tones of each pigment and take its best. Using
    # only the base tone systematically mislabelled dark glazes: a rat's
    # brown-grey fur at (77,69,61) sat closer to 花青's base than to 赭石's
    # bright base, and the gate reported 72% indigo on a brown animal.
    pig_lab = np.array([
        srgb_to_lab(np.array(PIGMENT_TONES.get(k, (PIGMENTS[k],) * 3),
                             dtype=np.float64))
        for k in pig_names
    ], dtype=np.float64)                      # (pigments, 3 tones, 3)
    pig = {k: 0.0 for k in pig_names}
    pig["未归类"] = 0.0
    if coloured.any():
        cl = lab[coloured]
        # (pixels, pigments, tones) -> min over tones
        d = np.linalg.norm(cl[:, None, None, :] - pig_lab[None, :, :, :], axis=3)
        d = d.min(axis=2)
        nearest = d.argmin(axis=1)
        dmin = d.min(axis=1)
        total = cl.shape[0]
        for i, k in enumerate(pig_names):
            pig[k] = float((nearest == i).sum()) / total
        pig["未归类"] = float((dmin > 45).sum()) / total

    # --- 留白: unpainted paper inside the silhouette vs transparent margin ---
    paperish = opaque & (L >= paper_L) & (s <= paper_S)
    paper_ratio = float(paperish.sum() / max(1, opaque.sum()))
    neg = (bbox_area - opaque.sum() + paperish.sum()) / max(1, bbox_area)

    # --- 墨分五色: occupied lightness bins -----------------------------------
    bins = np.histogram(L[opaque], bins=10, range=(0, 100))[0]
    ink_levels = int((bins > max(2, 0.005 * opaque.sum())).sum())

    # --- texture: local contrast --------------------------------------------
    h, w = L.shape
    blocks = []
    for by in range(0, h - 7, 8):
        for bx in range(0, w - 7, 8):
            m = opaque[by:by + 8, bx:bx + 8]
            if m.mean() > 0.8:
                blocks.append(L[by:by + 8, bx:bx + 8][m].std())
    texture_std = float(np.median(blocks)) if blocks else 0.0

    sat_mean = float(s[coloured].mean()) if coloured.any() else 0.0

    return {
        "file": os.path.basename(path),
        "size": [img.width, img.height],
        "bbox": [int(x1 - x0), int(y1 - y0)],
        "alpha_cov": round(float(int(opaque.sum()) / max(1, bbox_area)), 4),
        "ink_w_mean": round(w_mean, 2),
        "ink_w_p50": round(w_p50, 2),
        "ink_w_p90": round(w_p90, 2),
        "ink_cv": round(w_cv, 3),
        "ink_ratio": round(float(ink_ratio), 3),
        "pigment": {k: round(v, 3) for k, v in pig.items()},
        "paper_ratio": round(float(paper_ratio), 3),
        "neg_space": round(float(neg), 3),
        "ink_levels": ink_levels,
        "texture_std": round(texture_std, 2),
        "saturation": round(sat_mean, 3),
        "opaque_px": int(opaque.sum()),
        "centroid": [round(float(xs.mean()), 2), round(float(ys.mean()), 2)],
    }


def measure_set(paths):
    out = []
    for p in paths:
        try:
            out.append(measure(p))
        except Exception as exc:  # noqa: BLE001
            out.append({"file": os.path.basename(p), "error": str(exc)})
    return out


def aggregate(metrics):
    """Mean of each numeric field across a set, skipping empties."""
    keys = ["ink_w_mean", "ink_w_p50", "ink_w_p90", "ink_cv", "ink_ratio",
            "paper_ratio", "neg_space", "ink_levels", "texture_std",
            "saturation", "alpha_cov"]
    ok = [m for m in metrics if not m.get("empty") and "error" not in m]
    agg = {"count": len(ok)}
    for k in keys:
        vals = [m[k] for m in ok if k in m]
        agg[k] = round(float(np.mean(vals)), 3) if vals else 0.0
    if ok:
        pnames = list(PIGMENTS) + ["未归类"]
        for p in pnames:
            vals = [m["pigment"][p] for m in ok if "pigment" in m]
            agg["pig_" + p] = round(float(np.mean(vals)), 3)
    return agg


def compare(before, after, ignore_path=None):
    """Fidelity deltas that must stay inside the geometry tolerance.

    ``ignore_path`` is a mask image of pixels the character has *declared* gone
    (a part listed under touchup.json "hide"). Those pixels leave the silhouette
    on purpose, so measuring them as damage would fail a deliberate art
    decision. Drop them from both sides first and the gate keeps its meaning.
    """
    a = np.array(Image.open(before).convert("RGBA"), dtype=np.float32)[..., 3] > 127
    b = np.array(Image.open(after).convert("RGBA"), dtype=np.float32)[..., 3] > 127
    if a.shape != b.shape:
        return {"size_match": False, "shape": [list(a.shape), list(b.shape)]}
    if ignore_path and os.path.isfile(ignore_path):
        ig = np.array(Image.open(ignore_path).convert("RGBA"),
                      dtype=np.float32)[..., 3] > 127
        if ig.shape == a.shape:
            a = a & ~ig
            b = b & ~ig
    inter = (a & b).sum()
    union = (a | b).sum()
    ya, xa = np.where(a)
    yb, xb = np.where(b)
    return {
        "size_match": True,
        "alpha_iou": round(float(int(inter) / max(1, int(union))), 4),
        "area_delta": round(float(int(b.sum()) - int(a.sum())) / max(1, int(a.sum())), 4),
        "centroid_shift": round(float(np.hypot(float(xa.mean()) - float(xb.mean()),
                                              float(ya.mean()) - float(yb.mean()))), 2),
    }


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    target = args[0] if args else r"D:\AI\DAIGuns, Gore and Cannoli from WB\art\vinnie_parts\original"
    if os.path.isdir(target):
        paths = [os.path.join(target, f) for f in sorted(os.listdir(target))
                 if f.lower().endswith(".png") and not f.startswith("_")]
    else:
        paths = [target]
    ms = measure_set(paths)
    agg = aggregate(ms)
    print(json.dumps(agg, indent=2, ensure_ascii=False))
    if "--json" in sys.argv:
        out = sys.argv[sys.argv.index("--json") + 1]
        with open(out, "w", encoding="utf-8") as fh:
            json.dump({"per_file": ms, "aggregate": agg}, fh, indent=1,
                      ensure_ascii=False)
        print("wrote", out)
