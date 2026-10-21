"""Build the integrated character roster (HTML + Markdown + CSV).

Inputs
  tools/scripts/characters_meta.py      identity table (42 units)
  extracted/characters_v2/render_report.json   part counts / render status
  extracted/characters/asset_locations.json    sprite+texture location, dump hits
  extracted/names/level*.names.txt             which levels each prefab appears in

Outputs
  docs/CHARACTER_ROSTER.html    self-contained page, filterable, images embedded
  docs/CHARACTER_ROSTER.md      markdown table
  art/roster_reply_template.csv  one row per unit, ready for the art brief
"""
import os, io, sys, json, csv, base64, re, html
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from characters_meta import ROSTER, DOC_UNMATCHED

ROOT = r"D:\AI\DAIGuns, Gore and Cannoli from WB"
IMG = os.path.join(ROOT, "extracted", "characters")
DOCS = os.path.join(ROOT, "docs")
ART = os.path.join(ROOT, "art")
NAMES = os.path.join(ROOT, "extracted", "names")
os.makedirs(DOCS, exist_ok=True)
os.makedirs(ART, exist_ok=True)

FACTION_ORDER = {"玩家": 0, "人类敌人": 1, "僵尸": 2, "鼠怪": 3, "Boss": 4}
FACTION_EN = {"玩家": "PLAYER", "人类敌人": "HUMAN", "僵尸": "ZOMBIE",
              "鼠怪": "RODENT", "Boss": "BOSS"}
SRC_LABEL = {"doc": "附件直指", "visual": "图像判定", "prefab": "预制体命名"}

report = json.load(io.open(os.path.join(IMG, "render_report.json"), encoding="utf-8"))
locs = json.load(io.open(os.path.join(ROOT, "extracted", "characters",
                                      "asset_locations.json"), encoding="utf-8"))

# ---- level presence -------------------------------------------------------
level_names = {}
for f in sorted(os.listdir(NAMES)):
    if not (f.startswith("level") and f.endswith(".names.txt")):
        continue
    lvl = f.split(".")[0]
    # files are tab separated: <Type>\t<pathID>\t<Name>
    with io.open(os.path.join(NAMES, f), encoding="utf-8") as fh:
        level_names[lvl] = {ln.rstrip("\n").split("\t")[-1].strip()
                            for ln in fh if ln.strip()}


def levels_for(prefab):
    return [lvl for lvl in sorted(level_names, key=lambda s: int(re.sub(r"\D", "", s) or 0))
            if prefab in level_names[lvl]]


# ---- image embedding ------------------------------------------------------
_cache = {}


# EvilFrankie is a cutscene proxy with zero SpriteRenderers; it borrows the
# downed-pose art (documented in characters_meta.note).
IMG_FALLBACK = {"EvilFrankie": "EvilFrankieOnFloor"}


def thumb_b64(prefab, max_h=320):
    if prefab in _cache:
        return _cache[prefab]
    path = os.path.join(IMG, IMG_FALLBACK.get(prefab, prefab) + ".png")
    if not os.path.isfile(path):
        _cache[prefab] = ""
        return ""
    im = Image.open(path).convert("RGBA")
    if im.height > max_h:
        w = max(1, int(round(im.width * max_h / im.height)))
        im = im.resize((w, max_h), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "PNG", optimize=True)
    s = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")
    _cache[prefab] = s
    return s


units = []
for e in ROSTER:
    p = e["prefab"]
    r = report.get(p, {})
    loc = locs.get(p, {})
    parts = r.get("parts") or 0
    tex = loc.get("textures") or []
    hits = sum(1 for x in (loc.get("parts") or []) if x.get("in_dump_texture"))
    total = len(loc.get("parts") or [])
    units.append(dict(e,
                      parts=parts,
                      textures=tex,
                      dump_hit=hits,
                      dump_total=total,
                      levels=levels_for(p),
                      img=thumb_b64(p)))

# keep the curated order from characters_meta, only grouping by faction
_order = {e["prefab"]: i for i, e in enumerate(ROSTER)}
units.sort(key=lambda u: (FACTION_ORDER.get(u["faction"], 9), _order[u["prefab"]]))

