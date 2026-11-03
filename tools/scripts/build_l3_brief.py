"""Render docs/L3_RANGOON_BRIEF.html from the hand-written briefs.

Content lives in l3_brief_data.py (read off the actual textures, one by one);
this file only extracts pixels, builds the page and emits the machine-readable
JSON the generation step will consume.

Why the landmark set is chosen by role, not by area
--------------------------------------------------
L3's largest textures are almost all `Boat*` cabin pages -- 13 of the top 14 are
1024x1024 full-frame interiors, so a blind area cut gives thirteen variants of
the same room and no landmarks.  l3_brief_data.BRIEF picks one texture per role
instead: far parallax, cranes, quay, riveted bulkhead, porthole bulkhead, hold,
radio room, engine room, upper deck.

Outputs
-------
    docs/L3_RANGOON_BRIEF.html
    art/l3_brief/<name>.png      full-size original, the working reference
    art/l3_brief/<name>.jpg      520 px preview used by the page
    art/l3_brief.json            same briefs, machine-readable
"""
import io
import json
import os
import sys

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ggc_assets import AssetDB, DATA, PROJECT  # noqa: E402
from l3_brief_data import BRIEF, INTRO  # noqa: E402

ART = os.path.join(PROJECT, "art")
OUT = os.path.join(ART, "l3_brief")
DOC = os.path.join(PROJECT, "docs", "L3_RANGOON_BRIEF.html")

STYLE = ("风格：重彩国画，中等笔触，赭石与墨为主色，石青只进暗部，"
         "宣纸纤维可见，边缘有墨线勾勒")

CSS = """
:root{--bg:#17171b;--card:#23232a;--ink:#e8e8ee;--dim:#9a9ca8;--acc:#d6a860;
--line:#3a3a44;--red:#c05a4a;--grn:#5f9e6a}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
font:15px/1.65 -apple-system,"Segoe UI","Microsoft YaHei",sans-serif}
.wrap{max-width:1180px;margin:0 auto;padding:40px 28px 80px}
h1{font-size:29px;margin:0 0 6px}
h2{font-size:20px;margin:0 0 2px}
h3{font-size:16px;margin:30px 0 10px;color:var(--acc)}
.sub{color:var(--dim);margin:0 0 22px}
.note{background:var(--card);border-left:3px solid var(--acc);border-radius:6px;
padding:13px 17px;margin:14px 0}
.note p{margin:5px 0}
.note.warn{border-left-color:var(--red)}
table{width:100%;border-collapse:collapse;font-size:13.5px;margin:8px 0}
th,td{text-align:left;padding:6px 9px;border-bottom:1px solid var(--line);vertical-align:top}
th{color:var(--dim);font-size:12.5px;font-weight:600;white-space:nowrap}
td.num,th.num{text-align:right;font-variant-numeric:tabular-nums}
code,.mono{font-family:Consolas,monospace;font-size:12.5px;color:#c9d1d9}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;
padding:20px 22px;margin:20px 0}
.tag{font:12px Consolas,monospace;color:var(--dim);background:#1b1b21;
border:1px solid var(--line);border-radius:4px;padding:2px 7px;margin-left:8px}
.role{color:var(--acc);font-size:13px;margin:6px 0 12px}
.grid{display:grid;grid-template-columns:520px 1fr;gap:18px;align-items:start}
.shot{background:#0d0d10;border:1px solid var(--line);border-radius:8px;overflow:hidden;
display:block}
.shot img{display:block;width:100%;height:auto}
.prompt{background:#15151a;border:1px solid var(--line);border-left:3px solid var(--grn);
border-radius:6px;padding:11px 14px;margin:10px 0;font-size:13.5px;line-height:1.6;
color:#cfd6cf;white-space:pre-wrap;font-family:Consolas,"Microsoft YaHei",monospace}
.k{color:var(--dim);font-size:12px;letter-spacing:.4px;display:block;margin-bottom:2px}
ul{padding-left:18px;margin:4px 0}
li{margin:2px 0}
a{color:var(--acc);text-decoration:none}
.pill{display:inline-block;font-size:11.5px;padding:1px 8px;border-radius:10px;
background:#33333d;color:var(--dim);margin-left:6px}
.pill.sh{background:#333a2c;color:#a8c48a}
.pill.col{background:#3d2626;color:#d08a7a}
"""


