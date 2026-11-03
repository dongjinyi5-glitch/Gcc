# -*- coding: utf-8 -*-
"""看看用户提了哪些疑问还没答复，以及「待确认」页回答了没有。

不重建表格，只读。用法：

    python tools/scripts/qa_report.py

输出三类：
  * 未答复的疑问（用户写了、我还没回）—— 这些是下一轮要处理的
  * 已答复的疑问 —— 备查，确认没有答错行
  * 「待确认」页 A–H 的回答
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import qa_cells as QA  # noqa: E402
import build_component_xlsx as B  # noqa: E402


def main():
    keep, qa, asks = B.scan_prev()
    ans = QA.load(B.QA_ANSWERS)

    open_q = [(k, q) for k, (q, a) in qa.items() if q and not (a or ans.get(k))]
    done_q = [(k, q, a or ans.get(k)) for k, (q, a) in qa.items()
              if q and (a or ans.get(k))]

    print("=" * 60)
    print("未答复的疑问：%d 条" % len(open_q))
    for k, q in open_q:
        print("  [%s] %s" % (k, q))
    print("-" * 60)
    print("已答复：%d 条" % len(done_q))
    for k, q, a in done_q[:30]:
        print("  [%s] %s\n      → %s" % (k, q, a))
    print("-" * 60)
    print("「待确认」回答：%d 条" % len(asks))
    for k in sorted(asks):
        print("  %s → %s" % (k, asks[k]))
    print("=" * 60)
    print("判定分布：", end="")
    from collections import Counter
    print(dict(Counter(v[0] for v in keep.values())))


if __name__ == "__main__":
    main()
