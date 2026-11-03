# -*- coding: utf-8 -*-
"""手术式写回判定列：只改 sheet XML 里那几个 <t>文字</t>，其余 zip 条目字节原样复制。

为什么不用 openpyxl 存盘：这张表 15 MB、内嵌 3220 张缩略图，openpyxl 重新序列化
会整包重写，有丢图/丢样式的风险（用户已经因为一次重建丢过确认）。这里只碰
两个 sheet 的 XML 文本，图片、样式、列宽、行高、数据验证全部原封不动。

用户 2026-10-24 的授权：
  1. 「重绘清单 T1」160 行 判定 = 确认OK（全部）
  2. 「构件总表」图层 != 背景 的行（95 行：角色/武器/UI/特效）判定 = 确认OK
  3. 「构件总表」替换层级 == T1 的行（160 行，与 T1 页同一批构件）判定 = 确认OK
  4. 其余「背景」T2/T3/T4（1195 行）保持 待确认

用法：
    python tools/scripts/patch_verdicts.py --dry-run
    python tools/scripts/patch_verdicts.py
"""
import argparse
import json
import os
import re
import shutil
import sys
import time
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
XLSX = os.path.join(ROOT, "docs", "背景构件替换总表.xlsx")

OK, PEND = "确认OK", "待确认"

# 行：<row r="2" ...> ... </row>
RE_ROW = re.compile(r'(<row r="(\d+)"[^>]*>)(.*?)(</row>)', re.S)
# 单元格：同时兼容 <c .../> 与 <c ...>...</c>
#   注意 `([^>]*?)` 必须惰性，否则自闭合标签会把后续单元格吞进来
RE_CELL = re.compile(r'<c r="([A-Z]+)(\d+)"([^>]*?)(?:/>|>(.*?)</c>)', re.S)
RE_T = re.compile(r'<is><t[^>]*>(.*?)</t></is>', re.S)


def patch_sheet(xml, verdict_col, decide, stats, pend_counter=None):
    """decide(cols, rownum) -> 目标文字 或 None（不动）。第 1 行表头永远跳过。"""

    def one(m):
        head, rownum, body, tail = m.group(1), int(m.group(2)), m.group(3), m.group(4)
        if rownum == 1:
            return m.group(0)

        cells = {}
        for cm in RE_CELL.finditer(body):
            cells[cm.group(1)] = cm
        if verdict_col not in cells:
            return m.group(0)

        cols = {}
        for k, cm in cells.items():
            t = RE_T.search(cm.group(0))
            cols[k] = t.group(1) if t else ""

        target = decide(cols, rownum)
        if target is None:
            return m.group(0)

        cm = cells[verdict_col]
        old = cm.group(0)
        if RE_T.search(old):
            new = RE_T.sub(lambda x: "<is><t>%s</t></is>" % target, old, count=1)
        else:
            # 空单元格（自闭合）：补成 inlineStr
            new = '<c r="%s%s"%s t="inlineStr"><is><t>%s</t></is></c>' % (
                verdict_col, rownum, cm.group(3), target)

        if new == old:
            return m.group(0)
        stats[target] = stats.get(target, 0) + 1
        return head + body.replace(old, new, 1) + tail

    return RE_ROW.sub(one, xml)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--xlsx", default=XLSX)
    args = ap.parse_args()

    t0 = time.time()
    zin = zipfile.ZipFile(args.xlsx)

    wbxml = zin.read("xl/workbook.xml").decode("utf-8")
    rels = zin.read("xl/_rels/workbook.xml.rels").decode("utf-8")
    rid2tgt = {rid: tgt.lstrip("/") for tgt, rid in
               re.findall(r'Target="([^"]+)" Id="(rId\d+)"', rels)}
    sheet_of = {}
    for m in re.finditer(r'<sheet[^>]*name="([^"]+)"[^>]*r:id="(rId\d+)"', wbxml):
        sheet_of[m.group(1)] = rid2tgt.get(m.group(2))

    s1, s2 = sheet_of["重绘清单 T1"], sheet_of["构件总表"]
    print("重绘清单 T1 ->", s1, " 构件总表 ->", s2)

    # ---- 1) 重绘清单 T1：全部 确认OK（D=构件名, K=判定）----
    x1 = zin.read(s1).decode("utf-8")
    st1 = {}
    x1n = patch_sheet(x1, "K", lambda c, r: OK if c.get("D") else None, st1)

    # ---- 2) 构件总表：B=类别 C=图层 K=替换层级 Q=判定 ----
    x2 = zin.read(s2).decode("utf-8")
    st2, pend_cat = {}, {}

    def d2(cols, rn):
        if not cols.get("D"):
            return None
        lay, tier = cols.get("C", ""), cols.get("K", "")
        if lay != "背景" or tier.startswith("T1"):
            return OK
        cat = cols.get("B", "?")
        pend_cat[cat] = pend_cat.get(cat, 0) + 1
        return PEND

    x2n = patch_sheet(x2, "Q", d2, st2)

    print("重绘清单 T1 改动:", st1)
    print("构件总表   改动:", st2)
    print("仍待确认 %d 行：" % sum(pend_cat.values()),
          json.dumps(dict(sorted(pend_cat.items(), key=lambda x: -x[1])),
                     ensure_ascii=False))

    if args.dry_run:
        print("dry-run，未写盘")
        return

    # ---- 3) 备份 + 逐条目原样复制 ----
    bak = os.path.join(ROOT, "docs", "_archive",
                       "背景构件替换总表_%s_写判定前.xlsx"
                       % time.strftime("%Y%m%d_%H%M"))
    shutil.copy2(args.xlsx, bak)
    print("备份 ->", os.path.relpath(bak, ROOT))

    tmp = args.xlsx + ".tmp"
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
        for it in zin.infolist():
            if it.filename == s1:
                data = x1n.encode("utf-8")
            elif it.filename == s2:
                data = x2n.encode("utf-8")
            else:
                data = zin.read(it.filename)
            zi = zipfile.ZipInfo(it.filename, date_time=it.date_time)
            zi.compress_type = it.compress_type
            zi.external_attr = it.external_attr
            zout.writestr(zi, data)
    zin.close()
    os.replace(tmp, args.xlsx)
    print("已写回 %s（%.1f MB，%.0fs）"
          % (os.path.relpath(args.xlsx, ROOT),
             os.path.getsize(args.xlsx) / 1e6, time.time() - t0))


if __name__ == "__main__":
    sys.exit(main())
