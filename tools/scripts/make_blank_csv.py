"""生成一份"空白"的替代描述表（CSV，带 BOM，Excel 直接双击打开不乱码）。

给不想开浏览器、或者浏览器预览面板显示异常时用：
    1. 双击打开 art/角色替代描述_空白.csv（Excel / WPS 都行）
    2. 只在最后一列「替代描述」里写
    3. 保存（保持 CSV 格式），告诉我，我用 import_briefs_csv.py 读回来
"""

import csv
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from characters_meta import ROSTER  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "art", "角色替代描述_空白.csv")

HEAD = ["预制体", "中文名", "英文名", "阵营", "类型", "替代描述（请填写）"]


def main():
    rows = [HEAD]
    for e in ROSTER:
        rows.append([e["prefab"], e.get("cn", ""), e.get("en", ""),
                     e.get("faction", ""), e.get("role", ""), ""])
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    # utf-8-sig：BOM 让 Excel 认得出这是 UTF-8，不然中文会变乱码
    with io.open(OUT, "w", encoding="utf-8-sig", newline="") as fh:
        csv.writer(fh, lineterminator="\r\n").writerows(rows)
    print("blank csv:", len(rows) - 1, "rows ->", os.path.relpath(OUT, ROOT))


if __name__ == "__main__":
    main()