def main():
    os.makedirs(OUT, exist_ok=True)
    db = AssetDB(data_dir=DATA)
    rows = json.load(io.open(os.path.join(ART, "scene_inventory.json"), encoding="utf-8"))
    by_name = {}
    for r in rows:
        if "level3" in r["levels"]:
            by_name.setdefault(r["texture"], r)

    h = [f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<title>L3 仰光港 · 14 张地标改造 brief</title><style>{CSS}</style></head><body><div class="wrap">
<h1>L3 仰光港 · 14 张地标改造 brief</h1>
<p class="sub">第一关 · 1942.3 登船撤离 · 每张：现状 / 历史原型 / 必须保留 / 可改 / 生成提示</p>
{INTRO}
"""]

    out = []
    for i, name in enumerate(BRIEF, 1):
        role, now, hist, keep, change, prompt = BRIEF[name]
        r = by_name.get(name)
        if r is None:
            print(f"  ! {name} not in L3")
            continue
        obj = db.file_objs(r["file"]).get(r["path_id"])
        img = db.texture_image(obj)
        img.save(os.path.join(OUT, f"{name}.png"), optimize=True)
        im = img.convert("RGB")
        if im.width > 520:
            im = im.resize((520, round(im.height * 520 / im.width)), Image.LANCZOS)
        im.save(os.path.join(OUT, f"{name}.jpg"), quality=90, optimize=True,
                progressive=True)

        shared = [lv for lv in r["levels"] if lv != "level3"]
        pill = (f"<span class='pill sh'>共用 "
                f"{'/'.join(x.replace('level', 'L') for x in shared)}</span>"
                if shared else "")
        coll = ("<span class='pill col'>带碰撞 · 守轮廓</span>"
                if r.get("collider") else "")
        lo, hi = min(r["orders"]), max(r["orders"])
        rng = f"{lo}" if lo == hi else f"{lo}…{hi}"

        h.append(f"<section class='card'><h2>#{i:02d} {name}"
                 f"<span class='tag'>{r['size'][0]}×{r['size'][1]}</span>{pill}{coll}</h2>")
        h.append(f"<div class='role'>{role}</div>")
        h.append("<div class='grid'><div>")
        h.append(f"<a class='shot' href='../art/l3_brief/{name}.png'>"
                 f"<img src='../art/l3_brief/{name}.jpg'></a>")
        h.append("<table><tbody>"
                 f"<tr><th>painted</th><td class='num'>{r['painted'] / 1e6:.2f} Mpx</td></tr>"
                 f"<tr><th>fill</th><td class='num'>{r['fill']:.2f}</td></tr>"
                 f"<tr><th>引用</th><td class='num'>×{r['renderers']}</td></tr>"
                 f"<tr><th>order</th><td class='num'>{rng}</td></tr>"
                 f"<tr><th>来源</th><td class='mono'>{r['file']}#{r['path_id']}</td></tr>"
                 "</tbody></table></div><div>")
        h.append(f"<span class='k'>现状</span><p style='margin:0 0 12px'>{now}</p>")
        h.append(f"<span class='k'>历史原型</span><p style='margin:0 0 12px'>{hist}</p>")
        h.append(f"<span class='k'>必须保留</span><p style='margin:0 0 12px'>{keep}</p>")
        h.append(f"<span class='k'>可改</span><p style='margin:0 0 12px'>{change}</p>")
        h.append("<span class='k'>生成提示（配原图做 image-to-image）</span>"
                 f"<div class='prompt'>{prompt}\n{STYLE}。</div>")
        h.append("</div></div></section>")

        out.append({"index": i, "name": name, "role": role,
                    "file": r["file"], "path_id": r["path_id"],
                    "size": r["size"], "painted": r["painted"], "fill": r["fill"],
                    "renderers": r["renderers"], "orders": r["orders"],
                    "levels": r["levels"], "collider": bool(r.get("collider")),
                    "now": now, "history": hist, "keep": keep,
                    "change": change, "prompt": f"{prompt}\n{STYLE}。"})

    tot = sum(b["painted"] for b in out)
    h.append("<h3>汇总</h3><table><thead><tr><th>#</th><th>纹理</th><th>角色</th>"
             "<th class='num'>尺寸</th><th class='num'>painted</th><th class='num'>引用</th>"
             "<th>共用</th></tr></thead><tbody>")
    for b in out:
        sh = "/".join(x.replace("level", "L") for x in b["levels"] if x != "level3")
        h.append(f"<tr><td class='num'>{b['index']:02d}</td>"
                 f"<td class='mono'>{b['name']}</td><td>{b['role']}</td>"
                 f"<td class='num'>{b['size'][0]}×{b['size'][1]}</td>"
                 f"<td class='num'>{b['painted'] / 1e6:.2f} M</td>"
                 f"<td class='num'>×{b['renderers']}</td><td>{sh or '—'}</td></tr>")
    h.append(f"""</tbody></table>
<div class="note"><p>14 张合计 <b>{tot / 1e6:.1f} Mpx</b>，占 L3 全关（42.1 Mpx）的
<b>{tot / 42.1e6 * 100:.0f}%</b>。按 5–10 credits/张，这一关的地标重绘是
<b>{len(out) * 5}–{len(out) * 10} credits</b>。</p>
<p>其余 153 张走 T2 材质 / T3 道具的程序化路线，0 credits——但需要先把
<code>restyle_scene</code> 做出来。它是整个方案的成本支点。</p></div>
<p class="sub" style="margin-top:18px">数据：art/scene_inventory.json ·
机器可读版：art/l3_brief.json · 清单：docs/SCENE_LAYERS.html · 全局方案：docs/SCENE_PLAN.html</p>
</div></body></html>""")

    with io.open(DOC, "w", encoding="utf-8") as fh:
        fh.write("\n".join(h))
    with io.open(os.path.join(ART, "l3_brief.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    print(f"-> {DOC} ({os.path.getsize(DOC) / 1024:.0f} KB), {len(out)} briefs")


if __name__ == "__main__":
    main()
