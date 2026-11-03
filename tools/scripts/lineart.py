# -*- coding: utf-8 -*-
r"""白描底稿 —— 从原图抽出线描，作为重绘的输入。

为什么不是把原图直接喂给模型
---------------------------
前两次失败是同一个原因：原图 81% 的像素落在 L* 64 以下，模型拿到的是一张
几乎全黑的图，于是它"发明"了一张明亮的纸本插画，还把构图挪了位置。
结构信息在暗部里根本不存在，模型只能重画。

白描把结构**显式化**：
    1. 原图 L\* 通道做多尺度 Sobel，得到全部轮廓与内部结构线；
    2. alpha 通道也做一遍，得到剪影外廓（这条最重要，剪影是碰撞契约）；
    3. 原图的明暗压成一层"淡彩"灰阶，让模型知道哪块深哪块浅；
    4. 透明区填纸白 —— 模型看到的是一张完整的画，不会以为画错了地方。

这恰好就是国画自己的工序：**白描打底 → 设色**。底稿由程序从原图抽出，
设色交给模型。构图因此被锁死，模型只负责上色。

线条用墨色，纸用暖白，灰阶用极窄的一段（205–245），避免模型把它当成
"画面内容"去填满。
"""
import os
import sys

import numpy as np
from PIL import Image, ImageFilter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

PAPER = (250, 246, 238)      # 纸白（暖）
INK = (26, 22, 19)           # 墨
WASH_LO, WASH_HI = 205, 245  # 淡彩灰阶范围


def _shift(a, dy, dx):
    """平移数组，边界补零。"""
    out = np.zeros_like(a)
    h, w = a.shape
    ys0, ys1 = max(0, dy), min(h, h + dy)
    xs0, xs1 = max(0, dx), min(w, w + dx)
    if ys1 > ys0 and xs1 > xs0:
        out[ys0:ys1, xs0:xs1] = a[ys0 - dy:ys1 - dy, xs0 - dx:xs1 - dx]
    return out


def sobel(g):
    """Sobel 梯度幅值，输入 0..1 的二维数组。

    注意 `_shift` 的方向：`out[y,x] = a[y, x-dx]`，所以 dx>0 取到的是**左边**
    的像素，dx<0 取到的是右边。梯度必须是"右减左"，写成两边相加就变成了
    平滑，平面区域的梯度会等于邻域均值 —— 整幅图都会被判成边缘
    （实测平直的钢梁内部 p50 梯度 0.34，输出成了全黑剪影）。
    """
    right1, right2 = _shift(g, 0, -1), _shift(g, 0, -2)
    left1, left2 = _shift(g, 0, 1), _shift(g, 0, 2)
    down1, down2 = _shift(g, -1, 0), _shift(g, -2, 0)
    up1, up2 = _shift(g, 1, 0), _shift(g, 2, 0)

    gx = (right1 + 2 * right2 - left1 - 2 * left2) * 0.25
    gy = (down1 + 2 * down2 - up1 - 2 * up2) * 0.25
    return np.hypot(gx, gy)


def _blur(a, r):
    """数组做高斯模糊（走 PIL，避免 mode 'F' 的限制）。"""
    if r <= 0:
        return a
    u8 = np.clip(a * 255.0, 0, 255).astype(np.uint8)
    im = Image.fromarray(u8, "L").filter(ImageFilter.GaussianBlur(r))
    return np.asarray(im, np.float32) / 255.0


def to_lab_L(rgb):
    """sRGB uint8 -> L*（0..100）。"""
    c = rgb.astype(np.float32) / 255.0
    c = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    m = np.array([[0.4124, 0.3576, 0.1805],
                  [0.2126, 0.7152, 0.0722],
                  [0.0193, 0.1192, 0.9505]], np.float32)
    xyz = c.reshape(-1, 3) @ m.T
    xyz /= np.array([0.95047, 1.0, 1.08883], np.float32)
    f = np.where(xyz > 0.008856, np.cbrt(xyz), 7.787 * xyz + 16 / 116)
    return (116 * f[:, 1] - 16).reshape(rgb.shape[:2])


def _norm(E, ref=None):
    """按自身强度归一化到 0..1。

    两个场的量级差很远：L* 的 Sobel 峰值约 1.5，而 alpha 剪影的 Sobel 峰值
    可以到 2.1。混在一起取同一个百分位阈值会让其中一个整个消失（实测两个
    场都被阈值吃掉，输出全白）。所以各自归一化、各自取阈值。
    """
    hi = float(ref if ref is not None else E.max())
    if hi <= 1e-9:
        return np.zeros_like(E)
    return np.clip(E / hi, 0, 1)


def _ink(E, t, soft):
    """归一化梯度 -> 墨线浓度 0..1。"""
    return np.clip((E - t) / soft, 0, 1)


