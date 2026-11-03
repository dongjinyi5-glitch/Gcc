# -*- coding: utf-8 -*-
"""白描 -> 重彩上色 -> 回贴原图。

分工
----
模型只做它擅长的一件事：**按白描底稿上色**。构图、轮廓、位置全部由底稿锁死，
模型动不了。它输出一张有笔触的彩色画，我们再把它**贴回**原图。

回贴时有三件事必须守住：

1. **alpha 逐位不变** —— alpha 是碰撞契约，物理盒是按这个剪影建的。
2. **原图的 L\\* 保留** —— L* 里烘焙着游戏自己的光（灯晕、夜色、月光），
   这是美术烘进去的，换掉就毁了氛围。
3. **只有色度（a\\*, b\\*）来自模型** —— 模型给的是颜料，不是光。

所以合成公式是：

    L_out = L_orig + (模型明度的高频) * 门控
    a_out, b_out = 模型的色度 * 暗部衰减

暗部衰减的理由：真实的水墨重彩，亮处见色、暗处归墨。模型给的色度如果原样
贴上去，整个夜景会变成一片浑浊的橙红 —— 这是上一轮 lift-then-composite
失败的原因（红色渗进砖缝和轮胎）。衰减把深色区拉回墨色。

另外加了**边缘吸附**：把生成的色度往原图的剪影边界对齐，避免颜色跨过
轮廓渗到背景上。这是上一轮第二个失败点。
"""
import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from restyle_scene import box_blur  # noqa: E402


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


def _alpha_edge(alpha):
    """剪影边界带（0..1），用于把色度吸回轮廓内。"""
    a = alpha.astype(np.float32)
    inner = box_blur(a, 3)
    band = np.clip(a - inner, 0, 1) + np.clip(inner - a, 0, 1)
    return np.clip(band * 3.0, 0, 1)


def compose(orig, gen, detail=0.40, chroma_gain=1.0, floor=0.18,
            edge_lock=0.75, edge_width=2.0, crop_box=None, lift=0.0):
    """原图 + 模型上色图 -> 回贴结果 (RGBA)。

    orig : 原始贴图 RGBA（决定 alpha 与 L*）
    gen  : 模型按白描上色后的 RGB（提供色度与笔触）
    crop_box : 模型输入时的补边框 (x0, y0, w, h)。
        模型输入是 1024x1024 的正方形补边画，而原图可能不是正方形
        （bridge08 是 1024x996，补边 y0=14）。不按这个框裁回来，
        贴回去就会上下错位 14 像素。
    lift : 明度提亮强度 0..1，默认 0 = 老行为（明度完全锁原图）。
        原图是**暗底剪影**的构件（夜港、黑桅杆、纯黑起重机）在 lift=0 下
        永远出不了重彩 —— 模型画得再亮也被压回暗部，成品只是"暗部染了点色"。
        lift>0 时把模型明度的低频按比例混入，并按同样比例放开暗部色度衰减。
        代价：原图烘焙的夜景光效会被冲淡，是**美术取舍**，不是技术修正。
    """
    o = np.array(orig.convert("RGBA"))
    h, w = o.shape[:2]

    g0 = gen.convert("RGB")
    if crop_box:
        x0, y0, cw, ch = crop_box
        g0 = g0.crop((x0, y0, x0 + cw, y0 + ch))
    g = np.array(g0.resize((w, h), Image.LANCZOS))

    Lo, ao, bo = srgb_to_lab(o[..., :3])
    Lo, ao, bo = Lo.reshape(h, w), ao.reshape(h, w), bo.reshape(h, w)
    Lg, ag, bg = srgb_to_lab(g)
    Lg, ag, bg = Lg.reshape(h, w), ag.reshape(h, w), bg.reshape(h, w)

    alpha = o[..., 3].astype(np.float32) / 255.0

    # --- 1) 明度：原图为主，模型的笔触作高频叠加 -----------------------
    hp = Lg - box_blur(Lg, 6)
    gate = np.clip((Lo - 6) / 20, 0, 1) * np.clip((95 - Lo) / 20, 0, 1)
    L2 = Lo + hp * detail * gate

    # --- 1b) 可选：把模型明度的低频也混进来（暗底构件专用）------------
    if lift > 0:
        Llow = box_blur(Lg, 6)
        # 比笔触 gate 更宽松：纯黑区（Lo≈0）也要能抬起来
        gateL = np.clip((Lo - 1) / 10, 0, 1) * np.clip((150 - Lo) / 25, 0, 1)
        L2 = L2 + lift * (Llow - Lo) * gateL

    # --- 2) 色度：来自模型，暗部衰减到墨 ------------------------------
    # lift 越大，暗部衰减越放开（指数 <1），否则抬了明度色还是被压死
    cs = np.clip(Lo / 34.0, floor, 1.0) ** (1.0 - 0.7 * lift) * chroma_gain
    a2, b2 = ag * cs, bg * cs

    # --- 3) 边缘吸附：把色度往剪影内收，别渗到背景 --------------------
    if edge_lock > 0:
        band = _alpha_edge(alpha)
        bleed = np.clip(band - 0.05, 0, 1)
        # 边界外一圈的色度往内拉
        if edge_width > 0:
            shrink = np.clip(alpha - box_blur(alpha, int(edge_width)), 0, 1)
            shrink = np.clip(shrink * 2.0, 0, 1)
            pull = np.clip(1.0 - shrink, 0, 1)
            a2 = a2 * (1 - pull * edge_lock) + box_blur(a2, int(edge_width)) * (pull * edge_lock)
            b2 = b2 * (1 - pull * edge_lock) + box_blur(b2, int(edge_width)) * (pull * edge_lock)
        a2 = a2 * (1 - bleed * edge_lock * 0.5)
        b2 = b2 * (1 - bleed * edge_lock * 0.5)

    rgb = lab_to_srgb(L2.reshape(-1), a2.reshape(-1), b2.reshape(-1)).reshape(h, w, 3)
    out = np.dstack([rgb, o[..., 3]])           # alpha 逐位不变
    return Image.fromarray(out, "RGBA")


def alpha_identical(orig, out):
    """验收：alpha 必须逐位相同。"""
    a = np.array(orig.convert("RGBA"))[..., 3]
    b = np.array(out.convert("RGBA"))[..., 3]
    return bool((a == b).all()), int((a != b).sum())
