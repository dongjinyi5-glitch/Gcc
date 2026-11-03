# -*- coding: utf-8 -*-
"""整层合成重绘 → 按层 alpha 切回（路线 B 的脚手架）。

为什么需要它
------------
T1「白描 → 上色 → 回贴」在美术上不成立（2026-10-26 实测）：白描只给模型
一根线 + 大片空白，它要么退回白纸，要么自己编一整幅场景；而 compose 又把
明度锁死在原图上，成品永远是「原图 + 高饱和色块」。

路线 B 换了个顺序：

    1. 把一关的所有图层按 Unity 的排序与变换**合成一张完整的场景图**
    2. 模型对着这张完整图重绘（它终于能看到「完整的港口」而不是一根线）
    3. 再把重绘结果**按每层自己的 alpha 切回去**，逐层写回原贴图

第 3 步是本模块的核心。它必须守住两条：

* **alpha 逐位不变** —— alpha 是碰撞契约。切回只改 RGB，alpha 数组直接沿用原层。
* **不串层** —— 上层已经盖住的像素，不能写进下层。所以按「从上层到下层」的顺序
  处理，并维护一个 claimed 掩码：谁先认领谁拥有。

落点是**整张图集**（texture_file, texture_path_id），不是精灵裁剪图。同一张图集
常被多个精灵共用；写回时按 atlas_rect + rotation + 缩放，把裁剪像素反算回图集坐标
（见 ``_atlas_coords``），否则会写到别处、互相串色。

路线 B 的固有限制（``--verify`` 里单独统计、不算逻辑错误）：

* **resized** —— sprite_meta 会把 textureRect 拉伸到 m_Rect（trimmed 精灵被放大），
  是 LANCZOS 重采样，往返必然有损；
* **zero_tint** —— 白色遮罩/血条 tint≈0，合成时颜色被乘没，信息已不可逆；
* **multi_instance** —— 同一精灵一关里出现多次且 tint/背景不同，一个图集像素存不下多版本，
  只会留下最后绘制那次的样子。

用法
----
    # 1) 合成 + 导出每层原图（不调模型，零成本）
    python tools/scripts/scene_stack.py --level level4 --build

    # 2) 自检：把合成图当成"重绘结果"切回去，每层应还原成原图
    python tools/scripts/scene_stack.py --level level4 --verify

    # 3) 拿真正的模型输出切回
    python tools/scripts/scene_stack.py --level level4 --slice out/stack/level4/redrawn.png

产物落在 out/stack/<level>/ 下。
"""
import argparse
import io
import json
import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import scene_render as SR  # noqa: E402
from ggc_assets import AssetDB, DATA  # noqa: E402


