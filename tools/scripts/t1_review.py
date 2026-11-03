# -*- coding: utf-8 -*-
"""T1 重绘评审页 —— 把一批 T1 重绘做成一张可点的表。

为什么做成 HTML 而不是一堆 PNG
------------------------------
14 个构件 × 3 张图（原图 / 白描底稿 / G1 结果）= 42 张图。摊在文件夹里
没法比。做成一张表，每行一个构件：左边分数，中间三张图并排，
肉眼看"结构有没有跟住、颜色对不对"。

图直接以 base64 内嵌（缩到 320px 的 JPEG），所以这个 HTML 可以单独发给别人，
不会因为图丢了变成一堆空框。

用法
----
    python t1_review.py --level level9
    python t1_review.py --level level9 --out docs/T1重绘评审_level9.html
"""
import argparse
import base64
import datetime
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ggc_assets import PROJECT  # noqa: E402
from PIL import Image  # noqa: E402

ART = os.path.join(PROJECT, "art")
INV = os.path.join(ART, "scene_inventory.json")
DOCS = os.path.join(PROJECT, "docs")

THUMB_W = 320


def load_json(p, default=None):
    if os.path.exists(p):
        return json.load(io.open(p, encoding="utf-8"))
    return default if default is not None else {}


def b64_thumb(path, max_w=THUMB_W):
    """读图 -> 缩放 -> 白底合成 -> base64 JPEG。读不到返回 None。"""
    if not path or not os.path.exists(path):
        return None
    try:
        im = Image.open(path)
        if im.mode != "RGBA":
            im = im.convert("RGBA")
        w, h = im.size
        if w > max_w:
            im = im.resize((max_w, max(1, int(h * max_w / w))), Image.LANCZOS)
        bg = Image.new("RGB", im.size, (28, 26, 23))
        bg.paste(im, (0, 0), im)
        buf = io.BytesIO()
        bg.save(buf, "JPEG", quality=80)
        return "data:image/jpeg;base64," + \
            base64.b64encode(buf.getvalue()).decode("ascii")
    except Exception:
        return None


def latest_by_name(entries):
    """同名构件取最后一次尝试的结果（重跑会追加新条目）。"""
    out = {}
    for e in entries:
        if "edge" in e:
            out[e["name"]] = e
    return out


def build(level):
    rep_path = os.path.join(ART, "gen", "t1", level, "t1_report.json")
    entries = load_json(rep_path)
    if not entries:
        print("没有报告:", rep_path)
        return None
    res = latest_by_name(entries)
    inv = load_json(INV, [])
    tier_note = {}
    for r in inv:
        tier_note.setdefault(r["texture"], "%d×%d" % tuple(r["size"]))

    rows = []
    for name, e in res.items():
        d = os.path.join(ART, "gen", "t1", level)
        rows.append({
            "name": name,
            "size": tier_note.get(name, "?"),
            "goal": e.get("goal", ""),
            "edge": e.get("edge"), "sil": e.get("silhouette"),
            "pig": e.get("pigment"),
            "cover": e.get("cover"), "holes": e.get("holes"),
            "passed": bool(e.get("passed")),
            "verdict": e.get("verdict", ""),
            "alpha": e.get("alpha_identical"),
            "orig": b64_thumb(os.path.join(d, "%s_orig.png" % name)),
            "line": b64_thumb(os.path.join(d, "%s_lineart.png" % name)),
            "gen": b64_thumb(os.path.join(d, "%s_G1.png" % name)),
        })
    rows.sort(key=lambda r: (not r["passed"], -(r["edge"] or 0)))
    return rows


