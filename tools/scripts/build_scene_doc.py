"""Build docs/SCENE_LAYERS.html -- the reviewable scene-layer catalog.

Reads art/scene_inventory.json (names, sizes, painted area, renderer counts,
sorting orders) plus the sheets produced by scene_sheets.py / scene_render.py,
and emits one page:

    overview stats -> how to read the layers -> batch table -> one section per
    level (composited panorama + per-texture contact sheet + top-10 table)
    -> FX -> UI -> technique probe -> file list

Previews are written to art/scene_sheets/preview/ capped at 1400 px wide.  The
full-size sheets stay one click away, so the page itself stays a few MB instead
of ~90 MB of PNG.
"""
import io
import json
import os
import sys
from collections import defaultdict

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ggc_assets import PROJECT  # noqa: E402

ART = os.path.join(PROJECT, "art")
SHEETS = os.path.join(ART, "scene_sheets")
PREV = os.path.join(SHEETS, "preview")
DOC = os.path.join(PROJECT, "docs", "SCENE_LAYERS.html")

ORDER = ["level0"] + [f"level{i}" for i in range(3, 15)]

CSS = """
:root{--bg:#17171b;--card:#23232a;--card2:#2b2b33;--ink:#e8e8ee;--dim:#9a9ca8;
--acc:#d6a860;--line:#3a3a44;--red:#c05a4a;--grn:#5f9e6a}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
font:15px/1.65 -apple-system,"Segoe UI","Microsoft YaHei",sans-serif}
.wrap{max-width:1240px;margin:0 auto;padding:40px 28px 80px}
h1{font-size:30px;margin:0 0 6px;letter-spacing:.5px}
h2{font-size:22px;margin:0 0 4px}
h3{font-size:17px;margin:34px 0 10px;color:var(--acc)}
h4{font-size:14px;margin:0 0 8px;color:var(--dim);font-weight:600}
.sub{color:var(--dim);margin:0 0 26px}
.cards{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin:24px 0 30px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:16px 18px}
.card b{display:block;font-size:26px;color:var(--acc);letter-spacing:.5px}
.card span{color:var(--dim);font-size:13px}
.note{background:var(--card);border-left:3px solid var(--acc);border-radius:6px;
padding:14px 18px;margin:18px 0}
.note p{margin:6px 0}
table{width:100%;border-collapse:collapse;font-size:13.5px;margin:12px 0 6px}
th,td{text-align:left;padding:7px 9px;border-bottom:1px solid var(--line)}
th{color:var(--dim);font-weight:600;font-size:12.5px;letter-spacing:.3px}
td.num,th.num{text-align:right;font-variant-numeric:tabular-nums}
tr:hover td{background:#282830}
code,.mono{font-family:Consolas,monospace;font-size:12.5px;color:#c9d1d9}
.lv{background:var(--card);border:1px solid var(--line);border-radius:12px;
padding:22px 24px;margin:26px 0}
.tag{font:12px Consolas,monospace;color:var(--dim);background:#1b1b21;
border:1px solid var(--line);border-radius:4px;padding:2px 7px;margin-left:8px}
.meta{color:var(--dim);font-size:13.5px;margin:8px 0 14px}
.meta b{color:var(--ink);font-weight:600}
.shot{display:block;background:#0d0d10;border:1px solid var(--line);
border-radius:8px;overflow:hidden;margin:10px 0}
/* width:auto + max-width keeps a narrow sheet (level0 has 2 cells) at native
   size instead of stretching it to 1240 px and blurring the art */
.shot img{display:block;max-width:100%;width:auto;height:auto;margin:0 auto}
.cap{font-size:12.5px;color:var(--dim);margin:6px 0 16px}
.pair{display:grid;grid-template-columns:1fr 320px;gap:16px;align-items:start}
.small img{width:100%;display:block}
ol,ul{padding-left:20px}
li{margin:3px 0}
a{color:var(--acc);text-decoration:none}
a:hover{text-decoration:underline}
.pill{display:inline-block;font-size:11.5px;padding:1px 7px;border-radius:10px;
background:#33333d;color:var(--dim);margin-left:6px}
.warn{border-left-color:var(--red)}
.ok{border-left-color:var(--grn)}
"""


