"""Run the 重彩 acceptance gate on a rendered character pair.

Usage:
    python acceptance.py [CharacterName] [--faction 人类|僵尸|鼠怪]

Reads   validation/composite_<Char>_original.png
        validation/composite_<Char>_restyled.png
Writes  validation/STYLE_ACCEPTANCE_<Char>.json
        validation/STYLE_ACCEPTANCE_<Char>.md

The faction decides which palette the character is judged against -- see
style_metrics.SPEC_FACTION. The brush metrics are shared by all factions on
purpose: "重彩, 中等笔触" is a project-wide decision, so a zombie and a gangster
must be painted with the same tool.

Exit code is non-zero when any gate fails, so this can sit in a build pipeline.
"""
import io
import json
import os
import sys

import factions
import style_metrics as M

PROJECT = r"D:\AI\DAIGuns, Gore and Cannoli from WB"
VAL = os.path.join(PROJECT, "validation")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    char = args[0] if args else "Vinnie"
    faction = None
    if "--faction" in sys.argv:
        faction = sys.argv[sys.argv.index("--faction") + 1]
    if faction is None:
        faction = factions.faction_of(char)
    if faction not in M.SPEC_FACTION:
        raise SystemExit(f"unknown faction {faction!r}; "
                         f"expected one of {list(M.SPEC_FACTION)}")

    a_path = os.path.join(VAL, f"composite_{char}_original.png")
    b_path = os.path.join(VAL, f"composite_{char}_restyled.png")
    if not (os.path.isfile(a_path) and os.path.isfile(b_path)):
        raise SystemExit(f"composites for {char} missing -- "
                         f"run render_compare.py {char} first")

    before = M.measure(a_path)
    after = M.measure(b_path)
    fid = M.compare(a_path, b_path)
    rows = M.check(after, fid, faction=faction)
    triad = M.triad_ratio(after, faction=faction)
    design = M.SPEC_FACTION[faction]["triad"]
    failed = [r for r in rows if not r["pass"]]

    report = {
        "character": char,
        "faction": faction,
        "baseline_original": before,
        "restyled": after,
        "fidelity": fid,
        "checks": rows,
        "triad_measured": triad,
        "triad_design": design,
        "passed": len(rows) - len(failed),
        "total": len(rows),
        "gate": "PASS" if not failed else "FAIL",
    }
    # One report per character. A single shared filename meant the third
    # faction silently overwrote the first two, so the three-faction evidence
    # never existed at the same time.
    stem = f"STYLE_ACCEPTANCE_{char}"
    with io.open(os.path.join(VAL, stem + ".json"), "w",
                 encoding="utf-8") as fh:
        json.dump(report, fh, indent=1, ensure_ascii=False)

    lines = [
        f"# 重彩风格验收报告 — {char}（{faction}）",
        "",
        f"**结论：{report['gate']}**  "
        f"（{report['passed']}/{report['total']} 项通过）",
        "",
        f"度量对象：`validation/composite_{char}_restyled.png`"
        "（全部部件按引擎层级合成，原生分辨率）",
        f"判定基准：`SPEC_COMMON`（统一笔触）+ `SPEC_FACTION[{faction}]`（阵营颜料）",
        "",
        "## 1. 风格指标（三阵营共用）",
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

    lines += ["", "## 2. 颜料配比（按阵营）", "",
              "| 颜料 | 原始 | 重彩版 | 验收区间 | 结果 |", "|---|---|---|---|---|"]
    for r in rows:
        if r["name"].startswith("pig_"):
            pig = r["name"][4:]
            lines.append(
                f"| {pig} | {before['pigment'].get(pig)} | {r['value']} | "
                f"{r['min']}–{r['max']} | {'✅' if r['pass'] else '❌'} |")

    lines += ["", f"## 3. 三色配比（{faction}）", "",
              "| 颜料 | 设计意图 | 实测 |", "|---|---|---|"]
    for k in design:
        lines.append(f"| {k} | {design[k]:.0%} | {triad.get(k, 0):.1%} |")

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

    with io.open(os.path.join(VAL, stem + ".md"), "w",
                 encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")

    print(f"[{char} / {faction}] {report['gate']}: "
          f"{report['passed']}/{report['total']}")
    for r in failed:
        print(f"  FAIL {r['name']} = {r['value']} (need {r['min']}-{r['max']})")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
