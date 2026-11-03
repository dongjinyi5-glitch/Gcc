# -*- coding: utf-8 -*-
"""题材改造表：9 个兵种 + 42 条执行稿。

三层关系：faction（肉体）→ role（服装配色）→ brief（逐角色文字）。
这里守住三件事：兵种表与 ROLES 一致、42 个角色都有归属、鼠怪必须"不变"。
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import support  # noqa: E402

support.add_tools_path()
import characters_meta as CM  # noqa: E402
import theme_cbi as T  # noqa: E402


class TestRoles(unittest.TestCase):
    def test_nine_roles(self):
        self.assertEqual(len(T.ROLES), 9)
        self.assertEqual(set(T.ROLES), set(T.ROLE_KIND))

    def test_role_kind_has_pigment_spec(self):
        """每个兵种的每个槽位都必须是 (primary, secondary, allowed) 三元组。"""
        for role, slots in T.ROLE_KIND.items():
            self.assertTrue(slots, "%s 没有任何槽位" % role)
            for slot, spec in slots.items():
                self.assertEqual(len(spec), 3,
                                 "%s/%s 的 (primary, secondary, allowed) 不完整" % (role, slot))
                primary, _secondary, allowed = spec
                self.assertTrue(allowed, "%s/%s 的 allowed 颜料集合为空" % (role, slot))
                if primary is not None:
                    self.assertIn(primary, allowed,
                                  "%s/%s 的主色 %s 不在允许集合内" % (role, slot, primary))

    def test_unchanged_roles_are_declared(self):
        """鼠怪四体必须是"不变"——可执行地声明，而不是靠批处理脚本记得。"""
        self.assertEqual(list(T.UNCHANGED), ["鼠怪"])

    def test_green_layer_roles_subset_of_roles(self):
        self.assertTrue(T.GREEN_LAYER_ROLES <= set(T.ROLES))


class TestBriefs(unittest.TestCase):
    def test_every_unit_has_a_brief(self):
        prefabs = {r["prefab"] for r in CM.ROSTER}
        self.assertEqual(set(T.BRIEF), prefabs, "BRIEF 与 ROSTER 的角色集合不一致")

    def test_every_unit_has_a_role(self):
        prefabs = {r["prefab"] for r in CM.ROSTER}
        self.assertEqual(set(T.ROLE_OF), prefabs, "ROLE_OF 与 ROSTER 的角色集合不一致")

    def test_roles_referenced_by_briefs_exist(self):
        bad = {p: r for p, r in T.ROLE_OF.items() if r not in T.ROLE_KIND}
        self.assertEqual(bad, {}, "引用了不存在的兵种: %s" % bad)

    def test_briefs_are_substantive(self):
        """除了"保持原状"的鼠怪，其余角色的执行稿必须有实质内容。"""
        unchanged = {p for p, r in T.ROLE_OF.items() if r in T.UNCHANGED}
        thin = [p for p, s in T.BRIEF.items()
                if p not in unchanged and len(s.strip()) < 40]
        self.assertEqual(thin, [], "执行稿过短: %s" % thin)

    def test_unchanged_units_say_so(self):
        unchanged = {p for p, r in T.ROLE_OF.items() if r in T.UNCHANGED}
        self.assertEqual(len(unchanged), 4, "鼠怪应为 4 个")
        for p in unchanged:
            self.assertIn("保持原状", T.BRIEF[p], "%s 的稿子没有写明保持原状" % p)


class TestCompliance(unittest.TestCase):
    def test_no_real_person_names_in_briefs(self):
        """合规红线：不得出现真实人物相貌。

        这是一条"宁可误报"的检查——命中即失败，需要人工确认后再改词。
        """
        banned = ("东条英机", "松井石根", "板垣征四郎", "冈村宁次", "朝香宫",
                  "石原莞尔", "辻政信", "高市早苗", "戴安澜")
        hits = []
        for p, s in T.BRIEF.items():
            for name in banned:
                if name in s:
                    hits.append((p, name))
        self.assertEqual(hits, [], "执行稿出现真实人物姓名: %s" % hits)


if __name__ == "__main__":
    unittest.main()
