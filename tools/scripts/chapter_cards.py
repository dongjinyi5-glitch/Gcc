"""Export the chapter-select cards and annotate them with the level mapping.

These are the pictures the game itself puts on the 选择章节 screen: one 800x500
Texture2D per chapter, named after the scene.  They are the best reference we
have for "what does this level actually look like", because they are the game's
own composition rather than a photograph of a monitor -- and they matter twice
over, since they are UI assets that will need restyling too once the scene art
changes.  A chapter select showing the old cartoon art next to restyled levels
would be an obvious seam.

Where they live: 11 in resources.assets, but `Boat` sits in sharedassets2.assets,
which is why a resources-only scan finds 11 of 12.

The Chinese chapter names and the one-line captions come from photographs of the
chapter screen; the English texture names are authoritative and come from the
build settings scene list.

Usage
-----
    python chapter_cards.py            # export cards + build the sheet
    python chapter_cards.py --list     # just print the mapping
"""
import io
import json
import os
import sys

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ggc_assets as GA

PROJECT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(PROJECT, "art", "chapter_cards")
DOCS = os.path.join(PROJECT, "docs")

# (texture name, file, path_id, chapter name, card caption, level file, scene)
# Order follows the chapter list on screen, top to bottom.
CARDS = [
    ("Boat",             "sharedassets2.assets",   34, "轮船",               "到达即死亡",       "level3",  "boat"),
    ("HarbourPart1",     "resources.assets",      292, "暴徒镇港口",         "战争码头",         "level4",  "harbour"),
    ("HarbourPart2",     "resources.assets",     1596, "市郊",               "仓库暴乱",         "level5",  "harbourPart2"),
    ("Alleys",           "resources.assets",     1192, "暗黑小巷",           "一夜肢解",         "level6",  "alleyStreets"),
    ("Stripclub",        "resources.assets",     1259, "博尼诺的脱衣舞夜总会", "干净利索！",       "level7",  "stripclub"),
    ("Bridge",           "resources.assets",     1400, "军团据点",           "乔尼，拿起你的枪！", "level8",  "bridge"),
    ("BrokenBridge",     "resources.assets",     1138, "河流",               "遥远的桥",         "level9",  "brokenBridge"),
    ("SewersPart1",      "resources.assets",      740, "下水道",             "追逐白日梦",       "level10", "sewers"),
    ("SewersPart2",      "resources.assets",     1701, "存储器",             "大智若愚",         "level11", "sewersPart2"),
    ("SecretLab",        "resources.assets",     1899, "选择标签栏",         "月光屠杀",         "level12", "secretLab"),
    ("ConstructionSite", "resources.assets",      707, "建筑工地",           "有很长的路要走",   "level13", "constructionSite"),
    ("Rooftops",         "resources.assets",      554, "屋顶",               "圣诞老公公来了",   "level14", "rooftops"),
]

F_TITLE = ImageFont.truetype(os.path.join("C:/Windows/Fonts", "msyhbd.ttc"), 22)
F_SUB = ImageFont.truetype(os.path.join("C:/Windows/Fonts", "consola.ttf"), 13)
F_CAP = ImageFont.truetype(os.path.join("C:/Windows/Fonts", "msyh.ttc"), 15)


def export(db):
    os.makedirs(OUT, exist_ok=True)
    got = []
    for name, fname, pid, cn, cap, lv, scene in CARDS:
        obj = db.file_objs(fname).get(pid)
        if obj is None:
            print(f"  ! {name}: {fname}#{pid} not found")
            continue
        im = db.texture_image(obj)
        if im is None:
            print(f"  ! {name}: unreadable")
            continue
        p = os.path.join(OUT, f"{name}.png")
        im.save(p)
        got.append((name, cn, cap, lv, scene, p, im.size))
        print(f"  {name:<18} {im.size[0]}x{im.size[1]}  {cn}  -> {os.path.basename(p)}")
    return got


def sheet(got):
    """One page: card art with the three names it has (texture / chapter / scene)."""
    COLS, BOX = 4, 380
    PAD, HDR, FTR = 14, 46, 26
    rows = (len(got) + COLS - 1) // COLS
    W = PAD + COLS * (BOX + PAD)
    H = PAD + rows * (HDR + BOX * 500 // 800 + FTR + PAD)
    cell = BOX * 500 // 800
    cv = Image.new("RGB", (W, H), (24, 24, 28))
    d = ImageDraw.Draw(cv)
    for i, (name, cn, cap, lv, scene, p, _sz) in enumerate(got):
        c, r = i % COLS, i // COLS
        x = PAD + c * (BOX + PAD)
        y = PAD + r * (HDR + cell + FTR + PAD)
        d.text((x, y), f"{cn}", font=F_TITLE, fill=(232, 232, 238))
        d.text((x, y + 26), f"{name}  ·  {scene}  ·  {lv}", font=F_SUB, fill=(214, 168, 96))
        im = Image.open(p).convert("RGB").resize((BOX, cell), Image.LANCZOS)
        cv.paste(im, (x, y + HDR))
        d.text((x, y + HDR + cell + 4), f"「{cap}」", font=F_CAP, fill=(150, 152, 162))
    p = os.path.join(OUT, "_sheet.png")
    cv.save(p, optimize=True)
    print(f"sheet -> {p}  {cv.size}")
    return p


def write_json(got):
    rows = []
    for name, cn, cap, lv, scene, p, sz in got:
        rows.append({
            "texture": name, "chapter_cn": cn, "caption": cap,
            "level": lv, "scene": scene,
            "card": os.path.relpath(p, PROJECT).replace("\\", "/"),
            "size": list(sz),
        })
    p = os.path.join(OUT, "chapters.json")
    with io.open(p, "w", encoding="utf-8") as fh:
        json.dump(rows, fh, ensure_ascii=False, indent=1)
    print(f"json  -> {p}  {len(rows)} rows")


def main():
    if "--list" in sys.argv:
        for name, fname, pid, cn, cap, lv, scene in CARDS:
            print(f"{cn:<12} {cap:<10} {scene:<18} {lv:<8} {name}")
        return 0
    db = GA.AssetDB(data_dir=GA.DATA)
    got = export(db)
    if got:
        write_json(got)
        sheet(got)
    return 0 if len(got) == len(CARDS) else 1


if __name__ == "__main__":
    sys.exit(main())
