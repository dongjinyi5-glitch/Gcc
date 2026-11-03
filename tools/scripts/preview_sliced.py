# -*- coding: utf-8 -*-
"""零成本验收：把切回后的图集重新合成一遍，看「游戏里真正会看到的样子」。

为什么需要它
------------
`redrawn.png` 是**整张画布**的重绘结果，里面包含大量 alpha=0 的透明区
（天空、镜头外）。模型会把透明区当纸面填成一片金黄，于是在对比图里
"整关一片金黄"，但那些像素**切回时根本不写进图集**，游戏里看不到。

所以判断配色好不好，必须看「按 alpha 切回 → 再合成」的结果，而不是看
`redrawn.png`。这个脚本做的就是这件事，不调模型、不花钱。

做法
----
1. build_items 拿到每个四边形的几何、tint 和图集落点；
2. slice_back 用 redrawn.png 更新图集 RGB（alpha 不动）；
3. 用**更新后的图集**重新按同样几何合成一遍 —— 这就是游戏里的画面；
4. 并排输出「原始合成 / 切回后合成」，并给出配色统计。

用法
----
    python tools/scripts/preview_sliced.py --level level4
    python tools/scripts/preview_sliced.py --level level4 --redrawn out/redraw/level4/redrawn.png
"""
import argparse
import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import scene_stack as SS          # noqa: E402
from ggc_assets import PROJECT    # noqa: E402


def flatten_from_atlas(items, atlases, W, H):
    """与 SS.flatten 同样的合成顺序，但像素从（切回后的）图集里取。

    这是 flatten 的逆运算：flatten 用精灵裁剪图，这里用图集 + 反算坐标，
    所以取到的正是写回后的像素。
    """
    cv = np.zeros((H, W, 4), np.float32)
    for it in items:
        XX, YY, xi, yi, ok = SS._sample_coords(it)
        if not ok.any():
            continue
        key = (it["file"], it["path_id"])
        at = atlases.get(key)
        if at is None:
            continue
        arr = np.asarray(at.convert("RGBA"), np.float32) / 255.0
        ah, aw = arr.shape[0], arr.shape[1]
        ax, ay = SS._atlas_coords(it, xi, yi)
        axi = np.clip(np.round(ax).astype(np.int32), 0, aw - 1)
        ayi = np.clip(np.round(ay).astype(np.int32), 0, ah - 1)
        src = arr[ayi, axi]
        tr, tg, tb, ta = it["tint"]
        src = src.copy()
        src[..., 0] *= tr
        src[..., 1] *= tg
        src[..., 2] *= tb
        sa = src[..., 3:4] * ok[..., None] * ta
        x0, x1, y0, y1 = it["bbox"]
        da = cv[y0:y1, x0:x1, 3:4]
        out_a = sa + da * (1.0 - sa)
        with np.errstate(invalid="ignore", divide="ignore"):
            rgb = (src[..., :3] * sa + cv[y0:y1, x0:x1, :3] * da * (1.0 - sa))
            rgb = np.where(out_a > 1e-6, rgb / np.maximum(out_a, 1e-6), 0.0)
        cv[y0:y1, x0:x1, :3] = rgb
        cv[y0:y1, x0:x1, 3:4] = out_a
    return cv


def over_bg(cv, bg=(70, 74, 82)):
    """把 RGBA 合成图压到中性底上，模拟游戏天空/远景色。"""
    a = cv[..., 3:4]
    rgb = cv[..., :3] * a + np.array(bg, np.float32) / 255.0 * (1 - a)
    return Image.fromarray((np.clip(rgb, 0, 1) * 255).round().astype(np.uint8), "RGB")


