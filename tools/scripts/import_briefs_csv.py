"""把填好的 CSV 读回 validation/roster_briefs.json（与网页填写同一条落地路径）。

支持三种编码：utf-8-sig（本工程生成）、utf-8、gbk（Excel 中文版另存默认）。
列名只要含"预制体"和"替代描述"就能认；多余的列忽略。
"""

import csv
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from characters_meta import ROSTER  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
STATE = os.path.join(ROOT, "validation", "roster_briefs.json")
DEFAULT_IN = os.path.join(ROOT, "art", "角色替代描述_空白.csv")


def read_rows(path):
    for enc in ("utf-8-sig", "utf-8", "gbk"):
        try:
            with io.open(path, encoding=enc, newline="") as fh:
                return list(csv.reader(fh)), enc
        except UnicodeDecodeError:
            continue
    raise SystemExit("无法识别编码：%s" % path)


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_IN
    rows, enc = read_rows(src)
    if not rows:
        raise SystemExit("空文件")
    head = [c.strip() for c in rows[0]]
    try:
        i_key = next(i for i, c in enumerate(head) if "预制体" in c)
        i_val = next(i for i, c in enumerate(head) if "替代描述" in c or "描述" in c)
    except StopIteration:
        raise SystemExit("表头里找不到「预制体」或「替代描述」列：%s" % head)

    known = {e["prefab"] for e in ROSTER}
    data, unknown, empty = {}, [], 0
    for r in rows[1:]:
        if len(r) <= max(i_key, i_val):
            continue
        k, v = r[i_key].strip(), r[i_val].strip()
        if not k:
            continue
        if not v:
            empty += 1
            continue
        if k not in known:
            unknown.append(k)
            continue
        data[k] = v

    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    with io.open(STATE, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=1, sort_keys=True)

    print("encoding   :", enc)
    print("source     :", os.path.relpath(src, ROOT))
    print("filled     :", len(data), "/", len(known))
    print("blank rows :", empty)
    if unknown:
        print("unknown key:", ", ".join(unknown[:8]))
    print("->", os.path.relpath(STATE, ROOT))


if __name__ == "__main__":
    main()
