"""Extract every sprite part of a character, including inactive variants.

The prefabs carry every weapon/pose variant at once and toggle them with
``m_IsActive``. For a *full action set* we want all of them, so this script
walks with include_inactive=True and keeps unique sprites.

Also picks up baked animation textures (the tommygun cycle is stored as 41
full-character 128x128 frames rather than part swaps).

Outputs
-------
  art/<char>/original/*.png        one PNG per unique part, native size
  art/<char>/manifest.json         sprite/atlas metadata for write-back
"""
import io
import json
import os
import sys

from ggc_assets import AssetDB, PROJECT, tn

CHAR = sys.argv[1] if len(sys.argv) > 1 else "Vinnie"
OUT = os.path.join(PROJECT, "art", CHAR.lower() + "_parts")
ORIG = os.path.join(OUT, "original")
os.makedirs(ORIG, exist_ok=True)

db = AssetDB()

go = db.find_go(CHAR)
if go is None:
    raise SystemExit(f"GameObject {CHAR!r} not found")

parts = db.walk(go, include_inactive=True)
print(f"{CHAR}: {len(parts)} SpriteRenderer nodes (incl. inactive)", flush=True)

# --- unique sprites -----------------------------------------------------------
records = []
seen = set()
for p in parts:
    sp = db.resolve(p.sprite, p.ctx)
    if tn(sp) != "Sprite":
        continue
    key = (sp.assets_file.name, sp.path_id)
    if key in seen:
        # keep the active occurrence as the representative
        for r in records:
            if r["key"] == key and p.active:
                r["active"] = True
                r["slot"] = p.go_name
        continue
    seen.add(key)
    meta = db.sprite_meta(sp)
    if not meta or "image" not in meta:
        print(f"  [skip] {p.go_name}: {meta.get('error') if meta else 'no meta'}")
        continue
    records.append({
        "key": key,
        "slot": p.go_name,
        "active": p.active,
        "order": p.order,
        "sprite_name": meta["sprite_name"],
        "sprite_path_id": meta["sprite_path_id"],
        "sprite_file": meta["sprite_file"],
        "texture_name": meta["texture_name"],
        "texture_path_id": meta["texture_path_id"],
        "texture_file": meta["texture_file"],
        "texture_size": list(meta["texture_size"]),
        "atlas_rect": list(meta["atlas_rect"]),
        "size": list(meta["rect"]),
        "ppu": meta["ppu"],
        "image": meta["image"],
    })

print(f"unique part sprites: {len(records)}", flush=True)

# --- baked animation textures -------------------------------------------------
anim_frames = []
for fname in list(db._files):
    for o in db._files[fname].values():
        if tn(o) != "Texture2D":
            continue
        try:
            nm = o.read().m_Name or ""
        except Exception:
            continue
        if nm.startswith(CHAR.lower() + "_"):
            anim_frames.append((nm, o))
if not anim_frames:
    # frames may live in a file not loaded yet
    for f in sorted(os.listdir(db.data_dir)):
        if not f.endswith(".assets"):
            continue
        for o in db.file_objs(f).values():
            if tn(o) != "Texture2D":
                continue
            try:
                nm = o.read().m_Name or ""
            except Exception:
                continue
            if nm.startswith(CHAR.lower() + "_"):
                anim_frames.append((nm, o))

print(f"baked animation frames: {len(anim_frames)}", flush=True)

# --- write --------------------------------------------------------------------
manifest = {"character": CHAR, "parts": [], "frames": []}

for i, r in enumerate(sorted(records, key=lambda x: (x["order"], x["slot"]))):
    img = r.pop("image")
    fname = f"{i:02d}_{r['slot']}_{r['texture_name']}.png"
    img.save(os.path.join(ORIG, fname))
    r["file"] = fname
    r["key"] = list(r["key"])
    manifest["parts"].append(r)

for nm, o in sorted(anim_frames, key=lambda x: x[0]):
    img = db.texture_image(o)
    if img is None:
        continue
    fname = f"frame_{nm.split('_')[-1]}.png"
    img.save(os.path.join(ORIG, fname))
    manifest["frames"].append({
        "file": fname,
        "texture_name": nm,
        "texture_path_id": o.path_id,
        "texture_file": o.assets_file.name,
        "size": [img.width, img.height],
    })

with io.open(os.path.join(OUT, "manifest.json"), "w", encoding="utf-8") as fh:
    json.dump(manifest, fh, indent=1, ensure_ascii=False)

sizes = sorted({tuple(p["size"]) for p in manifest["parts"]})
print(f"written: {len(manifest['parts'])} parts + {len(manifest['frames'])} frames")
print("distinct part sizes:", len(sizes), "range:",
      min(sizes, key=lambda s: s[0] * s[1]), "->", max(sizes, key=lambda s: s[0] * s[1]))
print("DONE")
