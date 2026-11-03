"""Build per-family weapon reference composites + placement manifests.

Why this exists
---------------
The 24 weapon textures are shared by ~18 character prefabs each, so one
redrawn concept per family fixes every gun in the game.  But the prefab
assembles each weapon from 1-3 separate sprites by Transform, so the concept
image has to be built from the ORIGINAL parts at their real relative
geometry -- the model is never allowed to decide layout.

Two sources, both verified:
  * world pickup prefabs (TommygunWeaponPickup, LuparaWeaponPickup, ...) --
    the canonical standalone assembly of a weapon, all rotations identity,
    all scales 1.0.  Preferred wherever one exists.
  * Gangster1's hand hierarchy for the families with no pickup
    (Pistol45, Revolver, Flamethrower, Throwables).  There every weapon sits
    under HandFront at the same origin, so the relative geometry is the
    difference of node origins divided by the accumulated scale -- i.e. the
    weapon at native (1:1) pixel size, which is what the texture stores.

Outputs (per family)
--------------------
    art/weapon_refs/<family>_ref.png      RGBA composite, transparent bg
    art/weapon_refs/<family>_layout.json  per-part canvas_rect + identity
    art/weapon_refs/<family>_mask_<i>.png per-part alpha mask (native size)

The canvas_rect of every part is its footprint in the reference composite;
each part's own texture is exactly that many native pixels, so slicing a
registered concept back through canvas_rect is a 1:1 crop with no resample.

Usage
-----
    python weapon_layout.py            # all families
    python weapon_layout.py tommygun   # one family
"""
import io
import json
import os
import sys

import numpy as np
from PIL import Image

from ggc_assets import AssetDB, PROJECT, tn

BACKUP = os.path.join(PROJECT, "backup")
PRISTINE = {f: os.path.join(BACKUP, f)
            for f in os.listdir(BACKUP) if f.endswith(".assets")} \
    if os.path.isdir(BACKUP) else {}
OUT = os.path.join(PROJECT, "art", "weapon_refs")
os.makedirs(OUT, exist_ok=True)

PAD = 6  # transparent margin around the composite


def db():
    if not PRISTINE:
        raise SystemExit("backup/ missing -- refusing to build references "
                         "from already-patched game files")
    return AssetDB(file_map=PRISTINE)


def part_meta(d, p):
    """(meta, sprite_obj) for a Part, or (None, None)."""
    so = d.resolve(p.sprite, p.ctx)
    if so is None or tn(so) != "Sprite":
        return None, None
    m = d.sprite_meta(so)
    if not m or "error" in m:
        return None, None
    return m, so


def pickup_parts(d, prefab):
    go = d.find_go(prefab)
    if go is None:
        raise SystemExit(f"prefab {prefab} not found")
    out = []
    for p in d.walk(go):
        m, so = part_meta(d, p)
        if m:
            out.append((p, m, so))
    return out


def g1_parts(d, go_names):
    """Parts of Gangster1 whose GO name is in go_names (any depth)."""
    go = d.find_go("Gangster1")
    if go is None:
        raise SystemExit("Gangster1 not found")
    out = []
    for p in d.walk(go):
        if p.go_path.split("/")[-1] in go_names:
            m, so = part_meta(d, p)
            if m:
                out.append((p, m, so))
    return out


def native_offsets(parts):
    """Native-pixel offsets of every part relative to parts[0].

    parts: [(Part, meta, sprite_obj)].  Each Part's (x, y) is the node origin
    in world units (parent scale already applied); the sprite pivot sits on
    that origin.  Dividing the origin difference by the reference part's
    accumulated scale converts world units back to the part's own ppu space.
    """
    ref = parts[0]
    scale = ref[0].sx if abs(ref[0].sx) > 1e-6 else 1.0
    ppu_ref = ref[1]["ppu"] or 200.0
    offs = []
    for p, m, so in parts:
        dx = (p.x - ref[0].x) / scale * (m["ppu"] or 200.0)
        dy = (p.y - ref[0].y) / scale * (m["ppu"] or 200.0)
        offs.append((dx, dy))
    return offs