# ---------------------------------------------------------------- 几何
def build_items(db, lv, ppu=100.0):
    """把一关的渲染器展开成「带反变换的四边形列表」。

    几何算法与 scene_render.render 完全一致（同一套 world 矩阵、pivot、
    pixels-per-unit 和分位裁剪），否则合成图与游戏里看到的对不上。
    """
    quads = SR.collect(db, lv)
    if not quads:
        return [], 0, 0

    boxes = []
    for order, idx, m, meta, tint in quads:
        img = meta["image"]
        h = img.height
        pvx, pvy, sppu = meta["pivot_x"], meta["pivot_y"], meta["ppu"]
        pts = [SR.apply(m, (px - pvx) / sppu, (h - pvy - py) / sppu)
               for px, py in ((0, 0), (img.width, 0), (img.width, h), (0, h))]
        boxes.append((order, idx, meta, tint, img, pts))

    xs = [p[0] for b in boxes for p in b[5]]
    ys = [p[1] for b in boxes for p in b[5]]
    tail = 0.002
    x_lo, x_hi = np.quantile(np.array(xs), [tail, 1 - tail])
    y_lo, y_hi = np.quantile(np.array(ys), [tail, 1 - tail])
    minx, maxy = float(x_lo), float(y_hi)
    W = int(round((x_hi - x_lo) * ppu)) + 2
    H = int(round((y_hi - y_lo) * ppu)) + 2
    longest = max(W, H)
    if longest > SR.MAX_PX:
        k = SR.MAX_PX / longest
        ppu *= k
        W, H = max(1, int(W * k)), max(1, int(H * k))

    items = []
    for order, idx, meta, tint, img, pts in boxes:
        dst = [((cx - minx) * ppu + 1, (maxy - cy) * ppu + 1) for cx, cy in pts]
        A, b = [], []
        for (sx_, sy_), (dx, dy) in zip(((0, 0), (img.width, 0),
                                        (img.width, img.height), (0, img.height)),
                                       dst):
            A.append([sx_, sy_, 1, 0, 0, 0]); b.append(dx)
            A.append([0, 0, 0, sx_, sy_, 1]); b.append(dy)
        coef, *_ = np.linalg.lstsq(np.array(A, float), np.array(b, float),
                                   rcond=None)
        c0, c1, c2, c3, c4, c5 = coef
        if abs(c0 * c4 - c1 * c3) < 1e-9:
            continue
        x0 = max(0, int(min(p[0] for p in dst)))
        x1 = min(W, int(max(p[0] for p in dst)) + 1)
        y0 = max(0, int(min(p[1] for p in dst)))
        y1 = min(H, int(max(p[1] for p in dst)) + 1)
        if x1 <= x0 or y1 <= y0:
            continue
        items.append({
            "order": order, "idx": idx,
            "name": meta.get("texture_name") or meta.get("sprite_name") or "?",
            "file": meta.get("texture_file"), "path_id": meta.get("texture_path_id"),
            "sprite": meta.get("sprite_name"), "sprite_path_id": meta.get("sprite_path_id"),
            "atlas_rect": list(meta.get("atlas_rect") or ()),
            "rotation": int(meta.get("rotation", 0) or 0),
            "texture_size": list(meta.get("texture_size") or (img.width, img.height)),
            "coef": [float(v) for v in coef],
            "bbox": [x0, x1, y0, y1],
            "tint": [float(v) for v in tint],
            "size": [img.width, img.height],
            "_img": img,
        })

    # 每张图集（texture_file, texture_path_id）只解析一次，作为切回的落点。
    # 关键修正：之前把"精灵裁剪图"当成图层落点，而同一张图集被多个精灵共用，
    # 各自用裁剪坐标系写回 → 互相串色。现在落点是整张图集，写回时按 atlas_rect
    # + rotation 把裁剪像素反算回图集坐标。
    atlases = {}
    for it in items:
        key = (it["file"], it["path_id"])
        if key in atlases:
            continue
        objs = db.file_objs(it["file"])
        tex = objs.get(it["path_id"])
        atlases[key] = db.texture_image(tex) if tex is not None else None
    return items, W, H, atlases


def _atlas_coords(it, xi, yi):
    """精灵裁剪像素 (xi, yi) → 图集像素 (ax, ay)（浮点，调用方取整）。

    严格反算 ggc_assets.sprite_meta 的 裁剪 + 旋转 + 缩放：
      * 裁剪图 = 模型看到的精灵本体，几何变换用的是它的坐标；
      * sprite_meta 在 m_Rect 与 textureRect 尺寸不一致时会把裁剪图 LANCZOS
        放大/缩小到 m_Rect 尺寸，所以这里必须先把裁剪坐标按相同比例缩回
        textureRect（图集子区）坐标，否则会差出数倍、写到图集别处（串色）。
    """
    ar = it.get("atlas_rect") or (0, 0, it["size"][0], it["size"][1])
    x, y, w, h = [float(v) for v in ar[:4]]
    rw, rh = float(it["size"][0]), float(it["size"][1])   # 裁剪图（已含缩放）尺寸
    sx_ = xi * (w / rw)                 # 裁剪坐标 → textureRect 坐标
    sy_ = yi * (h / rh)
    ts = it.get("texture_size") or it["size"]
    H = int(ts[1])
    rot = int(it.get("rotation", 0) or 0)
    if rot == 1:                        # 裁剪时 rotate(-90) = 顺时针 90°
        ax = x + sy_
        ay = (H - y - 1) - sx_
    elif rot in (2, 3):                 # 裁剪时 rotate(90) = 逆时针 90°
        ax = x + h - 1 - sy_
        ay = (H - y - w) + sx_
    else:                               # rot == 0，直接平移
        ax = x + sx_
        ay = (H - y - h) + sy_
    return ax, ay


