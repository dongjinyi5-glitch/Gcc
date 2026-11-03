# -*- coding: utf-8 -*-
"""疑问 / 答复的单元格内富文本。

用户要的格式是：**同一个方格内，上面是他写的疑问（黑字），下面是我用红字写的答复**，
并作为备查记录留着。这不是"加一列答复"能做的 —— 必须用单元格富文本（CellRichText）。

两条硬约束：

1. **分隔符要能被纯文本读回。** read_only 模式读富文本只会给拼接后的字符串，
   拿不到颜色，所以答复块固定以 `\\n答复：` 开头；重建时按这个标记切，
   前面的就是用户原话，后面的就是我上次的答复。
2. **答复的正文以 `art/qa_answers.json` 为准，不以表格为准。** 表格只是渲染结果，
   JSON 才是可以版本管理的源。万一表格里还有答复而 JSON 里没有（比如上一轮手工改的），
   读回时补进 JSON，不让它丢。

颜色用 C00000（深红），不是纯红 FF0000 —— 纯红在浅底上刺眼，深红仍然一眼是红，
打印和截图都清楚。
"""
import io
import json
import os

from openpyxl.cell.rich_text import CellRichText, TextBlock
from openpyxl.cell.text import InlineFont

INK = "FF1C1A17"      # 疑问：正文墨色
RED = "FFC00000"      # 答复：深红
MARK = "\n答复："

SLOTS = 5             # 每个构件给 5 个疑问栏


def _font(color):
    return InlineFont(rFont="微软雅黑", sz=9, color=color)


F_Q = _font(INK)
F_A = _font(RED)


def make(question, answer):
    """疑问 + 答复 -> 一个单元格的值。没有答复时退化成普通字符串。"""
    q = (question or "").strip()
    a = (answer or "").strip()
    if not q and not a:
        return None
    if not a:
        return q
    if not q:
        # 只有答复没有疑问（极少见）：仍然用红字，方便一眼看出是答复
        return CellRichText([TextBlock(F_A, "答复：" + a)])
    return CellRichText([TextBlock(F_Q, q), TextBlock(F_A, MARK + a)])


def split(value):
    """单元格值 -> (疑问, 答复)。纯文本、CellRichText 都能处理。"""
    if value is None:
        return "", ""
    if isinstance(value, CellRichText):
        s = "".join(str(b) for b in value)
    else:
        s = str(value)
    i = s.find(MARK)
    if i < 0:
        return s.strip(), ""
    return s[:i].strip(), s[i + len(MARK):].strip()


def load(path):
    if os.path.exists(path):
        try:
            return json.load(io.open(path, encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(data, io.open(path, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)


def key(name, size, levels, slot):
    """稳定键。

    为什么带 levels：`ArmFront 54×126` 在「暴徒镇港口」和「屋顶」各有一张，
    只按 名称+尺寸 建键会把两行并成一行，用户给其中一张写「确认OK」，
    重建后两张都变成确认 —— 静默串行，比报错难查得多。
    关卡集合是静态的（来自 scene_inventory），加进去不影响稳定性。
    """
    return "%s|%s|%s|%d" % (name, size, levels, slot)
