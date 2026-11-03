"""Sort the in-engine screenshots into per-level, per-zone folders and build an index.

The shots come off `shot_hotkey.ps1` with only a timestamp for a name, so the first
job here is attribution: which level, which room.  That cannot be read off the file
name -- the 10:13-10:17 batch was tagged `L3` but was actually taken in 暴徒镇港口 /
市郊, and keeping it in the L3 set would have poisoned every later comparison.

Zone order follows how the level is actually walked: dock -> deck -> cargo hold ->
cabin -> engine room.  Files are *copied*, not moved, and the script is idempotent,
so re-running after a new batch only adds what is new.
"""
import io
import json
import os
import shutil

from PIL import Image, ImageDraw, ImageFont

PROJECT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
SHOTS = os.path.join(PROJECT, "art", "scene_shots")
OUT = os.path.join(SHOTS, "L3_boat")
DOC = os.path.join(OUT, "INDEX.html")
MANIFEST = os.path.join(OUT, "manifest.json")

FONT = "C:/Windows/Fonts/msyhbd.ttc"
FONTR = "C:/Windows/Fonts/msyh.ttc"

# zone id -> (folder, 中文名, 一句话说明)
ZONES = {
    "01_dock":   ("01_dock",   "码头与登船", "夜间港口：月亮、多船剪影、跳板与木栈道"),
    "02_deck":   ("02_deck",   "上层甲板",   "船舷栏杆、吊车与吊货、救生圈"),
    "03_cargo":  ("03_cargo",  "货舱",       "集装箱、麻袋、舱口与装卸平台"),
    "04_cabin":  ("04_cabin",  "船内主舱",   "卧铺、舷窗、书桌、长餐桌、红漆柜"),
    "05_engine": ("05_engine", "机舱锅炉",   "管道、阀门、锅炉、楼梯"),
}

