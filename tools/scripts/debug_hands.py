"""Tint each hand sprite a different colour and composite, to see the overlaps.

The complaint was "too many fingers on the handguard". The hand sprites are
separate textures placed a few pixels apart, so three of them can contribute
finger strips to the same stretch of handguard. Which ones, and in what order,
decides the fix -- so it has to be seen rather than guessed.

Writes art/<char>_parts/_hand_debug.png

Usage:
    python debug_hands.py Gangster1
"""
import io
import json
import math
import os
import sys

from PIL import Image

from ggc_assets import AssetDB, PROJECT, tn

CHAR = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("--") \
    else "Vinnie"
BASE = os.path.join(PROJECT, "art", CHAR.lower() + "_parts")
PPU_OUT = 150.0
PAD = 30
BACKUP = os.path.join(PROJECT, "backup")
PRISTINE = {f: os.path.join(BACKUP, f)
            for f in os.listdir(BACKUP) if f.endswith(".assets")}

# distinct hues so overlapping sprites separate by colour
TINTS = [(214, 39, 40), (31, 119, 180), (255, 127, 14), (44, 160, 44),
         (148, 103, 189), (227, 119, 194), (127, 127, 127), (188, 189, 34),
         (140, 86, 75), (23, 190, 207)]

db = AssetDB(file_map=PRISTINE)
go = db.find_go(CHAR)
if go is None:
    raise SystemExit(f"{CHAR} not found")
parts = [p for p in db.walk(go) if p.active]

resolved = []
minx = miny = 1e9
maxx = maxy = -1e9
for p in parts:
    sp = db.resolve(p.sprite, p.ctx)
    if tn(sp) != "Sprite":
        continue
    meta = db.sprite_meta(sp)
    if not meta or "image" not in meta:
        continue
    if not (p.go_name or "").lower().startswith("hand"):
        continue
    img = meta["image"]
    ppu = meta["ppu"]
    lx = p.x - (meta["pivot_x"] / ppu) * p.sx
    ly = p.y - (meta["pivot_y"] / ppu) * p.sy
    ux = lx + (img.width / ppu) * p.sx
    uy = ly + (img.height / ppu) * p.sy
    minx, maxx = min(minx, lx), max(maxx, ux)
    miny, maxy = min(miny, ly), max(maxy, uy)
    resolved.append((lx, ly, ux, uy, img, p))

if not resolved:
    raise SystemExit(f"no active hand sprites for {CHAR}")

W = int(math.ceil((maxx - minx) * PPU_OUT)) + PAD * 2
H = int(math.ceil((maxy - miny) * PPU_OUT)) + PAD * 2
canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
legend = []
resolved.sort(key=lambda r: (r[5].order, -r[5].depth))
for i, (lx, ly, ux, uy, img, p) in enumerate(resolved):
    tint = TINTS[i % len(TINTS)]
    a = img.convert("RGBA")
    solid = Image.new("RGBA", a.size, tint + (255,))
    solid.putalpha(a.split()[3])
    px = (lx - minx) * PPU_OUT + PAD
    py = (maxy - uy) * PPU_OUT + PAD
    pw = max(1, int(round((ux - lx) * PPU_OUT)))
    ph = max(1, int(round((uy - ly) * PPU_OUT)))
    canvas.alpha_composite(solid.resize((pw, ph), Image.LANCZOS),
                           (int(round(px)), int(round(py))))
    legend.append((tint, p.go_name, p.order, i, (lx, ly, ux, uy)))

sheet = Image.new("RGB", (W + 200, H), (232, 224, 208))
paper = Image.new("RGBA", (W, H), (243, 235, 220, 255))
paper.alpha_composite(canvas)
sheet.paste(paper.convert("RGB"), (0, 0))
from PIL import ImageDraw, ImageFont
d = ImageDraw.Draw(sheet)
try:
    f = ImageFont.truetype("msyh.ttc", 13)
except OSError:
    f = ImageFont.load_default()
y = 8
d.text((W + 10, y), f"{CHAR} 手部精灵叠加顺序", fill=(40, 30, 24), font=f)
y += 22
for tint, name, order, i, rect in legend:
    d.rectangle([W + 10, y + 2, W + 26, y + 14], fill=tint)
    d.text((W + 32, y), f"{i}: {name} o={order}", fill=(40, 30, 24), font=f)
    y += 20
    d.text((W + 32, y),
           f"   ({rect[0]:.1f},{rect[1]:.1f})-({rect[2]:.1f},{rect[3]:.1f})",
           fill=(120, 106, 92), font=ImageFont.truetype("msyh.ttc", 11))
    y += 18

out = os.path.join(BASE, "_hand_debug.png")
sheet.save(out)
print(f"saved {out}")
print("drawn back-to-front:")
for tint, name, order, i, rect in legend:
    print(f"  {i}: {name:<24} order={order}")
