"""Scene-layer catalog: per-level contact sheets, FX and UI batches.

Why the review unit is the *level*
----------------------------------
A texture name only means something inside its scene: "Part3Front_12" is
unreadable until you know it is a level8 street layer.  Scene art is authored
per scene, so the sheets are built per level, biggest art first.  level0 is the
animated main-menu backdrop, level1 is the NGUI widget scene (no SpriteRenderer
at all -- its art is atlas pages), level3..level14 are the twelve campaign maps.

Textures shared between levels appear on every sheet that uses them, tagged
with their other levels; the work estimate uses the unique count (1450), not
the sum of the sheets.

Batches
-------
    L00          animated menu backdrop (rain / fog / lightning / zombies)
    L03..L14     scene layers, one sheet per campaign map
    FX           particle-material textures (CFX_*), shader/palette work
    UI           NGUI atlas pages and logos, separate phase

Pixels are read from the live data dir.  That is safe here because no scene
texture has ever been patched -- the only patched textures are the 11
character hat/body pages, none of which appear in this inventory.

Usage
-----
    python scene_sheets.py            # build every sheet + scene_batches.json
    python scene_sheets.py --only L08 # one batch
"""
import io
import json
import os
import sys
from collections import defaultdict

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ggc_assets import AssetDB, DATA, PROJECT, tn  # noqa: E402

OUT = os.path.join(PROJECT, "art", "scene_sheets")
INV = os.path.join(PROJECT, "art", "scene_inventory.json")
BATCH_JSON = os.path.join(PROJECT, "art", "scene_batches.json")

FONT_DIR = "C:/Windows/Fonts"
F_TITLE = ImageFont.truetype(os.path.join(FONT_DIR, "msyhbd.ttc"), 26)
F_SUB = ImageFont.truetype(os.path.join(FONT_DIR, "consola.ttf"), 15)
F_NAME = ImageFont.truetype(os.path.join(FONT_DIR, "consola.ttf"), 13)
F_META = ImageFont.truetype(os.path.join(FONT_DIR, "consola.ttf"), 12)
F_IDX = ImageFont.truetype(os.path.join(FONT_DIR, "consolab.ttf"), 12)

BG = (26, 26, 30)
CARD = (38, 38, 44)
CARD2 = (44, 44, 51)
INK = (232, 232, 238)
DIM = (150, 152, 162)
ACC = (214, 168, 96)          # 赭石, matches the 重彩 palette

# Evidence-based themes: each label is read off the texture families that
# level actually uses, not guessed from the level index.
THEME = {
    "level0":  ("主菜单动态背景", "MainMenuBack/Front, Rain, Fog, Lightning, Zombie*"),
    "level3":  ("港口码头", "Boat*, Crane*, Quay*, Romp*, Ruim*, OutsideRailring"),
    "level4":  ("港区货场", "Harbour*, HarbourParallax, BigCrane, Hangar-insides, LedgeShip"),
    "level5":  ("港湾远景", "Harbour-Background*, CityParallax, OutskirtsParallax, BigCrane"),
    "level6":  ("老城街道", "StreetsBackground*, OldBuildingInside*, garage*, alley*"),
    "level7":  ("夜总会", "stripclub*, OldBuildingInside*"),
    "level8":  ("城区街区", "part2*, Part1Front*, Part3Front*, WallExtra, BridgeOverpass"),
    "level9":  ("河畔大桥", "Riverside_01, bridge*, BeginWallBack, ArmyBarriere*"),
    "level10": ("竖井与下水道", "Shafts*, Sewer*Outside*, Room1Front*, Gang*"),
    "level11": ("地铁与水库", "Subway*, WaterReservoir*, 2ndShafts*, Room2Front*, Wall*"),
    "level12": ("水库深处", "WaterReservoir*, CupperBolt"),
    "level13": ("车库与电梯", "Garage*, Rooms*, RoofTopStairs*, ElevatorShaft, buildingWall*"),
    "level14": ("齐柏林飞艇", "Zeppelin, BelluccioWall*, Rooftops*, BuildingWhite*, OldBuildingInside*"),
}
ORDER = ["level0"] + [f"level{i}" for i in range(3, 15)]