def prev(path, maxw=1400, quality=88):
    """Preview copy capped at maxw, written as JPEG.

    PNG is the wrong format here: these sheets are dark gradients with lots of
    text, so PNG runs to 2-4 MB each and 26 of them make a 44 MB page.  JPEG at
    q88 is ~250 KB for the same picture and the page becomes usable.  Nothing in
    this catalog needs alpha -- the sheets already composite onto a solid
    background.
    """
    if not os.path.isfile(path):
        return None
    os.makedirs(PREV, exist_ok=True)
    out = os.path.join(PREV, os.path.splitext(os.path.basename(path))[0] + ".jpg")
    if not os.path.isfile(out) or os.path.getmtime(out) < os.path.getmtime(path):
        im = Image.open(path).convert("RGB")
        if im.width > maxw:
            im = im.resize((maxw, round(im.height * maxw / im.width)), Image.LANCZOS)
        im.save(out, quality=quality, optimize=True, progressive=True)
    return "../art/scene_sheets/preview/" + os.path.basename(out)


def main():
    rows = json.load(io.open(os.path.join(ART, "scene_inventory.json"), encoding="utf-8"))
    # batches are keyed by id ("L3") but the inventory is keyed by level name
    # ("level3"); keep both maps or the theme column silently renders "?".
    batches = {b["id"]: b for b in
               json.load(io.open(os.path.join(ART, "scene_batches.json"), encoding="utf-8"))}
    by_level = {b["level"]: b for b in batches.values()}
    total_px = sum(r["painted"] for r in rows)
    total_wh = sum(r["area"] for r in rows)
    total_sr = sum(r["renderers"] for r in rows)
    shared = [r for r in rows if len(r["levels"]) > 1]

    per = defaultdict(lambda: {"n": 0, "p": 0, "sr": 0, "ord": set(), "rows": []})
    for r in rows:
        for lv in r["levels"]:
            d = per[lv]
            d["n"] += 1
            d["p"] += r["painted"]
            d["sr"] += r["renderers"]
            d["ord"].update(r["orders"])
            d["rows"].append(r)

    h = []
    h.append(f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<title>场景图层清单 — Guns, Gore and Cannoli 重彩化</title><style>{CSS}</style></head><body><div class="wrap">
<h1>场景图层清单</h1>
<p class="sub">Guns, Gore and Cannoli · Unity 4.3.4f1 · 全部 SpriteRenderer 场景图层 ·
按关卡分批 · 附名称与样图</p>

<div class="cards">
  <div class="card"><b>{len(rows)}</b><span>张场景纹理（去重）</span></div>
  <div class="card"><b>{total_px / 1e6:.0f} Mpx</b><span>有效绘制面积（非透明像素）</span></div>
  <div class="card"><b>{total_sr:,}</b><span>渲染实例（同一张图的复用）</span></div>
  <div class="card"><b>13</b><span>关卡批次 + FX + UI</span></div>
</div>

<div class="note">
<p><b>怎么读这份清单。</b>每个关卡一张<b>合成全景</b>（按 sortingOrder 把该关所有
SpriteRenderer 叠起来，这就是关卡实际长什么样），加一张<b>逐图缩略表</b>
（名称 / 尺寸 / 引用次数，按绘制面积排序）。全景里被裁掉的极端离群物件不会出现在
缩略表之外，缩略表才是完整清单。</p>
<p><b>为什么按关卡分批。</b>纹理名离开场景没有意义（<code>Part3Front_12</code> 只有
放在 level8 才读得懂），而美术本身也是按场景画的。</p>
<p><b>去重口径。</b>{len(shared)} 张纹理被多个关卡共用，会同时出现在多张缩略表里；
工作量按去重的 {len(rows)} 张算，不按各表相加的 {sum(d['n'] for d in per.values())} 行算。</p>
</div>

<h3>1. 分层结构（sortingOrder）</h3>
<p class="sub" style="margin-top:-6px">整数排序层，负数在最里侧（远景/视差），
0 附近是建筑与地面，正数是前景遮挡与光照叠加。层数越多，视差越细。</p>
<table><thead><tr><th>批次</th><th>主题</th><th class="num">纹理</th><th class="num">有效绘制</th>
<th class="num">实例</th><th class="num">sortingOrder</th><th class="num">层数</th></tr></thead><tbody>""")

    for lv in ORDER:
        if lv not in per:
            continue
        d = per[lv]
        o = sorted(d["ord"])
        h.append(f"<tr><td><a href='#{lv}'>{lv.replace('level', 'L')}</a></td>"
                 f"<td>{by_level.get(lv, {}).get('theme', '?')}</td>"
                 f"<td class='num'>{d['n']}</td><td class='num'>{d['p'] / 1e6:.1f} M</td>"
                 f"<td class='num'>{d['sr']:,}</td>"
                 f"<td class='num'>{o[0]} … {o[-1]}</td><td class='num'>{len(o)}</td></tr>")
    fx = batches.get("FX", {})
    ui = batches.get("UI", {})
    h.append(f"<tr><td>FX</td><td>粒子层</td><td class='num'>{fx.get('textures', 0)}</td>"
             f"<td class='num'>—</td><td class='num'>810</td><td class='num'>—</td>"
             f"<td class='num'>—</td></tr>")
    h.append(f"<tr><td>UI</td><td>NGUI 图集</td><td class='num'>{ui.get('textures', 0)}</td>"
             f"<td class='num'>—</td><td class='num'>—</td><td class='num'>—</td>"
             f"<td class='num'>—</td></tr></tbody></table>")

    # ---------------------------------------------------------------- levels
    h.append("<h3>2. 分批清单（每关：合成全景 + 逐图缩略表）</h3>")
    for lv in ORDER:
        if lv not in per:
            continue
        d = per[lv]
        o = sorted(d["ord"])
        bid = lv.replace("level", "L")
        theme = by_level.get(lv, {}).get("theme", "?")
        h.append(f"<section class='lv' id='{lv}'><h2>{bid} {theme}"
                 f"<span class='tag'>{lv}</span></h2>")
        h.append(f"<div class='meta'><b>{d['n']}</b> 张纹理 · "
                 f"<b>{d['p'] / 1e6:.1f}</b> Mpx 有效绘制 · "
                 f"<b>{d['sr']:,}</b> 实例 · sortingOrder <b>{o[0]}…{o[-1]}</b>"
                 f"（{len(o)} 层）</div>")

        strip = prev(os.path.join(SHEETS, f"scene_{lv}_rows.png"))
        full = f"../art/scene_sheets/scene_{lv}_rows.png"
        if strip is None:
            # narrow levels (level0) are not split, so only the plain strip exists
            strip = prev(os.path.join(SHEETS, f"scene_{lv}.png"))
            full = f"../art/scene_sheets/scene_{lv}.png"
        if strip:
            h.append(f"<a class='shot' href='{full}'><img src='{strip}' "
                     f"alt='{lv} panorama'></a>")
            h.append("<div class='cap'>合成全景 — 全部可见 SpriteRenderer 按 sortingOrder "
                     "叠加，alpha 混合，含 m_Color 着色。宽图已折成数行；点击看原始尺寸。</div>")

        # A 2012 px index sheet cannot be read inside a 1240 px page, so the
        # inline sheet is the 24-cell "largest layers" version (260 px cells,
        # legible at full page width) and the full index is one click away.
        topsheet = prev(os.path.join(SHEETS, f"{lv}_top.png"), maxw=1400)
        if topsheet and d["n"] > 24:
            # skipped when the level has <= 24 textures: the "top 24" would just
            # be the whole index again, rendered as a narrow strip
            h.append("<h4 style='margin:18px 0 6px'>主要图层 — 绘制面积前 24</h4>")
            h.append(f"<a class='shot' href='../art/scene_sheets/{lv}_top.png'>"
                     f"<img src='{topsheet}' alt='{lv} top 24'></a>")
            h.append("<div class='cap'>格内标签为 painted（有效绘制面积）。"
                     f"完整 {d['n']} 张见 <a href='../art/scene_sheets/{lv}.png'>"
                     f"逐图缩略表 {lv}.png</a>（2012px，含名称与尺寸）。</div>")

        top = sorted(d["rows"], key=lambda r: -r["painted"])[:12]
        h.append("<h4>绘制面积最大的 12 张</h4><table><thead><tr>"
                 "<th>纹理</th><th class='num'>尺寸</th><th class='num'>painted</th>"
                 "<th class='num'>引用</th></tr></thead><tbody>")
        for r in top:
            w, hh = r["size"]
            h.append(f"<tr><td class='mono'>{r['texture']}</td>"
                     f"<td class='num'>{w}×{hh}</td>"
                     f"<td class='num'>{r['painted'] / 1e6:.2f} M</td>"
                     f"<td class='num'>×{r['renderers']}</td></tr>")
        h.append("</tbody></table>")
        h.append("</section>")

    # ------------------------------------------------------------------- fx/ui
    for key, title, note in (
            ("FX", "3. FX 粒子层",
             "8 张粒子材质贴图，被 810 个 ParticleSystemRenderer、12 个材质共用。"
             "建议改调色板/Shader 着色，不重画。"),
            ("UI", "4. UI 图层（NGUI）",
             "UI 不走 SpriteRenderer，是 Material 引用的图集页，所以不在上面的统计里。"
             "11 张，独立小批次。")):
        if key not in batches:
            continue
        h.append(f"<h3>{title}</h3><p class='sub' style='margin-top:-6px'>{note}</p>")
        p = prev(os.path.join(SHEETS, f"{key.lower()}.png"))
        if p:
            h.append(f"<a class='shot' href='../art/scene_sheets/{key.lower()}.png'>"
                     f"<img src='{p}'></a>")

    # -------------------------------------------------------------- technique
    h.append("""<h3>5. 技术路线验证：程序化重彩为什么不能直接用</h3>
<div class="note warn"><p>把角色用的 <code>restyle_ink</code> 直接套到场景层上，
默认规则是 garment（石青+石绿），砖墙会变成蓝绿马赛克。它的槽位语义是为角色设计的
（skin / garment / hat / weapon），场景需要一套自己的规则：按明度分层决定墨与赭石，
只在暗部上石青，并叠加纸纹。</p></div>""")
    p = prev(os.path.join(SHEETS, "probe_restyle.png"), 1100)
    if p:
        h.append(f"<a class='shot' href='../art/scene_sheets/probe_restyle.png'>"
                 f"<img src='{p}'></a>")

    h.append("""<h3>6. 交付物</h3>
<table><tbody>
<tr><td class="mono">art/scene_inventory.json</td><td>1450 行结构化清单：名称、文件、path_id、尺寸、fill、painted、引用次数、关卡、sortingOrder、GameObject 名</td></tr>
<tr><td class="mono">art/scene_inventory.csv</td><td>同上的表格版，可直接在 Excel 里筛选</td></tr>
<tr><td class="mono">art/scene_sheets/level*.png</td><td>13 张逐图缩略表</td></tr>
<tr><td class="mono">art/scene_sheets/scene_level*.png</td><td>13 张合成全景（另附 <code>_rows</code> 折行版）</td></tr>
<tr><td class="mono">art/scene_sheets/top_backdrops.png</td><td>面积最大的 48 张，用于定风格基调</td></tr>
<tr><td class="mono">art/scene_sheets/fx.png · ui.png</td><td>粒子层与 UI 图集</td></tr>
<tr><td class="mono">tools/scripts/scene_survey.py</td><td>按关卡统计对象类型</td></tr>
<tr><td class="mono">tools/scripts/scene_textures.py</td><td>走 PPtr 建清单</td></tr>
<tr><td class="mono">tools/scripts/scene_stats.py</td><td>算 fill / painted 有效面积</td></tr>
<tr><td class="mono">tools/scripts/scene_sheets.py</td><td>出缩略表</td></tr>
<tr><td class="mono">tools/scripts/scene_render.py</td><td>合成全景（Transform 链 + alpha 混合 + m_Color）</td></tr>
</tbody></table>
<p class="sub" style="margin-top:24px">生成于 Guns, Gore and Cannoli 美术替换项目 · 数据源 ggc_Data（场景层未打补丁，读取即原始美术）</p>
</div></body></html>""")

    with io.open(DOC, "w", encoding="utf-8") as fh:
        fh.write("\n".join(h))
    print(f"-> {DOC}  ({os.path.getsize(DOC) / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
