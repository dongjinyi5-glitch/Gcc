"""Render the character straight out of the *patched game files*.

This is not a preview of the art folder: it loads ``ggc_Data/resources.assets``
and the sharedassets files, walks the real Vinnie prefab, and composites the
sprites the engine would sample. If the patch landed, this image shows it; if a
texture region was written to the wrong offset, this image breaks.

Use ``--dir`` to point at the pristine backup instead and get the before image
from the same code path.
"""
import math
import os
import sys

from PIL import Image, ImageDraw

from ggc_assets import AssetDB, tn

PROJECT = r"D:\AI\Guns, Gore and Cannoli from WB"
PPU_OUT = 150.0
PAD = 30


def compose(db, char):
    go = db.find_go(char)
    if go is None:
        raise SystemExit(f"{char} not found")
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
        img = meta["image"]
        ppu = meta["ppu"]
        lx = p.x - (meta["pivot_x"] / ppu) * p.sx
        ly = p.y - (meta["pivot_y"] / ppu) * p.sy
        ux = lx + (img.width / ppu) * p.sx
        uy = ly + (img.height / ppu) * p.sy
        minx, maxx = min(minx, lx), max(maxx, ux)
        miny, maxy = min(miny, ly), max(maxy, uy)
        resolved.append((lx, ly, ux, uy, img))

    W = int(math.ceil((maxx - minx) * PPU_OUT)) + PAD * 2
    H = int(math.ceil((maxy - miny) * PPU_OUT)) + PAD * 2
    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    for lx, ly, ux, uy, img in resolved:
        px = (lx - minx) * PPU_OUT + PAD
        py = (maxy - uy) * PPU_OUT + PAD
        pw = max(1, int(round((ux - lx) * PPU_OUT)))
        ph = max(1, int(round((uy - ly) * PPU_OUT)))
        canvas.alpha_composite(img.resize((pw, ph), Image.LANCZOS),
                               (int(round(px)), int(round(py))))
    return canvas, len(resolved)


def main():
    char = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("-") else "Vinnie"
    use_backup = "--backup" in sys.argv
    data_dir = (os.path.join(PROJECT, "backup") if use_backup
                else r"D:\BaiduNetdiskDownload\意大利黑1\Guns, Gore and Cannoli\ggc_Data")
    tag = "original" if use_backup else "patched"

    db = AssetDB(data_dir=data_dir)
    canvas, n = compose(db, char)
    out_dir = os.path.join(PROJECT, "art", "original-capture")
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, f"{char.lower()}_{tag}_from_gamefiles.png")
    canvas.save(out)

    # a paper-backed copy for eyeballing
    paper = Image.new("RGBA", canvas.size, (243, 235, 220, 255))
    paper.alpha_composite(canvas)
    dr = ImageDraw.Draw(paper)
    dr.text((6, 4), f"{char} — read directly from {tag} game files",
            fill=(60, 48, 38))
    paper.convert("RGB").save(out.replace(".png", "_paper.png"))
    print(f"composed {n} parts -> {out}")


if __name__ == "__main__":
    main()
