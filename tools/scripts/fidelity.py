# -*- coding: utf-8 -*-
"""重绘保真度打分 —— 判断模型有没有真的照着白描底稿画。

为什么需要打分
--------------
白描路线的全部价值在于「构图被锁死」。但模型可能不听：它可能把结构改了、
可能把物件缩小了、可能自己另画一张。这些都要能**自动**判出来，
否则 160 张只能靠人眼一张张看。

三个分数
--------
* **edge** —— 生成的图里，边缘像素落在白描墨线带上的比例（双向取平均）。
  白描底稿是「已知的正确结构」，模型画的边缘应当落在墨线上。
  这个量直接回答"结构有没有被改"。
* **silhouette** —— 生成的图里「非纸色」区域与原图剪影的 IoU。
  量「物件有没有跑到别处、缩小、变大」。
* **pigment** —— 颜色区域的丰富度（色度的空间变化）。
  量「有没有真的画出颜料层次」，而不是一块平涂。

归一化用 p99.5 而不是 max
-------------------------
第一版用 max 归一化，结果是**原图自己只得 0.09 分，比水平翻转的负���对照
还低** —— 因为原图是硬边矢量画，单条边的梯度峰值极高，除以峰值之后
其它所有边都被压到阈值以下。改用 p99.5（restyle_scene 里同一个约定）之后，
边沿强度变成相对量，不同画法的图才可以互相比较。
"""
import os
import sys

import numpy as np
from PIL import Image, ImageFilter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lineart import sobel  # noqa: E402
from recompose import srgb_to_lab  # noqa: E402

# 成品与原图的平均 ΔE 下限。低于它说明模型等于没上色，回贴后还是原图。
# 6 是「肉眼能看出明显换色」的量级；原图自身 ΔE=0，纯染色版实测约 3。
PASS_DE = 6.0


def _edges(g, pct=99.5):
    """归一化梯度：p99.5 分位映射到 1。"""
    e = sobel(g)
    if e.size == 0:
        return e
    p = float(np.percentile(e, pct))
    return np.clip(e / max(p, 1e-6), 0.0, 1.0)


def _dilate(mask, k=5):
    im = Image.fromarray((mask * 255).astype(np.uint8), "L")
    im = im.filter(ImageFilter.MaxFilter(k))
    return np.asarray(im, np.float32) / 255.0