def build_family(name, parts, side_by_side=False):
    """Composite parts at native scale; write ref png + layout json."""
    offs = native_offsets(parts)
    if side_by_side:
        # throwables all sit on one origin in the prefab; lay them out left
        # to right, pivots on a shared baseline (dy = 0)
        gap = 14
        cursor = 0.0
        offs = []
        for p, m, so in parts:
            w = m["rect"][0]
            offs.append((cursor, 0.0))
            cursor += w + gap

    # Placement math, all in y-down image space:
    #   the part's pivot sits on its node origin; relative to the reference
    #   part's origin that is (dx, -dy) after the world->image y flip, and the
    #   image's own top-left is (-pivot_x, -(h - pivot_y)) from its pivot.
    placements = []
    for (p, m, so), (dx, dy) in zip(parts, offs):
        w, h = m["rect"]
        left = dx - m["pivot_x"]
        top = -dy - (h - m["pivot_y"])
        placements.append((left, top, w, h))
    minx = min(pl[0] for pl in placements) - PAD
    miny = min(pl[1] for pl in placements) - PAD
    maxx = max(pl[0] + pl[2] for pl in placements) + PAD
    maxy = max(pl[1] + pl[3] for pl in placements) + PAD
    W = int(round(maxx - minx))
    H = int(round(maxy - miny))

    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    layout = {"family": name, "canvas": [W, H], "parts": []}
    for idx, ((p, m, so), (dx, dy), (left, top, w, h)) in enumerate(
            zip(parts, offs, placements)):
        img = m["image"]
        if img.mode != "RGBA":
            img = img.convert("RGBA")
        left = int(round(left - minx))
        top = int(round(top - miny))
        canvas.alpha_composite(img, (left, top))
        mask = img.getchannel("A")
        mask_path = os.path.join(OUT, f"{name}_mask_{idx}.png")
        mask.save(mask_path)
        layout["parts"].append({
            "index": idx,
            "go_path": p.go_path,
            "active": bool(p.active),
            "order": p.order,
            "canvas_rect": [left, top, img.width, img.height],
            "sprite_name": m["sprite_name"],
            "sprite_file": m["sprite_file"],
            "sprite_path_id": m["sprite_path_id"],
            "texture_name": m["texture_name"],
            "texture_file": m["texture_file"],
            "texture_path_id": m["texture_path_id"],
            "native_size": [img.width, img.height],
            "atlas_rect": [int(round(v)) for v in m["atlas_rect"]],
            "texture_size": list(m["texture_size"]),
            "rotation": int(m.get("rotation") or 0),
            "pivot": [m["pivot_x"], m["pivot_y"]],
            "ppu": m["ppu"],
            "mask": os.path.basename(mask_path),
        })
    ref_path = os.path.join(OUT, f"{name}_ref.png")
    canvas.save(ref_path)
    with io.open(os.path.join(OUT, f"{name}_layout.json"), "w",
                 encoding="utf-8") as fh:
        json.dump(layout, fh, ensure_ascii=False, indent=1)
    print(f"{name}: {W}x{H} canvas, {len(parts)} parts -> {ref_path}")
    return ref_path


FAMILIES = {
    # family        source prefab / Gangster1 GO names        side_by_side
    "tommygun":     ("pickup:TommygunWeaponPickup", False),
    "lupara":       ("pickup:LuparaWeaponPickup", False),
    "magnum":       ("pickup:MagnumWeaponPickup", False),
    "maximgun":     ("pickup:MaximgunWeaponPickup", False),
    "shotgun":      ("pickup:ShotgunWeaponPickup", False),
    "teslacoilgun": ("pickup:TeslacoilgunWeaponPickup", False),
    "bazooka":      ("pickup:BazookaWeaponPickup", False),
    "pistol45":     ("g1:Pistol,Pistol45-Slide,ammoclip", False),
    "revolver":     ("g1:Revolver", False),
    "flamethrower": ("g1:Flamethrower,FuelTankFlamethrower,HoseFlamethrower",
                     False),
    "throwables":   ("g1:Grenade,GasGrenade,Molotov", True),
}


def main():
    want = [a for a in sys.argv[1:] if not a.startswith("--")] or list(FAMILIES)
    d = db()
    for fam in want:
        if fam not in FAMILIES:
            print(f"!! unknown family {fam}")
            continue
        src, sbs = FAMILIES[fam]
        if src.startswith("pickup:"):
            parts = pickup_parts(d, src.split(":", 1)[1])
        else:
            names = set(src.split(":", 1)[1].split(","))
            parts = g1_parts(d, names)
            # keep a deterministic order: main body first
            order = {n: i for i, n in enumerate(
                src.split(":", 1)[1].split(","))}
            parts.sort(key=lambda t: order.get(t[0].go_path.split("/")[-1], 99))
        if not parts:
            print(f"!! {fam}: no parts")
            continue
        build_family(fam, parts, side_by_side=sbs)


if __name__ == "__main__":
    main()