# ---------------------------------------------------------------- markdown
lines = ["# 《枪、血、意大利卷》角色全清单（42 个战斗单位）", ""]
lines.append("> 形象图位于 `extracted/characters/`，由完整 TRS（平移 + 旋转 + 缩放）"
             "从原始备份 `backup/` 渲染，未经重彩改写。")
lines.append("")
cur = None
for u in units:
    if u["faction"] != cur:
        cur = u["faction"]
        lines.append(f"\n## {cur}（{FACTION_EN[cur]}）\n")
        lines.append("| 形象 | 中文名 | 英文名 | 类型 | 预制体 | 部件 | 贴图 |")
        lines.append("| :--- | :--- | :--- | :--- | :--- | ---: | ---: |")
    lines.append(f"| ![{u['cn']}](../extracted/characters/{u['prefab']}.png) | **{u['cn']}** | "
                 f"{u['en']} | {u['role']} | `{u['prefab']}` | {u['parts']} | "
                 f"{len(u['textures'])} |")
with io.open(os.path.join(DOCS, "CHARACTER_ROSTER.md"), "w", encoding="utf-8") as fh:
    fh.write("\n".join(lines) + "\n")

# --------------------------------------------------------------------- csv
with io.open(os.path.join(ART, "roster_reply_template.csv"), "w", encoding="utf-8-sig",
             newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["预制体", "中文名", "英文名", "阵营", "类型", "附件原型", "识别依据",
                "形象图", "关键特征/配色", "武器", "描述", "备注",
                "部件数", "关卡(未解析)", "贴图数", "dump命中", "请填写：国画替代描述"])
    for u in units:
        w.writerow([u["prefab"], u["cn"], u["en"], u["faction"], u["role"],
                    u["anchor"], SRC_LABEL.get(u["src"], u["src"]),
                    f"extracted/characters_v2/{u['prefab']}.png",
                    u["look"], u["weapon"], u["desc"], u["note"],
                    u["parts"], "", len(u["textures"]),
                    f"{u['dump_hit']}/{u['dump_total']}", ""])

# -------------------------------------------------------------------- html
def esc(s):
    return html.escape(str(s or ""), quote=True)


cards = []
for i, u in enumerate(units):
    texs = "".join(f'<code>{esc(t)}.png</code>' for t in u["textures"])
    cards.append(f"""
<article class="card" data-faction="{esc(u['faction'])}" data-src="{esc(u['src'])}"
         data-search="{esc((u['cn'] + u['en'] + u['prefab'] + u['anchor']).lower())}">
  <div class="fig"><img loading="lazy" src="{u['img']}" alt="{esc(u['cn'])}"></div>
  <div class="body">
    <div class="faction f{esc(FACTION_EN[u['faction']])}">{esc(u['faction'])}</div>
    <h3>{esc(u['cn'])}</h3>
    <p class="en">{esc(u['en'])}</p>
    <p class="role">{esc(u['role'])}</p>
    <p class="look">{esc(u['look'])}</p>
    <p class="desc">{esc(u['desc'])}</p>
    <dl>
      <dt>武器</dt><dd>{esc(u['weapon'])}</dd>
      <dt>预制体</dt><dd><code>{esc(u['prefab'])}</code> · {u['parts']} 件部件 · {len(u['textures'])} 张贴图</dd>
      <dt>素材定位</dt><dd>image/Texture2D 命中 <b>{u['dump_hit']}/{u['dump_total']}</b></dd>
    </dl>
    <details><summary>贴图清单</summary><div class="texs">{texs}</div></details>
    <p class="note">{esc(u['note'])}</p>
    <p class="anchor">附件原型：{esc(u['anchor'])} · 识别依据：{esc(SRC_LABEL.get(u['src'], u['src']))}</p>
    <label class="brief">国画重彩替代描述
      <textarea data-prefab="{esc(u['prefab'])}" rows="2"
        placeholder="填写该角色的重彩改造要求（配色/笔触/纹样）…"></textarea>
    </label>
  </div>
</article>""")

