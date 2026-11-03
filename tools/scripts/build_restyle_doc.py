"""Build docs/RESTYLE_ALL.html -- the whole game, restyled, level by level.

Pairs each level's original panorama with the restyle_scene v2 output at the same
scale, so the only variable is the palette.  The numbers in the table are read
from art/scene_inventory.json; the historical theme comes from build_scene_plan.MAP
so the two documents cannot disagree about what a level is supposed to be.

Previews are JPEG, not PNG: these are dark gradients with a lot of thin lamps,
which PNG stores at 2-4 MB each, and 26 of them would make the page unopenable.
"""
import io
import json
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ggc_assets import PROJECT  # noqa: E402
from build_scene_plan import MAP  # noqa: E402

ART = os.path.join(PROJECT, "art")
SHEETS = os.path.join(ART, "scene_sheets")
CMP = os.path.join(ART, "scene_restyle", "cmp")
DOC = os.path.join(PROJECT, "docs", "RESTYLE_ALL.html")
INV = os.path.join(ART, "scene_inventory.json")

ORDER = ["level0"] + [f"level{i}" for i in range(3, 15)]
W = 1800            # comparison strip width
FONT = "C:/Windows/Fonts/msyhbd.ttc"
FONTS = "C:/Windows/Fonts/consola.ttf"


def counts():
    rows = json.load(io.open(INV, encoding="utf-8"))
    n, px = {}, {}
    for r in rows:
        for lv in r["levels"]:
            n[lv] = n.get(lv, 0) + 1
            px[lv] = px.get(lv, 0.0) + r.get("painted", 0) / 1e6
    return n, px


def content_box(a, b, thr=12, pad=12):
    """Shared crop box, so the two strips stay pixel-aligned.

    A level's panorama bbox is set by the *transform* extremes, not by where the
    art is: level8 is 7000x1033 with the street occupying a 200 px band in the
    middle, so at page width the art was a 50 px smear.  Crop to the union of
    both images' non-black pixels and the same width shows five times the detail.
    """
    la, lb = np.asarray(a.convert("L")), np.asarray(b.convert("L"))
    m = np.maximum(la, lb) > thr
    if not m.any():
        return None
    ys = np.where(m.any(axis=1))[0]
    xs = np.where(m.any(axis=0))[0]
    return (max(0, int(xs[0]) - pad), max(0, int(ys[0]) - pad),
            min(a.width, int(xs[-1]) + pad), min(a.height, int(ys[-1]) + pad))


def strip(lv, note):
    a = Image.open(os.path.join(SHEETS, f"scene_{lv}.png")).convert("RGB")
    b = Image.open(os.path.join(SHEETS, f"scene_{lv}_restyled.png")).convert("RGB")
    box = content_box(a, b)
    if box:
        a, b = a.crop(box), b.crop(box)
    k = W / a.width
    a = a.resize((W, max(1, int(a.height * k))), Image.LANCZOS)
    b = b.resize((W, max(1, int(b.height * k))), Image.LANCZOS)
    pad, hdr = 26, 30
    cv = Image.new("RGB", (W, hdr + a.height + pad + hdr + b.height), (22, 22, 26))
    d = ImageDraw.Draw(cv)
    f = ImageFont.truetype(FONTS, 14)
    y = 0
    for tag, im in (("original", a), ("restyle_scene v2", b)):
        d.text((10, y + 6), f"{lv} — {tag}", font=f, fill=(150, 152, 162))
        y += hdr
        cv.paste(im, (0, y))
        y += im.height + pad
    p = os.path.join(CMP, f"{lv}.jpg")
    cv.save(p, quality=88, optimize=True, progressive=True)
    print(f"  {p} {cv.size}")
    return p


def main():
    os.makedirs(CMP, exist_ok=True)
    n, px = counts()
    parts, rows = [], []
    for lv in ORDER:
        a = os.path.join(SHEETS, f"scene_{lv}.png")
        b = os.path.join(SHEETS, f"scene_{lv}_restyled.png")
        if not (os.path.isfile(a) and os.path.isfile(b)):
            print(f"  ! {lv} missing a panorama, skipped")
            continue
        hist, when, fit, orig, _why, _todo, _risk = MAP[lv]
        p = strip(lv, "")
        rel = os.path.relpath(p, os.path.join(PROJECT, "docs")).replace("\\", "/")
        rows.append(
            f"<tr><td class=lv>{lv.replace('level', 'L')}</td>"
            f"<td>{hist}<span class=d>{when} · 吻合{fit}</span></td>"
            f"<td class=n>{n.get(lv, 0)}</td><td class=n>{px.get(lv, 0):.1f}</td>"
            f"<td><a href='#{lv}'>看对比</a></td></tr>")
        parts.append(
            f"<section id={lv}><h2>{lv.replace('level', 'L')} · {hist}"
            f"<span class=d>{when}　原版：{orig}</span></h2>"
            f"<div class=shot><img src='{rel}' alt='{lv}'></div></section>")

    tot_n = sum(n.values())
    tot_px = sum(px.values())

    # Close-up evidence.  The level strips answer "did the palette change"; these
    # answer "does it survive being looked at", which is the part that decides
    # whether the pass is usable or only a placeholder.
    detail = []
    for fn, cap in (("_preview.png", "八张代表贴图：上原图 / 下重彩（缩略）"),
                    ("_cmp_level3_ship.png", "L3 船体段 1:1 前后对比")):
        p = os.path.join(ART, "scene_restyle", fn)
        if os.path.isfile(p):
            rel = os.path.relpath(p, os.path.join(PROJECT, "docs")).replace("\\", "/")
            detail.append(f"<div class=shot><img src='{rel}' alt='{fn}'></div>"
                          f"<p class=cap>{cap}</p>")

    html = f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">
