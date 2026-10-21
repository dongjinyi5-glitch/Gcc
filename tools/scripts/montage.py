"""Quick labelled montage for visual identification of roster PNGs.

usage: python montage.py out.png Gangster1 Gangster2 ...
"""
import os, sys
from PIL import Image, ImageDraw, ImageFont

ROOT = r"D:\AI\DAIGuns, Gore and Cannoli from WB"
CH = os.path.join(ROOT, "extracted", "characters")

def font(size):
    for p in (r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\simhei.ttf"):
        if os.path.isfile(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    return ImageFont.load_default()

out = sys.argv[1]
names = sys.argv[2:]
CELL_W, CELL_H = 380, 480
COLS = min(3, len(names))
rows = (len(names) + COLS - 1) // COLS
sheet = Image.new("RGB", (COLS * CELL_W, rows * CELL_H), (250, 247, 240))
d = ImageDraw.Draw(sheet)
f = font(22)
for i, n in enumerate(names):
    cx, cy = (i % COLS) * CELL_W, (i // COLS) * CELL_H
    d.rectangle([cx + 3, cy + 3, cx + CELL_W - 3, cy + CELL_H - 3],
                fill=(255, 255, 252), outline=(190, 180, 160))
    p = os.path.join(CH, n + ".png")
    im = Image.open(p).convert("RGBA")
    im.thumbnail((CELL_W - 30, CELL_H - 60), Image.LANCZOS)
    bg = Image.new("RGBA", im.size, (255, 255, 252, 255))
    bg.alpha_composite(im)
    sheet.paste(bg.convert("RGB"),
                (cx + (CELL_W - im.width) // 2, cy + 14 + (CELL_H - 60 - im.height) // 2))
    d.text((cx + CELL_W // 2, cy + CELL_H - 30), n, font=f, fill=(20, 20, 20), anchor="mm")
sheet.save(out)
print(out, sheet.size)
