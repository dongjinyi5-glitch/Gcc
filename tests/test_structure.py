# -*- coding: utf-8 -*-
"""目录结构完整性。

全部脚本同处 tools/scripts/，彼此靠 bare import（`from ggc_assets import …`）相连。
这种布局的脆弱点是"某个 import 指向了不存在的文件"——IDE 不报错、运行才炸。
本测试用静态 AST 分析把这件事守住，不执行任何业务脚本。

安全边界：只读 .py 文本 + 解析 AST，不 import 被测脚本，不写文件。
"""
import ast
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import support  # noqa: E402

# 已实测"导入即静默"的模块（不加载游戏资源、不写文件、不联网）。
# scene_survey / transplant_check 故意不在列：它们在 import 阶段就会读 1.3GB resources.assets。
SILENT_MODULES = (
    "characters_meta", "factions", "theme_cbi", "component_taxonomy",
    "component_tiers", "redraw_targets", "historical_map", "l3_brief_data",
    "lineart", "qa_cells",
)

# 本轮整理**不执行**物理搬迁，因此这些分类目录不应存在
FORBIDDEN_DIRS = ("assets", "characters", "scenes", "rendering", "qa", "docs")


class TestLayout(unittest.TestCase):
    def test_scripts_dir_exists(self):
        self.assertTrue(os.path.isdir(support.SCRIPTS), "缺少 tools/scripts/")

    def test_py_count(self):
        """91 个 .py 一个不少。"""
        self.assertEqual(len(support.script_paths()), 91,
                         "tools/scripts/ 下 .py 数量变了（原为 91）")

    def test_ps1_count(self):
        self.assertEqual(len(support.ps1_paths()), 2,
                         "tools/scripts/ 下 .ps1 数量变了（原为 2）")

    def test_no_category_subdirs(self):
        """分类目前只是文档（见 tools/README.md），不应存在物理分类目录。"""
        found = [d for d in FORBIDDEN_DIRS
                 if os.path.isdir(os.path.join(support.TOOLS, d))]
        self.assertEqual(found, [], "出现了物理分类目录（本轮约定不搬迁）: %s" % found)

    def test_no_shim_residue(self):
        """不应存在 runpy 兼容垫片（垫片属于搬迁方案的一部分，本轮未做）。"""
        bad = [os.path.basename(p) for p in support.script_paths()
               if "run_path(" in support.read(p)]
        self.assertEqual(bad, [], "检测到 runpy 垫片残留: %s" % bad)

    def test_no_bootstrap_residue(self):
        """不应存在为搬迁注入的 sys.path bootstrap 块。"""
        bad = [os.path.basename(p) for p in support.script_paths()
               if "path bootstrap: tools/* on sys.path" in support.read(p)]
        self.assertEqual(bad, [], "检测到 bootstrap 注入残留: %s" % bad)


class TestImports(unittest.TestCase):
    def test_local_imports_resolve(self):
        """每个指向本地模块的 import，都必须在 tools/scripts/ 下存在同名 .py。"""
        names = support.module_names()
        broken = []
        for p in support.script_paths():
            tree = ast.parse(support.read(p))
            wanted = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    wanted.update(a.name.split(".")[0] for a in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                    wanted.add(node.module.split(".")[0])
            for name in wanted:
                if name in names:
                    continue          # 本地模块，已在 names 中
                # 名字看起来是本地模块（有同名文件被删）或标准库/第三方，分别处理
                if name in support.THIRD_PARTY:
                    continue
                if name in sys.stdlib_module_names:
                    continue
                broken.append((os.path.basename(p), name))
        self.assertEqual(broken, [], "这些 import 既不是本地模块也不是已声明依赖: %s" % broken)

    def test_no_stdlib_shadowing(self):
        """脚本名与标准库重名会导致 import 被遮蔽。"""
        clash = support.module_names() & set(sys.stdlib_module_names)
        self.assertEqual(clash, set(), "脚本名与标准库重名: %s" % sorted(clash))

    def test_third_party_declared(self):
        """requirements.txt 必须覆盖脚本用到的第三方包。"""
        req = os.path.join(support.PROJ, "requirements.txt")
        self.assertTrue(os.path.isfile(req), "缺少 requirements.txt")
        declared = set()
        for line in support.read(req).splitlines():
            line = line.split("#")[0].strip()
            if not line:
                continue
            name = line.split("==")[0].split(">=")[0].split("<")[0].strip().lower()
            declared.add(name)
        # import 名 -> requirements 里的包名
        req_name = {"PIL": "pillow", "numpy": "numpy",
                    "UnityPy": "unitypy", "openpyxl": "openpyxl"}
        for pkg in sorted(support.THIRD_PARTY):
            self.assertIn(req_name.get(pkg, pkg.lower()), declared,
                          "requirements.txt 未声明 %s（脚本 import 名 %s）" % (pkg, pkg))


class TestSilentModules(unittest.TestCase):
    def test_silent_modules_exist(self):
        missing = [m for m in SILENT_MODULES
                   if not os.path.isfile(os.path.join(support.SCRIPTS, m + ".py"))]
        self.assertEqual(missing, [], "静默模块缺失: %s" % missing)

    def test_silent_modules_have_no_main_guard_side_effect(self):
        """被测试导入的模块不得在模块级调用 open/write/urlopen 等。"""
        risky = {"open", "write", "makedirs", "mkdir", "remove", "unlink", "rmtree",
                 "system", "Popen", "urlopen", "save", "copy", "move", "rename",
                 "truncate", "connect"}
        bad = []
        for m in SILENT_MODULES:
            p = os.path.join(support.SCRIPTS, m + ".py")
            tree = ast.parse(support.read(p))
            hits = []
            for node in tree.body:
                if isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.If,
                                     ast.Import, ast.ImportFrom)):
                    continue
                for sub in ast.walk(node):
                    if isinstance(sub, ast.Call):
                        fn = getattr(sub.func, "id", None) or getattr(sub.func, "attr", None)
                        if fn in risky:
                            hits.append(fn)
            if hits:
                bad.append((m, sorted(set(hits))))
        self.assertEqual(bad, [], "这些模块在导入阶段就有副作用风险: %s" % bad)


class TestNoSecretsInTests(unittest.TestCase):
    """测试代码不得引用密钥目录或密钥文件名。

    注意：敏感词按片段拼接，避免测试自身命中自己（上一版就是栽在这里）。
    """

    @staticmethod
    def _tokens():
        secret_dir = "." + "sec" + "rets"
        names = ["dash" + "scope", "model" + "scope", "goo" + "gle",
                 "gi" + "tee", "silicon" + "flow", "aliyun_" + "ak"]
        return [secret_dir] + [n + ".txt" for n in names]

    def test_tests_do_not_reference_secrets(self):
        here = os.path.dirname(os.path.abspath(__file__))
        tokens = self._tokens()
        bad = []
        for f in sorted(os.listdir(here)):
            if not f.endswith(".py"):
                continue
            src = support.read(os.path.join(here, f))
            for token in tokens:
                if token in src:
                    bad.append((f, token))
        self.assertEqual(bad, [], "测试代码里出现了密钥路径引用: %s" % bad)


if __name__ == "__main__":
    unittest.main()
