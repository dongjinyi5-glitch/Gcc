"""Build the component replacement workbook.

The user reviews 1450 components and decides whether the replacement meets the
brief, so the sheet is built around one comparison: 原图 next to 最新替换图, at
the same size, on the same row.  Everything else in the row exists to make that
comparison actionable -- which chapters the component appears in (in the Chinese
names the chapter-select screen shows), how big it is, what the replacement did
to it, and what I recommend doing next.

Two things this deliberately does NOT do:

* it does not hide the non-background rows (角色部件 / 武器 / UI).  They are in the
  table with 图层 set, because "all the pieces in the picture" is what was asked
  for, and a component you cannot see is a component nobody remembers.
* it does not overwrite the reviewer's own column.  On rebuild, 判定 and 备注 are
  read back out of the previous workbook first -- a table you cannot write in is
  not a review tool.

Versions live in art/component_versions.json, not in the sheet, so the next
version (an ImageGen redraw, say) can be appended without rebuilding the file.
"""
import io
import json
import os
import sys

import openpyxl
from openpyxl.drawing.image import Image as XLImage
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ggc_assets import PROJECT  # noqa: E402
from component_taxonomy import LEVEL_CN, classify  # noqa: E402
import historical_map as H  # noqa: E402
import qa_cells as QA  # noqa: E402
from component_tiers import TIER_LABEL, TIER_NOTE, assign  # noqa: E402
from redraw_targets import target as redraw_target  # noqa: E402

ART = os.path.join(PROJECT, "art")
INV = os.path.join(ART, "scene_inventory.json")
THUMBS = os.path.join(ART, "component_thumbs")
METRICS = os.path.join(ART, "component_metrics.json")
VERSIONS = os.path.join(ART, "component_versions.json")
QA_ANSWERS = os.path.join(ART, "qa_answers.json")   # 我的答复（源）
QA_ASKS = os.path.join(ART, "ask_answers.json")     # 用户对「待确认」8 问的回答
OUT = os.path.join(PROJECT, "docs", "背景构件替换总表.xlsx")
OUT_ALT = os.path.join(PROJECT, "docs", "背景构件替换总表_备用.xlsx")

VERDICTS = ["待确认", "确认OK"]
# 表头把两个选项写全：腾讯文档之类不渲染下拉的阅读器里，至少知道能填什么
VERDICT_HEAD = "判定（待确认 / 确认OK）"

LIMIT = int(os.environ.get("LIMIT", "0"))     # 0 = all rows, for smoke tests

# Review order: the pieces that carry the look come first, so the first screen
# of the sheet is the decision, not the small props.
CAT_ORDER = [
    "船体与船舱", "码头与栈桥", "港口远景层", "天空与月亮", "街巷与建筑外墙",
    "室内空间", "桥梁与桥头堡", "下水道与竖井", "蓄水池与水面", "屋顶与飞艇",
    "建筑工地", "车辆与载具", "军用工事", "管线与钢结构", "栏杆楼梯与通道",
    "货箱麻袋桶", "招牌与标识", "灯光与灯具", "街道设施与小道具", "自然物",
    "尸体与残骸", "阴影与遮挡层", "彩蛋", "特效",
    "角色部件", "武器", "界面与章节卡",
]
LAYER_ORDER = ["背景", "特效", "角色", "武器", "UI"]

W_IMG = 132          # px; both columns identical so the pair reads as one strip
H_IMG = 99
ROW_PT = 77

INK = "1C1A17"
MUT = "6D675E"
HEAD_BG = "3E3A33"
BAND = ["FFFFFF", "F7F4EE"]
FILL_SHIP = PatternFill("solid", fgColor="DDEBD6")
FILL_DRAFT = PatternFill("solid", fgColor="F2EFE8")
FILL_REDRAW = PatternFill("solid", fgColor="F8E2DC")
FILL_OK = PatternFill("solid", fgColor="E4EFE0")
FILL_ASK = PatternFill("solid", fgColor="FFF3D6")
THIN = Side(style="thin", color="DED8CE")
BOX = Border(bottom=THIN)


def load_json(p, default=None):
    if os.path.exists(p):
        return json.load(io.open(p, encoding="utf-8"))
    return default if default is not None else {}


def lv_str(levels):
    return "、".join(LEVEL_CN.get(l, l) for l in levels)


def rkey(name, size, lvs):
    """一行的稳定键：构件名 + 尺寸 + 关卡集合。

    见 qa_cells.key 的说明 —— 只按 名称+尺寸 会把 ArmFront 的两行并成一行。
    """
    return "%s|%s|%s" % (name, size, lvs)


