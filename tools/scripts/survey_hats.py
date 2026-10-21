"""Survey every character's headgear sprite, so a helmet can be borrowed.

The Hat texture on the gangster-type characters is a 139x76 strip whose opaque
area fills the whole frame -- it is a fedora silhouette with no room for a steel
helmet dome. But the game also ships soldiers, and a soldier's headgear sprite
may well BE a helmet. If one exists, reusing it is far cheaper and more
faithful than trying to draw a dome inside a fedora-shaped alpha.

Walks all 42 prefabs (including inactive variants), collects every sprite whose
GameObject name looks like headgear, and writes them to art/hats/ with the
sprite's own size and opaque fill, which is what decides whether a dome fits.

Usage:
    python survey_hats.py
"""
import io
import json
import os

from PIL import Image

from ggc_assets import AssetDB, PROJECT, tn
import characters_meta

OUT = os.path.join(PROJECT, "art", "hats")
os.makedirs(OUT, exist_ok=True)

KEYS = ("hat", "helm", "cap", "hoed", "pet", "kepi", "helm")

BACKUP = os.path.join(PROJECT, "backup")
PRISTINE = {f: os.path.join(BACKUP, f)
            for f in os.listdir(BACKUP) if f.endswith(".assets")}
db = AssetDB(file_map=PRISTINE)

rows = []
for name in characters_meta.ROSTER:
    char = name["prefab"] if isinstance(name, dict) else name
    go = db.find_go(char)
    if go is None:
        continue
    seen = set()
    for p in db.walk(go, include_inactive=True):
        gname = (p.go_name or "").lower()
        if not any(k in gname for k in KEYS):
            continue
        sp = db.resolve(p.sprite, p.ctx)
        if tn(sp) != "Sprite":
            continue
        meta = db.sprite_meta(sp)
        if not meta or "image" not in meta:
            continue
        key = (meta["sprite_file"], meta["sprite_path_id"])
        if key in seen:
            continue
        seen.add(key)
        img = meta["image"]
        alpha = img.split()[3]
        hist = alpha.histogram()
        opaque = sum(hist[9:])
        fill = opaque / float(img.width * img.height)
        fname = f"{char}__{p.go_name}.png"
        img.save(os.path.join(OUT, fname))
        rows.append({
            "character": char,
            "slot": p.go_name,
            "file": fname,
            "size": [img.width, img.height],
            "fill": round(fill, 3),
            "active": bool(p.active),
        })

with io.open(os.path.join(OUT, "index.json"), "w", encoding="utf-8") as fh:
    json.dump(rows, fh, indent=1, ensure_ascii=False)

rows.sort(key=lambda r: (-r["size"][1], r["character"]))
print(f"{len(rows)} headgear sprites from {len({r['character'] for r in rows})} characters")
print(f"{'character':<22}{'slot':<26}{'size':<12}{'h/w':>6}{'fill':>7}")
for r in rows:
    w, h = r["size"]
    print(f"{r['character']:<22}{str(r['slot'])[:24]:<26}"
          f"{f'{w}x{h}':<12}{h / max(1, w):>6.2f}{r['fill']:>7.2f}")
