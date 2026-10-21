"""Compare one slot across two prefabs: transform, sprite identity, texture.

Used to decide whether a sprite can be transplanted between prefabs. A Hat
sprite can be re-pointed at another prefab's sprite only if the receiving
GameObject's Transform places it in the same place at the same size -- otherwise
the helmet ends up on the character's shoulder.

Usage:
    python transplant_check.py <sourceChar> <destChar> [slot]
"""
import sys

from ggc_assets import AssetDB, PROJECT, tn

SRC = sys.argv[1] if len(sys.argv) > 1 else "ZombieSoldier"
DST = sys.argv[2] if len(sys.argv) > 2 else "Gangster1"
SLOT = sys.argv[3] if len(sys.argv) > 3 else "Hat"

BACKUP = os.path.join(PROJECT, "backup") if False else None  # placeholder
import os
BACKUP = os.path.join(PROJECT, "backup")
PRISTINE = {f: os.path.join(BACKUP, f)
            for f in os.listdir(BACKUP) if f.endswith(".assets")}
db = AssetDB(file_map=PRISTINE)


def dump(char):
    go = db.find_go(char)
    if go is None:
        print(f"  {char}: not found")
        return None
    for p in db.walk(go, include_inactive=True):
        if (p.go_name or "").lower() != SLOT.lower():
            continue
        sp = db.resolve(p.sprite, p.ctx)
        if tn(sp) != "Sprite":
            continue
        m = db.sprite_meta(sp)
        if not m:
            continue
        print(f"  {char:<16} active={p.active!s:<5} "
              f"pos=({p.x:.3f},{p.y:.3f}) scale=({p.sx:.3f},{p.sy:.3f}) "
              f"rot={getattr(p, 'rz', 0):.3f} order={p.order}")
        print(f"      sprite {m['sprite_file']} #{m['sprite_path_id']} "
              f"{m['image'].width}x{m['image'].height} ppu={m['ppu']} "
              f"pivot=({m['pivot_x']:.3f},{m['pivot_y']:.3f})")
        return p
    print(f"  {char}: no {SLOT} sprite")
    return None


print(f"--- slot '{SLOT}' ---")
a = dump(SRC)
b = dump(DST)

if a and b:
    print("\nplacement maths (unity units, origin at the part's own pivot):")
    for tag, p in (("source", a), ("dest", b)):
        sp = db.resolve(p.sprite, p.ctx)
        m = db.sprite_meta(sp)
        ppu, sx, sy = m["ppu"], p.sx, p.sy
        w = m["image"].width / ppu * sx
        h = m["image"].height / ppu * sy
        print(f"  {tag:<7} top-left=({p.x - m['pivot_x'] / ppu * sx:+.3f},"
              f"{p.y - m['pivot_y'] / ppu * sy:+.3f})  size={w:.3f}x{h:.3f} "
              f"-> {w * 100:.1f}x{h * 100:.1f} px @100ppu")
    print("\nIf the two top-left rows and sizes are close, the sprite can be "
          "re-pointed; if not, the Transform has to move too.")