def _sample_coords(it, bbox=None):
    """返回该四边形在画布上的像素网格，以及对应的源图坐标。"""
    x0, x1, y0, y1 = bbox or it["bbox"]
    c0, c1, c2, c3, c4, c5 = it["coef"]
    det = c0 * c4 - c1 * c3
    ia, ib = c4 / det, -c1 / det
    ic, id_ = -c3 / det, c0 / det
    ie = -(ia * c2 + ib * c5)
    if_ = -(ic * c2 + id_ * c5)
    XX, YY = np.meshgrid(np.arange(x0, x1, dtype=np.float32),
                         np.arange(y0, y1, dtype=np.float32))
    sxv = ia * XX + ib * YY + ie
    syv = ic * XX + id_ * YY + if_
    w, h = it["size"]
    ok = ((sxv >= 0) & (sxv < w - 0.5) & (syv >= 0) & (syv < h - 0.5))
    xi = np.clip(sxv.astype(np.int32), 0, w - 1)
    yi = np.clip(syv.astype(np.int32), 0, h - 1)
    return XX, YY, xi, yi, ok


# ---------------------------------------------------------------- 合成
def flatten(items, W, H, canvas=None):
    """按顺序把四边形叠成一张 RGBA 场景图（与 scene_render.render 同一套算法）。"""
    cv = np.zeros((H, W, 4), np.float32) if canvas is None else canvas
    for it in items:
        XX, YY, xi, yi, ok = _sample_coords(it)
        if not ok.any():
            continue
        arr = np.asarray(it["_img"].convert("RGBA"), np.float32) / 255.0
        src = arr[yi, xi]
        tr, tg, tb, ta = it["tint"]
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


# ---------------------------------------------------------------- 切回
def slice_back(items, atlases, redrawn, W, H, alpha_min=0.02, report=None):
    """把重绘后的整层图按每层 alpha 切回，返回 {key: layer_dict}。

    redrawn : PIL.Image 或 ndarray，尺寸必须是 (W, H)
    atlases : {(file, path_id): PIL.Image} —— 整张图集，作为写回落点
    key     : (texture_file, texture_path_id) —— 与版本库、清单的同一套身份

    核心保证：
    * **alpha 逐位不变** —— 图层数组直接克隆自整张图集，切回只改 RGB，alpha 一个字节都不碰。
    * **不串层** —— 按"从上层到下层"顺序处理，claimed 掩码让先认领者拥有该画布像素。
    * **裁剪→图集反算** —— 精灵在图集里只是个裁剪+旋转的小块，写回必须搬回正确图集坐标，
      否则和共用同一图集的其他精灵互相串色。
    """
    if isinstance(redrawn, Image.Image):
        rd = redrawn.convert("RGB")
        if rd.size != (W, H):
            rd = rd.resize((W, H), Image.LANCZOS)
        rd = np.asarray(rd, np.float32) / 255.0
    else:
        rd = np.asarray(redrawn, np.float32) / 255.0
        if rd.shape[:2] != (H, W):
            raise ValueError("redrawn 尺寸 %s 与画布 %s 不一致"
                             % (rd.shape[:2], (H, W)))

    layers = {}
    for it in items:
        key = (it["file"], it["path_id"])
        if key not in layers:
            a0 = atlases.get(key)
            if a0 is None:                       # 理论不会发生：build_items 已解析
                a0 = it["_img"]
            arr = np.array(a0.convert("RGBA"), np.float32) / 255.0
            layers[key] = {
                "name": it["name"], "file": it["file"], "path_id": it["path_id"],
                "atlas_rect": it["atlas_rect"], "arr": arr, "visible": 0,
            }

    claimed = np.zeros((H, W), bool)
    # 从最上层往下走：先认领的拥有该像素
    for it in reversed(items):
        XX, YY, xi, yi, ok = _sample_coords(it)
        if not ok.any():
            continue
        key = (it["file"], it["path_id"])
        lay = layers[key]["arr"]
        aw, ah = lay.shape[1], lay.shape[0]
        ax, ay = _atlas_coords(it, xi, yi)
        # 反算出来的是浮点图集坐标，取整后再索引；越界由 inb 挡在 take 之外
        axi = np.round(ax).astype(np.int32)
        ayi = np.round(ay).astype(np.int32)
        inb = (axi >= 0) & (axi < aw) & (ayi >= 0) & (ayi < ah)
        axc = np.clip(axi, 0, aw - 1)
        ayc = np.clip(ayi, 0, ah - 1)
        a = lay[..., 3][ayc, axc] * it["tint"][3]
        take = ok & inb & (a > alpha_min) & ~claimed[it["bbox"][2]:it["bbox"][3],
                                                     it["bbox"][0]:it["bbox"][1]]
        if not take.any():
            continue
        # XX/YY 是 canvas 坐标系的浮点网格，索引 rd（画布尺寸数组）必须转成整数
        XXi = XX.astype(np.int32)
        YYi = YY.astype(np.int32)
        col = rd[YYi[take], XXi[take]]
        # 合成图里已经乘过 tint，写回贴图前要除掉，否则运行时会二次着色
        tr, tg, tb = it["tint"][0], it["tint"][1], it["tint"][2]
        col = np.stack([col[:, 0] / max(tr, 1e-3),
                        col[:, 1] / max(tg, 1e-3),
                        col[:, 2] / max(tb, 1e-3)], axis=-1)
        lay[ayi[take], axi[take], :3] = np.clip(col, 0.0, 1.0)
        layers[key]["visible"] += int(take.sum())
        claimed[it["bbox"][2]:it["bbox"][3],
                it["bbox"][0]:it["bbox"][1]] |= take

    out = {}
    for key, lay in layers.items():
        arr8 = (np.clip(lay["arr"], 0, 1) * 255).round().astype(np.uint8)
        out[key] = {"name": lay["name"], "file": lay["file"],
                    "path_id": lay["path_id"], "atlas_rect": lay["atlas_rect"],
                    "image": Image.fromarray(arr8, "RGBA"),
                    "visible": lay["visible"]}
    if report is not None:
        report["layers"] = len(out)
        report["visible_px"] = int(claimed.sum())
        report["canvas"] = [W, H]
    return out


