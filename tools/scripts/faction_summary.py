"""Aggregate the per-character acceptance reports into one three-faction sheet.

Usage:
    python faction_summary.py

Reads   validation/STYLE_ACCEPTANCE_<Char>.json   (one per faction representative)
Writes  validation/STYLE_ACCEPTANCE.md            (three-faction summary)
        art/original-capture/faction_triptych.png (original vs 重彩, 3 factions)

Why a separate step
-------------------
`acceptance.py` judges one character. Running it three times used to overwrite
one shared report file, so the three-faction evidence never co-existed. This
script is the only place that reads all of them at once, and it refuses to
write a summary unless all three factions are represented.
"""
import io
import json
import os
import sys

from PIL import Image, ImageDraw

PROJECT = r"D:\AI\DAIGuns, Gore and Cannoli from WB"
VAL = os.path.join(PROJECT, "validation")
OUT_IMG = os.path.join(PROJECT, "art", "original-capture", "faction_triptych.png")

# One representative per faction -- the pilot character that was restyled and
# gated. Order matters: it is the order used in the summary table.
REPS = [("人类", "Vinnie"), ("僵尸", "ZombieRegular"), ("鼠怪", "ZombieRat")]

PAPER = (243, 235, 220)
INK = (60, 50, 40)


def load():
    reports = []
    missing = []
    for faction, char in REPS:
        p = os.path.join(VAL, f"STYLE_ACCEPTANCE_{char}.json")
        if not os.path.isfile(p):
            missing.append(p)
            continue
        with io.open(p, encoding="utf-8") as fh:
            reports.append(json.load(fh))
    if missing:
        raise SystemExit("missing report(s), run acceptance.py first:\n  "
                         + "\n  ".join(missing))
    return reports


def triptych(reports):
    """Original on top, 重彩 below, one column per faction."""
    cols = []
    for rep in reports:
        char = rep["character"]
        a = Image.open(os.path.join(VAL, f"composite_{char}_original.png")).convert("RGBA")
        b = Image.open(os.path.join(VAL, f"composite_{char}_restyled.png")).convert("RGBA")
        cols.append((rep["faction"], char, a, b))

    pad, top, gap = 24, 52, 28
    colw = [max(a.width, b.width) for _, _, a, b in cols]
    rowh = [max(a.height for _, _, a, _ in cols), max(b.height for _, _, _, b in cols)]
    W = sum(colw) + gap * (len(cols) - 1) + pad * 2
    H = top + rowh[0] + rowh[1] + gap + pad
    canvas = Image.new("RGB", (W, H), PAPER)
    d = ImageDraw.Draw(canvas)

    x = pad
    for i, (faction, char, a, b) in enumerate(cols):
        # centre each sprite in its column so the silhouettes line up
        ax = x + (colw[i] - a.width) // 2
        bx = x + (colw[i] - b.width) // 2
        canvas.paste(a, (ax, top), a)
        canvas.paste(b, (bx, top + rowh[0] + gap), b)
        d.text((x, 14), f"{faction}  {char}", fill=INK)
        d.text((x, 28), "上：原始    下：重彩", fill=INK)
        x += colw[i] + gap

    os.makedirs(os.path.dirname(OUT_IMG), exist_ok=True)
    canvas.save(OUT_IMG)
    return canvas.size


def main():
    reports = load()

    # --- markdown ---------------------------------------------------------
    L = [
        "# 重彩风格验收 — 三阵营汇总",
        "",
        "笔触指标三族共用（`SPEC_COMMON`）：重彩+中等笔触是项目级决定，",
        "僵尸和黑帮必须用同一支笔。颜料配比按阵营分别判定（`SPEC_FACTION`），",
        "因为三族的「衣物」语义完全不同：西服是毛料、烂衫是布、鼠怪是毛。",
        "",
        "## 1. 门禁结果",
        "",
        "| 阵营 | 代表角色 | 结论 | 通过项 |",
        "|---|---|---|---|",
    ]
    for rep in reports:
        L.append(f"| {rep['faction']} | {rep['character']} | "
                 f"**{rep['gate']}** | {rep['passed']}/{rep['total']} |")

    L += ["", "## 2. 共用笔触指标（实测）", "",
          "墨线宽度/线宽变异/墨量/肌理是**共用**区间；饱和度按阵营各自判定",
          "（僵尸是最不鲜艳的一族，这是设定，不是缺陷）。", "",
          "| 指标 | 人类 | 僵尸 | 鼠怪 | 区间 |", "|---|---|---|---|---|"]
    keys = ["ink_w_mean", "ink_w_p90", "ink_cv", "ink_ratio",
            "paper_ratio", "ink_levels", "texture_std", "saturation"]
    labels = {
        "ink_w_mean": "墨线均宽 px", "ink_w_p90": "墨线 P90 px",
        "ink_cv": "线宽 CV", "ink_ratio": "墨覆盖率",
        "paper_ratio": "留白率", "ink_levels": "墨阶数",
        "texture_std": "肌理强度", "saturation": "饱和度",
    }
    for k in keys:
        vals = " | ".join(str(rep["restyled"].get(k)) for rep in reports)
        # Bands are per-faction; printing one faction's band for all three was
        # wrong and hid the fact that 僵尸 is allowed a lower saturation.
        bands = []
        for rep in reports:
            r = next((x for x in rep["checks"] if x["name"] == k), None)
            if r:
                bands.append((rep["faction"], f"{r['min']}–{r['max']}"))
        distinct = {b for _, b in bands}
        if len(distinct) == 1:
            band = distinct.pop()                     # same for all factions
        else:
            band = "；".join(f"{f} {b}" for f, b in bands)
        L.append(f"| {labels.get(k, k)} | {vals} | {band} |")

    L += ["", "## 3. 颜料配比（每族自己的区间）", "",
          "| 阵营 | 颜料 | 原始 | 重彩 | 区间 | 结果 |", "|---|---|---|---|---|---|"]
    for rep in reports:
        for r in rep["checks"]:
            if r["name"].startswith("pig_"):
                pig = r["name"][4:]
                L.append(f"| {rep['faction']} | {pig} | "
                         f"{rep['baseline_original']['pigment'].get(pig)} | "
                         f"{r['value']} | {r['min']}–{r['max']} | "
                         f"{'✅' if r['pass'] else '❌'} |")

    L += ["", "## 4. 三色配比（设计 vs 实测）", "",
          "| 阵营 | 颜料 | 设计 | 实测 |", "|---|---|---|---|"]
    for rep in reports:
        for k, v in rep["triad_design"].items():
            L.append(f"| {rep['faction']} | {k} | {v:.0%} | "
                     f"{rep['triad_measured'].get(k, 0):.1%} |")

    L += ["", "## 5. 几何保真（三族必须全部为 1.000）", "",
          "| 阵营 | alpha_iou | centroid_shift | area_delta |", "|---|---|---|---|"]
    for rep in reports:
        f = rep["fidelity"]
        L.append(f"| {rep['faction']} | {f['alpha_iou']} | "
                 f"{f['centroid_shift']} | {f['area_delta']} |")

    bad = [r for rep in reports for r in rep["checks"] if not r["pass"]]
    L += ["", "## 6. 未通过项", ""]
    L += [f"- {r['name']} = {r['value']}（要求 {r['min']}–{r['max']}）"
          for r in bad] or ["无。三族全部通过。"]

    with io.open(os.path.join(VAL, "STYLE_ACCEPTANCE.md"), "w",
                 encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")

    size = triptych(reports)
    print(f"summary written: {len(reports)} factions, {len(bad)} failing checks")
    print(f"triptych: {OUT_IMG} {size}")
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
