"""Build a before/after comparison sheet for restyled sprite parts.

Layout: one row per part, original on the left, 重彩 version on the right, both
shown at the same integer zoom on a paper-toned background so the stroke width
can be judged the way the player sees it.
"""
import os
import sys

from PIL import Image, ImageDraw

PROJECT = r"D:\AI\DAIGuns, Gore and Cannoli from WB"


def build(char="vinnie", zoom=2, cols=4, out=None, only=None):
    src = os.path.join(PROJECT, "art", f"{char}_parts", "original")
    dst = os.path.join(PROJECT, "art", f"{char}_parts", "restyled")
    files = [f for f in sorted(os.listdir(dst)) if f.endswith(".png")]
    if only:
        files = [f for f in files if any(o in f for o in only)]
    if not files:
        raise SystemExit("nothing restyled yet")

    cell_w, cell_h = 300, 240
    rows = (len(files) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * cell_w, rows * cell_h), (232, 224, 208))
    dr = ImageDraw.Draw(sheet)

    for i, f in enumerate(files):
        a = Image.open(os.path.join(src, f)).convert("RGBA")
        b = Image.open(os.path.join(dst, f)).convert("RGBA")
        cx, cy = (i % cols) * cell_w, (i // cols) * cell_h
        box_w = cell_w // 2 - 8

        for j, im in enumerate((a, b)):
            im = im.copy()
            im.thumbnail((box_w - 6, cell_h - 40), Image.NEAREST)
            bg = Image.new("RGBA", (box_w, cell_h - 34), (243, 235, 220, 255))
            bg.alpha_composite(im, ((box_w - im.width) // 2,
                                    (cell_h - 34 - im.height) // 2))
            sheet.paste(bg.convert("RGB"), (cx + 4 + j * (box_w + 4), cy + 26))
        dr.text((cx + 6, cy + 6), f[:34], fill=(40, 30, 24))
        dr.text((cx + 6, cy + 16), "original  |  重彩", fill=(120, 100, 80))

    out = out or os.path.join(PROJECT, "art", f"{char}_parts", "_compare.png")
    sheet.save(out)
    print("saved", out, sheet.size)
    return out


if __name__ == "__main__":
    only = sys.argv[1:] or None
    build(only=only)