<title>全库重彩化 — restyle_scene v2</title><style>
:root{{--bg:#15151a;--card:#1e1e24;--ink:#e8e8ee;--dim:#969aa6;--acc:#d6a860}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--ink);
font:15px/1.75 "Microsoft YaHei",system-ui,sans-serif}}
.wrap{{max-width:1240px;margin:0 auto;padding:48px 28px 96px}}
h1{{font-size:30px;margin:0 0 6px;letter-spacing:.5px}}
.sub{{color:var(--dim);margin:0 0 34px;font-size:14px}}
h2{{font-size:19px;margin:44px 0 14px;border-left:3px solid var(--acc);
padding-left:12px}}
h2 .d{{display:block;font-size:13px;color:var(--dim);font-weight:400;
margin-top:4px;border:0}}
.card{{background:var(--card);border-radius:10px;padding:22px 24px;margin:0 0 26px}}
table{{width:100%;border-collapse:collapse;font-size:13.5px}}
th{{text-align:left;color:var(--dim);font-weight:500;padding:7px 8px;
border-bottom:1px solid #33333c}}
td{{padding:7px 8px;border-bottom:1px solid #26262e;vertical-align:top}}
td.n{{text-align:right;font-family:Consolas,monospace}}
td.lv{{font-family:Consolas,monospace;color:var(--acc)}}
td .d{{display:block;color:var(--dim);font-size:12px}}
a{{color:var(--acc)}}
.shot{{background:#000;border-radius:8px;overflow:hidden;margin-bottom:10px}}
.shot img{{display:block;max-width:100%;width:auto;height:auto}}
p.cap{{color:var(--dim);font-size:12.5px;margin:0 0 18px}}
ul{{margin:8px 0 0 20px;padding:0}} li{{margin:4px 0}}
.k{{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin:0 0 26px}}
.k div{{background:var(--card);border-radius:9px;padding:14px 16px}}
.k b{{display:block;font-size:22px;font-family:Consolas,monospace;color:var(--acc)}}
.k span{{color:var(--dim);font-size:12.5px}}
</style></head><body><div class=wrap>
<h1>全库重彩化 · restyle_scene v2</h1>
<p class=sub>13 关全景，同一比例、同一位置，唯一的变量是配色。
alpha 逐位不变、L* 不动，所以几何与烘焙光照和原版逐像素对齐。</p>

<div class=k>
<div><b>{tot_n}</b><span>关卡-贴图槽位</span></div>
<div><b>{tot_px:.0f} Mpx</b><span>绘制面积（含跨关重复）</span></div>
<div><b>1450</b><span>唯一贴图（去重后实跑）</span></div>
<div><b>0</b><span>credits</span></div>
</div>

<div class=card>
<h2 style="margin-top:0">它做了什么，没做什么</h2>
<p>七步：光源估计（L*² 加权）→ 按亮度门控去色偏 → 冷暖双斜坡（按 L* 查表，
色度不随变暗衰减）→ 石绿/朱红掩膜（读原始 Lab 色相）→ 色块洗涤（只糊 a*/b*，
不动 L*）→ 绝对阈值墨线 → 纸纹。</p>
<p><b>守住了</b>：alpha 逐位相同（剪影＝碰撞与网格契约）；L* 只在墨线处下降，
灯光晕、窗光、火光全部原位。</p>
<p><b>没做到</b>：不产生笔触。远看成立，凑近看没有笔锋与飞白；平涂低对比贴图
（整片铆接钢板）最差；只有四支色相，紫、青、大面积鲜艳蓝会被压到最近的支上。</p>
<p>详细取舍与六版失败记录见 <a href="RESTYLE_SCENE.md">RESTYLE_SCENE.md</a>。</p>
</div>

<div class=card>
<h2 style="margin-top:0">凑近看</h2>
{''.join(detail)}
</div>

<div class=card>
<h2 style="margin-top:0">逐关</h2>
<table><thead><tr><th>关卡</th><th>历史原型</th><th>贴图</th>
<th>Mpx</th><th></th></tr></thead><tbody>
{''.join(rows)}
</tbody></table>
</div>

{''.join(parts)}
</div></body></html>"""
    io.open(DOC, "w", encoding="utf-8").write(html)
    print(f"-> {DOC} {len(html) / 1024:.0f} KB")


if __name__ == "__main__":
    main()
