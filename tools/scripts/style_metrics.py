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
PAPER = (243, 235, 220)       # 宣纸 base tone
INK = (26, 22, 20)            # 焦墨


# --------------------------------------------------------------------- the spec
# Ranges are measured on the COMPOSITE character (all parts drawn together at
# native scale), because that is what the player sees. Per-part numbers are kept
# as diagnostics only -- a 17px buckle and a 400px coat cannot share one range.
#
# Rationale for each band lives in docs/STYLE_SPEC.md.
SPEC = {
    "ink_w_mean":   (1.50, 3.00),   # 中等笔触: mean stroke width, native px
    "ink_w_p90":    (2.80, 6.00),   # 提按: the loaded part of the stroke
    "ink_cv":       (0.30, 1.20),   # 笔触粗细必须有变化, not a vector outline
    "ink_ratio":    (0.20, 0.45),   # 墨色覆盖: 重彩 is ink-led but not a silhouette
    "paper_ratio":  (0.003, 0.15),  # 留白: 重彩 keeps little bare paper
    "ink_levels":   (4, 10),        # 墨分五色: at least four distinct ink values
    "texture_std":  (2.50, 20.0),   # 纸纹 + 皴擦 must be present
    "saturation":   (0.35, 0.85),   # 矿物颜料 must read as saturated
    "pigment": {
        "石青": (0.26, 0.45),       # 主色
        "石绿": (0.07, 0.24),       # 辅色 (青绿叠色)
        "朱红": (0.012, 0.10),      # 点缀
        "赭石": (0.14, 0.32),       # 肤色/木石
        "花青": (0.00, 0.35),       # 阴面
        "藤黄": (0.00, 0.08),       # 金/铜
    },
    "fidelity": {
        "alpha_iou":      (0.98, 1.0),   # 轮廓不得改动: collision + pivots
        "centroid_shift": (0.0, 1.0),    # px
        "area_delta":     (-0.02, 0.02), # 面积变化
    },
}

# 主色 : 辅色 : 点缀  design intent for the mineral triad
TRIAD = {"石青": 0.60, "石绿": 0.30, "朱红": 0.10}


def check(metrics, fidelity=None):
    """Compare measured metrics against SPEC. Returns list of check rows."""
    rows = []
    for key, rng in SPEC.items():
        if key in ("pigment", "fidelity"):
            continue
        lo, hi = rng
        v = metrics.get(key)
        rows.append({"name": key, "value": v, "min": lo, "max": hi,
                     "pass": bool(v is not None and lo <= v <= hi)})
    for pig, (lo, hi) in SPEC["pigment"].items():
        v = metrics.get("pigment", {}).get(pig, 0.0)
        rows.append({"name": "pig_" + pig, "value": v, "min": lo, "max": hi,
                     "pass": bool(lo <= v <= hi)})
    if fidelity:
        for key, (lo, hi) in SPEC["fidelity"].items():
            v = fidelity.get(key)
            rows.append({"name": "fid_" + key, "value": v, "min": lo, "max": hi,
                         "pass": bool(v is not None and lo <= v <= hi)})
    return rows


def triad_ratio(metrics):
    p = metrics.get("pigment", {})
    vals = {k: p.get(k, 0.0) for k in TRIAD}
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
    pig_lab = srgb_to_lab(np.array([PIGMENTS[k] for k in pig_names], dtype=np.float64))
    pig = {k: 0.0 for k in pig_names}
    pig["未归类"] = 0.0
    if coloured.any():
        cl = lab[coloured]
        d = np.linalg.norm(cl[:, None, :] - pig_lab[None, :, :], axis=2)
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


def compare(before, after):
    """Fidelity deltas that must stay inside the geometry tolerance."""
    a = np.array(Image.open(before).convert("RGBA"), dtype=np.float32)[..., 3] > 127
    b = np.array(Image.open(after).convert("RGBA"), dtype=np.float32)[..., 3] > 127
    if a.shape != b.shape:
        return {"size_match": False, "shape": [list(a.shape), list(b.shape)]}
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
