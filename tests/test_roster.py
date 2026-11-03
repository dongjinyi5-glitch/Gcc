# -*- coding: utf-8 -*-
"""角色身份表：42 个战斗单位。

ROSTER 是唯一身份表，42 这个数字是被实测校正过的（手写名单漏了 9 个挂
Unit / UnitSpike 脚本的单位）。这里守住"不退回 33、不出现重复 prefab"。
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import support  # noqa: E402

support.add_tools_path()
import characters_meta as CM  # noqa: E402

FACTIONS = {"玩家", "人类敌人", "僵尸", "鼠怪", "Boss"}
FIELDS = ("prefab", "faction", "cn", "en", "role", "look")


class TestRoster(unittest.TestCase):
    def test_unit_count_is_42(self):
        self.assertEqual(len(CM.ROSTER), 42)

    def test_prefab_names_are_unique(self):
        names = [r["prefab"] for r in CM.ROSTER]
        self.assertEqual(len(names), len(set(names)), "存在重复 prefab")

    def test_required_fields_present(self):
        for r in CM.ROSTER:
            for f in FIELDS:
                self.assertIn(f, r, "%s 缺少字段 %s" % (r.get("prefab"), f))
                self.assertTrue(str(r[f]).strip(), "%s 的 %s 为空" % (r["prefab"], f))

    def test_faction_values_are_known(self):
        bad = [r["prefab"] for r in CM.ROSTER if r["faction"] not in FACTIONS]
        self.assertEqual(bad, [], "未知阵营: %s" % bad)

    def test_doc_unmatched_is_documented(self):
        """附件里 17 条原型有 1 条全库无对应 Unit，必须留下原因而不是悄悄丢掉。"""
        self.assertEqual(len(CM.DOC_UNMATCHED), 1)
        self.assertTrue(CM.DOC_UNMATCHED[0].get("reason"))


if __name__ == "__main__":
    unittest.main()
