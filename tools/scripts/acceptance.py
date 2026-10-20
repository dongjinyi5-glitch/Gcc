"""Run the 重彩 acceptance gate on a rendered character pair.

Usage:
    python acceptance.py [CharacterName]

Reads   validation/composite_original.png
        validation/composite_restyled.png
Writes  validation/STYLE_ACCEPTANCE.json
        validation/STYLE_ACCEPTANCE.md

Exit code is non-zero when any gate fails, so this can sit in a build pipeline.
"""
import io
import json
import os
import sys

import style_metrics as M

PROJECT = r"D:\AI\DAIGuns, Gore and Cannoli from WB"
VAL = os.path.join(PROJECT, "validation")


def main():
    char = sys.argv[1] if len(sys.argv) > 1 else "Vinnie"
    a_path = os.path.join(VAL, "composite_original.png")
    b_path = os.path.join(VAL, "composite_restyled.png")
    if not (os.path.isfile(a_path) and os.path.isfile(b_path)):
        raise SystemExit("composite images missing -- run render_compare.py first")

    before = M.measure(a_path)
    after = M.measure(b_path)
    fid = M.compare(a_path, b_path)
    rows = M.check(after, fid)
    triad = M.triad_ratio(after)
    failed = [r for r in rows if not r["pass"]]

    report = {
        "character": char,
        "baseline_original": before,
        "restyled": after,
        "fidelity": fid,
        "checks": rows,
        "triad_measured": triad,
        "triad_design": M.TRIAD,
        "passed": len(rows) - len(failed),
        "total": len(rows),
        "gate": "PASS" if not failed else "FAIL",
    }
    with io.open(os.path.join(VAL, "STYLE_ACCEPTANCE.json"), "w",
                 encoding="utf-8") as fh:
        json.dump(report, fh, indent=1, ensure_ascii=False)

    lines = [
        f"# 重彩风格验收报告 — {char}",
        "",
        f"**结论：{report['gate']}**  "
        f"（{report['passed']}/{report['total']} 项通过）",
        "",
        "度量对象：`validation/composite_restyled.png`（全部部件按引擎层级合成，原生分辨率）",
        "",
        "## 1. 风格指标",
        "",
        "| 指标 | 原始卡通 | 重彩版 | 验收区间 | 结果 |",
        "|---|---|---|---|---|",
    ]
    labels = {
        "ink_w_mean": "墨线平均宽度 (px)",
        "ink_w_p90": "墨线 90 分位宽度 (px)",
        "ink_cv": "线宽变异系数",
        "ink_ratio": "墨色覆盖率",
        "paper_ratio": "留白率",
        "ink_levels": "墨阶数",
        "texture_std": "肌理强度",
        "saturation": "彩色区饱和度",
    }
    for r in rows:
        if not r["name"].startswith("pig_") and not r["name"].startswith("fid_"):
            lines.append(
                f"| {labels.get(r['name'], r['name'])} | {before.get(r['name'])} | "
                f"{r['value']} | {r['min']}–{r['max']} | "
                f"{'✅' if r['pass'] else '❌'} |")

    lines += ["", "## 2. 颜料配比", "",
              "| 颜料 | 原始 | 重彩版 | 验收区间 | 结果 |", "|---|---|---|---|---|"]
    for r in rows:
        if r["name"].startswith("pig_"):
            pig = r["name"][4:]
            lines.append(
                f"| {pig} | {before['pigment'].get(pig)} | {r['value']} | "
                f"{r['min']}–{r['max']} | {'✅' if r['pass'] else '❌'} |")

    lines += ["", "## 3. 三色配比（主色 : 辅色 : 点缀）", "",
              "| 颜料 | 设计意图 | 实测 |", "|---|---|---|"]
    for k in M.TRIAD:
        lines.append(f"| {k} | {M.TRIAD[k]:.0%} | {triad.get(k, 0):.1%} |")

    lines += ["", "## 4. 几何保真（必须全部通过）", "",
              "| 项 | 值 | 区间 | 结果 |", "|---|---|---|---|"]
    for r in rows:
        if r["name"].startswith("fid_"):
            lines.append(f"| {r['name'][4:]} | {r['value']} | "
                         f"{r['min']}–{r['max']} | {'✅' if r['pass'] else '❌'} |")

    if failed:
        lines += ["", "## 未通过项", ""]
        for r in failed:
            lines.append(f"- `{r['name']}` = {r['value']}，要求 "
                         f"{r['min']}–{r['max']}")

    with io.open(os.path.join(VAL, "STYLE_ACCEPTANCE.md"), "w",
                 encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")

    print(f"{report['gate']}: {report['passed']}/{report['total']}")
    for r in failed:
        print(f"  FAIL {r['name']} = {r['value']} (need {r['min']}-{r['max']})")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
