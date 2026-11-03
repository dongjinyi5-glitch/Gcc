# -*- coding: utf-8 -*-
"""场景构件分档：分类器 + 替换层级 T1–T4。

这两个模块决定了"一张贴图算什么、按哪一档处理"，是场景重绘的分派依据。
分类器有一个刻意的设计：**未匹配的名字返回「未分类/背景」而不是报错**，
让它显眼地出现在报表里。
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import support  # noqa: E402

support.add_tools_path()
import component_taxonomy as CT  # noqa: E402
import component_tiers as TR  # noqa: E402


class TestLevelNames(unittest.TestCase):
    def test_level_map_covers_13_scenes(self):
        self.assertEqual(len(CT.LEVEL_CN), 13)

    def test_level_keys_are_level_files(self):
        for k in CT.LEVEL_CN:
            self.assertRegex(k, r"^level\d+$")

    def test_level_names_are_non_empty(self):
        for k, v in CT.LEVEL_CN.items():
            self.assertTrue(v.strip(), "%s 没有中文名" % k)


class TestClassify(unittest.TestCase):
    def test_rules_are_loaded(self):
        self.assertGreaterEqual(len(CT.RULES), 20)

    def test_character_slots_are_recognised(self):
        """Hat / Crotch 这类角色部件必须判成角色层——判错会把它当背景重绘。"""
        for name in ("Hat", "Crotch", "Head"):
            cat, layer = CT.classify(name)
            self.assertEqual(layer, "角色", "%s 被判成了 %s 层" % (name, layer))

    def test_case_insensitive(self):
        self.assertEqual(CT.classify("HAT"), CT.classify("hat"))

    def test_unknown_falls_back_loudly(self):
        """未匹配必须落到「未分类/背景」，不能静默归到某个具体类别。"""
        self.assertEqual(CT.classify("zzz_definitely_not_a_real_texture"), ("未分类", "背景"))


class TestTiers(unittest.TestCase):
    def test_four_tiers(self):
        self.assertEqual(sorted(TR.TIER_LABEL), ["T1", "T2", "T3", "T4"])
        self.assertEqual(sorted(TR.TIER_NOTE), ["T1", "T2", "T3", "T4"])

    def test_labels_are_non_empty(self):
        for k, v in TR.TIER_LABEL.items():
            self.assertTrue(v.strip(), "%s 没有中文标签" % k)

    def test_tier_notes_explain_each_tier(self):
        for k, v in TR.TIER_NOTE.items():
            self.assertGreater(len(v.strip()), 4, "%s 的说明过短" % k)


if __name__ == "__main__":
    unittest.main()
