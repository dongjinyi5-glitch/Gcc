# -*- coding: utf-8 -*-
"""把用户的确认结论写回 背景构件替换总表.xlsx（就地写，不重建，不动格式）。

用户 2026-10-24 的授权：
  1. 「重绘清单 T1」页 160 行判定 **全部 = 确认OK**。
  2. 「构件总表」页 **除去「背景」图层** 的行（角色/武器/UI/特效 = 95 行），
     同意按「我的建议」列的口径实施 → 判定 = 确认OK。
  3. 剩下的「背景」图层 T2/T3/T4（1195 行）保持 待确认 —— 用户没看过，
     不能替他勾。

一致性处理：T1 的 160 行在「构件总表」里也是「背景」图层，但它们在
「重绘清单 T1」页已被逐行确认，同一个构件不能两页给出相反结论，
所以「构件总表」里 替换层级 == T1 换内容 的行同样写 确认OK。

用法：
    python tools/scripts/apply_confirmations.py --dry-run
    python tools/scripts/apply_confirmations.py
"""
import argparse
import io
import json
import os
import shutil
import sys
import time

import openpyxl

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
XLSX = os.path.join(ROOT, "docs", "背景构件替换总表.xlsx")
OK = "确认OK"
PEND = "待确认"


def find(head, *cands):
    for c in cands:
        if c in head:
            return head.index(c)
    for i, h in enumerate(head):
        if any(c in str(h) for c in cands):
            return i
    raise KeyError(cands)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--xlsx", default=XLSX)
    args = ap.parse_args()

    t0 = time.time()
    wb = openpyxl.load_workbook(args.xlsx)

    # ---------- 1) 重绘清单 T1：全 160 行 = 确认OK ----------
    ws1 = wb["重绘清单 T1"]
    h1 = [c.value for c in ws1[1]]
    j1 = find(h1, "判定（待确认 / 确认OK）", "判定")
    n1 = 0
    for r in range(2, ws1.max_row + 1):
        name = ws1.cell(row=r, column=find(h1, "构件名") + 1).value
        if not name:
            continue
        ws1.cell(row=r, column=j1 + 1).value = OK
        n1 += 1

    # ---------- 2) 构件总表：非背景 或 T1 → 确认OK ----------
    ws2 = wb["构件总表"]
    h2 = [c.value for c in ws2[1]]
    j_lay = find(h2, "图层")
    j_tier = find(h2, "替换层级")
    j_ver = find(h2, "判定（待确认 / 确认OK）", "判定")
    j_cat = find(h2, "构件类别")
    j_name = find(h2, "构件名")

    stat = {"nonbg": 0, "t1": 0, "pend": 0}
    pend_cats = {}
    for r in range(2, ws2.max_row + 1):
        name = ws2.cell(row=r, column=j_name + 1).value
        if not name:
            continue
        lay = str(ws2.cell(row=r, column=j_lay + 1).value or "")
        tier = str(ws2.cell(row=r, column=j_tier + 1).value or "")
        cell = ws2.cell(row=r, column=j_ver + 1)
        if lay != "背景":
            cell.value = OK
            stat["nonbg"] += 1
        elif tier.startswith("T1"):
            cell.value = OK
            stat["t1"] += 1
        else:
            cell.value = PEND
            stat["pend"] += 1
            cat = str(ws2.cell(row=r, column=j_cat + 1).value or "")
            pend_cats[cat] = pend_cats.get(cat, 0) + 1

    total_ok = stat["nonbg"] + stat["t1"]
    print("重绘清单 T1：%d 行 -> 确认OK" % n1)
    print("构件总表：确认OK %d（非背景 %d + T1 %d）／待确认 %d"
          % (total_ok, stat["nonbg"], stat["t1"], stat["pend"]))
    print("仍待确认的类别：", json.dumps(
        dict(sorted(pend_cats.items(), key=lambda x: -x[1])), ensure_ascii=False))

    if args.dry_run:
        print("dry-run，未写盘")
        return

    # ---------- 3) 落盘（先备份） ----------
    bak = os.path.join(ROOT, "docs", "_archive",
                       "背景构件替换总表_%s_写判定前.xlsx"
                       % time.strftime("%Y%m%d_%H%M"))
    shutil.copy2(args.xlsx, bak)
    print("备份 ->", os.path.relpath(bak, ROOT))

    wb.save(args.xlsx)
    print("已写回 %s（%.1f MB，%.0fs）"
          % (os.path.relpath(args.xlsx, ROOT),
             os.path.getsize(args.xlsx) / 1e6, time.time() - t0))

    # ---------- 4) 回读自检 ----------
    wb2 = openpyxl.load_workbook(args.xlsx, read_only=True)
    a = wb2["重绘清单 T1"]
    cnt1 = {}
    for r in a.iter_rows(min_row=2, values_only=True):
        v = r[j1]
        cnt1[v] = cnt1.get(v, 0) + 1
    b = wb2["构件总表"]
    cnt2 = {}
    for r in b.iter_rows(min_row=2, values_only=True):
        v = r[j_ver]
        cnt2[v] = cnt2.get(v, 0) + 1
    print("回读 重绘清单T1:", cnt1)
    print("回读 构件总表  :", cnt2)
    wb2.close()


if __name__ == "__main__":
    sys.exit(main())