# src -> (zone, new name, 标题, 备注)
SHOTS_MAP = [
    ("L3_20261023_120704_08.png", "01_dock", "L3_01_dock_01_harbour_panorama.png",
     "港口全景 · 多船剪影",
     "最有价值的一张：整条水平线的船队剪影、三台吊车、月亮。构图可直接作为 L3 天幕重绘的底稿。"),
    ("L3_20261023_120502_05.png", "01_dock", "L3_01_dock_02_gangway_moon.png",
     "登船跳板 · 月亮",
     "跳板与船舷的交界，水面色阶从深蓝到近黑。水面笔法的唯一参考。"),
    ("L3_20261023_120639_07.png", "01_dock", "L3_01_dock_03_stairs_bulwark.png",
     "码头楼梯 · 船舷侧壁",
     "左侧钢梯与右侧船舷铆钉板，远景是第二层船队。纵深关系的参考。"),

    ("L3_20261023_175740_16.png", "02_deck", "L3_02_deck_02_steelwall_stairs.png",
     "甲板 · 钢制舱壁与舷梯口",
     "整面铆钉钢板、钢梯、右侧透出主舱。船内到船外的分界，材质对比最强。"),
    ("L3_20261023_180025_17.png", "02_deck", "L3_02_deck_03_gangway_moon.png",
     "甲板 · 舷梯与月亮",
     "通往上层平台的钢梯、月亮、远处第二艘船、成堆木箱。船外空间关系的参考。"),

    ("L3_20261023_120624_06.png", "02_deck", "L3_02_deck_01_crane_lifering.png",
     "甲板吊车 · 救生圈",
     "吊车吊起担架与尸体、救生圈、栏杆、下方月亮。吊索的线条最清楚的一张。"),

    ("L3_20261023_180448_18.png", "03_cargo", "L3_03_cargo_04_loading_combat.png",
     "货舱 · 装卸区战斗",
     "从舱内往外看，天窗透月光、红布麻袋、铁皮集装箱、斜撑木板，出怪状态。"),

    ("L3_20261023_120804_09.png", "03_cargo", "L3_03_cargo_01_containers.png",
     "货舱 · 集装箱与麻袋",
     "木箱、铁皮集装箱、红布麻袋、斜撑木板，构成 L3 的主体重复图案。"),
    ("L3_20261023_121034_11.png", "03_cargo", "L3_03_cargo_02_hatch_lookup.png",
     "货舱装卸口 · 仰视",
     "从舱内往上看月光透进舱口，是唯一一张逆光视角。"),
    ("L3_20261023_120946_10.png", "03_cargo", "L3_03_cargo_03_combat.png",
     "货舱 · 战斗（含僵尸）",
     "同一区域出怪状态，可确认角色在货舱暗部的可读性。"),

    ("L3_20261023_175413_12.png", "04_cabin", "L3_04_cabin_03_start_clean.png",
     "主舱起点 · 卧铺区（干净版）",
     "本关开局第一屏。无教程红条，卧铺、舷窗、书桌、海报墙完整可见，取代被遮挡的那张。"),
    ("L3_20261023_175433_13.png", "04_cabin", "L3_04_cabin_04_mess_body.png",
     "主舱餐区 · 尸体",
     "红漆储物柜、舷窗、控制台、盘绳。同一空间的血污状态。"),

    ("L3_20261023_120142_01.png", "04_cabin", "L3_04_cabin_01_bunks.png",
     "主舱卧铺区",
     "上下铺、舷窗、书桌、海报墙。顶部有教程红条遮挡天花板。"),
    ("L3_20261023_120200_02.png", "04_cabin", "L3_04_cabin_02_mess.png",
     "主舱餐区 · 红漆柜",
     "长桌、红漆储物柜、管道阀门。画面中央被教程条与大片血污遮挡。"),

    ("L3_20261023_175538_14.png", "05_engine", "L3_05_engine_03_corridor.png",
     "机舱前段 · 红柜与管道",
     "红漆柜、海图、成排管道、成堆麻袋。主舱到机舱的过渡段，两种材质的交界。"),
    ("L3_20261023_175631_15.png", "05_engine", "L3_05_engine_04_boilers.png",
     "机舱 · 锅炉组与斜梯",
     "三台卧式锅炉、巨大的斜向梯架、黄铜阀门。金属反光最集中的一张。"),

    ("L3_20261023_120243_03.png", "05_engine", "L3_05_engine_01_boiler.png",
     "机舱 · 锅炉与阀门",
     "锅炉、压力表、阀门组、盘绳。金属高光与铜绿的最集中处。"),
    ("L3_20261023_120405_04.png", "05_engine", "L3_05_engine_02_stairs_mess.png",
     "机舱→餐厅过渡 · 楼梯",
     "左侧钢梯通往上层，右侧长餐桌与舷窗。两个空间的光比对照。"),
]

# 拍错了关的三张：文件名带 L3，实际在 暴徒镇港口 / 市郊
MISFILED = [
    ("L3_20261023_101338_01_game.png", "L4_L5_harbour", "harbour_01_ship_gangway.png",
     "船舷外壁 · 跳板", "推定 L4 暴徒镇港口", "深蓝铆钉船壳、救生圈、黄色舷灯。"),
    ("L3_20261023_101743_03_game.png", "L4_L5_harbour", "harbour_02_brick_quay.png",
     "红砖码头 · 系船柱", "推定 L4 暴徒镇港口", "砖墙纹理即 Quay_05，已确认为重绘后状态。"),
    ("L3_20261023_101706_02_game.png", "L4_L5_harbour", "harbour_03_fuel_oil_yard.png",
     "FUEL OIL 罐车区", "推定 L5 市郊", "1926 年式油罐车、蒸汽船驾驶室。"),
]

ANALYSIS = [
    ("ingame_now.png", "早期实机帧"), ("_brick_3way.png", "Quay_05 三方对比"),
    ("_quay05_cmp.png", "Quay_05 重绘对比"), ("_zoom_left.png", "左半细节"),
    ("_zoom_left_tank.png", "左侧储罐细节"), ("_zoom_right.png", "右半细节"),
    ("_zoom_right_crane.png", "右侧吊车细节"), ("_zoom_sky.png", "天空细节"),
]