faction_counts = {}
for u in units:
    faction_counts[u["faction"]] = faction_counts.get(u["faction"], 0) + 1
chips = ['<button class="chip on" data-f="all">全部 <b>%d</b></button>' % len(units)]
for f in sorted(faction_counts, key=lambda k: FACTION_ORDER.get(k, 9)):
    chips.append('<button class="chip" data-f="%s">%s <b>%d</b></button>'
                 % (esc(f), esc(f), faction_counts[f]))

unmatched = "".join(
    f"<li><b>{esc(x['cn'])}</b>（{esc(x['en'])}）— {esc(x['reason'])}</li>"
    for x in DOC_UNMATCHED)

total_tex = sum(len(u["textures"]) for u in units)
hit = sum(u["dump_hit"] for u in units)
tot = sum(u["dump_total"] for u in units)

HTML = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>《枪、血、意大利卷》角色全清单 · 42 单位</title>
<style>
:root{{
  --paper:#f6f2e8; --card:#fffdf7; --ink:#1d1a16; --sub:#6b6357;
  --line:#d9cfba; --accent:#8c2f27; --gold:#a9853f;
}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--paper);color:var(--ink);
  font:15px/1.7 "Songti SC","SimSun",Georgia,serif;
  background-image:radial-gradient(circle at 12% 8%,rgba(169,133,63,.07),transparent 42%),
                   radial-gradient(circle at 88% 92%,rgba(140,47,39,.06),transparent 46%);}}
header{{padding:52px 32px 26px;text-align:center;border-bottom:1px solid var(--line)}}
h1{{margin:0;font-size:34px;letter-spacing:.08em;font-weight:700}}
h1 small{{display:block;font-size:13px;letter-spacing:.32em;color:var(--gold);
  font-weight:400;margin-top:12px;font-family:Georgia,serif}}
.stats{{display:flex;gap:34px;justify-content:center;margin-top:22px;flex-wrap:wrap;
  font-family:Georgia,serif;color:var(--sub);font-size:13px}}
.stats b{{display:block;font-size:24px;color:var(--accent);font-family:Georgia,serif}}
.toolbar{{position:sticky;top:0;z-index:9;background:rgba(246,242,232,.94);
  backdrop-filter:blur(8px);border-bottom:1px solid var(--line);
  padding:14px 32px;display:flex;gap:10px;flex-wrap:wrap;align-items:center}}
.chip{{border:1px solid var(--line);background:var(--card);color:var(--sub);
  padding:7px 15px;border-radius:999px;cursor:pointer;font-size:13px;
  font-family:inherit;transition:.18s}}