def build_lineart(orig, wash_lo=WASH_LO, wash_hi=WASH_HI,
                  t_struct=0.10, t_sil=0.22):
    """原图 RGBA -> 白描底稿 RGB。

    返回 (lineart, info)。info 里带着中间量，方便出问题时回看。
    """
    o = np.array(orig.convert("RGBA"))
    h, w = o.shape[:2]
    alpha = o[..., 3].astype(np.float32) / 255.0

    # --- 1) 结构线：L* 的多尺度 Sobel -----------------------------------
    L = to_lab_L(o[..., :3]) / 100.0
    Lm = np.where(alpha > 0.5, L, np.nan)          # 透明区不参与
    fill = np.nanmean(Lm) if np.isfinite(Lm).any() else 0.5
    Lm = np.where(np.isfinite(Lm), Lm, fill)

    e1 = sobel(Lm)                                # 细节尺度
    small = np.asarray(Image.fromarray(
        np.clip(Lm * 255, 0, 255).astype(np.uint8), "L"
    ).resize((max(2, w // 3), max(2, h // 3)), Image.LANCZOS), np.float32) / 255.0
    e2 = np.asarray(Image.fromarray(
        np.clip(sobel(small) * 255 * 3, 0, 255).astype(np.uint8), "L"
    ).resize((w, h), Image.LANCZOS), np.float32) / 255.0
    E = np.maximum(_norm(e1), _norm(e2) * 0.95)

    # --- 2) 剪影外廓 --------------------------------------------------
    a_soft = np.asarray(Image.fromarray(
        (alpha * 255).astype(np.uint8), "L").filter(
            ImageFilter.GaussianBlur(1.2)), np.float32) / 255.0
    a_small = np.asarray(Image.fromarray(
        ((alpha > 0.5).astype(np.float32) * 255).astype(np.uint8), "L").resize(
        (max(2, w // 4), max(2, h // 4)), Image.LANCZOS), np.float32) / 255.0
    a_small = np.asarray(Image.fromarray(
        (a_small * 255).astype(np.uint8), "L").resize((w, h), Image.LANCZOS),
        np.float32) / 255.0
    Es = np.maximum(_norm(sobel(a_soft)), _norm(sobel(a_small)) * 0.95)

    # --- 3) 阈值 + 羽化 -------------------------------------------------
    E = _blur(E, 0.8)
    Es = _blur(Es, 0.7)
    ink_s = _ink(E, t_struct, 0.22)
    ink_o = _ink(Es, t_sil, 0.26)
    # 结构线只画在有内容的地方；剪影线必须画到 alpha 边界上，
    # 那是模型判断"物件到哪为止"的唯一依据（也就是碰撞轮廓）。
    ink = np.maximum(ink_s * (alpha > 0.02), ink_o)

    # --- 4) 淡彩灰阶 ----------------------------------------------------
    opaque = alpha > 0.5
    if opaque.any():
        lo = float(np.percentile(Lm[opaque], 3))
        hi = float(np.percentile(Lm[opaque], 97))
    else:
        lo, hi = 0.0, 1.0
    if hi - lo < 1e-3:
        hi = lo + 1e-3
    t = np.clip((Lm - lo) / (hi - lo), 0, 1)
    wash = wash_hi - (wash_hi - wash_lo) * t          # 深 -> 浅灰

    # --- 5) 合成 --------------------------------------------------------
    paper = np.array(PAPER, np.float32)
    bg = np.empty((h, w, 3), np.float32)
    bg[..., 0] = np.where(opaque, wash, paper[0])
    bg[..., 1] = np.where(opaque, wash, paper[1])
    bg[..., 2] = np.where(opaque, wash, paper[2])
    rgb = bg
    k = ink[..., None]
    rgb = rgb * (1 - k) + np.array(INK, np.float32) * k

    out = Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8), "RGB")
    info = {"ink_cover": round(float((ink > 0.25).mean()), 4),
            "struct_cover": round(float((ink_s > 0.25).mean()), 4),
            "sil_cover": round(float((ink_o > 0.25).mean()), 4),
            "opaque_px": int(opaque.sum())}
    return out, info


def prepare_for_model(lineart, size=1024, pad=PAPER):
    """白描底稿 -> 模型的输入（居中补边，不拉伸）。同时返回裁回原图的框。"""
    im = lineart.convert("RGB")
    tw, th = size, size
    scale = min(tw / im.width, th / im.height)
    nw, nh = max(1, round(im.width * scale)), max(1, round(im.height * scale))
    rs = im.resize((nw, nh), Image.LANCZOS)
    canvas = Image.new("RGB", (tw, th), pad)
    x0, y0 = (tw - nw) // 2, (th - nh) // 2
    canvas.paste(rs, (x0, y0))
    return canvas, (x0, y0, nw, nh)
