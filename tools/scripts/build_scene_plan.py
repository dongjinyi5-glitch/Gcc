"""Build docs/SCENE_PLAN.html -- the historical remap, level by level.

Pairs each level's composited panorama (from scene_render.py) with the historical
scene it is proposed to become, the structural reason the swap works, the art
notes, and the level's 14 landmark textures (the T1 redraw list) with painted
area and a collider flag.

The mapping is a design decision, not parsed data, so it lives here as MAP.  The
numbers next to it are all read from art/scene_inventory.json.
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
DOC = os.path.join(PROJECT, "docs", "SCENE_PLAN.html")

ORDER = ["level0"] + [f"level{i}" for i in range(3, 15)]

# level -> (历史原型, 时间, 吻合强度, 游戏原型, 形态吻合点, [改造要点], 风险/备注)
MAP = {
    "level0": ("滇缅公路雨季 · 行军纵队", "1942", "中",
               "雨夜城市剪影（动态菜单）",
               "雨、雾、闪电全部现成，剪影层直接换成行军纵队",
               ["只换剪影层：卡车、骡马、斗笠行军纵队、路边障碍",
                "雨/雾保留，闪电改暖白，不要霓虹蓝",
                "天际线换成怒江峡谷轮廓，去掉城市高楼",
                "招牌文字全部去掉，换路牌与里程碑"],
               "菜单只有 2 张图，成本最低，但它是玩家第一眼"),
    "level3": ("仰光港", "1942.3", "极强",
               "港口码头（栈桥/吊车/江轮）",
               "栈桥、门吊、江轮、货栈，形制一字不差",
               ["门吊改蒸汽/柴油吊杆，拆掉霓虹招牌",
                "江轮改伊洛瓦底江蒸汽船（明轮、烟囱、货舱口）",
                "仓库改铅皮顶、锈铁皮、油毛毡",
                "栈桥加木板与缆桩，堆汽油桶与弹药箱",
                "灯改马灯/煤油灯，色温压暖"],
               ""),
    "level4": ("腊戍转运站（滇缅公路终点）", "1942.4", "很强",
               "港区货场（仓库/机库/大吊车）",
               "成排仓库、油桶堆场、卡车队列",
               ["货场改成滇缅公路物资堆场：油桶、弹药箱、轮胎堆",
                "机库内部改修理厂：千斤顶、零件架、焊接火花",
                "大吊车改门式起重/蒸汽吊",
                "加里程标、卡车队列、帆布篷"],
               ""),
    "level5": ("曼德勒 · 伊洛瓦底江", "1942.4", "强",
               "港湾远景（江岸天际线）",
               "江岸轮廓 + 佛塔剪影",
               ["远景天际线换成伊洛瓦底江岸 + 佛塔尖",
                "城市剪影降饱和，墨 + 赭石为主",
                "水面改江面：平缓、反光弱",
                "城郊视差层换稻田/竹丛"],
               ""),
    "level6": ("腾冲古城", "1942.5 沦陷 / 1944.9 攻城", "很强",
               "老城街道（木楼/石板巷/牌坊）",
               "火山石墙、木构楼、牌坊、石板街",
               ["砖墙换火山石墙（腾冲特有），抹灰换夯土",
                "木构楼加挑檐、木板墙、瓦顶",
                "加牌坊、门楼、拴马石",
                "石板街换火山石铺面，去掉柏油与井盖",
                "店铺招牌换布幌/木牌，不用霓虹"],
               ""),
    "level7": ("蓝姆伽/雷多 军人俱乐部（后方插叙）", "1943", "弱",
               "夜总会（室内娱乐场）",
               "室内布局不变，改成后方补给站兼酒馆",
               ["保留室内空间与动线，只换材质与陈设",
                "舞台改食堂/简报台，加地图与黑板",
                "吧台改补给台：罐头、咖啡、香烟",
                "霓虹灯管换马灯与汽灯"],
               "⚠ 这里没有对应的著名战斗场景。硬套一场战役会变成"
               "「在夜总会里打松山」。建议定位为后方插叙关，不要挂战役名。"),
    "level8": ("同古（Toungoo）城区", "1942.3", "很强",
               "城区街区（街区/高架/路障）",
               "火车站、街区、锡唐河铁桥、路障",
               ["街区建筑换缅式木构 + 砖混混合，加火车站雨棚",
                "高架桥换钢桁铁路桥/公路桥",
                "路障换沙袋、拒马、铁丝网",
                "加铁轨、站台、信号臂",
                "招牌换英文/缅文，去掉霓虹"],
               ""),
    "level9": ("惠通桥", "1942.5.5", "极强",
               "河畔大桥（河谷/大桥/桥头堡）",
               "怒江峡谷单孔钢桁桥 + 盘山公路 + 桥头堡",
               ["桥体改单孔钢桁架（惠通桥形制），保留跨度与桥面高度",
                "加桥头堡、岗亭、之字形盘山公路",
                "河谷改怒江峡谷：陡壁、浑水、雾气",
                "桥面加炸药箱与引线（叙事道具）",
                "时间点：1942 年 5 月 5 日清晨，工兵营引爆"],
               "形制天然吻合，是整套方案里改动收益最高的一关"),
    "level10": ("松山 · 坑道接近", "1944.7", "强",
                "竖井与下水道",
                "竖井 + 水平坑道，工兵掘进，形制天然吻合",
                ["管道改木支撑 + 掘进土壁，加矿灯/马灯",
                 "竖井加吊篮、绳索、滑车",
                 "加炸药箱、风箱、铁镐、土筐",
                 "土色用红壤 + 火山灰，不是水泥"],
                "时间点：1944 年 8 月 20 日爆破前的掘进阶段"),
    "level11": ("松山 · 地下工事群", "1944.8", "强",
                "地铁与水库",
                "地下兵舍、弹药库、蓄水池",
                ["站台改地下兵舍/弹药库，混凝土换原木支护",
                 "加弹药箱、步枪架、野战电话",
                 "蓄水池保留（松山工事确有蓄水设施）",
                 "照明改汽灯/手电，去掉日光灯"],
                ""),
    "level12": ("松山 · 蓄水池与指挥所", "1944.8", "中",
                "水库深处",
                "终局段，深水 + 竖井",
                ["水面改浑浊蓄水池，加铁梯与浮桥",
                 "加指挥所：地图桌、野战电台、沙盘",
                 "混凝土加裂缝与渗水"],
                "⚠ 这一段历史依据最薄。建议做成「工事最深处」的象征场景，"
                "不强调具体战役细节。"),
    "level13": ("雷多 · 中印公路工程处", "1944", "强",
                "车库与电梯",
                "机械库、修理厂、弹药升降机",
                ["车库改工程机械库：推土机、压路机、卡车",
                 "电梯改物资/弹药升降机（钢丝绳 + 木笼）",
                 "营房改工兵宿舍：行军床、工具墙",
                 "加中印公路路牌、里程标、油桶"],
                ""),
    "level14": ("密支那机场 · 驼峰航线", "1944.8", "弱",
                "齐柏林飞艇（巨型浮空器/机库）",
                "飞艇 → 停机坪上的 C-46；吊舱 → 机腹/机舱；机库/塔台",
                ["飞艇改成停机中的 C-46/C-47 运输机（双发、高垂尾）",
                 "吊舱改机腹货舱门 / 机舱内部",
                 "背景加机库、塔台、探照灯、跑道灯",
                 "加驼峰航线元素：货物网、油桶、降落伞包"],
                "⚠ 1942 年缅甸战场没有飞艇。这一张要改剪影——但它没有碰撞，"
                "技术上可行，需要重做 mesh 覆盖率验证。"),
}

CSS = """
:root{--bg:#17171b;--card:#23232a;--ink:#e8e8ee;--dim:#9a9ca8;--acc:#d6a860;
--line:#3a3a44;--red:#c05a4a;--grn:#5f9e6a}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
font:15px/1.65 -apple-system,"Segoe UI","Microsoft YaHei",sans-serif}
.wrap{max-width:1240px;margin:0 auto;padding:40px 28px 80px}
h1{font-size:30px;margin:0 0 6px}
h2{font-size:21px;margin:0 0 2px}
h3{font-size:17px;margin:34px 0 10px;color:var(--acc)}
h4{font-size:13px;margin:14px 0 6px;color:var(--dim);font-weight:600;
letter-spacing:.4px;text-transform:none}
.sub{color:var(--dim);margin:0 0 24px}
.cards{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin:22px 0 28px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:15px 17px}
.card b{display:block;font-size:25px;color:var(--acc)}
.card span{color:var(--dim);font-size:12.5px}
.note{background:var(--card);border-left:3px solid var(--acc);border-radius:6px;
padding:13px 17px;margin:16px 0}
.note p{margin:5px 0}
.note.warn{border-left-color:var(--red)}
table{width:100%;border-collapse:collapse;font-size:13.5px;margin:10px 0}
th,td{text-align:left;padding:7px 9px;border-bottom:1px solid var(--line)}
th{color:var(--dim);font-size:12.5px;font-weight:600}
td.num,th.num{text-align:right;font-variant-numeric:tabular-nums}
tr:hover td{background:#282830}
code,.mono{font-family:Consolas,monospace;font-size:12.5px;color:#c9d1d9}
.lv{background:var(--card);border:1px solid var(--line);border-radius:12px;
padding:20px 22px;margin:22px 0}
.tag{font:12px Consolas,monospace;color:var(--dim);background:#1b1b21;
border:1px solid var(--line);border-radius:4px;padding:2px 7px;margin-left:8px}
.fit{display:inline-block;font-size:11.5px;padding:1px 8px;border-radius:10px;
margin-left:8px;background:#33333d;color:var(--dim)}
.fit.s5{background:#3d3320;color:#e8c07a}
.fit.s4{background:#333a2c;color:#a8c48a}
.fit.s3{background:#2e343d;color:#9fb6cc}
.fit.s2{background:#33333d;color:#a8aab4}
.fit.s1{background:#3d2626;color:#d08a7a}
.pair2{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin:12px 0}
.box{background:#1b1b21;border:1px solid var(--line);border-radius:8px;padding:11px 14px}
.box .k{font-size:11.5px;color:var(--dim);letter-spacing:.5px}
.box .v{font-size:15.5px;margin-top:2px}
.shot{display:block;background:#0d0d10;border:1px solid var(--line);
border-radius:8px;overflow:hidden;margin:10px 0}
.shot img{display:block;max-width:100%;width:auto;height:auto;margin:0 auto}
.cap{font-size:12.5px;color:var(--dim);margin:6px 0 14px}
ul{padding-left:19px;margin:8px 0}
li{margin:3px 0}
a{color:var(--acc);text-decoration:none}
a:hover{text-decoration:underline}
.flow{display:flex;flex-wrap:wrap;gap:7px;align-items:center;margin:10px 0}
.chip{background:#1b1b21;border:1px solid var(--line);border-radius:6px;
padding:5px 10px;font-size:12.5px}
.chip b{color:var(--acc);font-weight:600}
.arrow{color:var(--dim);font-size:12px}
.era{color:var(--dim);font-size:12.5px;margin:16px 0 4px;letter-spacing:.5px}
.col{color:var(--red);font-size:11px}
"""


def prev(path, maxw=1400, quality=88):
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


FIT_CLASS = {"极强": "s5", "很强": "s4", "强": "s3", "中": "s2", "弱": "s1"}


def main():
    rows = json.load(io.open(os.path.join(ART, "scene_inventory.json"), encoding="utf-8"))
    per = defaultdict(list)
    for r in rows:
        for lv in r["levels"]:
            per[lv].append(r)
    total_px = sum(r["painted"] for r in rows)
    n_col = sum(1 for r in rows if r.get("collider"))
    p_col = sum(r["painted"] for r in rows if r.get("collider"))

    # T1 = top 14 painted per level, unioned (matches the tier split in the plan)
    t1 = set()
    for lv, rs in per.items():
        for r in sorted(rs, key=lambda x: -x["painted"])[:14]:
            t1.add((r["file"], r["path_id"]))
    p_t1 = sum(r["painted"] for r in rows if (r["file"], r["path_id"]) in t1)
    c_t1 = sum(1 for r in rows if (r["file"], r["path_id"]) in t1 and r.get("collider"))

    h = [f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<title>场景图层改造方案 — 中国远征军战场</title><style>{CSS}</style></head><body><div class="wrap">
<h1>场景图层改造方案</h1>
<p class="sub">从虚构黑帮城市 → 中国远征军战场 · 逐关映射 · 四层改造法 · 成本与约束</p>

<div class="cards">
  <div class="card"><b>13</b><span>关卡映射（12 战役关 + 菜单）</span></div>
  <div class="card"><b>{len(t1)}</b><span>张地标重绘（占画面 {p_t1 / total_px * 100:.0f}%）</span></div>
  <div class="card"><b>{p_col / total_px * 100:.1f}%</b><span>画面带碰撞，{n_col} 张需守轮廓</span></div>
  <div class="card"><b>810–1620</b><span>地标重绘 credits</span></div>
</div>

<div class="note">
<p><b>可以换，而且场景层比角色层更适合换历史。</b>{n_col} / {len(rows)} 张纹理带碰撞，
但它们只占 <b>{p_col / total_px * 100:.1f}%</b> 的绘制面积——剩下 96% 是纯装饰，
改轮廓不改物理。碰撞体是独立对象（Box 4876 / Polygon 566 / Edge 229 / Circle 83），
不跟贴图绑定，所以「换画面不换物理」是成立的。</p>
<p><b>地标层几乎全自由：</b>{len(t1)} 张地标（占画面 {p_t1 / total_px * 100:.0f}%）
里只有 <b>{c_t1} 张</b>带碰撞。天际线、主建筑立面、桥、吊车——这些决定「这是哪儿」的图，
基本可以随便改。</p>
</div>

<h3>1. 叙事线</h3>
<p class="sub" style="margin-top:-6px">游戏关卡原型是固定的，严格年代顺序做不到，
所以<b>形态优先于年代</b>，排成两幕。</p>
<div class="era">第一幕 · 1942 入缅与撤退</div>
<div class="flow">
<span class="chip"><b>L3</b> 仰光港 1942.3</span><span class="arrow">→</span>
<span class="chip"><b>L4</b> 腊戍转运站 1942.4</span><span class="arrow">→</span>
<span class="chip"><b>L5</b> 曼德勒·伊洛瓦底江 1942.4</span><span class="arrow">→</span>
<span class="chip"><b>L6</b> 腾冲古城 1942.5</span><span class="arrow">→</span>
<span class="chip"><b>L7</b> 后方俱乐部 1943（插叙）</span><span class="arrow">→</span>
<span class="chip"><b>L8</b> 同古城区 1942.3</span><span class="arrow">→</span>
<span class="chip"><b>L9</b> 惠通桥 1942.5.5</span>
</div>
<div class="era">第二幕 · 1944 反攻</div>
<div class="flow">
<span class="chip"><b>L10</b> 松山坑道 1944.7</span><span class="arrow">→</span>
<span class="chip"><b>L11</b> 松山地下工事 1944.8</span><span class="arrow">→</span>
<span class="chip"><b>L12</b> 蓄水池与指挥所 1944.8</span><span class="arrow">→</span>
<span class="chip"><b>L13</b> 雷多中印公路 1944</span><span class="arrow">→</span>
<span class="chip"><b>L14</b> 密支那机场 1944.8</span>
</div>

<h3>2. 四层改造法</h3>
<table><thead><tr><th>层</th><th class="num">张数</th><th class="num">绘制面积</th>
<th class="num">占画面</th><th class="num">带碰撞</th><th>做法</th></tr></thead><tbody>
<tr><td><b>T1 地标重绘</b></td><td class="num">{len(t1)}</td>
<td class="num">{p_t1 / 1e6:.1f} Mpx</td><td class="num">{p_t1 / total_px * 100:.0f}%</td>
<td class="num">{c_t1}</td><td>AI/手绘，5–10 credits/张</td></tr>
<tr><td>T2 材质重画</td><td class="num">250</td><td class="num">95.5 Mpx</td>
<td class="num">23%</td><td class="num">30</td>
<td>程序化：火山石/夯土/竹篾/锈铁皮</td></tr>
<tr><td>T3 道具替换</td><td class="num">960</td><td class="num">164.2 Mpx</td>
<td class="num">39%</td><td class="num">218</td>
<td>程序化 + 局部替换；带碰撞的只改表面</td></tr>
<tr><td>T4 只调色</td><td class="num">78</td><td class="num">4.3 Mpx</td>
<td class="num">1%</td><td class="num">20</td><td>Shader/调色板，粒子不重画</td></tr>
</tbody></table>
<p class="sub" style="margin-top:-2px">T1 清单 = 每关绘制面积前 14 张，去重后 {len(t1)} 张；
每关的 14 张列在下方卡片里。</p>

<div class="note warn">
<p><b>成本支点是 T2/T3 的程序化。</b>T3 的 960 张若全走 AI 要 4,800–9,600 credits，
不现实。所以 <code>restyle_scene</code>（按明度分墨/赭石、暗部才上石青）必须先做出来——
现成的 <code>restyle_ink</code> 不能直接用，实测会把砖墙变蓝绿马赛克。</p>
</div>

<h3>3. 硬约束</h3>
<table><thead><tr><th>约束</th><th>原因</th><th>怎么守</th></tr></thead><tbody>
<tr><td><b>alpha 通道</b></td><td>精灵网格与碰撞按原轮廓做</td><td>重绘时 alpha 位对位保留</td></tr>
<tr><td><b>218 张碰撞道具的剪影</b></td><td>玩家会站上去/撞上去</td><td>只改表面不改外形</td></tr>
<tr><td><b>烘焙光照位置</b></td><td>夜景灯窗的光画在贴图里</td><td>重绘对齐原灯位，否则夜里「没有灯」</td></tr>
<tr><td><b>sortingOrder 层序</b></td><td>52–97 层视差，跨层会穿帮</td><td>换形制不改 order</td></tr>
<tr><td><b>精灵网格覆盖率</b></td><td>超出 tight mesh 的部分被裁掉</td><td>换形制要重做多边形覆盖率验证</td></tr>
<tr><td><b>水面/玻璃滚动 UV</b></td><td>靠材质 UV 动画</td><td>接缝必须可平铺</td></tr>
</tbody></table>
<p class="sub" style="margin-top:-2px"><b>最容易翻车的是光照。</b>现在每张夜景图里都烤着暖色灯窗，
重画成白天或换光源位置，关卡会立刻「失光」——玩家看到的是黑块，不是战场。</p>

<h3>4. 逐关映射</h3>
"""]

    for lv in ORDER:
        if lv not in per:
            continue
        hist, when, fit, game, match, notes, risk = MAP[lv]
        bid = lv.replace("level", "L")
        d = per[lv]
        p = sum(r["painted"] for r in d)
        h.append(f"<section class='lv'><h2>{bid} {hist}"
                 f"<span class='tag'>{when}</span>"
                 f"<span class='fit {FIT_CLASS[fit]}'>吻合 {fit}</span></h2>")
        h.append("<div class='pair2'>")
        h.append(f"<div class='box'><div class='k'>游戏原型</div>"
                 f"<div class='v'>{game}</div></div>")
        h.append(f"<div class='box'><div class='k'>历史原型</div>"
                 f"<div class='v'>{hist} · {when}</div></div></div>")
        h.append(f"<p class='cap'><b>形态吻合点：</b>{match}</p>")

        strip = prev(os.path.join(SHEETS, f"scene_{lv}_rows.png"))
        full = f"../art/scene_sheets/scene_{lv}_rows.png"
        if strip is None:
            strip = prev(os.path.join(SHEETS, f"scene_{lv}.png"))
            full = f"../art/scene_sheets/scene_{lv}.png"
        if strip:
            h.append(f"<a class='shot' href='{full}'><img src='{strip}'></a>")
            h.append("<div class='cap'>现状合成全景 — 这是要改的对象</div>")

        h.append("<h4>改造要点</h4><ul>")
        for n in notes:
            h.append(f"<li>{n}</li>")
        h.append("</ul>")

        if risk:
            h.append(f"<div class='note warn'><p>{risk}</p></div>")

        marks = sorted(d, key=lambda r: -r["painted"])[:14]
        h.append(f"<h4>T1 地标清单 — 该关绘制面积前 14 张（共 {len(d)} 张 / "
                 f"{p / 1e6:.1f} Mpx）</h4>")
        h.append("<table><thead><tr><th>纹理</th><th class='num'>尺寸</th>"
                 "<th class='num'>painted</th><th class='num'>引用</th>"
                 "<th>碰撞</th></tr></thead><tbody>")
        for r in marks:
            w, hh = r["size"]
            flag = "<span class='col'>● 需守轮廓</span>" if r.get("collider") else "—"
            h.append(f"<tr><td class='mono'>{r['texture']}</td>"
                     f"<td class='num'>{w}×{hh}</td>"
                     f"<td class='num'>{r['painted'] / 1e6:.2f} M</td>"
                     f"<td class='num'>×{r['renderers']}</td>"
                     f"<td>{flag}</td></tr>")
        h.append("</tbody></table></section>")

    h.append("""<h3>5. 下一步</h3>
<div class="note"><p>1. 先出 <b>L3 仰光港</b> 的 14 张地标改造 brief：每张给
「原图 / 历史参照 / 必须保留的结构 / 可改的部分」。<br>
2. 同时把 <code>restyle_scene</code> 的规则定下来（明度分层 + 材质映射 + 纸纹），
这是 T2/T3 的前提。<br>
3. 一关做完验收（风格、光照、碰撞、层序四项），再复制到其余 12 关。</p></div>
<p class="sub" style="margin-top:20px">数据源：art/scene_inventory.json（1450 行）·
方案文字版：docs/SCENE_PLAN.md · 清单与样图：docs/SCENE_LAYERS.html</p>
</div></body></html>""")

    with io.open(DOC, "w", encoding="utf-8") as fh:
        fh.write("\n".join(h))
    print(f"-> {DOC} ({os.path.getsize(DOC) / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