# 还能补的：只剩可选。L3 的拍摄已经完成。
OPTIONAL = [
    ("可选", "01_dock", "水面近景（贴近跳板下的水面，画面只留水和倒影）",
     "水面在国画里靠 石青/花青 波纹加留白，现在图里水面只占很细一条，"
     "看不出笔法层次。不影响重绘启动，什么时候顺手拍到都行。"),
]

# 已经排除、不必再拍的
CLOSED = [
    ("船体外观全景", "游戏内每一屏都是局部视角，整条船无法一次入画。",
     "不需要 —— 原生全景贴图（7000×1018）本来就包含整条船，比任何截图都完整。"),
    ("驾驶室 / 舵轮", "本关没有这一间。",
     "已由你确认排除。`Wheelhouse_01` 这张贴图存在，但它是船体外观件，不是可进入的房间。"),
]

CSS = """
:root{--bg:#faf8f4;--card:#fff;--ink:#1c1a17;--mut:#6d675e;--line:#e2dcd2;
--warm:#8c4a2f;--cool:#2c5a7c;--gold:#a8791f}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
font:15px/1.75 "Microsoft YaHei","PingFang SC",sans-serif}
.wrap{max-width:1180px;margin:0 auto;padding:56px 32px 96px}
h1{font-size:30px;margin:0 0 6px;letter-spacing:.5px}
.sub{color:var(--mut);font-size:14px;margin-bottom:34px}
h2{font-size:20px;margin:56px 0 6px;padding-top:22px;border-top:1px solid var(--line)}
h2 .zid{font:12px/1 monospace;color:var(--gold);margin-right:10px;vertical-align:2px}
h2 small{font-weight:400;color:var(--mut);font-size:13px;margin-left:10px}
h3{font-size:16px;margin:0 0 4px}
table{border-collapse:collapse;width:100%;font-size:14px;margin:16px 0 8px}
th,td{text-align:left;padding:9px 12px;border-bottom:1px solid var(--line);vertical-align:top}
th{background:#f2ede4;font-weight:700;font-size:13px;color:#4a443b}
tr:hover td{background:#fdfcf9}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(330px,1fr));gap:20px;margin-top:18px}
figure{margin:0;background:var(--card);border:1px solid var(--line);border-radius:8px;overflow:hidden;
box-shadow:0 1px 2px rgba(0,0,0,.04)}
figure img{display:block;width:100%;height:auto;background:#111}
figcaption{padding:11px 13px 13px}
figcaption b{font-size:14px}
figcaption p{margin:5px 0 0;font-size:12.5px;line-height:1.6;color:var(--mut)}
code{font:12px/1 Consolas,monospace;color:#8a8378;background:#f1ece3;
padding:2px 5px;border-radius:3px;display:inline-block;margin-top:6px}
.p0{color:#a32a1e;font-weight:700}.p1{color:#b07a17;font-weight:700}
.p2{color:#4a6b2f;font-weight:700}.p3{color:#6d675e;font-weight:700}
.note{background:#fff8ea;border-left:3px solid var(--gold);padding:13px 16px;
font-size:13.5px;color:#5b5348;margin:20px 0;border-radius:0 5px 5px 0}
.ok{background:#f0f5ee;border-left:3px solid #4a6b2f;padding:13px 16px;
font-size:13.5px;color:#3d4a34;margin:20px 0;border-radius:0 5px 5px 0}
"""


def build():
    os.makedirs(OUT, exist_ok=True)
    for z in ZONES:
        os.makedirs(os.path.join(OUT, z), exist_ok=True)
    os.makedirs(os.path.join(SHOTS, "L4_L5_harbour"), exist_ok=True)
    os.makedirs(os.path.join(SHOTS, "_analysis"), exist_ok=True)

    manifest = []
    for src, zone, name, title, note in SHOTS_MAP:
        s = os.path.join(SHOTS, src)
        if not os.path.exists(s):
            print("missing:", src)
            continue
        d = os.path.join(OUT, zone, name)
        shutil.copy2(s, d)
        im = Image.open(d)
        manifest.append(dict(zone=zone, zone_cn=ZONES[zone][1], file=name, title=title,
                             note=note, size=list(im.size), src=src))
        print("ok  %-14s %s" % (zone, name))

    for src, folder, name, title, guess, note in MISFILED:
        s = os.path.join(SHOTS, src)
        if not os.path.exists(s):
            print("missing:", src)
            continue
        d = os.path.join(SHOTS, folder, name)
        shutil.copy2(s, d)
        print("ok  %-14s %s" % (folder, name))

    for src, title in ANALYSIS:
        s = os.path.join(SHOTS, src)
        if os.path.exists(s):
            shutil.copy2(s, os.path.join(SHOTS, "_analysis", src))

    with io.open(MANIFEST, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)

    contact_sheet(manifest)
    write_index(manifest)


