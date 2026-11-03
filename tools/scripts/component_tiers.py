# -*- coding: utf-8 -*-
"""替换层级 T1–T4。

表格原来的毛病不是"数据错"，是**只展示了兜底层**：1450 行全部 current=R1，而 R1 是
restyle（保剪影、只换色）。于是整张表看上去就是"给原图换个颜色"——用户一眼就看出来
这和"用中国远征军的 12 个场景替换"不是一件事。

分层的唯一目的，就是把「换内容」和「只换色」在表上分开：

    T1 换内容   每关绘制面积前 14 张，去重 —— 决定"这是哪儿"的地标
    T2 材质     铺满画面的材质（fill ≥ 0.6），不换构图，换颜料
    T3 道具     离散物件（fill < 0.6），换具体形制
    T4 只调色   极小件，调色阶即可

阈值不是拍的：fill 的中位数是 0.707，0.6 正好切在"铺满/离散"的谷底；
面积 20k px 以下（约 140×140）的物件在 1360×768 画面上不到 2%，单独重绘没有收益。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from component_taxonomy import classify  # noqa: E402

TOP_PER_LEVEL = 14      # 与 SCENE_PLAN 的 T1 定义一致
FILL_MAT = 0.6          # ≥ 视为铺满材质
TINY_PX = 20000         # < 视为极小件

TIER_LABEL = {
    "T1": "T1 换内容",
    "T2": "T2 材质重画",
    "T3": "T3 道具替换",
    "T4": "T4 只调色",
}
TIER_NOTE = {
    "T1": "要改成历史场景里的东西，形状可以变（这层几乎没有碰撞）",
    "T2": "铺满画面，不换构图，换颜料与笔触",
    "T3": "离散物件，换具体形制与年代",
    "T4": "极小件，调色阶即可",
}


def assign(inv):
    """返回 {(file,path_id): tier}，只对背景层分层；角色/武器/UI 不参与。"""
    bg = [r for r in inv if classify(r["texture"])[1] == "背景"]
    levels = sorted({l for r in bg for l in r["levels"]})

    t1 = set()
    for lv in levels:
        sel = sorted((r for r in bg if lv in r["levels"]), key=lambda r: -r["area"])
        for r in sel[:TOP_PER_LEVEL]:
            t1.add((r["file"], r["path_id"]))

    out = {}
    for r in bg:
        k = (r["file"], r["path_id"])
        if k in t1:
            out[k] = "T1"
        elif r["fill"] >= FILL_MAT:
            out[k] = "T2"
        elif r["area"] < TINY_PX:
            out[k] = "T4"
        else:
            out[k] = "T3"
    return out


def census(inv, tiers):
    """按层统计张数与面积，用来在说明页给一行总账。"""
    rows = []
    tot_n = tot_a = 0
    for t in ("T1", "T2", "T3", "T4"):
        sel = [r for r in inv if tiers.get((r["file"], r["path_id"])) == t]
        a = sum(r["area"] for r in sel)
        rows.append((t, len(sel), a))
        tot_n += len(sel)
        tot_a += a
    return rows, tot_n, tot_a