# ---------------------------------------------------------------- 命令行
def cmd_build(args):
    db = AssetDB(data_dir=DATA)
    items, W, H, atlases = build_items(db, args.level)
    print("%s: %d 个四边形，画布 %dx%d" % (args.level, len(items), W, H))
    outdir = os.path.join(args.out, args.level)
    os.makedirs(outdir, exist_ok=True)

    flat = flatten(items, W, H)
    img = Image.fromarray((np.clip(flat, 0, 1) * 255).round().astype(np.uint8), "RGBA")
    flat_p = os.path.join(outdir, "scene_flat.png")
    img.save(flat_p)

    man = {"level": args.level, "canvas": [W, H], "count": len(items),
           "items": [{k: v for k, v in it.items() if k != "_img"} for it in items]}
    json.dump(man, io.open(os.path.join(outdir, "scene_stack.json"), "w",
                           encoding="utf-8"), ensure_ascii=False, indent=1)
    print("合成图 -> %s" % flat_p)
    print("清单   -> %s" % os.path.join(outdir, "scene_stack.json"))
    return 0


def cmd_verify(args):
    """往返自检（零成本，不调模型）。

    硬契约：alpha 必须逐位一致——切回只改 RGB，图集 alpha 原样沿用。
    RGB 只在"干净"图集上校验：单实例、未缩放、非零 tint。其余三类是路线 B
    的固有限制（不是逻辑错误），单独统计、不计入判定：
      * resized        sprite_meta 把 textureRect 拉伸到 m_Rect（LANCZOS 重采样，往返有损）
      * zero_tint      白色遮罩/血条 tint≈0，合成时颜色被乘没，信息已不可逆
      * multi_instance 同一精灵在一关出现多次且 tint/背景不同，一个图集像素存不下多版本
    """
    db = AssetDB(data_dir=DATA)
    items, W, H, atlases = build_items(db, args.level)
    flat = flatten(items, W, H)
    flat8 = (np.clip(flat, 0, 1) * 255).round().astype(np.uint8)
    rep = {}
    layers = slice_back(items, atlases, flat8, W, H, report=rep)

    def resized(it):
        ar = it.get("atlas_rect") or ()
        return len(ar) >= 4 and (abs(it["size"][0] - ar[2]) > 1
                                 or abs(it["size"][1] - ar[3]) > 1)
    cnt, is_res, is_zt = {}, {}, {}
    for it in items:
        k = (it["file"], it["path_id"])
        cnt[k] = cnt.get(k, 0) + 1
        is_res[k] = is_res.get(k, False) or resized(it)
        is_zt[k] = is_zt.get(k, False) or (min(it["tint"][:3]) < 0.05)

    alpha_bad = 0
    cat = {"resized": 0, "zero_tint": 0, "multi_instance": 0, "clean_single": 0}
    clean_px = clean_dev = clean_worst = 0
    clean_worst_k = None
    for key, lay in layers.items():
        rec = np.asarray(lay["image"], np.uint8)
        org = np.asarray(atlases[key].convert("RGBA"), np.uint8)
        if org.shape != rec.shape:
            print("  尺寸不符 %s %s vs %s" % (lay["name"], org.shape, rec.shape))
            alpha_bad += 1
            continue
        if not np.array_equal(org[..., 3], rec[..., 3]):
            alpha_bad += 1
            print("  !! alpha 被改动 %s" % lay["name"])
        m = org[..., 3] == 255
        if not m.any():
            continue
        d = np.abs(org[..., :3].astype(int) - rec[..., :3].astype(int)).max(2)
        if is_res[key]:
            cat["resized"] += 1
            continue
        if is_zt[key]:
            cat["zero_tint"] += 1
            continue
        if cnt[key] > 1:
            cat["multi_instance"] += 1
            continue
        cat["clean_single"] += 1
        clean_px += int(m.sum())
        clean_dev += int((d[m] > 2).sum())
        w = int(d[m].max())
        if w > clean_worst:
            clean_worst, clean_worst_k = w, key

    frac = (100.0 * clean_dev / clean_px) if clean_px else 0.0
    print("\n自检：%d 张图集，画布 %dx%d，覆盖像素 %d"
          % (rep.get("layers", 0), W, H, rep.get("visible_px", 0)))
    print("  硬契约 alpha 逐位一致：%s"
          % ("通过 ✓" if alpha_bad == 0 else "失败 ✗（%d 张被改）" % alpha_bad))
    print("  干净图集（单实例/未缩放/非零tint）：%d 张，不透明像素 %d"
          % (cat["clean_single"], clean_px))
    wk = ("%s:%d" % (clean_worst_k[0].split('.')[0], clean_worst_k[1])
          if clean_worst_k else "-")
    print("    偏差>2 像素：%d（%.4f%%），最大偏差 %d（%s）"
          % (clean_dev, frac, clean_worst, wk))
    print("  路线B固有限制（不计入判定）：缩放 %d、零tint %d、多实例 %d"
          % (cat["resized"], cat["zero_tint"], cat["multi_instance"]))
    ok = (alpha_bad == 0) and (frac < 0.5)
    print("  结论：%s"
          % ("slice-back 逻辑正确 ✓（alpha 无损；干净图集偏差仅极少数边缘像素）"
             if ok else "需检查 ✗"))
    return 0 if ok else 1