# NGUI art lives in resources.assets and is referenced by Material, not by
# SpriteRenderer -- found by name, listed explicitly so the batch is auditable.
UI_NAMES = ["HudAtlasHD", "HudAtlasSD", "MenuAtlasHD", "MainMenuBackground",
            "logoClaeys_1920x1080", "logoGGC_1024x768", "logoClaeys", "logoCMS",
            "GGCBarLogo", "HintFont", "ControllerButtons"]

_thumb_cache = {}


# --------------------------------------------------------------------- pixels
def thumb(db, fname, pid, box):
    """Decoded texture scaled to fit ``box``, cached by (file, path_id).

    The cache holds the *scaled* image, not the original: 1450 textures at full
    size would be several GB, while 150px thumbs are ~90 KB each.
    """
    key = (fname, pid, box)
    if key in _thumb_cache:
        return _thumb_cache[key]
    obj = db.file_objs(fname).get(pid)
    img = None
    if obj is not None and tn(obj) == "Texture2D":
        try:
            full = db.texture_image(obj)
        except Exception:
            full = None
        if full is not None and full.width and full.height:
            img = full.copy()
            img.thumbnail((box, box), Image.LANCZOS)
    _thumb_cache[key] = img
    return img


def checker(w, h, sq=8, a=(46, 46, 52), b=(58, 58, 65)):
    tile = Image.new("RGB", (w, h), a)
    d = ImageDraw.Draw(tile)
    for y in range(0, h, sq):
        for x in range(0, w, sq):
            if ((x // sq) + (y // sq)) % 2:
                d.rectangle([x, y, x + sq - 1, y + sq - 1], fill=b)
    return tile


def fit_text(draw, s, font, maxw):
    if draw.textlength(s, font=font) <= maxw:
        return s
    while s and draw.textlength(s + "..", font=font) > maxw:
        s = s[:-1]
    return s + ".."


# ---------------------------------------------------------------------- sheet
def draw_sheet(title, subtitle, items, path, cols=12, box=150, ordinal=True):
    """items: list of dicts with name / size / sr / tag / img / note."""
    cw, ch = box + 14, box + 40
    pad, head = 22, 78
    rows = max(1, (len(items) + cols - 1) // cols)
    W = pad * 2 + cols * cw
    H = head + pad + rows * ch
    sheet = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(sheet)

    d.rectangle([0, 0, W, head - 12], fill=(33, 33, 38))
    d.rectangle([0, head - 12, W, head - 9], fill=ACC)
    d.text((pad, 14), title, font=F_TITLE, fill=INK)
    d.text((pad, 48), subtitle, font=F_SUB, fill=DIM)

    for i, it in enumerate(items):
        r, c = divmod(i, cols)
        x = pad + c * cw
        y = head + r * ch
        d.rounded_rectangle([x, y, x + cw - 4, y + ch - 4], 5,
                            fill=CARD if r % 2 == 0 else CARD2)
        if it.get("img") is not None:
            im = it["img"]
            ox = x + (cw - 4 - im.width) // 2
            oy = y + (box - im.height) // 2 + 3
            bgc = checker(im.width, im.height)
            bgc.paste(im, (0, 0), im)
            sheet.paste(bgc, (ox, oy))
            d.rectangle([ox - 1, oy - 1, ox + im.width, oy + im.height],
                        outline=(80, 80, 88))
        else:
            d.text((x + 10, y + box // 2 - 6), "no pixels", font=F_META, fill=(120, 70, 70))
        if ordinal:
            d.text((x + 6, y + 5), f"#{i + 1:03d}", font=F_IDX, fill=ACC)
        nm = fit_text(d, it["name"], F_NAME, cw - 12)
        d.text((x + 6, y + box + 8), nm, font=F_NAME, fill=INK)
        w, h = it["size"]
        meta = f"{w}x{h}"
        if it.get("sr"):
            meta += f" x{it['sr']}"
        if it.get("tag"):
            meta += f" {it['tag']}"
        d.text((x + 6, y + box + 23), fit_text(d, meta, F_META, cw - 12),
               font=F_META, fill=DIM)

    sheet.save(path, optimize=True)
    print(f"  -> {os.path.basename(path)}  {W}x{H}  {len(items)} cells")
    return path


# ----------------------------------------------------------------------- data
def fx_rows(db):
    """Particle-material textures, aggregated over every level."""
    agg = defaultdict(lambda: {"levels": set(), "mats": set(), "sr": 0})
    for lv in ORDER:
        objs = db.file_objs(lv)
        for o in objs.values():
            if tn(o) != "ParticleSystemRenderer":
                continue
            st = o.read_typetree()
            ctx = db.ctx_of(o)
            for mp in (st.get("m_Materials") or []):
                mat = db.resolve(mp, ctx)
                if mat is None or tn(mat) != "Material":
                    continue
                try:
                    mt = mat.read_typetree()
                except Exception:
                    continue
                for pair in (mt.get("m_SavedProperties", {}).get("m_TexEnvs") or []):
                    try:
                        pname, pval = pair[0].get("name"), pair[1]
                    except Exception:
                        continue
                    if pname != "_MainTex":
                        continue
                    tex = db.resolve(pval.get("m_Texture") or {}, db.ctx_of(mat))
                    if tex is None or tn(tex) != "Texture2D":
                        continue
                    k = (tex.assets_file.name, tex.path_id)
                    agg[k]["levels"].add(lv)
                    agg[k]["mats"].add(mt.get("m_Name", "?"))
                    agg[k]["sr"] += 1
    rows = []
    for (f, pid), r in agg.items():
        obj = db.file_objs(f).get(pid)
        tt = obj.read_typetree()
        rows.append({"texture": tt.get("m_Name", "?"), "file": f, "path_id": pid,
                     "size": [tt.get("m_Width"), tt.get("m_Height")],
                     "levels": sorted(r["levels"], key=lambda s: int(s[5:])),
                     "materials": sorted(r["mats"]), "sr": r["sr"]})
    rows.sort(key=lambda x: -(x["size"][0] * x["size"][1]))
    return rows


def ui_rows(db):
    objs = db.file_objs("resources.assets")
    want = set(UI_NAMES)
    rows = []
    for pid, o in objs.items():
        if tn(o) != "Texture2D":
            continue
        try:
            tt = o.read_typetree()
        except Exception:
            continue
        if tt.get("m_Name") not in want:
            continue
        rows.append({"texture": tt["m_Name"], "file": "resources.assets",
                     "path_id": pid,
                     "size": [tt.get("m_Width"), tt.get("m_Height")],
                     "levels": ["level1"], "materials": ["NGUI atlas"], "sr": 0})
    rows.sort(key=lambda x: -(x["size"][0] * x["size"][1]))
    return rows


# ----------------------------------------------------------------------- main
def main(only=None):
    os.makedirs(OUT, exist_ok=True)
    db = AssetDB(data_dir=DATA)
    inv = json.load(io.open(INV, encoding="utf-8"))

    by_level = defaultdict(list)
    for r in inv:
        for lv in r["levels"]:
            by_level[lv].append(r)

    batches = []
    for lv in ORDER:
        if only and only != lv:
            continue
        rows = sorted(by_level.get(lv, []), key=lambda x: -x["area"])
        if not rows:
            continue
        items = []
        for r in rows:
            others = [x for x in r["levels"] if x != lv]
            items.append({
                "name": r["texture"], "size": r["size"],
                "sr": r["renderers"], "img": thumb(db, r["file"], r["path_id"], 150),
                "tag": ("+" + ",".join(o.replace("level", "L") for o in others)) if others else "",
            })
        theme, evidence = THEME.get(lv, ("?", ""))
        area = sum(r["area"] for r in rows)
        sub = (f"{lv}  |  {len(rows)} textures  |  {area / 1e6:.1f} Mpx  |  "
               f"{sum(r['renderers'] for r in rows)} renderers  |  {evidence}")
        draw_sheet(f"{lv.replace('level', 'L')}  {theme}", sub, items,
                   os.path.join(OUT, f"{lv}.png"))

        # A 2012 px sheet with 150 px cells is a file index, not something you
        # can look at in a browser.  This second sheet shows only the 24 largest
        # layers at 260 px, which *is* readable inline -- the panorama plus this
        # is what actually lets someone judge the art.
        top = sorted(rows, key=lambda x: -x["painted"])[:24]
        titems = []
        for r in top:
            titems.append({
                "name": r["texture"], "size": r["size"], "sr": r["renderers"],
                "img": thumb(db, r["file"], r["path_id"], 260),
                "tag": f"{r['painted'] / 1e6:.2f}M",
            })
        draw_sheet(f"{lv.replace('level', 'L')}  {theme} — 绘制面积前 24",
                   "cells sorted by painted area (alpha>8 px), tag = painted Mpx; "
                   f"full {len(rows)}-texture index in {lv}.png",
                   titems, os.path.join(OUT, f"{lv}_top.png"),
                   cols=min(6, len(titems)), box=260)
        batches.append({"id": lv.replace("level", "L"), "level": lv, "theme": theme,
                        "kind": "scene", "textures": len(rows),
                        "px": area, "renderers": sum(r["renderers"] for r in rows),
                        "sheet": f"{lv}.png"})

    if not only or only == "top":
        # The parallax backdrops: the art that actually defines the look.
        top = sorted(inv, key=lambda x: -x["area"])[:48]
        items = []
        for r in top:
            items.append({
                "name": r["texture"], "size": r["size"], "sr": r["renderers"],
                "img": thumb(db, r["file"], r["path_id"], 320),
                "tag": ",".join(x.replace("level", "L") for x in r["levels"]),
            })
        draw_sheet("TOP 48  最大场景图层", 
                   "the 48 biggest textures = parallax backdrops and building walls; "
                   "this is the set that defines the look of the game",
                   items, os.path.join(OUT, "top_backdrops.png"),
                   cols=6, box=320)

    if not only or only == "FX":
        fx = fx_rows(db)
        items = [{"name": r["texture"], "size": r["size"], "sr": r["sr"],
                  "img": thumb(db, r["file"], r["path_id"], 150),
                  "tag": r["levels"][0].replace("level", "L")} for r in fx]
        draw_sheet("FX  粒子层", 
                   f"{len(fx)} particle-material textures | CFX_* cartoon-fx sheets | "
                   "recommend palette/shader tint, not redraw",
                   items, os.path.join(OUT, "fx.png"))
        batches.append({"id": "FX", "level": "-", "theme": "粒子层", "kind": "fx",
                        "textures": len(fx), "sheet": "fx.png",
                        "px": sum(r["size"][0] * r["size"][1] for r in fx)})
        json.dump(fx, io.open(os.path.join(PROJECT, "art", "scene_fx.json"), "w",
                              encoding="utf-8"), ensure_ascii=False, indent=1)

    if not only or only == "UI":
        ui = ui_rows(db)
        items = [{"name": r["texture"], "size": r["size"],
                  "img": thumb(db, r["file"], r["path_id"], 260)} for r in ui]
        draw_sheet("UI  NGUI 图集与 Logo", 
                   f"{len(ui)} textures | HudAtlasHD/SD, MenuAtlasHD, MainMenuBackground, logos | "
                   "referenced by Material, not SpriteRenderer",
                   items, os.path.join(OUT, "ui.png"), cols=6, box=260)
        batches.append({"id": "UI", "level": "level1", "theme": "UI 图集", "kind": "ui",
                        "textures": len(ui), "sheet": "ui.png",
                        "px": sum(r["size"][0] * r["size"][1] for r in ui)})
        json.dump(ui, io.open(os.path.join(PROJECT, "art", "scene_ui.json"), "w",
                              encoding="utf-8"), ensure_ascii=False, indent=1)

    if not only:
        json.dump(batches, io.open(BATCH_JSON, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        print(f"\n{len(batches)} batches -> {BATCH_JSON}")
    return batches


if __name__ == "__main__":
    only = None
    if "--only" in sys.argv:
        only = sys.argv[sys.argv.index("--only") + 1]
    main(only)