.chip:hover{{border-color:var(--gold);color:var(--ink)}}
.chip.on{{background:var(--ink);border-color:var(--ink);color:#f6f2e8}}
.chip b{{font-family:Georgia,serif;opacity:.6;margin-left:4px;font-weight:400}}
.chip.exp{{border-color:var(--gold);color:var(--accent);margin-left:auto}}
.chip.exp:hover{{background:var(--gold);color:#fff}}
.brief{{margin-top:10px;font-size:11px;letter-spacing:.06em;color:var(--sub);
  display:flex;flex-direction:column;gap:4px}}
.brief textarea{{width:100%;resize:vertical;border:1px solid var(--line);
  background:#fbf6ea;border-radius:2px;padding:7px 9px;font-family:inherit;
  font-size:12.5px;line-height:1.6;color:var(--ink);outline:none}}
.brief textarea:focus{{border-color:var(--gold);background:#fffdf7}}
#q{{margin-left:0;border:1px solid var(--line);background:var(--card);
  padding:8px 14px;border-radius:999px;min-width:220px;font-family:inherit;
  font-size:13px;color:var(--ink);outline:none}}
#q:focus{{border-color:var(--gold)}}
main{{padding:30px 32px 80px;display:grid;gap:26px;
  grid-template-columns:repeat(auto-fill,minmax(330px,1fr));max-width:1680px;margin:0 auto}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:3px;
  display:flex;flex-direction:column;overflow:hidden;
  box-shadow:0 1px 0 rgba(0,0,0,.03),0 8px 26px -18px rgba(60,40,20,.45)}}
.card.hide{{display:none}}
.fig{{height:268px;display:flex;align-items:flex-end;justify-content:center;
  padding:14px 14px 0;background:
    linear-gradient(180deg,#fffdf7 0%,#faf5e9 100%);
  border-bottom:1px solid var(--line);position:relative}}
.fig img{{max-width:100%;max-height:254px;object-fit:contain;
  filter:drop-shadow(0 6px 10px rgba(60,40,20,.18))}}
.body{{padding:16px 18px 18px;display:flex;flex-direction:column;gap:7px}}
.faction{{align-self:flex-start;font-size:11px;letter-spacing:.14em;
  padding:3px 9px;border-radius:2px;color:#fff;font-family:Georgia,serif}}
.fPLAYER{{background:#2f5d50}} .fHUMAN{{background:#3c4a63}}
.fZOMBIE{{background:#5c4a34}} .fRODENT{{background:#6b5b3e}} .fBOSS{{background:#8c2f27}}
h3{{margin:2px 0 0;font-size:21px;letter-spacing:.03em}}
.en{{margin:0;color:var(--gold);font-family:Georgia,serif;font-size:13px;
  letter-spacing:.06em;font-style:italic}}
.role{{margin:2px 0 0;font-size:13px;color:var(--accent)}}
.look,.desc{{margin:4px 0 0;font-size:13.5px;color:var(--ink)}}
.desc{{color:#3d382f}}
dl{{margin:10px 0 0;display:grid;grid-template-columns:64px 1fr;gap:4px 10px;
  font-size:12.5px;border-top:1px dashed var(--line);padding-top:10px}}
dt{{color:var(--sub);font-size:11.5px;letter-spacing:.08em}}
dd{{margin:0;color:var(--ink)}}
code{{font-family:Consolas,monospace;font-size:11.5px;background:#f1ead9;
  padding:1px 5px;border-radius:2px;color:#5a4a2f}}
.lv{{display:inline-block;background:#eee5d2;border-radius:2px;padding:0 5px;
  font-size:11px;margin-right:3px;font-family:Georgia,serif}}
.lv.none{{opacity:.5}}
details{{margin-top:8px;font-size:12px}}
summary{{cursor:pointer;color:var(--gold);letter-spacing:.06em}}
.texs{{margin-top:6px;display:flex;flex-wrap:wrap;gap:4px}}
.note{{margin:8px 0 0;font-size:12px;color:var(--sub);border-left:2px solid var(--line);
  padding-left:9px}}
.anchor{{margin:6px 0 0;font-size:11px;color:#a0968a}}
footer{{border-top:1px solid var(--line);padding:34px 32px 60px;max-width:1100px;
  margin:0 auto;color:var(--sub);font-size:13px}}
footer h2{{font-size:16px;color:var(--ink);letter-spacing:.06em}}
footer li{{margin:6px 0}}
.method{{background:var(--card);border:1px solid var(--line);padding:20px 24px;
  margin-top:22px;font-size:13px;line-height:1.9}}
.method code{{font-size:11.5px}}
</style>
</head>
<body>
<header>
  <h1>《枪、血、意大利卷》角色全清单
    <small>GUNS, GORE AND CANNOLI — COMPLETE UNIT ROSTER</small></h1>
  <div class="stats">
    <div><b>{len(units)}</b>战斗单位</div>
    <div><b>{len(faction_counts)}</b>阵营</div>
    <div><b>{sum(u['parts'] for u in units)}</b>精灵部件</div>
    <div><b>{total_tex}</b>张角色贴图</div>
    <div><b>{hit}/{tot}</b>素材定位命中</div>
  </div>
</header>

<div class="toolbar">
  {''.join(chips)}
  <button class="chip exp" id="exp">导出填写结果 CSV</button>
  <input id="q" type="search" placeholder="搜索中文名 / 英文名 / 预制体…">
</div>

<main>
{''.join(cards)}
</main>

<footer>
  <h2>未能对应的附件条目</h2>
  <ul>{unmatched}</ul>

  <div class="method">
    <b>这份清单是怎么做出来的</b><br>
    1. 遍历 <code>resources.assets</code> 里所有带 <code>Unit</code> / <code>UnitSpike</code>
       脚本的 GameObject，得到 <b>42</b> 个真正的战斗单位（旧清单的 33 个来自手写名单，
       漏了 Goon1–3、Vito、Salvatore、Paulie、Soldier、FatCook、FatDockworker 共 9 个）。<br>
    2. 逐个预制体走 Transform 树，跳过 <code>m_IsActive=False</code> 的武器/姿势变体，
       解析每个 SpriteRenderer 的 Sprite → 源 Texture2D，并在
       <code>image/Texture2D/</code> 里逐个核对文件名，命中率 {hit}/{tot}。<br>
    3. 形象图从 <b>backup/</b>（未被重彩改写的原始备份）渲染，使用完整 TRS
       （平移 + 旋转 + 缩放）——旧渲染器丢弃了旋转，导致鼠尾叠成尖锥、
       气球浮尸的绳子消失、四肢角度错位。<br>
    4. 中文名/特征/武器/描述按附件逐条对齐；附件未覆盖的变体标注为「图像判定」，
       并在备注里写明判定依据与不确定点。
  </div>
</footer>

<script>
const chips=[...document.querySelectorAll('.chip')];
const cards=[...document.querySelectorAll('.card')];
const q=document.getElementById('q');
let f='all';
function apply(){{
  const s=(q.value||'').trim().toLowerCase();
  cards.forEach(c=>{{
    const okF = f==='all' || c.dataset.faction===f;
    const okS = !s || c.dataset.search.includes(s);
    c.classList.toggle('hide', !(okF&&okS));
  }});
}}
chips.forEach(b=>b.addEventListener('click',()=>{{
  chips.forEach(x=>x.classList.remove('on'));
  b.classList.add('on'); f=b.dataset.f; apply();
}}));
q.addEventListener('input',apply);

// ---- fill-in briefs: persist to localStorage, export as CSV ----
const KEY='ggc_roster_briefs_v1';
const saved=JSON.parse(localStorage.getItem(KEY)||'{{}}');
document.querySelectorAll('.brief textarea').forEach(t=>{{
  const k=t.dataset.prefab;
  if(saved[k]) t.value=saved[k];
  t.addEventListener('input',()=>{{
    const all=JSON.parse(localStorage.getItem(KEY)||'{{}}');
    if(t.value.trim()) all[k]=t.value; else delete all[k];
    localStorage.setItem(KEY,JSON.stringify(all));
  }});
}});
document.getElementById('exp').addEventListener('click',()=>{{
  const rows=[['预制体','中文名','英文名','阵营','类型','国画重彩替代描述']];
  document.querySelectorAll('.card').forEach(c=>{{
    const t=c.querySelector('.brief textarea');
    rows.push([t.dataset.prefab,
               c.querySelector('h3').textContent,
               c.querySelector('.en').textContent,
               c.querySelector('.faction').textContent,
               c.querySelector('.role').textContent,
               (t.value||'').replace(/"/g,'""')]);
  }});
  const csv='\ufeff'+rows.map(r=>r.map(x=>'"'+x+'"').join(',')).join('\r\n');
  const a=document.createElement('a');
  a.href=URL.createObjectURL(new Blob([csv],{{type:'text/csv'}}));
  a.download='GGC_角色替代描述.csv';
  a.click();
}});
</script>
</body>
</html>"""

with io.open(os.path.join(DOCS, "CHARACTER_ROSTER.html"), "w", encoding="utf-8") as fh:
    fh.write(HTML)

print("units:", len(units))
print("html:", os.path.getsize(os.path.join(DOCS, "CHARACTER_ROSTER.html")) // 1024, "KB")
print("md:", os.path.getsize(os.path.join(DOCS, "CHARACTER_ROSTER.md")) // 1024, "KB")
print("csv:", os.path.getsize(os.path.join(ART, "roster_reply_template.csv")) // 1024, "KB")
