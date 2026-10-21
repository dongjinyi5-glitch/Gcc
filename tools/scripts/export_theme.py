"""Export the CBI re-theme execution spec in three formats.

    python export_theme.py

Writes
    validation/THEME_CBI_SPEC.md            human-readable spec (grouped by role)
    validation/theme_cbi.json               machine copy (role + brief per prefab)
    art/角色替代描述_通用方案.csv            one row per character, Excel-friendly

The CSV deliberately mirrors the layout of the blank form the user filled in,
so the two files can be diffed row by row: 预制体 / 中文名 / 英文名 / 阵营 /
兵种 / 替代描述.

Why a separate file rather than overwriting roster_briefs.json
-------------------------------------------------------------
roster_briefs.json is what the USER wrote. It must stay untouched as evidence of
intent, including the parts we cannot act on. The compliant rewrite lives here,
and the diff between the two is exactly the list of things that were changed and
why -- which is what a reviewer needs to see.
"""
import csv
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import theme_cbi as T
from characters_meta import ROSTER

PROJECT = r"D:\AI\DAIGuns, Gore and Cannoli from WB"
VAL = os.path.join(PROJECT, "validation")
ART = os.path.join(PROJECT, "art")
LOCS = os.path.join(PROJECT, "extracted", "characters", "asset_locations.json")


def load_locations():
    """parts / textures counts live in the asset scan, not in characters_meta."""
    if not os.path.isfile(LOCS):
        return {}
    with io.open(LOCS, encoding="utf-8") as fh:
        raw = json.load(fh)
    return {k: {"parts": len(v.get("parts") or []),
                "textures": len(v.get("textures") or [])}
            for k, v in raw.items()}

ROLE_ORDER = [T.EXPEDITIONARY, T.IJA_GENERAL, T.IJA_OFFICER, T.IJA_SOLDIER,
              T.IJA_NAVY, T.IJA_MEDIC, T.CIVILIAN_WORK, T.CIVILIAN_LIGHT, T.RAT]

ROLE_NOTE = {
    T.EXPEDITIONARY: "石绿为主、赭石压黄调（HBT 橄榄绿）；唯一允许青绿积染的一档",
    T.IJA_GENERAL: "赭石打底、藤黄提金线（呢料将官服），朱红只做领章",
    T.IJA_OFFICER: "同是国防色但压暗一档，辅色用墨而非藤黄",
    T.IJA_SOLDIER: "国防色偏绿（洗晒发青），辅色走石绿；铁帽压到墨带石绿",
    T.IJA_NAVY: "花青与纸对分（水兵白 + 藏青），全场唯一高明度冷色块",
    T.IJA_MEDIC: "纸为主、花青压褶缝（白色军医外套），朱红只点阶级章与血迹",
    T.CIVILIAN_WORK: "花青为主、赭石压土色（作务衣 / 工装粗布）",
    T.CIVILIAN_LIGHT: "纸为底、花青压深色制服与阴影（女学生 / 割烹着 / 白围裙）",
    T.RAT: "按用户要求保持原状，引擎遇到该兵种直接原样返回",
}

LOCS_BY_PREFAB = {}

HEADER = """# 通用历史身份方案 · 执行稿

> 本文件是 **可执行的美术规格**，不是意向书。每条描述都能直接翻成
> `restyle_ink.py` 的颜料表与笔触参数。

## 0. 与原始填写稿的差异（必读）

用户原始填写稿（`validation/roster_briefs.json`）里，有 21 条指向二战日军的
**真实个人**（多为甲级战犯），1 条指向**在任日本首相**，Vinnie 一条要求使用
本国抗日英烈的相貌。这些指向一律未采用：

- 本作含断肢、爆头、肢解等极端血腥表现，把真实人物（尤其战犯与在任外国
  政府首脑）做成被反复击杀的角色，属政治敏感内容，同时构成侮辱诽谤；
- 抗日英烈另受《英雄烈士保护法》保护，不得用于此类形象。

**保留的是**：年代、兵种、装备、服饰考据、配色意图、动作与体型。
**替换的是**：「谁的脸」→「哪类人」。全部面部为虚构设计。

原始稿保持原样存档，未做任何修改——它是用户意图的证据。

## 1. 兵种分层与配色

| 兵种 | 角色数 | 颜料策略 |
|---|---:|---|
"""


