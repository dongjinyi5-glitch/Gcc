# -*- coding: utf-8 -*-
"""测试公共路径设置。

这些测试只读：
  - 不打开游戏 .assets，不加载大型资源
  - 不调用外部 API，不联网
  - 不读密钥目录（测试代码里不出现任何密钥文件名）
  - 不写任何文件

只导入已确认"导入即静默"的纯数据模块（见 tests/test_structure.py 的 SILENT_MODULES）。
"""
import os
import sys

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(PROJ, "tools")
SCRIPTS = os.path.join(TOOLS, "scripts")

# 第三方依赖（其余非标准库导入都应能在 tools/scripts/ 下找到同名脚本）
THIRD_PARTY = {"PIL", "numpy", "UnityPy", "openpyxl"}


def add_tools_path():
    """把 tools/scripts/ 加入 sys.path（全部脚本同目录，bare import 即可）。"""
    if SCRIPTS not in sys.path:
        sys.path.insert(0, SCRIPTS)


def read(path):
    """读文本（显式关闭，避免 ResourceWarning 淹没真正的失败信息）。"""
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def script_paths():
    """-> [绝对路径, ...]，覆盖 tools/scripts/ 下全部 .py。"""
    if not os.path.isdir(SCRIPTS):
        return []
    return [os.path.join(SCRIPTS, f) for f in sorted(os.listdir(SCRIPTS))
            if f.endswith(".py") and os.path.isfile(os.path.join(SCRIPTS, f))]


def ps1_paths():
    if not os.path.isdir(SCRIPTS):
        return []
    return [os.path.join(SCRIPTS, f) for f in sorted(os.listdir(SCRIPTS))
            if f.endswith(".ps1") and os.path.isfile(os.path.join(SCRIPTS, f))]


def module_names():
    return {os.path.basename(p)[:-3] for p in script_paths()}
