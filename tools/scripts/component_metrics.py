"""Per-component numbers behind the "my recommendation" column.

A reviewer looking at 1450 rows needs to know, before opening any of them,
*which replacements actually did something*.  Two facts decide it here:

* 暗部占比 -- share of the component's own pixels below L* 25.  In this palette
  the restyler maps low luminance onto 墨 and nothing else, so a component that
  is mostly dark comes back as a flat silhouette: the shape survives, the
  painting does not.  That is exactly what L3's night shots showed in engine.
* 覆盖率 -- share of pixels whose chroma actually moved by more than 2 units.
  A big landmark with 5% coverage was not repainted, it was left alone.

Both are sampled on a 4-pixel grid: the statistic is a ratio, and full resolution
buys nothing for it while costing 16x the time.

Cached to art/component_metrics.json so rebuilding the workbook is instant.
"""
import io
import json
import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ggc_assets import AssetDB, PROJECT, baseline_map  # noqa: E402

INV = os.path.join(PROJECT, "art", "scene_inventory.json")
RESTYLED = os.path.join(PROJECT, "art", "scene_restyle", "all")
OUT = os.path.join(PROJECT, "art", "component_metrics.json")
STEP = 4


def to_lab(rgb):
    """sRGB uint8 HxWx3 -> L*, a*, b* float, same matrices as restyle_scene."""
    c = rgb.astype(np.float32) / 255.0
    c = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    m = np.array([[0.4124, 0.3576, 0.1805],
                  [0.2126, 0.7152, 0.0722],
                  [0.0193, 0.1192, 0.9505]], np.float32)
    xyz = c.reshape(-1, 3) @ m.T
    xyz /= np.array([0.95047, 1.0, 1.08883], np.float32)
    f = np.where(xyz > 0.008856, np.cbrt(xyz), 7.787 * xyz + 16 / 116)
    L = 116 * f[:, 1] - 16
    a = 500 * (f[:, 0] - f[:, 1])
    b = 200 * (f[:, 1] - f[:, 2])
    return L, a, b


def metrics(orig, new):
    o = np.array(orig.convert("RGBA"))[::STEP, ::STEP]
    n = np.array(new.convert("RGBA"))[::STEP, ::STEP]
    h = min(o.shape[0], n.shape[0])
    w = min(o.shape[1], n.shape[1])
    o, n = o[:h, :w], n[:h, :w]
    mask = (o[..., 3] > 16) & (n[..., 3] > 16)
    if mask.sum() < 8:
        return dict(dark=0.0, dC=0.0, cover=0.0, px=0)

    Lo, ao, bo = to_lab(o[..., :3])
    Ln, an, bn = to_lab(n[..., :3])
    m = mask.reshape(-1)
    Lo, ao, bo, Ln, an, bn = Lo[m], ao[m], bo[m], Ln[m], an[m], bn[m]

    Co = np.hypot(ao, bo)
    Cn = np.hypot(an, bn)
    dC = np.abs(Cn - Co)
    return dict(dark=float((Lo < 25).mean()),
                dC=float(dC.mean()),
                cover=float((dC > 2).mean()),
                px=int(m.sum()))


def advice(m, area):
    """-> (建议, 一句话理由).

    Tiered by area, not by darkness.  Dark-pixel share was tried first and
    rejected: the median component in this game is 78% dark, so "dark" does not
    discriminate -- it would have flagged 640 of 1450, half of them 40-pixel
    bottles.  Area does discriminate: 320 components (22%) hold ~85% of all the
    pixels in the game, and those are the ones whose brushwork the player sees.
    The two measured numbers ride along in the reason text so the call can be
    argued with.
    """
    if m["px"] == 0:
        return "待核", "无有效像素"
    cov = m["cover"] * 100
    if area >= 1.0e6:
        return "P1 重绘", "面积 %.1f Mpx，是画面地标；现版覆盖率 %.0f%%" % (area / 1e6, cov)
    if area >= 2.5e5:
        return "P2 待核", "面积 %.2f Mpx；现版覆盖率 %.0f%%，看效果再定" % (area / 1e6, cov)
    return "P3 换色阶", "小件，现版覆盖率 %.0f%%，换色阶即可" % cov


def main():
    inv = json.load(io.open(INV, encoding="utf-8"))
    cache = {}
    if os.path.exists(OUT):
        cache = json.load(io.open(OUT, encoding="utf-8"))

    db = AssetDB(file_map=baseline_map())   # 原图必须取 2015 备份
    objs = {}
    todo = [r for r in inv if "%s__%d" % (r["file"], r["path_id"]) not in cache]
    print("to compute:", len(todo))
    for i, r in enumerate(todo):
        k = "%s__%d" % (r["file"], r["path_id"])
        src = os.path.join(RESTYLED, k + ".png")
        if not os.path.exists(src):
            continue
        if r["file"] not in objs:
            objs[r["file"]] = db.file_objs(r["file"])
        obj = objs[r["file"]].get(r["path_id"])
        if obj is None:
            continue
        try:
            m = metrics(db.texture_image(obj), Image.open(src))
        except Exception as e:
            print("  fail", r["texture"], e)
            continue
        a, why = advice(m, r["area"])
        m["advice"] = a
        m["why"] = why
        cache[k] = m
        if (i + 1) % 100 == 0:
            print("  %d/%d" % (i + 1, len(todo)))
            json.dump(cache, io.open(OUT, "w", encoding="utf-8"))

    json.dump(cache, io.open(OUT, "w", encoding="utf-8"), ensure_ascii=False)
    print("cached", len(cache))


if __name__ == "__main__":
    main()