def main():
    os.makedirs(VAL, exist_ok=True)
    os.makedirs(ART, exist_ok=True)
    global LOCS_BY_PREFAB
    LOCS_BY_PREFAB = load_locations()

    by_role = {}
    for e in ROSTER:
        by_role.setdefault(T.role_of(e["prefab"]), []).append(e)

    lines = [HEADER.rstrip()]
    for role in ROLE_ORDER:
        rows = by_role.get(role, [])
        lines.append(f"| {role} | {len(rows)} | {ROLE_NOTE[role]} |")

    lines += [
        "",
        "两层正交：**faction**（人类 / 僵尸 / 鼠怪）决定「这是不是活人肉体」，"
        "**role** 决定「穿什么、什么颜色」。所以日军士兵丧尸和日军士兵本人"
        "共用同一套军服配色，但皮肤一个走活人肉色、一个走尸斑灰。",
        "",
        "---",
        "",
        "## 2. 逐角色执行稿",
        "",
    ]

    for role in ROLE_ORDER:
        rows = by_role.get(role, [])
        if not rows:
            continue
        lines += [f"### {role}（{len(rows)}）", ""]
        for e in rows:
            brief = T.BRIEF[e["prefab"]].replace("\n", "\n> ")
            loc = LOCS_BY_PREFAB.get(e["prefab"], {})
            stat = (f"　部件 {loc['parts']}　贴图 {loc['textures']}"
                    if loc else "")
            lines += [
                f"**`{e['prefab']}` · {e['cn']}**  ",
                f"英文名：{e['en']}{stat}",
                "",
                f"> {brief}",
                "",
            ]

    lines += [
        "---",
        "",
        "## 3. 不出现的元素",
        "",
        "- 旭日旗、军国主义标语、天皇肖像等符号",
        "- 任何真实人物的相貌（历史人物、在任政治人物、抗日英烈）",
        "- 对军服的美化处理：按年代考据画，不追加荣誉性修饰",
        "",
        "## 4. 引擎落地方式",
        "",
        "```python",
        "# theme_cbi.py",
        "ROLE_OF[prefab]        -> 兵种",
        "ROLE_KIND[role][kind]  -> (primary, secondary, allowed)",
        "#",
        "# restyle_ink.py",
        "restyle(img, slot, faction=..., role=...)",
        "```",
        "",
        "`鼠怪` 四体在 `UNCHANGED` 集合中，`restyle()` 首行直接返回原图副本，",
        "不经过任何像素处理——「不变」必须是可执行的，不能靠批处理脚本记得。",
        "",
    ]

    with io.open(os.path.join(VAL, "THEME_CBI_SPEC.md"), "w",
                 encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")

    payload = {}
    for e in ROSTER:
        p = e["prefab"]
        payload[p] = {
            "cn": e["cn"], "en": e["en"], "faction": e["faction"],
            "role": T.role_of(p), "brief": T.BRIEF[p],
            "unchanged": T.role_of(p) in T.UNCHANGED,
        }
    with io.open(os.path.join(VAL, "theme_cbi.json"), "w",
                 encoding="utf-8") as fh:
        json.dump(payload, fh, indent=1, ensure_ascii=False)

    # Excel-friendly: UTF-8 BOM so double-clicking does not open as GBK mojibake
    csv_path = os.path.join(ART, "角色替代描述_通用方案.csv")
    with io.open(csv_path, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh, lineterminator="\r\n")
        w.writerow(["预制体", "中文名", "英文名", "阵营", "兵种", "替代描述（通用方案）"])
        for role in ROLE_ORDER:
            for e in by_role.get(role, []):
                w.writerow([e["prefab"], e["cn"], e["en"], e["faction"],
                            role, T.BRIEF[e["prefab"]].replace("\n", " ")])

    print(f"wrote {os.path.join(VAL, 'THEME_CBI_SPEC.md')}")
    print(f"wrote {os.path.join(VAL, 'theme_cbi.json')}")
    print(f"wrote {csv_path}  ({len(ROSTER)} rows)")
    for role in ROLE_ORDER:
        print(f"  {role:12s} {len(by_role.get(role, [])):2d}")


if __name__ == "__main__":
    main()
