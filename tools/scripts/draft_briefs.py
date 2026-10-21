"""为 42 个角色生成"国画重彩替代描述"草稿，预填进清单页。

依据不是拍脑袋，而是三条已经跑通的东西：
  1. `docs/STYLE_SPEC.md` 的 SPEC_FACTION（各阵营颜料区间）
  2. `restyle_ink.py` 的 FACTION_KIND / SLOT_RULES（颜料→部位映射）
  3. `characters_meta.ROSTER` 里的 look / role / weapon 文本（逐角色特征）

草稿写到 `validation/roster_briefs_draft.json`，与用户真实填写
（`validation/roster_briefs.json`）分开存放——这样能 diff 出用户到底改了什么。
"""

import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from characters_meta import ROSTER  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "validation", "roster_briefs_draft.json")

# 阵营 → (主色, 辅色, 点睛色, 墨线, 笔法)
FACTION_STYLE = {
    "玩家": ("石青", "石绿", "朱红", "1.4–1.6px 中锋", "衣纹皴擦、面部只渲染"),
    "人类敌人": ("石青", "石绿", "朱红", "1.4–1.6px 中锋", "衣纹皴擦、面部只渲染"),
    "僵尸": ("花青", "石绿", "朱红", "1.6–1.8px 带飞白", "撕裂衣料与烂肉用皴擦，皮肤薄罩"),
    "鼠怪": ("赭石", "花青", "焦墨", "1.5–1.7px 短促", "顺毛走向短笔，不做皴擦"),
    "Boss": ("石青", "赭石", "朱红", "1.6–2.0px 提按", "重彩积染，暗部焦墨压住"),
}

# 关键词 → 覆盖性描述（优先级从上到下）
KEYWORD_RULES = [
    (("白西装", "全白", "白色西裤", "白衬衫", "白衬衣"),
     "白色衣物按重彩规矩处理：纸白留底、淡墨分染褶缝，不铺白粉，"
     "朱红只点领带与枪口火光。"),
    (("浴袍",), "浴袍用胭脂调朱红薄染三层，湿边自然晕开；腰带石青压一道。"),
    (("衬衫", "酒红", "紫红", "艳粉"), "花色衬衫用胭脂+朱红分染，深色处压胭脂，"
                                        "不铺满、留纸白作高光。"),
    (("防毒面具", "军装", "迷彩"), "军装石绿打底、花青压暗，防毒面具用石绿+焦墨，"
                                  "镜片留纸白反光。"),
    (("护士", "白大褂"), "白衣纸白留底、淡墨勾褶，血渍用朱红点厾，不铺白粉。"),
    (("警", "制服"), "制服石青为主，肩章与纽扣用焦墨点，帽檐压重。"),
    (("水手", "海军"), "水手服石青+纸白，领巾朱红，绳结焦墨。"),
    (("屠夫", "围裙"), "围裙朱红积染、边缘留水痕，围裙下的皮肉赭石渲染。"),
    (("光头", "秃"), "头皮用赭石渲染，高光留纸白，不勾发线。"),
    (("西装", "大衣", "风衣"), "西装石青平涂打底，褶缝石绿压暗，领带朱红。"),
    (("棒球棍", "球棒"), "木器用赭石+焦墨顺纹扫出木纹，金属件留冷灰。"),
    (("铁", "金属", "护甲", "盾"), "金属件以焦墨勾边、石青薄罩出冷光，高光留纸白。"),
    (("鼠", "尾"), "鼠尾按节分段，赭石打底、末端渐淡，焦墨点节。"),
    (("烂", "腐", "伤", "血"), "创口朱红打底、胭脂压暗，边缘用干笔皴出烂肉质感。"),
]

SIZE_HINT = {
    "玩家": "全身一套动作共用同一套配色，跑/跳/射击不得改色相。",
    "人类敌人": "与玩家同阵营配色，但压一档明度，保证同屏可区分。",
    "僵尸": "整体降饱和，只留伤口一处高饱和朱红，形成视觉焦点。",
    "鼠怪": "全身暖赭，靠明度差分层，不加青绿避免串色。",
    "Boss": "明度对比拉到最大，关键部位（头/手/武器）加焦墨重勾。",
}


def pick_extra(look, role, weapon):
    text = " ".join(x for x in (look, role, weapon) if x)
    for keys, desc in KEYWORD_RULES:
        if any(k in text for k in keys):
            return desc
    return ""


def draft_for(e):
    primary, secondary, accent, ink, brush = FACTION_STYLE.get(
        e["faction"], FACTION_STYLE["人类敌人"])
    parts = [
        "【颜料】主色%s、辅色%s压暗部、%s只作点睛（不超过画面 1/10）。" % (
            primary, secondary, accent),
        "【笔法】墨线%s，%s；%s" % (ink, brush, SIZE_HINT.get(e["faction"], "")),
        "【本色】%s。" % (e.get("look") or ""),
    ]
    extra = pick_extra(e.get("look", ""), e.get("role", ""), e.get("weapon", ""))
    if extra:
        parts.append("【要点】%s" % extra)
    return "".join(parts)


def main():
    data = {e["prefab"]: draft_for(e) for e in ROSTER}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with io.open(OUT, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=1, sort_keys=True)
    print("draft:", len(data), "->", os.path.relpath(OUT, ROOT))
    for e in ROSTER[:2]:
        print("\n" + e["prefab"] + ":\n  " + data[e["prefab"]])


if __name__ == "__main__":
    main()