def build_versions(inv):
    """Create the registry on first run; never rewrite an existing one."""
    if os.path.exists(VERSIONS):
        return load_json(VERSIONS)
    reg = {
        "_scheme": {
            "R": "restyle —— 脚本按颜料色阶重映射，保留原明度与 alpha",
            "G": "ImageGen 重绘 —— 按提示词重新绘制，形与笔触都变",
            "H": "手工修版 —— 在上一版基础上局部修补",
        },
        "_note": "每个构件的 versions 数组按时间追加，current 指向最新版。"
                 "表格只显示 current；历史版本在「版本记录」页。",
        "components": {},
    }
    for r in inv:
        k = "%s__%d" % (r["file"], r["path_id"])
        shipped = "level3" in r["levels"]
        reg["components"][k] = {
            "name": r["texture"],
            "current": "R1",
            "shipped": shipped,
            "versions": [{
                "v": "R1",
                "date": "2026-10-22",
                "kind": "restyle",
                "file": "art/scene_restyle/all/%s.png" % k,
                "note": ("restyle v2 全库扫描；已写入 sharedassets4.assets"
                         if shipped else "restyle v2 全库扫描；尚未入包"),
            }],
        }
    json.dump(reg, io.open(VERSIONS, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    return reg


def scan_prev():
    """Pull the reviewer's own input out of the previous workbook, in one pass.

    Returns (keep, qa):
      keep -- {(构件名, 尺寸): (判定, 备注)}
      qa   -- {"构件名|尺寸|栏号": (疑问, 上次答复)}

    Two things this has to get right:

    * **Key on (构件名, 原始尺寸), not 序号.** The sort order changes whenever the
      tiering changes, so positional row numbers silently re-attach last round's
      decisions to the wrong component.  Name+size survives a re-sort.
    * **Only trust 备注 / 疑问 in the new schema.** In the first 15-column workbook
      the 备注 column was pre-filled with my own auto-generated explanation, so
      reading it back would launder my text into "the reviewer said so".
    """
    src = None
    for p in (OUT_ALT, OUT):
        if os.path.exists(p) and (src is None or
                                  os.path.getmtime(p) > os.path.getmtime(src)):
            src = p
    keep, qa = {}, {}
    asks = {}
    if not src:
        return keep, qa, asks
    try:
        wb = openpyxl.load_workbook(src, read_only=True, data_only=True)
        ws = wb["构件总表"]
        rows = ws.iter_rows(values_only=True)
        head = list(next(rows))
        i_name = head.index("构件名")
        i_size = head.index("原始尺寸")
        i_lv = head.index("用于关卡")
        i_v = next((i for i, h in enumerate(head) if h.startswith("判定")), None)
        if i_v is None:
            wb.close()
            return keep, qa, asks
        new_schema = "替换层级" in head
        i_n = head.index("备注") if new_schema else None
        i_q = [head.index("疑问%d" % (k + 1)) for k in range(QA.SLOTS)
               if "疑问%d" % (k + 1) in head]

        def grab(row, name_i, size_i, lv_i, q_idx):
            for slot, ci in enumerate(q_idx, start=1):
                q, a = QA.split(row[ci])
                if q or a:
                    qa[QA.key(row[name_i], row[size_i], row[lv_i], slot)] = (q, a)

        for row in rows:
            if row[i_name] is None:
                continue
            k = rkey(row[i_name], row[i_size], row[i_lv])
            keep[k] = (row[i_v], row[i_n] if i_n is not None else None)
            grab(row, i_name, i_size, i_lv, i_q)

        # 重绘清单 T1 页也能写判定/备注/疑问，两处合并（T1 页优先，因为它更聚焦）
        if new_schema and "重绘清单 T1" in wb.sheetnames:
            w2 = wb["重绘清单 T1"]
            it = w2.iter_rows(values_only=True)
            h2 = list(next(it))
            j_name, j_size = h2.index("构件名"), h2.index("尺寸")
            j_lv = h2.index("章节")
            j_note = h2.index("备注") if "备注" in h2 else None
            j_q = [h2.index("疑问%d" % (k + 1)) for k in range(QA.SLOTS)
                   if "疑问%d" % (k + 1) in h2]
            for row in it:
                if row[j_name] is None:
                    continue
                k = rkey(row[j_name], row[j_size], row[j_lv])
                if j_note is not None and row[j_note]:
                    v = keep.get(k, ("待确认", None))[0]
                    keep[k] = (v, row[j_note])
                grab(row, j_name, j_size, j_lv, j_q)

        # 「待确认」页：用户对 8 个问题的回答，按编号读回
        if "待确认" in wb.sheetnames:
            w3 = wb["待确认"]
            it3 = w3.iter_rows(values_only=True)
            h3 = list(next(it3))
            if "你的回答" in h3:
                k_no, k_ans = h3.index("编号"), h3.index("你的回答")
                for row in it3:
                    if row[k_no] and row[k_ans]:
                        asks[str(row[k_no]).strip()] = str(row[k_ans]).strip()
        wb.close()
    except Exception as e:
        print("  回读失败，判定/疑问将重置:", e)
    return keep, qa, asks


def build():
    inv = load_json(INV, [])
    met = load_json(METRICS, {})
    ver = build_versions(inv)
    keep, qa, asks = scan_prev()

    # 答复以 JSON 为准；表格里还留着的答复（比如上一轮手工写的）补进 JSON，不丢
    ans = QA.load(QA_ANSWERS)
    added = 0
    for k, (q, a) in qa.items():
        if a and k not in ans:
            ans[k] = a
            added += 1
    if added:
        QA.save(QA_ANSWERS, ans)
        print("  从表格补回 %d 条旧答复" % added)
    q_open = [k for k, (q, a) in qa.items() if q and not a]

    ask_ans = QA.load(QA_ASKS)
    before = dict(ask_ans)
    ask_ans.update({k: v for k, v in asks.items() if v})
    if ask_ans != before:
        QA.save(QA_ASKS, ask_ans)

    tiers = assign(inv)
    rows = []
    for r in inv:
        k = "%s__%d" % (r["file"], r["path_id"])
        cat, layer = classify(r["texture"])
        m = met.get(k, {})
        v = ver["components"].get(k, {})
        cur = v.get("current", "—")
        tier = tiers.get((r["file"], r["path_id"]), "—")
        # 一个构件横跨多关时，目标形态按"它最主要的那一关"来写
        main_lv = r["levels"][0] if r["levels"] else "level0"
        rows.append(dict(
            key=k, name=r["texture"], cat=cat, layer=layer,
            levels=r["levels"], size=r["size"], area=r["area"],
            shipped=v.get("shipped", False), ver=cur,
            dark=m.get("dark"), cover=m.get("cover"),
            advice=m.get("advice", "待核"), why=m.get("why", ""),
            tier=tier,
            hist=H.describe(r["levels"]) if layer == "背景" else "—",
            goal=redraw_target(main_lv, cat, tier),
        ))

    tier_rank = {"T1": 0, "T2": 1, "T3": 2, "T4": 3, "—": 4}
    rows.sort(key=lambda d: (LAYER_ORDER.index(d["layer"]),
                             tier_rank.get(d["tier"], 4),
                             CAT_ORDER.index(d["cat"]) if d["cat"] in CAT_ORDER else 99,
                             -d["area"]))
    if LIMIT:
        rows = rows[:LIMIT]

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "构件总表"
    head = ["序号", "构件类别", "图层", "构件名", "用于关卡", "历史原型",
            "原始尺寸", "原图", "现版 R1（只换色）", "版本", "替换层级", "状态",
            "目标形态（重绘要求）", "暗部占比", "覆盖率", "我的建议", VERDICT_HEAD, "备注"]
    head += ["疑问%d" % (k + 1) for k in range(QA.SLOTS)]
    ws.append(head)

    for c in range(1, len(head) + 1):
        cell = ws.cell(row=1, column=c)
        cell.font = Font(name="微软雅黑", size=10, bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor=HEAD_BG)
        cell.alignment = Alignment(horizontal="center", vertical="center",
                                   wrap_text=True)
    ws.row_dimensions[1].height = 34

    widths = [6, 17, 6, 30, 30, 36, 11, 20, 20, 7, 13, 13, 52, 8, 8, 15, 15, 40]
    widths += [30] * QA.SLOTS
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w

    qa_col0 = len(head) - QA.SLOTS + 1      # 第一栏「疑问1」的列号

    cat_seen, band = None, 0
    for i, d in enumerate(rows):
        r = i + 2
        if d["cat"] != cat_seen:
            cat_seen = d["cat"]
            band ^= 1
        fill = PatternFill("solid", fgColor=BAND[band])

        # 状态必须看版本号：已经升到 G* 的 T1 不能再写「待重绘」，
        # 否则表里明明摆着重绘图，状态却说没画
        ver_s = str(d["ver"] or "")
        if ver_s.startswith("G"):
            status = "已重绘（%s）" % ver_s
        elif d["tier"] == "T1":
            status = "待重绘（R1 仅底色）"
        elif d["shipped"]:
            status = "已入包（R1 换色）"
        elif d["layer"] == "背景":
            status = "草稿（R1 换色）"
        else:
            status = "其他流水线"

        rk = rkey(d["name"], "%d×%d" % tuple(d["size"]), lv_str(d["levels"]))
        mine = d["advice"] + (" —— " + d["why"] if d["why"] else "")
        vals = [i + 1, d["cat"], d["layer"], d["name"],
                lv_str(d["levels"]),
                d["hist"],
                "%d×%d" % tuple(d["size"]), None, None, d["ver"],
                TIER_LABEL.get(d["tier"], "—"), status, d["goal"],
                d["dark"], d["cover"], mine,
                keep.get(rk, ("待确认", None))[0],
                keep.get(rk, (None, None))[1] or None]
        vals += [None] * QA.SLOTS
        for c, v in enumerate(vals, start=1):
            cell = ws.cell(row=r, column=c, value=v)
            cell.font = Font(name="微软雅黑", size=9, color=INK)
            cell.fill = fill
            cell.border = BOX
            cell.alignment = Alignment(
                vertical="center",
                horizontal="center" if c in (1, 3, 7, 10, 11, 12, 14, 15, 17) else "left",
                wrap_text=c in (5, 6, 13, 18) or c >= qa_col0)

        # 疑问栏：疑问黑字 + 我的答复红字，同格上下排
        for slot in range(QA.SLOTS):
            qk = QA.key(d["name"], "%d×%d" % tuple(d["size"]),
                        lv_str(d["levels"]), slot + 1)
            q, a = qa.get(qk, ("", ""))
            cell = ws.cell(row=r, column=qa_col0 + slot)
            if q or a:
                cell.value = QA.make(q, ans.get(qk, a))
            else:
                cell.value = None

        if d["dark"] is not None:
            ws.cell(row=r, column=14).number_format = "0%"
            ws.cell(row=r, column=15).number_format = "0%"
        # 替换层级是这张表的判据，用底色直接区分"换内容"和"只换色"
        ws.cell(row=r, column=11).fill = (
            FILL_REDRAW if d["tier"] == "T1" else FILL_OK if d["tier"] == "T4"
            else FILL_ASK)
        ws.cell(row=r, column=12).fill = FILL_REDRAW if d["tier"] == "T1" else FILL_DRAFT
        ws.cell(row=r, column=16).fill = (
            FILL_REDRAW if d["advice"].startswith("P1")
            else FILL_OK if d["advice"].startswith("P3")
            else FILL_ASK)
        ws.cell(row=r, column=17).fill = FILL_ASK
        ws.row_dimensions[r].height = ROW_PT

        for col, sub in ((8, "orig"), (9, "new")):
            p = os.path.join(THUMBS, sub, d["key"] + ".jpg")
            if os.path.exists(p):
                img = XLImage(p)
                img.width, img.height = W_IMG, H_IMG
                ws.add_image(img, "%s%d" % (get_column_letter(col), r))

    ws.freeze_panes = "E2"
    ws.auto_filter.ref = "A1:%s%d" % (get_column_letter(len(head)), len(rows) + 1)
    verdict_dv(ws, "Q", 2, len(rows) + 1)

    summary(wb, rows)
    categories(wb, rows)
    chapters_sheet(wb, rows)
    t1_sheet(wb, rows, keep, qa, ans)
    versions_sheet(wb, ver, rows)
    asks_sheet(wb, ask_ans)
    readme(wb, rows, tiers)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    dst = OUT
    try:
        wb.save(dst)
    except PermissionError:
        dst = OUT_ALT
        wb.save(dst)
        print("  %s 正被 Excel 打开，已另存为 %s" % (os.path.basename(OUT),
                                              os.path.basename(OUT_ALT)))
    print("saved ->", dst, "%.1f MB" % (os.path.getsize(dst) / 1e6))
    if q_open:
        print("  待我答复的疑问 %d 条：" % len(q_open))
        for k in q_open[:20]:
            print("    ", k, "→", qa[k][0][:40])
    if ask_ans:
        print("  「待确认」已收到回答 %d 条" % len(ask_ans))


def summary(wb, rows):
    ws = wb.create_sheet("按关卡汇总")
    head = ["关卡", "构件总数", "背景构件", "T1 换内容", "T2 材质", "T3 道具",
            "T4 只调色", "已入包", "总面积 Mpx", "T1 面积占比"]
    ws.append(head)
    style_head(ws, head)

    order = [k for k in LEVEL_CN]
    for lv in order:
        sel = [d for d in rows if lv in d["levels"]]
        if not sel:
            continue
        bg = [d for d in sel if d["layer"] == "背景"]
        area = sum(d["area"] for d in sel) / 1e6
        a1 = sum(d["area"] for d in sel if d["tier"] == "T1") / 1e6
        ws.append([LEVEL_CN[lv], len(sel), len(bg),
                   sum(1 for d in sel if d["tier"] == "T1"),
                   sum(1 for d in sel if d["tier"] == "T2"),
                   sum(1 for d in sel if d["tier"] == "T3"),
                   sum(1 for d in sel if d["tier"] == "T4"),
                   sum(1 for d in sel if d["shipped"]),
                   round(area, 1), (a1 / area) if area else 0])
    tot = ["合计", len(rows),
           sum(1 for d in rows if d["layer"] == "背景"),
           sum(1 for d in rows if d["tier"] == "T1"),
           sum(1 for d in rows if d["tier"] == "T2"),
           sum(1 for d in rows if d["tier"] == "T3"),
           sum(1 for d in rows if d["tier"] == "T4"),
           sum(1 for d in rows if d["shipped"]),
           round(sum(d["area"] for d in rows) / 1e6, 1),
           sum(d["area"] for d in rows if d["tier"] == "T1") /
           sum(d["area"] for d in rows)]
    ws.append(tot)
    for c in range(1, len(head) + 1):
        ws.cell(row=ws.max_row, column=c).font = Font(name="微软雅黑", size=10, bold=True)
        ws.cell(row=ws.max_row, column=c).fill = PatternFill("solid", fgColor="EFE9DD")
    for r in range(2, ws.max_row + 1):
        ws.cell(row=r, column=10).number_format = "0.0%"
    widths = [22, 11, 11, 11, 10, 10, 11, 10, 13, 13]
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = "B2"


def chapters_sheet(wb, rows):
    """12 个章节 -> 历史原型。这是用户质疑的那件事的正面回答。

    表格原先只回答"脚本对这张图做了什么"，这一页回答"这一关应该变成哪儿"。
    """
    ws = wb.create_sheet("历史场景对照")
    head = ["章节", "卡面标题", "场景文件", "历史原型", "时间", "形态吻合",
            "构件数", "T1 地标", "T1 面积 Mpx", "这一关要变成什么样"]
    ws.append(head)
    style_head(ws, head)

    for lv in H.ORDER:
        c = H.CHAPTERS.get(lv)
        if not c:
            continue
        sel = [d for d in rows if lv in d["levels"]]
        t1 = [d for d in sel if d["tier"] == "T1"]
        ws.append([c["cn"], c["card"], c["scene"], c["hist"], c["date"],
                   c["strength"], len(sel), len(t1),
                   round(sum(d["area"] for d in t1) / 1e6, 1), c["intent"]])
    for r in range(2, ws.max_row + 1):
        for col in range(1, len(head) + 1):
            cell = ws.cell(row=r, column=col)
            cell.font = Font(name="微软雅黑", size=10, color=INK)
            cell.alignment = Alignment(vertical="center", wrap_text=col in (4, 10),
                                       horizontal="left" if col in (4, 10) else "center")
        ws.row_dimensions[r].height = 46
        strength = ws.cell(row=r, column=6).value
        ws.cell(row=r, column=6).fill = (
            FILL_OK if strength == "极强" else FILL_ASK if strength in ("很强", "强")
            else FILL_REDRAW)
    widths = [20, 20, 18, 30, 20, 10, 9, 9, 13, 62]
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = "B2"

    r = ws.max_row + 2
    ws.cell(row=r, column=1, value="形态吻合度说明").font = Font(
        name="微软雅黑", size=10, bold=True, color=HEAD_BG)
    notes = [
        ("极强 / 很强", "游戏原型的形制和历史原型本来就对得上，几乎不用改几何，只换内容。"),
        ("强", "结构能对上，但要改一批构件才成立。"),
        ("弱", "对不上，只能做插叙或局部暗示（夜总会、飞艇两关），不要硬套战役名。"),
        ("已排除", "；".join("%s（%s → %s）" % (a, b, c) for a, b, c in H.CLOSED)),
    ]
    for i, (k, v) in enumerate(notes):
        rr = r + 1 + i
        ws.cell(row=rr, column=1, value=k).font = Font(name="微软雅黑", size=9, color=INK)
        cell = ws.cell(row=rr, column=2, value=v)
        cell.font = Font(name="微软雅黑", size=9, color=MUT)
        cell.alignment = Alignment(vertical="top", wrap_text=True)
        ws.merge_cells(start_row=rr, start_column=2, end_row=rr, end_column=10)


def t1_sheet(wb, rows, keep, qa, ans):
    """T1 换内容清单 —— 这才是真正要"用远征军场景替换"的那 160 张。"""
    ws = wb.create_sheet("重绘清单 T1")
    head = ["序号", "章节", "历史原型", "构件名", "构件类别", "尺寸", "面积 Mpx",
            "目标形态", "原图", "现版 R1", VERDICT_HEAD, "备注"]
    head += ["疑问%d" % (k + 1) for k in range(QA.SLOTS)]
    ws.append(head)
    style_head(ws, head)

    qa_col0 = len(head) - QA.SLOTS + 1
    sel = [d for d in rows if d["tier"] == "T1"]
    sel.sort(key=lambda d: (H.ORDER.index(d["levels"][0]) if d["levels"] and
                            d["levels"][0] in H.ORDER else 99, -d["area"]))
    for i, d in enumerate(sel):
        r = i + 2
        lv = d["levels"][0] if d["levels"] else "level0"
        lvs = lv_str(d["levels"])
        sz = "%d×%d" % tuple(d["size"])
        vals = [i + 1, lvs, H.describe(d["levels"]), d["name"], d["cat"],
                sz, round(d["area"] / 1e6, 3),
                d["goal"], None, None,
                keep.get(rkey(d["name"], sz, lvs), ("待确认", None))[0],
                keep.get(rkey(d["name"], sz, lvs), (None, None))[1]]
        vals += [None] * QA.SLOTS
        for col, v in enumerate(vals, start=1):
            cell = ws.cell(row=r, column=col, value=v)
            cell.font = Font(name="微软雅黑", size=9, color=INK)
            cell.fill = PatternFill("solid", fgColor=BAND[i % 2])
            cell.border = BOX
            cell.alignment = Alignment(vertical="center",
                                       wrap_text=col in (2, 3, 8, 12) or col >= qa_col0,
                                       horizontal="left" if col in (2, 3, 8, 12)
                                       or col >= qa_col0 else "center")
        ws.cell(row=r, column=11).fill = FILL_ASK
        for slot in range(QA.SLOTS):
            qk = QA.key(d["name"], sz, lvs, slot + 1)
            q, a = qa.get(qk, ("", ""))
            cell = ws.cell(row=r, column=qa_col0 + slot)
            cell.value = QA.make(q, ans.get(qk, a)) if (q or a) else None
        ws.row_dimensions[r].height = ROW_PT
        for col, sub in ((9, "orig"), (10, "new")):
            p = os.path.join(THUMBS, sub, d["key"] + ".jpg")
            if os.path.exists(p):
                img = XLImage(p)
                img.width, img.height = W_IMG, H_IMG
                ws.add_image(img, "%s%d" % (get_column_letter(col), r))

    widths = [6, 18, 30, 30, 17, 11, 10, 56, 20, 20, 15, 30] + [30] * QA.SLOTS
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = "D2"
    ws.auto_filter.ref = "A1:%s%d" % (get_column_letter(len(head)), len(sel) + 1)
    verdict_dv(ws, "K", 2, len(sel) + 1)
    return len(sel)


def categories(wb, rows):
    ws = wb.create_sheet("按类别汇总")
    head = ["构件类别", "构件数", "覆盖关卡数", "总面积 Mpx",
            "T1 换内容", "T2 材质", "T3 道具", "T4 只调色"]
    ws.append(head)
    style_head(ws, head)
    from collections import defaultdict
    agg = defaultdict(lambda: [0, set(), 0.0, 0, 0, 0, 0])
    for d in rows:
        a = agg[d["cat"]]
        a[0] += 1
        a[1].update(d["levels"])
        a[2] += d["area"]
        for j, t in enumerate(("T1", "T2", "T3", "T4")):
            a[3 + j] += 1 if d["tier"] == t else 0
    for cat in CAT_ORDER:
        if cat not in agg:
            continue
        a = agg[cat]
        ws.append([cat, a[0], len(a[1]), round(a[2] / 1e6, 1), a[3], a[4], a[5], a[6]])
    widths = [20, 9, 11, 13, 11, 10, 10, 11]
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = "B2"


def versions_sheet(wb, ver, rows):
    ws = wb.create_sheet("版本记录")
    head = ["构件名", "构件类别", "版本", "日期", "类型", "说明", "是否当前"]
    ws.append(head)
    style_head(ws, head)
    by_name = {d["key"]: d for d in rows}
    for k, v in ver["components"].items():
        d = by_name.get(k)
        if not d:
            continue
        for it in v["versions"]:
            ws.append([v["name"], d["cat"], it["v"], it["date"], it["kind"],
                       it["note"], "是" if it["v"] == v["current"] else ""])
    widths = [30, 17, 7, 12, 10, 62, 9]
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = "A2"


ASKS = [
    ("A", "轮船的船体与舱壁",
     "93 个构件里大部分是夜间暗部，restyle 只把明度压成墨，形状保住了但笔触没有。"
     "章节截图已确认这一点（船壳、木栈道、集装箱在实机里都是平涂深色）。",
     "船体与船舱整类走 ImageGen 重绘，restyle 只留作对齐用的底稿。",
     "是否同意整类重绘？还是先挑 3-5 个最大的试画，看过效果再定？"),
    ("B", "重绘清单怎么划",
     "1450 个构件里，320 个（22%）占了全游戏 85% 的像素。剩下 1130 个加起来不到 15%，"
     "而且大多是酒瓶、玻璃碴、小招牌这类一眼扫过的东西。",
     "按面积分三档：P1 重绘 ≥1.0 Mpx（319 个）、P2 待核 0.25–1.0 Mpx（336 个）、"
     "P3 换色阶 <0.25 Mpx（794 个）。表里已经标好。",
     "这个分档线认可吗？特别是 0.25 Mpx 那条：低于它的 794 个我打算全部用换色阶，不重画。"),
    ("C", "章节选择卡（12 张）",
     "12 张 800×500 的章节卡是 NGUI 界面资源，画的就是关卡本身。"
     "只改关卡不改卡，进游戏会看到旧卡面配新关卡。",
     "和对应关卡的地标一起重绘，排在 T1 地标之后。",
     "是否同意把章节卡并入美术排期？"),
    ("D", "「选择标签栏」这个章节名",
     "第 10 章的名字显示为「选择标签栏」，实际场景是 secretLab、卡面标题是「月光屠杀」。"
     "这是一句界面文案漏进了章节名表，属于本地化 bug。",
     "改造时顺带改成「秘密实验室」，白送一个修 bug 的加分项。",
     "改，还是保持原样？"),
    ("E", "共享纹理的推进顺序",
     "Quay_05 这类贴图被 3 个关卡共用。按关卡推进会出现半新半旧的画面（现在已经发生）。",
     "按「共享组」为单位整组推进：一个组的所有关卡一起换。",
     "同意的话，下一步我出共享组清单和推进顺序。"),
    ("F", "全部 1450 个构件的替换口径",
     "目前每个构件都有一版 restyle（R1），轮船的 167 个已入包，其余 1283 个只是草稿。"
     "但 R1 是换色不是换内容 —— 上一版表格没有把这两件事分开，所以看上去全表都只是换色。",
     "按替换层级分流：T1 换内容（重绘）、T2 材质重画（换颜料）、T3 道具替换（换形制）、"
     "T4 只调色。层级和 P1/P2/P3 两套视角一起看：层级决定「改不改内容」，建议决定「多急」。",
     "这个分流方式认可吗？认可我就按 T4/T3 → T2 → T1 的顺序推进（先易后难，T1 最后做但要最用心）。"),
    ("G", "T1 这 160 张的目标形态",
     "「重绘清单 T1」页给每一行都写了目标形态（说形状、说材质、说该出现的历史物件）。"
     "这是第一次把「该变成什么」写出来，之前只有「脚本做了什么」。",
     "逐关逐类写死的，不是套话。比如河流的桥梁写「惠通桥单孔钢桁桥：桥面断口、坠江桥板、"
     "铆接桁梁」，轮船的船舱写「运兵舱铺板、枪架、担架吊带」。",
     "请重点看这一页。哪一行的目标写得不对或不够具体，直接在「备注」里写，我按你的改完再开工。"),
    ("H", "形态吻合度「弱」的两关怎么办",
     "12 关里有两关对不上：夜总会（L7）在真实战役里没有对应场景；屋顶+飞艇（L14）的飞艇"
     "要改轮廓才能变成 C-46。其余 10 关吻合度都是「强」以上。",
     "L7 做成「曼德勒英军俱乐部」插叙，不硬套战役名；L14 保留飞艇关卡玩法，把飞艇外形换成"
     "停机坪上的 C-46，塔台与机库顶重绘。",
     "这两关按上面处理，还是你有更合适的处理方式？"),
]


def verdict_dv(ws, col_letter, r1, r2):
    """判定列的下拉：待确认 / 确认OK。

    两个刻意的选择：

    * `showErrorMessage=False` —— 允许直接打字（比如写「要改：偏冷」）。
      下拉只是省事，不是限制；卡死在二选一，遇到"部分可以"反而没法记。
    * `showDropDown=None` —— 不写这个属性。OOXML 里它的语义是**反的**
      （写 1 表示隐藏箭头），有些阅读器按字面理解会把 0 当成"不显示"。
      不写就回到默认值，任何实现都不会理解错。
    """
    dv = DataValidation(type="list", formula1='"%s"' % ",".join(VERDICTS),
                        allow_blank=True, showErrorMessage=False,
                        showDropDown=None)
    dv.promptTitle = "判定"
    dv.prompt = "选「确认OK」= 这一行通过；选「待确认」= 还没定。也可以直接打字。"
    dv.showInputMessage = True
    ws.add_data_validation(dv)
    dv.add("%s%d:%s%d" % (col_letter, r1, col_letter, r2))


def asks_sheet(wb, answers):
    ws = wb.create_sheet("待确认")
    head = ["编号", "事项", "现状 / 问题", "我的建议", "需要你定的", "你的回答"]
    ws.append(head)
    style_head(ws, head)
    for a in ASKS:
        ws.append(list(a) + [answers.get(a[0]) or None])
    for r in range(2, ws.max_row + 1):
        for c in range(1, 7):
            cell = ws.cell(row=r, column=c)
            cell.font = Font(name="微软雅黑", size=10, color=INK)
            cell.alignment = Alignment(vertical="top", wrap_text=True)
        ws.row_dimensions[r].height = 84
        ws.cell(row=r, column=1).alignment = Alignment(horizontal="center",
                                                       vertical="center")
        ws.cell(row=r, column=5).fill = FILL_ASK
        ws.cell(row=r, column=6).fill = PatternFill("solid", fgColor="EAF1FA")
    widths = [7, 24, 58, 48, 40, 40]
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = "C2"


README = [
    ("这一版改了什么",
     "上一版的「替换图」一列，1450 行全部是 R1，而 R1 是 restyle —— 保剪影、只换颜色。"
     "所以整张表看上去就是「给原图换个色」，和说好的「用中国远征军的 12 个场景替换」不是一回事。"
     "这一版把两件事分开：新增「替换层级」列，T1 才是真的换内容（{n1} 张），"
     "其余是材质/道具/小件，本来就只该换色。新增「历史原型」和「目标形态」两列，"
     "回答「这块东西应该变成什么」，而不是「脚本对它做了什么」。"),
    ("这是什么", "《枪、血、黑手党》全部背景构件的替换总表。一行一个构件，"
              "左边是原图，右边是当前的 R1（换色版），两张同尺寸并排。"),
    ("替换层级", "T1 换内容 —— 每关绘制面积前 14 张，去重 {n1} 张，占画面 {p1}%。"
             "这一层决定「这是哪儿」，必须重绘成历史场景里的东西，形状可以变。"
             "T2 材质重画 —— 铺满画面的材质，不换构图，换颜料与笔触。"
             "T3 道具替换 —— 离散物件，换具体形制与年代。"
             "T4 只调色 —— 极小件，调色阶即可。"
             "表里按 T1→T4 排序，所以第一屏就是要重绘的那批。"),
    ("历史原型", "每个关卡对应哪个历史场景，来自 docs/CHAPTERS.md 的核准结果（用 mainData 的"
             "build settings 场景表 + 12 张章节卡贴图核对过，不是猜的）。"
             "注意：早先 SCENE_PLAN.md 里那套标签是按美术猜的，L3/L4/L5/L8/L13/L14 六关写错了，"
             "这一列用的是校正后的。"),
    ("目标形态", "这一列是可验收的重绘要求：说形状、说材质、说该出现的历史物件。"
             "T1 的 {n1} 行逐关逐类写死；T2/T3/T4 是通用口径（换颜料 / 换形制 / 调色阶）。"
             "如果你觉得某一行写得不对，直接写在「备注」里，我按你的改。"),
    ("怎么用", "先看「历史场景对照」页，确认 12 关的历史原型对不对（尤其形态吻合标「弱」的两关）。"
            "再看「重绘清单 T1」页，那 {n1} 张是真正要重画的，逐行看「目标形态」是否符合你的期望。"
            "最后在「构件总表」里按「替换层级」筛选复核其余构件。"
            "第 17 列「判定」是下拉，第 18 列「备注」写意见，第 19–23 列是疑问栏，"
            "我下次生成时会把这些全读回来，不会丢。"),
    ("判定怎么填", "第 17 列「判定（待确认 / 确认OK）」是下拉：待确认 / 确认OK。"
             "选「确认OK」的行我视为已通过，不再动它；选「待确认」的我继续跟进。"
             "下拉允许你直接打字（比如写「要改：偏冷」），它只是省事，不是限制。"
             "**如果看不到下拉箭头**：腾讯文档、部分在线预览不渲染数据验证，只显示单元格里的字。"
             "这种情况直接打字「确认OK」即可，效果完全一样 —— 我读的是文字，不是下拉状态。"),
    ("怎么提疑问", "第 19–23 列是「疑问1」到「疑问5」，一行给 5 个位置，别把几件事挤在一个格里。"
             "你在格子里写疑问，我下一版会在**同一格、你的疑问下面**用红字写答复，"
             "格式是「答复：……」，问题和答复永远在一起，翻查不会串行。"
             "答复正文存在 art/qa_answers.json，重建表格不会丢。"),
    ("行高", "为了两张缩略图能对齐，行高固定 77 磅，疑问格里的长文字可能显示不全。"
           "点单元格看编辑栏能读到全文，或者临时把行高拉大（不影响别的页）。"),
    ("待确认页", "最后一列「你的回答」是留给你写 A–H 八个问题的回答的。"
             "填完跟我说一声，我读回来按你的决定推进。"),
    ("关卡名", "全部用章节选择界面上的中文名：轮船、暴徒镇港口、市郊、暗黑小巷、"
            "博尼诺的脱衣舞夜总会、军团据点、河流、下水道、存储器、选择标签栏、"
            "建筑工地、屋顶。不再用 L3/L4 这种内部编号。"),
    ("图层", "背景 = 本项目要替换的；角色 / 武器 / UI = 其他流水线在做，"
           "列在这里只为让画面完整，可以忽略。特效 = 火、烟、水花、电，需要单独排期。"),
    ("版本", "R = restyle（脚本换色阶，保留原明度和轮廓）；G = 重绘（真的重画：白描底稿 → "
           "模型上色 → 回贴原图 L* 与 alpha）；H = 手工修版。数字是第几版。"
           "表里只显示最新版，历史版本见「版本记录」页。G1 已经在逐关铺开，"
           "「状态」列写「已重绘（G1）」的就是已经出图的那批。"),
    ("暗部占比", "该构件自己有多少像素落在 L* 25 以下。全表中位数 78% —— 这个游戏整体就是暗的，"
             "所以这个数只能参考，不能单独当判据。它真正有用的时候是看单个构件："
             "暗部占比越接近 100%，restyle 出来的就越接近平涂剪影。"),
    ("覆盖率", "替换后色相真正移动超过 2 的像素比例。中位数 69%，说明 restyle 确实大面积改了色 ——"
             "但改了色不等于换了内容。"),
    ("我的建议", "按面积分三档：P1 重绘（≥1.0 Mpx）、P2 待核（0.25–1.0 Mpx）、"
             "P3 换色阶（<0.25 Mpx）。它和「替换层级」是两套视角："
             "层级说的是「该不该换内容」，建议说的是「多急」。"
             "一个 T2 大材质可能是 P1 急件，一个 T1 小地标可能是 P3 —— 两条一起看。"),
    ("状态", "已重绘（G1）= 真的重画过了，右边那张「现版」图就是重绘结果。"
           "待重绘（R1 仅底色）= T1，R1 只是对齐用的底色，还没有真正重画。"
           "已入包（R1 换色）= 已写进游戏资源包并验证过，但只是换色版（目前只有轮船的 167 个）。"
           "草稿（R1 换色）= 有换色版但还没写进游戏。"),
    ("尺寸", "原始纹理尺寸。面积大的构件在画面里占比大，优先处理。"),
    ("注意", "同一张纹理可能被多个关卡共用（比如红砖码头 Quay_05 被轮船、暴徒镇港口、"
           "市郊三关共用）。所以替换必须整组推进，否则会出现半新半旧的画面。"),
]


def readme(wb, rows, tiers):
    ws = wb.create_sheet("说明", 0)
    ws.column_dimensions["A"].width = 16
    ws.column_dimensions["B"].width = 118
    ws["A1"] = "背景构件替换总表"
    ws["A1"].font = Font(name="微软雅黑", size=18, bold=True, color=HEAD_BG)
    ws["B1"] = "%d 个构件 · 13 个关卡 · 生成于 2026-10-23" % len(rows)
    ws["B1"].font = Font(name="微软雅黑", size=10, color=MUT)
    ws.row_dimensions[1].height = 30

    # 总账放最前面：一句话说清"换内容"和"只换色"各占多少
    tot_a = sum(d["area"] for d in rows) or 1
    led = []
    for t in ("T1", "T2", "T3", "T4"):
        sel = [d for d in rows if d["tier"] == t]
        a = sum(d["area"] for d in sel)
        led.append((t, len(sel), a))
    r = 3
    ws.cell(row=r, column=1, value="总账").font = Font(name="微软雅黑", size=11,
                                                   bold=True, color=HEAD_BG)
    r += 1
    for t, n, a in led:
        ws.cell(row=r, column=1, value=TIER_LABEL[t]).font = Font(
            name="微软雅黑", size=10, bold=t == "T1", color=INK)
        ws.cell(row=r, column=2,
                value="%d 张 · %.1f Mpx · 占画面 %.1f%% —— %s"
                      % (n, a / 1e6, a / tot_a * 100, TIER_NOTE[t])).font = Font(
            name="微软雅黑", size=10, color=INK if t == "T1" else MUT)
        ws.cell(row=r, column=2).fill = FILL_REDRAW if t == "T1" else PatternFill()
        r += 1

    r += 1
    n1 = sum(1 for d in rows if d["tier"] == "T1")
    a1 = sum(d["area"] for d in rows if d["tier"] == "T1") / tot_a * 100
    for k, v in README:
        v = v.format(n1=n1, p1="%.0f" % a1) if "{" in v else v
        a = ws.cell(row=r, column=1, value=k)
        a.font = Font(name="微软雅黑", size=10, bold=True, color=HEAD_BG)
        a.alignment = Alignment(vertical="top")
        b = ws.cell(row=r, column=2, value=v)
        b.font = Font(name="微软雅黑", size=10, color=INK)
        b.alignment = Alignment(vertical="top", wrap_text=True)
        ws.row_dimensions[r].height = 15 * (1 + len(v) // 54)
        r += 1
    r += 1
    # 疑问/答复的格式示例：真的用富文本，让用户先看见效果再动手写
    ws.cell(row=r, column=1, value="疑问格长这样").font = Font(
        name="微软雅黑", size=10, bold=True, color=HEAD_BG)
    demo = ws.cell(row=r, column=2,
                   value=QA.make("示例：这张桥的断口朝哪边？（你写的疑问是黑字）",
                                 "朝东岸。1942.5.5 炸桥时东侧先断，"
                                 "所以桥板朝东侧江面倾斜（我的答复是红字，永远在你下面）。"))
    demo.alignment = Alignment(vertical="top", wrap_text=True)
    demo.border = BOX
    ws.row_dimensions[r].height = 42
    r += 1
    ws.cell(row=r, column=1, value="页签").font = Font(name="微软雅黑", size=10,
                                                    bold=True, color=HEAD_BG)
    r += 1
    for name, desc in [("历史场景对照", "12 个章节各对应哪个历史场景，以及这一关要变成什么样"),
                       ("重绘清单 T1", "真正要换内容的那批，逐行写了目标形态 —— 先看这一页"),
                       ("构件总表", "全部构件，原图与 R1 并排，按替换层级排序"),
                       ("按关卡汇总", "每关有多少 T1/T2/T3/T4"),
                       ("按类别汇总", "27 个类别各有多少、多少需要换内容"),
                       ("版本记录", "每个构件的版本历史"),
                       ("待确认", "需要你拍板的 8 件事，最后一列留给你写回答")]:
        ws.cell(row=r, column=1, value=name).font = Font(name="微软雅黑", size=10)
        ws.cell(row=r, column=2, value=desc).font = Font(name="微软雅黑", size=10,
                                                        color=MUT)
        r += 1


def style_head(ws, head):
    for c in range(1, len(head) + 1):
        cell = ws.cell(row=1, column=c)
        cell.font = Font(name="微软雅黑", size=10, bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor=HEAD_BG)
        cell.alignment = Alignment(horizontal="center", vertical="center",
                                   wrap_text=True)
    ws.row_dimensions[1].height = 28


if __name__ == "__main__":
    build()