CSS = """
*{box-sizing:border-box}
body{margin:0;background:#14130F;color:#EDE7D9;
 font:14px/1.6 "Microsoft YaHei",-apple-system,"Segoe UI",sans-serif}
.wrap{max-width:1500px;margin:0 auto;padding:28px 24px 60px}
h1{font-size:22px;margin:0 0 6px;font-weight:600;letter-spacing:.5px}
.sub{color:#9A9284;font-size:13px;margin-bottom:20px}
.sum{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:22px}
.pill{border:1px solid #3A352C;border-radius:999px;padding:6px 14px;font-size:12.5px;
 background:#1C1A16;color:#C9C0AF}
.pill b{color:#F2E9D6;font-weight:600}
.pill.ok{border-color:#3E5B3C;background:#1B2419;color:#A9C79E}
.pill.no{border-color:#6B3B32;background:#261A17;color:#DDA294}
table{width:100%;border-collapse:collapse;background:#1A1815;
 border:1px solid #2E2A23;border-radius:10px;overflow:hidden}
th{background:#232019;color:#CFC6B4;font-weight:600;font-size:12.5px;
 text-align:left;padding:10px 12px;border-bottom:1px solid #33302A;white-space:nowrap}
td{padding:12px;border-bottom:1px solid #262320;vertical-align:top}
tr:last-child td{border-bottom:none}
tr.bad{background:#201815}
.nm{font-weight:600;font-size:14px;color:#F2E9D6;margin-bottom:4px}
.sz{color:#8E8778;font-size:12px}
.goal{color:#A79E8C;font-size:12px;margin-top:6px;max-width:260px}
.sc{font-variant-numeric:tabular-nums;font-size:12.5px;line-height:1.9}
.sc b{color:#F2E9D6}
.sc .lo{color:#D08A6A}
.sc .hi{color:#8FBF7A}
.badge{display:inline-block;border-radius:4px;padding:2px 8px;font-size:11.5px;
 font-weight:600;margin-top:6px}
.badge.ok{background:#2C4029;color:#A9C79E}
.badge.no{background:#4A2A23;color:#E0A08F}
.imgs{display:flex;gap:10px}
figure{margin:0;text-align:center}
figure img{display:block;border:1px solid #2E2A23;border-radius:6px;
 background:#0E0D0B;max-width:100%}
figcaption{color:#8E8778;font-size:11px;margin-top:5px}
.pill2{color:#F2E9D6}
"""

HTML = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<title>T1 重绘评审 · {level}</title><style>{css}</style></head>
<body><div class="wrap">
<h1>T1 重绘评审 · {level}（{cn}）</h1>
<div class="sub">生成于 {date} · 白描底稿 → Qwen-Image-Edit-2509 上色 → 回贴原图 L* 与 alpha ·
每行三张：原图 / 白描底稿 / G1 结果。分数由 fidelity.py 自动判定（edge 门限 0.40）。</div>
<div class="sum">{summary}</div>
<table><thead><tr>
<th>构件</th><th>目标形态</th><th>保真度</th><th>判定</th><th>原图 / 白描底稿 / G1 结果</th>
</tr></thead><tbody>{rows}</tbody></table>
</div></body></html>
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--level", default="level9")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    from component_taxonomy import LEVEL_CN
    cn = LEVEL_CN.get(args.level, args.level)

    rows = build(args.level)
    if not rows:
        return
    ok = sum(1 for r in rows if r["passed"])
    no = len(rows) - ok
    summary = (
        '<div class="pill">构件 <b>%d</b></div>'
        '<div class="pill ok">达标 <b>%d</b></div>'
        '<div class="pill no">未达标 <b>%d</b></div>'
        '<div class="pill">门槛 edge ≥ 0.40 / 空洞 holes ≤ 0.06 / 颜料 pig ≥ 0.30</div>'
    ) % (len(rows), ok, no)

    trs = []
    for r in rows:
        figs = []
        for src, cap in ((r["orig"], "原图"), (r["line"], "白描底稿"),
                         (r["gen"], "G1 结果")):
            if src:
                figs.append('<figure><img src="%s"><figcaption>%s</figcaption></figure>'
                            % (src, cap))
            else:
                figs.append('<figure><figcaption style="padding-top:60px">%s 缺失</figcaption>'
                            '</figure>' % cap)
        e = r["edge"] or 0
        p = r["pig"] or 0
        cov = r["cover"] if r["cover"] is not None else 0
        ho = r["holes"] if r["holes"] is not None else 0
        sc = ('<div class="sc">'
              'edge <b class="pill2">%.3f</b><br>' % e +
              '颜料 pig <b class="pill2">%.3f</b><br>' % p +
              '精灵覆盖 <b class="pill2">%.3f</b><br>' % cov +
              '空洞 holes <b class="pill2">%.3f</b><br>' % ho +
              'alpha 逐位一致：<b>%s</b></div>' % ("是" if r["alpha"] else "否"))
        trs.append(
            '<tr class="%s">'
            '<td><div class="nm">%s</div><div class="sz">%s</div></td>'
            '<td><div class="goal">%s</div></td>'
            '<td>%s</td>'
            '<td><span class="badge %s">%s</span></td>'
            '<td><div class="imgs">%s</div></td></tr>'
            % ("bad" if not r["passed"] else "", r["name"], r["size"], r["goal"],
               sc, "ok" if r["passed"] else "no",
               "通过" if r["passed"] else "未达标", "".join(figs)))

    html = HTML.format(level=args.level, cn=cn, css=CSS, summary=summary,
                       date=datetime.date.today().isoformat(),
                       rows="".join(trs))
    out = args.out or os.path.join(DOCS, "T1重绘评审_%s.html" % args.level)
    with io.open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print("评审页 -> %s  (%.1f MB, %d 个构件, 达标 %d)"
          % (out, os.path.getsize(out) / 1e6, len(rows), ok))


if __name__ == "__main__":
    main()