def palette_stats(cv, tag):
    """配色统计：可见像素的平均色相分布与彩度，用来判断"是不是一片金黄"。"""
    a = cv[..., 3]
    m = a > 0.5
    if not m.any():
        print("  %s: 无可见像素" % tag)
        return
    rgb = cv[..., :3][m]
    mx = rgb.max(1)
    mn = rgb.min(1)
    sat = np.where(mx > 1e-6, (mx - mn) / np.maximum(mx, 1e-6), 0)
    warm = (rgb[:, 0] > rgb[:, 2] + 0.05)          # R 明显高于 B = 暖色
    cool = (rgb[:, 2] > rgb[:, 0] + 0.02)          # B 高于 R = 冷色
    print("  %-8s 可见 %.1f%%  平均彩度 %.3f  暖色 %.1f%%  冷色 %.1f%%  平均RGB %s"
          % (tag, 100.0 * m.mean(), sat.mean(), 100.0 * warm.mean(),
             100.0 * cool.mean(),
             tuple(int(v * 255) for v in rgb.mean(0))))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--level", default="level4")
    ap.add_argument("--redrawn", default=None)
    ap.add_argument("--tag", default=None, help="输出目录后缀，与 redraw_scene 的 --tag 对应")
    a = ap.parse_args()

    odir = os.path.join(PROJECT, "out", "redraw", a.level + (a.tag or ""))
    rp = a.redrawn or os.path.join(odir, "redrawn.png")
    redrawn = Image.open(rp).convert("RGB")

    db = SS.AssetDB(data_dir=SS.DATA)
    items, W, H, atlases = SS.build_items(db, a.level)
    print("%s: %d 个四边形，画布 %dx%d，图集 %d 张" % (a.level, len(items), W, H, len(atlases)))

    # 「之前」必须用改包前生成的合成图。
    # 游戏目录里的贴图已经被我们改写过，再从 DATA 重新合成会把成品当成原图，
    # 对比就成了"自己比自己"。scene_flat.png 是 --build 的产物，早于任何写包。
    flat_p = os.path.join(PROJECT, "out", "stack", a.level, "scene_flat.png")
    if os.path.isfile(flat_p):
        of = Image.open(flat_p).convert("RGBA")
        orig = np.asarray(of, np.float32) / 255.0
        if (of.width, of.height) != (W, H):
            print("  ! scene_flat 尺寸 %s 与画布 %s 不一致，退回现场合成"
                  % (of.size, (W, H)))
            orig = SS.flatten(items, W, H)
    else:
        print("  ! 缺 scene_flat.png，退回现场合成（注意：可能已被写包污染）")
        orig = SS.flatten(items, W, H)
    rep = {}
    layers = SS.slice_back(items, atlases, redrawn, W, H, report=rep)

    # 用切回后的图集替换，再合成 = 游戏里的画面
    after_atlases = {k: v["image"] for k, v in layers.items()}
    after = flatten_from_atlas(items, after_atlases, W, H)

    print("配色统计：")
    palette_stats(orig, "原图")
    palette_stats(after, "切回后")

    o_img = over_bg(orig)
    a_img = over_bg(after)

    # 上下对比
    cmp_ = Image.new("RGB", (W, H * 2 + 8), (0, 0, 0))
    cmp_.paste(o_img, (0, 0))
    cmp_.paste(a_img, (0, H + 8))
    p1 = os.path.join(odir, "PREVIEW_sliced_compare.png")
    cmp_.save(p1)
    p2 = os.path.join(odir, "PREVIEW_sliced.png")
    a_img.save(p2)

    # 中段细节对比（缝最容易暴露的地方）
    cx = int(W * 0.70)
    cw = min(1400, W)
    cx = min(cx, W - cw)
    c = Image.new("RGB", (cw, H * 2 + 8), (0, 0, 0))
    c.paste(o_img.crop((cx, 0, cx + cw, H)), (0, 0))
    c.paste(a_img.crop((cx, 0, cx + cw, H)), (0, H + 8))
    p3 = os.path.join(odir, "PREVIEW_sliced_detail.png")
    c.save(p3)

    print("已写出：\n  %s\n  %s\n  %s" % (p1, p2, p3))
    return 0


if __name__ == "__main__":
    sys.exit(main())