def cmd_slice(args):
    db = AssetDB(data_dir=DATA)
    items, W, H, atlases = build_items(db, args.level)
    outdir = os.path.join(args.out, args.level)
    os.makedirs(os.path.join(outdir, "sliced"), exist_ok=True)
    red = Image.open(args.slice)
    rep = {}
    layers = slice_back(items, atlases, red, W, H, report=rep)
    for (f, pid), lay in sorted(layers.items(), key=lambda kv: kv[1]["name"]):
        safe = "".join(c if c.isalnum() or c in "._-" else "_" for c in lay["name"])
        p = os.path.join(outdir, "sliced", "%s_%s.png" % (safe, pid))
        lay["image"].save(p)
    print("切回 %d 张图集 -> %s" % (len(layers), os.path.join(outdir, "sliced")))
    return 0


def main():
    ap = argparse.ArgumentParser(description="整层合成重绘 → 按层 alpha 切回")
    ap.add_argument("--level", default="level4")
    ap.add_argument("--out", default=os.path.join("out", "stack"))
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--build", action="store_true", help="合成整层场景图并导出清单")
    g.add_argument("--verify", action="store_true", help="往返自检（零成本，不调模型）")
    g.add_argument("--slice", metavar="REDRAWN.png", help="把重绘结果按层切回")
    args = ap.parse_args()
    if args.build:
        return cmd_build(args)
    if args.verify:
        return cmd_verify(args)
    return cmd_slice(args)


if __name__ == "__main__":
    sys.exit(main())
