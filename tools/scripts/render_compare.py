"""Render a character twice -- original art vs 重彩 restyle -- and stack them.

This is the offline equivalent of an in-game screenshot: it uses the *same*
prefab hierarchy, the same pivot/PPU maths and the same sorting order as the
engine, so if the composition is wrong here it will be wrong in game too.

Outputs art/<char>_parts/_character_compare.png
"""
import json
import math
import os
import sys

from PIL import Image, ImageDraw

from ggc_assets import AssetDB, PROJECT, tn

CHAR = sys.argv[1] if len(sys.argv) > 1 else "Vinnie"
# Which override folder to compose from. "restyled" is the deterministic ink
# recolor; "redraw" is the plan-B redrawn art. Both compose into the same
# baseline so the two routes can be judged against one original.
OVERRIDE_DIR = (sys.argv[sys.argv.index("--dir") + 1]
                if "--dir" in sys.argv else "restyled")
SUFFIX = OVERRIDE_DIR
BASE = os.path.join(PROJECT, "art", CHAR.lower() + "_parts")
MANIFEST = os.path.join(BASE, "manifest.json")
PPU_OUT = 150.0
PAD = 30

# The "before" side MUST come from the pristine backups. Once a texture is
# patched in place, reading the live game file returns the restyled pixels, and
# the baseline column silently becomes a copy of the result column -- the
# comparison then reads ~zero difference while proving nothing.
BACKUP = os.path.join(PROJECT, "backup")
PRISTINE = {}
if os.path.isdir(BACKUP):
    PRISTINE = {f: os.path.join(BACKUP, f)
                for f in os.listdir(BACKUP) if f.endswith(".assets")}


def load_overrides():
    with open(MANIFEST, encoding="utf-8") as fh:
        man = json.load(fh)
    ov = {}
    for p in man["parts"]:
        path = os.path.join(BASE, OVERRIDE_DIR, p["file"])
        if os.path.isfile(path):
            ov[(p["sprite_file"], p["sprite_path_id"])] = path
    for f in man["frames"]:
        path = os.path.join(BASE, OVERRIDE_DIR, f["file"])
        if os.path.isfile(path):
            ov[("frame", f["texture_name"])] = path
    return ov


def compose(db, parts, overrides):
    """Return (canvas, part_count). Uses restyled art when available."""
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
        key = (meta["sprite_file"], meta["sprite_path_id"])
        if key in overrides:
            img = Image.open(overrides[key]).convert("RGBA")
        else:
            img = meta["image"]
        ppu = meta["ppu"]
        lx = p.x - (meta["pivot_x"] / ppu) * p.sx
        ly = p.y - (meta["pivot_y"] / ppu) * p.sy
        ux = lx + (img.width / ppu) * p.sx
        uy = ly + (img.height / ppu) * p.sy
        minx, maxx = min(minx, lx), max(maxx, ux)
        miny, maxy = min(miny, ly), max(maxy, uy)
        resolved.append((lx, ly, ux, uy, img))

    if not resolved:
        return None, 0
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
    if not PRISTINE:
        raise SystemExit("backup/ is missing -- cannot render a trustworthy "
                         "'before' side from patched game files")
    db = AssetDB(file_map=PRISTINE)
    go = db.find_go(CHAR)
    if go is None:
        raise SystemExit(f"{CHAR} not found")
    parts = [p for p in db.walk(go) if p.active]

    before, n1 = compose(db, parts, {})
    overrides = load_overrides()
    after, n2 = compose(db, parts, overrides)
    print(f"parts composed: original {n1}, restyled {n2}, overrides {len(overrides)}")

    # paper background, side by side with a divider
    gap = 24
    W = before.width + after.width + gap
    H = max(before.height, after.height) + 34
    sheet = Image.new("RGB", (W, H), (232, 224, 208))
    paper = Image.new("RGBA", (before.width, before.height), (243, 235, 220, 255))
    paper.alpha_composite(before)
    sheet.paste(paper.convert("RGB"), (0, 34))
    paper2 = Image.new("RGBA", (after.width, after.height), (243, 235, 220, 255))
    paper2.alpha_composite(after)
    sheet.paste(paper2.convert("RGB"), (before.width + gap, 34))

    dr = ImageDraw.Draw(sheet)
    dr.text((6, 10), f"{CHAR}  —  original (cartoon)", fill=(40, 30, 24))
    dr.text((before.width + gap + 6, 10), f"{CHAR}  —  {SUFFIX}",
            fill=(40, 30, 24))
    dr.line([(before.width + gap // 2, 0), (before.width + gap // 2, H)],
            fill=(190, 178, 158))

    # transparent copies for measurement (a paper backdrop would count as 留白
    # and flatten texture_std to zero). Names are character-scoped so a zombie
    # pilot does not silently overwrite the Vinnie baseline.
    vdir = os.path.join(PROJECT, "validation")
    os.makedirs(vdir, exist_ok=True)
    before.save(os.path.join(vdir, f"composite_{CHAR}_original.png"))
    after.save(os.path.join(vdir, f"composite_{CHAR}_{SUFFIX}.png"))
    # keep the plain names pointing at the reference character (Vinnie)
    if CHAR == "Vinnie" and SUFFIX == "restyled":
        before.save(os.path.join(vdir, "composite_original.png"))
        after.save(os.path.join(vdir, "composite_restyled.png"))

    out = os.path.join(BASE, f"_character_compare_{SUFFIX}.png")
    sheet.save(out)
    print("saved", out, sheet.size)


if __name__ == "__main__":
    main()