def contact_sheet(manifest):
    """One labelled strip, zone-grouped -- for eyeballing coverage at a glance."""
    cw, ch, lab = 400, 226, 34
    cols = 4
    rows = (len(manifest) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * cw, rows * (ch + lab)), "#14120f")
    dr = ImageDraw.Draw(sheet)
    f = ImageFont.truetype(FONTR, 13)
    for i, m in enumerate(manifest):
        im = Image.open(os.path.join(OUT, m["zone"], m["file"])).convert("RGB")
        im.thumbnail((cw - 8, ch - 8), Image.LANCZOS)
        x, y = (i % cols) * cw, (i // cols) * (ch + lab)
        sheet.paste(im, (x + (cw - im.width) // 2, y + (ch - im.height) // 2))
        dr.text((x + 6, y + ch + 8), m["zone"][:2] + " " + m["title"][:24],
                font=f, fill="#e8e2d6")
    sheet.save(os.path.join(OUT, "_sheet.png"))
    print("sheet ->", os.path.join(OUT, "_sheet.png"))


def write_index(manifest):
    by_zone = {}
    for m in manifest:
        by_zone.setdefault(m["zone"], []).append(m)

    h = ['<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">',
         "<title>L3 轮船 · 实机截图归档</title><style>%s</style></head><body><div class=wrap>" % CSS,
         "<h1>L3 轮船 · 实机截图归档</h1>",
         '<div class="sub">共 %d 张 · 全部 1360×768（游戏实际渲染分辨率，非 1080P）· '
         '按关卡动线分五个区域<br>补丁状态：L3 的 167 张纹理已写入 sharedassets4.assets，'
         '本批截图确认仍在生效（货舱天空采样 19/23/33，重绘值 19/23/34，原始 3/24/41）</div>'
         % len(manifest)]

    h.append("<h2>覆盖总表</h2><table><tr><th>区域</th><th>张数</th><th>关键画面</th>"
             "<th>够用吗</th></tr>")
    verdict = {"01_dock": ("够", "全景、跳板、楼梯三个机位齐全"),
               "02_deck": ("够", "吊车、钢制舱壁、舷梯三个机位，船外空间关系清楚了"),
               "03_cargo": ("够", "平视、仰视、战斗、装卸四种状态都有"),
               "04_cabin": ("够", "补到干净的开局首屏，红条遮挡问题解决"),
               "05_engine": ("够", "锅炉、阀门组、斜梯、过渡段各一张")}
    for z, (folder, cn, desc) in ZONES.items():
        ms = by_zone.get(z, [])
        best = ms[0]["title"] if ms else "—"
        v = verdict[z]
        h.append("<tr><td><b>%s</b><br><span style='color:#6d675e;font-size:12.5px'>%s</span></td>"
                 "<td>%d</td><td>%s</td><td>%s<br><span style='font-size:12.5px;color:#6d675e'>%s</span></td></tr>"
                 % (cn, desc, len(ms), best, v[0], v[1]))
    h.append("</table>")

    h.append('<div class="ok"><b>L3 拍摄已完成。</b>18 张覆盖五个区域加上区域之间的过渡段，'
             '从开局第一屏（主舱卧铺）一直到船外舷梯，动线每一段都有图。'
             '补丁也确认在生效 —— 货舱天空采样 19/23/33，重绘值 19/23/34，原始 3/24/41。</div>')

    h.append("<h2>还可补（可选，不影响开工）</h2><table>"
             "<tr><th style='width:56px'>优先级</th><th style='width:110px'>区域</th>"
             "<th>要拍什么</th><th>为什么</th></tr>")
    for p, z, what, why in OPTIONAL:
        h.append("<tr><td class=p3>%s</td><td>%s</td><td>%s</td>"
                 "<td style='color:#6d675e;font-size:13px'>%s</td></tr>"
                 % (p, ZONES[z][1], what, why))
    h.append("</table>")

    h.append("<h2>已排除，不必再拍</h2><table>"
             "<tr><th style='width:170px'>项目</th><th style='width:300px'>原因</th>"
             "<th>结论</th></tr>")
    for what, why, concl in CLOSED:
        h.append("<tr><td><b>%s</b></td><td style='color:#6d675e'>%s</td>"
                 "<td style='font-size:13px'>%s</td></tr>" % (what, why, concl))
    h.append("</table>")
    h.append('<div class="note"><b>关于连续逐屏截图：</b>这个提议方向是对的，但对轮船这一关'
             '收益已经不大 —— 原生全景贴图（7000×1018）比任何拼接都完整，'
             '逐屏截图能补的只是视差层的实际观感。<b>建议把「连续逐屏」留到河流、'
             '下水道这几关</b>：那几关的纵深更复杂，而且没有轮船这样一张现成的长条全景。</div>')

    h.append('<div class="ok"><b>顺带确认的边界：</b>夜间区域（L* 5–20）restyle 只会得到近中性墨，'
             '所以船壳、木栈道、集装箱、锅炉这些地标必须走 ImageGen 重绘，restyle 只能兜底。'
             '这条结论已经落进《背景构件替换总表》的分档（P1 重绘 / P2 待核 / P3 换色阶）。</div>')

    for z, (folder, cn, desc) in ZONES.items():
        ms = by_zone.get(z, [])
        if not ms:
            continue
        h.append("<h2><span class=zid>%s</span>%s<small>%s</small></h2>" % (z, cn, desc))
        h.append('<div class="grid">')
        for m in ms:
            h.append('<figure><img src="%s/%s" alt="%s" loading=lazy>'
                     "<figcaption><b>%s</b><p>%s</p><code>%s/%s</code></figcaption></figure>"
                     % (m["zone"], m["file"], m["title"], m["title"], m["note"],
                        m["zone"], m["file"]))
        h.append("</div>")

    h.append("<h2>附录 A · 拍错关的三张（已移出 L3）</h2>")
    h.append('<div class="note">这三张文件名带 <code>L3_</code>，但拍摄时人在'
             '<b>暴徒镇港口 / 市郊</b>。留在 L3 集合里会让后面所有对比失真，'
             '已移到 <code>art/scene_shots/L4_L5_harbour/</code>。'
             '其中红砖码头那张的砖纹就是 Quay_05 —— 已被 L3/L4/L5 共用，'
             '这正是「共享纹理必须整组推进」那条规则的实物证据。</div>')
    h.append("<table><tr><th>文件</th><th>内容</th><th>推定关卡</th><th>备注</th></tr>")
    for src, folder, name, title, guess, note in MISFILED:
        h.append("<tr><td><code>%s</code></td><td>%s</td><td>%s</td>"
                 "<td style='font-size:13px;color:#6d675e'>%s</td></tr>"
                 % (name, title, guess, note))
    h.append("</table>")

    h.append("<h2>附录 B · 分析产物</h2>")
    h.append('<div class="note">下面这些不是游戏截图，是我之前做对比、取样时生成的图，'
             '已归到 <code>art/scene_shots/_analysis/</code>，不要和实机截图混在一起。</div>')
    h.append("<p style='font-size:13.5px;color:#6d675e'>%s</p>"
             % "、".join("%s（%s）" % (n, t) for n, t in ANALYSIS
                        if os.path.exists(os.path.join(SHOTS, "_analysis", n))))

    h.append("</div></body></html>")
    with io.open(DOC, "w", encoding="utf-8") as f:
        f.write("\n".join(h))
    print("doc  ->", DOC)


if __name__ == "__main__":
    build()
