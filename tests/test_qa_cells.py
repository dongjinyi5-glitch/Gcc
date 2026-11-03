# -*- coding: utf-8 -*-
"""疑问 / 答复 单元格的富文本往返。

这是用户在《背景构件替换总表.xlsx》里提问题、我们写答复的那一格。
格式一旦坏掉，答复就会变成看不见的富文本片段——所以往返必须严格相等。
纯内存操作，不读写任何 xlsx。
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import support  # noqa: E402

support.add_tools_path()
import qa_cells as QC  # noqa: E402


class TestRoundtrip(unittest.TestCase):
    def test_question_and_answer_survive(self):
        q = "为什么这张要重画？"
        a = "因为线条断了，且袖口颜色不对。"
        self.assertEqual(QC.split(QC.make(q, a)), (q, a))

    def test_plain_text_degrades_to_string(self):
        """没有答复时退化成普通字符串——Excel 里才好编辑。"""
        v = QC.make("只有疑问", "")
        self.assertIsInstance(v, str)
        self.assertEqual(QC.split(v), ("只有疑问", ""))

    def test_split_handles_plain_cell(self):
        self.assertEqual(QC.split("纯文本没有标记"), ("纯文本没有标记", ""))

    def test_answer_marker_is_present(self):
        """答复必须带可识别的前缀，否则下次读取分不清哪段是答复。"""
        v = QC.make("问", "答")
        self.assertNotIsInstance(v, str)
        self.assertEqual(QC.split(v)[1], "答")


class TestKey(unittest.TestCase):
    def test_key_is_stable(self):
        a = QC.key("Hat", "132x89", ["level4"], 1)
        b = QC.key("Hat", "132x89", ["level4"], 1)
        self.assertEqual(a, b)

    def test_key_distinguishes_slots(self):
        a = QC.key("Hat", "132x89", ["level4"], 1)
        b = QC.key("Hat", "132x89", ["level4"], 2)
        self.assertNotEqual(a, b)

    def test_key_contains_all_parts(self):
        k = QC.key("Hat", "132x89", ["level4"], 3)
        for part in ("Hat", "132x89", "level4", "3"):
            self.assertIn(part, k)


class TestConstants(unittest.TestCase):
    def test_slot_count(self):
        self.assertEqual(QC.SLOTS, 5, "每个构件给 5 个疑问栏，改这个数会影响既有表格")

    def test_colours_are_argb_hex(self):
        for c in (QC.INK, QC.RED):
            self.assertRegex(c, r"^[0-9A-Fa-f]{8}$")


if __name__ == "__main__":
    unittest.main()
