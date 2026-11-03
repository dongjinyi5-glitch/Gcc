"""Build character roster deliverables from roster.json + rendered PNGs.

Outputs:
  extracted/characters/contact_sheet.png   all characters, labelled
  docs/CHARACTER_ROSTER.html               self-contained card page w/ fill-in fields
  docs/CHARACTER_ROSTER.md                 markdown table for quick reply
  art/roster_reply_template.csv            structured reply template
"""
import os, io, json, base64, csv
from PIL import Image, ImageDraw, ImageFont

ROOT = r"D:\AI\Guns, Gore and Cannoli from WB"
CH = os.path.join(ROOT, "extracted", "characters")
DOCS = os.path.join(ROOT, "docs")
ART = os.path.join(ROOT, "art")
os.makedirs(DOCS, exist_ok=True)
os.makedirs(ART, exist_ok=True)

roster = json.load(io.open(os.path.join(CH, "roster.json"), encoding="utf-8"))

FACTION_ORDER = {"玩家": 0, "人类敌人": 1, "僵尸": 2, "鼠怪": 3, "Boss": 4}
roster.sort(key=lambda e: (FACTION_ORDER.get(e["faction"], 9), e["name"]))

# ---------------- contact sheet ----------------
def font(size):
    for p in (r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\simhei.ttf",
              r"C:\Windows\Fonts\simsun.ttc"):
        if os.path.isfile(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    return ImageFont.load_default()

CELL_W, CELL_H = 200, 300
COLS = 6
items = [e for e in roster if e.get("file")]
rows = (len(items) + COLS - 1) // COLS
sheet = Image.new("RGB", (COLS * CELL_W, rows * CELL_H), (246, 242, 232))
d = ImageDraw.Draw(sheet)
f_name = font(17)
f_meta = font(13)

for i, e in enumerate(items):
    cx = (i % COLS) * CELL_W
    cy = (i // COLS) * CELL_H
    d.rectangle([cx + 4, cy + 4, cx + CELL_W - 4, cy + CELL_H - 4],
                fill=(255, 253, 248), outline=(200, 190, 172))
    p = os.path.join(CH, e["file"])
    try:
        im = Image.open(p).convert("RGBA")
        im.thumbnail((CELL_W - 24, CELL_H - 78), Image.LANCZOS)
        bg = Image.new("RGBA", im.size, (255, 253, 248, 255))
        bg.alpha_composite(im)
        sheet.paste(bg.convert("RGB"),
                    (cx + (CELL_W - im.width) // 2, cy + 12 + (CELL_H - 78 - im.height) // 2))
    except Exception:
        pass
    d.text((cx + CELL_W // 2, cy + CELL_H - 56), e["name"], font=f_name,
           fill=(28, 26, 24), anchor="mm")
    lv = e.get("levels") or []
    d.text((cx + CELL_W // 2, cy + CELL_H - 32), f"{e['faction']} · {len(lv)}关",
           font=f_meta, fill=(122, 96, 72), anchor="mm")

sheet.save(os.path.join(CH, "contact_sheet.png"))
print("contact sheet:", sheet.size)

# ---------------- HTML ----------------
def b64(p):
    with open(p, "rb") as fh:
        return "data:image/png;base64," + base64.b64encode(fh.read()).decode()

groups = {}
for e in roster:
    groups.setdefault(e["faction"], []).append(e)

cards_html = []
for faction, items_g in groups.items():
    cards_html.append(f'<section class="group"><h2>{faction}'
                      f'<span class="count">{len(items_g)}</span></h2><div class="grid">')
    for e in items_g:
        img = b64(os.path.join(CH, e["file"])) if e.get("file") else ""
        lv = "、".join(x.replace("level", "第") + "关" for x in (e.get("levels") or [])) or "—"
        scripts = "、".join(e.get("scripts") or []) or "—"
        note = f'<div class="note">{e["note"]}</div>' if e.get("note") else ""
        cards_html.append(f"""
        <article class="card" data-name="{e['name']}">
          <div class="pic">{f'<img src="{img}" alt="{e["name"]}">' if img else '<span class="noimg">无独立外观</span>'}</div>
          <h3>{e['name']}</h3>
          <dl>
            <div><dt>阵营</dt><dd>{e['faction']}</dd></div>
            <div><dt>身体部件</dt><dd>{e.get('sprite_parts', 0)} 块</dd></div>
            <div><dt>行为脚本</dt><dd>{scripts}</dd></div>
            <div><dt>出场关卡</dt><dd class="lv">{lv}</dd></div>
          </dl>
          {note}
          <label>替换角色描述
            <textarea data-key="{e['name']}" rows="3"
              placeholder="例：手持青龙偃月刀的赤面武将，重彩朱红战袍，墨线勾边…"></textarea>
          </label>
        </article>""")
    cards_html.append("</div></section>")

html = f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>角色清单 · Guns, Gore and Cannoli 国画替换</title>
<style>
:root{{--paper:#f7f3e8;--ink:#1c1a18;--muted:#7a6048;--line:#d9cdb6;--red:#a8322a;--card:#fffdf7}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--paper);color:var(--ink);
font-family:"Microsoft YaHei","PingFang SC",system-ui,sans-serif;line-height:1.6}}
header{{padding:32px 40px 20px;border-bottom:2px solid var(--ink);background:
linear-gradient(180deg,#fffdf7,var(--paper))}}
h1{{margin:0;font-size:28px;letter-spacing:.04em}}
h1 em{{font-style:normal;color:var(--red)}}
.sub{{color:var(--muted);font-size:14px;margin-top:8px}}
.toolbar{{position:sticky;top:0;z-index:9;display:flex;gap:10px;align-items:center;
padding:12px 40px;background:rgba(247,243,232,.96);border-bottom:1px solid var(--line);
backdrop-filter:blur(6px);flex-wrap:wrap}}
button{{font:inherit;font-size:13px;padding:7px 16px;border:1px solid var(--ink);
background:var(--card);color:var(--ink);cursor:pointer;border-radius:2px}}
button:hover{{background:var(--ink);color:var(--paper)}}
button.primary{{background:var(--red);border-color:var(--red);color:#fff}}
button.primary:hover{{background:#8c2620;border-color:#8c2620}}
#stat{{font-size:13px;color:var(--muted);margin-left:auto}}
main{{padding:8px 40px 60px}}
.group h2{{font-size:19px;margin:34px 0 14px;padding-left:12px;border-left:4px solid var(--red);
display:flex;align-items:center;gap:10px}}
.count{{font-size:12px;font-weight:400;color:var(--muted);border:1px solid var(--line);
border-radius:10px;padding:1px 8px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:16px}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:3px;padding:14px;
display:flex;flex-direction:column;gap:8px;transition:.15s}}
.card:hover{{border-color:var(--ink);box-shadow:0 2px 10px rgba(28,26,24,.08)}}
.pic{{height:210px;display:flex;align-items:center;justify-content:center;
background:repeating-linear-gradient(45deg,#fbf8f0,#fbf8f0 8px,#f6f1e4 8px,#f6f1e4 16px);
border-radius:2px;overflow:hidden}}
.pic img{{max-width:100%;max-height:100%;object-fit:contain;image-rendering:auto}}
.noimg{{color:var(--muted);font-size:13px}}
.card h3{{margin:2px 0 0;font-size:16px;letter-spacing:.02em}}
dl{{margin:0;font-size:12.5px}}
dl div{{display:flex;gap:8px;padding:2px 0;border-bottom:1px dotted #ece2cd}}
dt{{color:var(--muted);flex:0 0 62px}}
dd{{margin:0;flex:1}}
dd.lv{{font-size:11.5px;line-height:1.5;color:#4a4238}}
.note{{font-size:11.5px;color:var(--red);background:#fdf3ef;padding:5px 8px;border-left:3px solid var(--red)}}
label{{font-size:12px;color:var(--muted);display:flex;flex-direction:column;gap:5px;margin-top:auto}}
textarea{{font:inherit;font-size:12.5px;color:var(--ink);border:1px solid var(--line);
border-radius:2px;padding:7px;resize:vertical;background:#fffefb}}
textarea:focus{{outline:none;border-color:var(--red);box-shadow:0 0 0 2px rgba(168,50,42,.12)}}
footer{{padding:20px 40px 50px;color:var(--muted);font-size:12px;border-top:1px solid var(--line)}}
</style></head><body>
<header>
  <h1>角色清单 · <em>重彩水墨</em>替换对照表</h1>
  <div class="sub">Guns, Gore and Cannoli（GOG / Unity 4.3.4f1）· 共 {len(roster)} 个角色 ·
  形象图由游戏预制体层级实时拼合渲染（非截图）· 笔触偏好：中等粗细 · 风格：重彩</div>
</header>
<div class="toolbar">
  <button class="primary" onclick="exportCSV()">导出填写结果 CSV</button>
  <button onclick="exportJSON()">导出 JSON</button>
  <button onclick="clearAll()">清空</button>
  <span id="stat"></span>
</div>
<main>{''.join(cards_html)}</main>
<footer>
  填写说明：在每个角色下方输入你想要的替代形象（题材、服饰、配色、道具、气质均可），
  内容会即时保存在本机浏览器。完成后点「导出填写结果 CSV」，把文件发回即可进入下一阶段。
</footer>
<script>
const KEY='ggc_roster_desc_v1';
let store=JSON.parse(localStorage.getItem(KEY)||'{{}}');
const areas=[...document.querySelectorAll('textarea')];
areas.forEach(t=>{{t.value=store[t.dataset.key]||'';
  t.addEventListener('input',()=>{{store[t.dataset.key]=t.value;
    localStorage.setItem(KEY,JSON.stringify(store));updateStat();}});}});
function updateStat(){{const n=areas.filter(t=>t.value.trim()).length;
  document.getElementById('stat').textContent=`已填写 ${{n}} / ${{areas.length}}`;}}
updateStat();
function download(name,text,type){{
  const b=new Blob([text],{{type:type||'text/plain;charset=utf-8'}});
  const a=document.createElement('a');a.href=URL.createObjectURL(b);a.download=name;a.click();}}
function exportCSV(){{
  const rows=[['角色名','阵营','身体部件数','出场关卡','替换角色描述']];
  areas.forEach(t=>{{const card=t.closest('.card');
    const lv=card.querySelector('dd.lv')?.textContent||'';
    rows.push([t.dataset.key,card.querySelector('dd')?.textContent||'',
      card.querySelectorAll('dd')[1]?.textContent||'',lv,t.value.replace(/\\n/g,' ')]);}});
  const csv='\\ufeff'+rows.map(r=>r.map(c=>`"${{String(c).replace(/"/g,'""')}}"`).join(',')).join('\\r\\n');
  download('ggc_roster_reply.csv',csv,'text/csv;charset=utf-8');}}
function exportJSON(){{
  const out={{}};areas.forEach(t=>{{if(t.value.trim())out[t.dataset.key]=t.value.trim();}});
  download('ggc_roster_reply.json',JSON.stringify(out,null,2),'application/json');}}
function clearAll(){{if(!confirm('确定清空全部填写内容？'))return;store={{}};
  localStorage.removeItem(KEY);areas.forEach(t=>t.value='');updateStat();}}
</script></body></html>"""

io.open(os.path.join(DOCS, "CHARACTER_ROSTER.html"), "w", encoding="utf-8").write(html)
print("html:", len(html), "chars")

# ---------------- Markdown ----------------
md = ["# 角色清单（待你逐项确认替换形象）", "",
      f"> 数据来源：`resources.assets` 预制体层级实时解析 + `level*` 场景关键字扫描。共 **{len(roster)}** 个角色。",
      "> 形象图：`extracted/characters/<角色名>.png`（由身体部件按 Transform 位置拼合渲染）。",
      "> 风格基准：**重彩**，笔触**中等粗细**。", "",
      "| # | 角色 | 阵营 | 身体部件 | 行为脚本 | 出场关卡 | 替换形象（请填写） |",
      "|---|------|------|---------|---------|---------|------------------|"]
for i, e in enumerate(roster, 1):
    lv = "、".join(x.replace("level", "L") for x in (e.get("levels") or [])) or "—"
    sc = "、".join(e.get("scripts") or []) or "—"
    md.append(f"| {i} | **{e['name']}** | {e['faction']} | {e.get('sprite_parts',0)} | {sc} | {lv} |  |")
md += ["", "---", "",
       "## 填写建议", "",
       "每个角色只需一句话即可，包含：**题材身份 + 主色 + 关键道具/特征**。例如：",
       "",
       "- `Vinnie` → 青衫佩剑的江湖侠客，墨黑长发束冠，朱红腰带",
       "- `ZombieSoldier` → 残破甲胄的阴兵，灰绿锈色，手持断戟",
       "- `ZombieRatBoss` → 镇墓巨鼠妖，焦墨皮毛，獠牙泛金",
       "",
       "填写完成后可直接回复我，或使用 `docs/CHARACTER_ROSTER.html` 导出 CSV 发回。"]
io.open(os.path.join(DOCS, "CHARACTER_ROSTER.md"), "w", encoding="utf-8").write("\n".join(md))

# ---------------- CSV template ----------------
with io.open(os.path.join(ART, "roster_reply_template.csv"), "w", encoding="utf-8-sig", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["角色名", "阵营", "身体部件数", "出场关卡", "替换角色描述"])
    for e in roster:
        w.writerow([e["name"], e["faction"], e.get("sprite_parts", 0),
                    ";".join(e.get("levels") or []), ""])

print("md + csv done")