def score(lineart, gen, orig=None, composite=None):
    """-> dict(edge, silhouette, pigment, verdict)。

    edge / pigment 量的是**模型原图** gen（模型有没有照白描画、有没有颜料层次）；
    silhouette / holes / cover 量的是**成品 composite**（G1）——只有成品才决定
    精灵内部到底有没有被画上。模型原图里"没画到的地方"会被回贴时保住的原图
    L* 填回去，所以不能用它来判断空洞，否则会把一堆无害的 overflow 误判成洞。

    三张图可能分辨率不同，先统一到白描底稿分辨率；大图超过 1400 边长就等比缩到
    1400 以内压内存。
    """
    la_im = lineart.convert("RGB")
    g_im = gen.convert("RGB")
    H, W = la_im.size[1], la_im.size[0]
    cap = 1400
    if max(H, W) > cap:
        s = cap / max(H, W)
        la_im = la_im.resize((int(W * s), int(H * s)), Image.LANCZOS)
        g_im = g_im.resize(la_im.size, Image.LANCZOS)
    elif g_im.size != la_im.size:
        g_im = g_im.resize(la_im.size, Image.LANCZOS)

    la = np.array(la_im).astype(np.float32) / 255.0
    gl = la.mean(axis=2)

    # 白描的墨线：底图上是深色，且落在墨的边缘带上
    dark = gl < 0.45
    e_l = _edges(gl)
    ink_thin = (e_l > 0.25) & (dark | (e_l > 0.50))

    g = np.array(g_im).astype(np.float32) / 255.0
    gg = g.mean(axis=2)
    e_g = _edges(gg)
    gen_edge = e_g > 0.25

    # 双向匹配，两个方向都允许 3 像素容差（模型画的线不必与底稿逐像素重合）
    #   fwd：生成的边，有多少落在墨线带里
    #   bwd：墨线，有多少被生成的边覆盖
    ink_band = _dilate(ink_thin, 7) > 0.5
    gen_band = _dilate(gen_edge, 7) > 0.5
    n_ge, n_ink = gen_edge.sum(), ink_thin.sum()
    fwd = float((gen_edge & ink_band).sum() / n_ge) if n_ge > 8 else 0.0
    bwd = float((ink_thin & gen_band).sum() / n_ink) if n_ink > 8 else 0.0

    # 取**绑定**的那一个（min），不是平均。
    # 噪声图在 bwd 上会接近 1（到处都是边，天然覆盖所有墨线），
    # 平均会让噪声拿到最高分；min 才能同时压住噪声与错位图。
    edge = min(fwd, bwd)

    # silhouette / holes / cover：只用成品 composite 算（见函数说明）。
    # 模型原图里的"没画到"会被原图 L* 填回，不能用它判洞。
    sil = None
    holes = None
    cover = None
    if orig is not None:
        o_im = orig.convert("RGBA")
        if o_im.size != la_im.size:
            o_im = o_im.resize(la_im.size, Image.LANCZOS)
        o = np.array(o_im)
        shape = o[..., 3] > 128
        # 用来判"有没有画上"的图：优先 composite，否则退化用 gen
        if composite is not None:
            c_im = composite.convert("RGB")
            if c_im.size != la_im.size:
                c_im = c_im.resize(la_im.size, Image.LANCZOS)
            c = np.array(c_im).astype(np.float32) / 255.0
            Lc, ac, bc = srgb_to_lab((c * 255).astype(np.uint8))
        else:
            # 没有成品就退化为量模型原图（自检、离线复算会走这条）
            Lc, ac, bc = srgb_to_lab((g * 255).astype(np.uint8))
        Lc = Lc.reshape(o.shape[:2])
        ac = ac.reshape(o.shape[:2])
        bc = bc.reshape(o.shape[:2])
        sat = np.hypot(ac, bc)
        nonpaper = (sat > 14) | (Lc < 78)
        union = float((nonpaper | shape).sum())
        sil = float((nonpaper & shape).sum()) / union if union > 0 else 0.0
        # 关键：精灵内部有没有"空洞"（画上去了没有）—— 真正要拦的。
        # overflow（画到精灵外）被保住的 alpha 裁掉，无害。
        scount = float(shape.sum())
        holes = float((shape & ~nonpaper).sum()) / scount if scount > 0 else 0.0
        cover = float((shape & nonpaper).sum()) / scount if scount > 0 else 0.0

    # pigment: 8x8 块的色度均值标准差
    Lc, ac, bc = srgb_to_lab((g * 255).astype(np.uint8))
    ac, bc = ac.reshape(g.shape[:2]), bc.reshape(g.shape[:2])
    chroma = np.hypot(ac, bc)
    bs, cells = 8, []
    h, w = chroma.shape
    for y in range(0, h - bs, bs):
        for x in range(0, w - bs, bs):
            cells.append(chroma[y:y + bs, x:x + bs].mean())
    cells = np.array(cells)
    pigment = float(cells.std() / 20.0) if cells.size else 0.0

    # delta_e: 成品相对原图的真实改动量（ΔE76，只看精灵内部）。
    # 为什么必须有这一条：edge 只看「模型边缘落没落在墨线上」，pigment 只看
    # 「模型图里色度丰不丰富」。模型完全可以画一张构图正确、色彩绚烂、但
    # **整幅是它自己编的新场景** —— 两个指标都会高分，而回贴后成品和原图
    # 几乎一样（因为 compose 保住了原图 L*，只借了色度）。
    # 2026-10-26 实测：Harbour_Background_04 成品与原图平均只差 ΔE≈3，
    # 肉眼就是「黑桅杆染了点绿」，却拿了 edge=0.776 / pig=0.604 判通过。
    delta_e = None
    chroma_ratio = None
    if orig is not None and composite is not None:
        o2 = np.array(orig.convert("RGBA").resize(la_im.size, Image.LANCZOS))
        mask = o2[..., 3] > 128
        if mask.sum() > 0:
            # 注意：上面的 Lc/ac/bc 已被 pigment 段覆盖成扁平的模型图版本，
            # 这里必须重新从 composite 算，不能复用。
            c2 = np.array(composite.convert("RGB").resize(la_im.size, Image.LANCZOS)
                          ).astype(np.float32) / 255.0
            Lc2, ac2, bc2 = srgb_to_lab((c2 * 255).astype(np.uint8))
            Lc2 = Lc2.reshape(mask.shape)
            ac2 = ac2.reshape(mask.shape)
            bc2 = bc2.reshape(mask.shape)
            Lo2, ao2, bo2 = srgb_to_lab(o2[..., :3])
            Lo2 = Lo2.reshape(mask.shape); ao2 = ao2.reshape(mask.shape)
            bo2 = bo2.reshape(mask.shape)
            de = np.sqrt((Lc2 - Lo2) ** 2 + (ac2 - ao2) ** 2 + (bc2 - bo2) ** 2)
            delta_e = float(de[mask].mean())
            co = np.hypot(ao2, bo2)[mask].mean()
            cg = np.hypot(ac2, bc2)[mask].mean()
            chroma_ratio = float(cg / max(co, 1e-3))

    verdict = "通过"
    # 阈值 0.40：实测 原图(结构真值)=0.53、重绘=0.63、噪声=0.34、翻转=0.23。
    # 取 0.40 是为了让噪声(0.34)稳稳落在门槛外，而不是压在 0.34 的边上。
    # silhouette(IoU) 会误伤"模型把缝隙填实、画到剪影外被 alpha 裁掉"的情况，
    # 那是无害的 overflow；真正要拦的是"精灵内部有洞"（holes）。
    if edge < 0.40:
        verdict = "结构没跟住（模型重画了）"
    elif holes is not None and holes > 0.06:
        verdict = "物件内部有空洞（没画上）"
    elif delta_e is not None and delta_e < PASS_DE:
        verdict = "几乎没变（成品与原图差异 ΔE=%.1f）" % delta_e
    elif pigment < 0.30:
        verdict = "颜色太平，缺颜料层次"

    return {"edge": round(edge, 3),
            "fwd": round(fwd, 3), "bwd": round(bwd, 3),
            "silhouette": None if sil is None else round(sil, 3),
            "cover": None if cover is None else round(cover, 3),
            "holes": None if holes is None else round(holes, 3),
            "pigment": round(pigment, 3),
            "delta_e": None if delta_e is None else round(delta_e, 2),
            "chroma_ratio": None if chroma_ratio is None else round(chroma_ratio, 2),
            "verdict": verdict}
