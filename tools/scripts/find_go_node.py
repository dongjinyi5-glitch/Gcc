"""Who else references this sprite's texture?

The question that decides whether a part can be fixed per character. A sprite
texture lives once in the .assets; if two prefabs point at it, editing the
pixels for one character edits them for both. A GameObject, by contrast, is
per-prefab -- flipping its ``m_IsActive`` only affects the one character.

So: before reaching for a texture edit, ask what else shares it.

Usage:
    python shared_sprite.py Gangster1 HoseFlamethrower
    python shared_sprite.py Gangster1 Hat --all
"""
import glob
import io
import json
import os
import sys

from ggc_assets import AssetDB, PROJECT, tn

BACKUP = os.path.join(PROJECT, "backup")
PRISTINE = {f: os.path.join(BACKUP, f)
            for f in os.listdir(BACKUP) if f.endswith(".assets")}

args = sys.argv[1:]
CHAR = next((a for a in args if not a.startswith("--")), "Gangster1")
NEEDLE = args[1] if len(args) > 1 and not args[1].startswith("--") else "Hat"
SHOW_ALL = "--all" in args

db = AssetDB(file_map=PRISTINE)
go = db.find_go(CHAR)
if go is None:
    raise SystemExit(f"{CHAR} not found")

# every character that has been extracted has a manifest naming its parts'
# textures; that is the cheapest complete answer to "who shares this".
manifests = {}
for d in sorted(glob.glob(os.path.join(PROJECT, "art", "*_parts"))):
    p = os.path.join(d, "manifest.json")
    if os.path.isfile(p):
        with io.open(p, encoding="utf-8") as fh:
            manifests[os.path.basename(d)[:-len("_parts")]] = json.load(fh)

found = 0
for part in db.walk(go, include_inactive=True):
    if (part.go_name or "").lower() != NEEDLE.lower():
        continue
    sp = db.resolve(part.sprite, part.ctx)
    if tn(sp) != "Sprite":
        continue
    meta = db.sprite_meta(sp)
    if not meta:
        continue
    found += 1
    # the manifest keys parts by TEXTURE, and so must this: the sprite object
    # id (#281) and the texture it crops from (#127) are different objects
    key = (meta["texture_file"], meta["texture_path_id"])
    sharers = sorted(c for c, man in manifests.items()
                     for q in man["parts"]
                     if (q.get("texture_file"), q.get("texture_path_id")) == key)
    print(f"{CHAR}/{part.go_path or part.go_name}")
    print(f"    active={part.active}  order={part.order}")
    print(f"    sprite {meta['sprite_file']} #{meta['sprite_path_id']} "
          f"{meta['image'].width}x{meta['image'].height} ppu={meta['ppu']}")
    print(f"    texture {meta['texture_file']} #{meta['texture_path_id']} "
          f"{meta['texture_size'][0]}x{meta['texture_size'][1]}")
    print(f"    referenced by: {', '.join(sharers) or '(no extracted character)'}")
    if len(sharers) > 1:
        print("    -> SHARED: a pixel edit here changes every character listed. "
              "A per-character fix has to go through the GameObject, not the "
              "texture.")
    else:
        print("    -> private to this character: a pixel edit is safe.")
    if not SHOW_ALL:
        break

if not found:
    print(f"{CHAR}: no active-or-inactive sprite node named {NEEDLE!r}")
