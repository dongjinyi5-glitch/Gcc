"""Split the shared Hat so the hero and the villains can wear different helmets.

The conflict (docs/HAT_CONFLICT.md)
-----------------------------------
One texture, `sharedassets15.assets#71`, backs the Hat sprite of **nine**
prefabs: Vinnie, VinnieRagdoll, VinnieCutScenes (远征军) plus Gangster1,
Frankie, EvilFrankieOnFloor, Goon3, Scientist, Salvatore (日军).
A Sprite is texture + rect + pivot + mesh, so one texture holds one art version.

The fix -- consolidate, don't clone
-----------------------------------
Rather than inventing a new Sprite (impossible here: `env.save()` corrupts this
build), note that the game already ships a **second** Hat sprite that is
geometrically identical and already carries four villains:

    #229  sharedassets15#71   139x76  offset (-3.9155, -8.9911)  ppu 200  8 verts
    #3633 resources#832       139x76  offset (-3.9155, -8.9911)  ppu 200 13 verts

Identical rect, identical offset, identical PPU, and both meshes cover 100% of
the new art (measured).  So:

    sharedassets15#71  <- 美制 M1        Vinnie x3 (they keep sprite #229)
    resources#832      <- 昭五式铁帽     Gangster2/3/6, BonninoBoss (keep #3633)
    6 villains         m_Sprite #229 -> #3633   (6 x 8 bytes, zero shift)

Total: 2 equal-length texture writes + 6 PPtr edits, **no new objects**.
Vinnie is never re-pointed, so the hero carries the least risk.  `resources#906`
(Soldier) is left completely untouched -- important, because `theme_cbi` maps
Soldier to 日军士兵, so giving him an M1 would be a thematic error.

Art (B2, zero credits)
----------------------
`restyle_ink.py` with slot **`hat`** plus an explicit **role**, so the pigment
comes from `theme_cbi.ROLE_KIND` instead of the faction default:

    role 远征军   hat -> 赭石 + 墨   (khaki / olive drab, the M1 reading)
    role 日军士兵 hat -> 墨  + 石绿  (国防色偏橄榄, the 昭五式 reading)

With no role the `hat` slot falls back to plain 墨 and the helmet becomes a
muddy black lump -- that was the first failed attempt.  `slot='garment'` gives
石青+石绿, which looks fine but violates the 远征军 band (石青 must stay
<= 0.06 there), so it is wrong for the hero.

Geometry: the two sprites share m_Offset exactly, so a villain repointed from
#229 to #3633 does not move by a single pixel.  #3633 samples 137.92 of the 139
px width; the 昭五式 art is empty past column 136, so nothing is lost.

Usage
-----
    python split_hat.py --dry     # build art, report offsets, write nothing
    python split_hat.py           # build art + patch the two .assets files
    python split_hat.py --verify  # re-read the patched files and check
"""
import io
import json
import os
import struct
import sys

import numpy as np
from PIL import Image, ImageDraw

from ggc_assets import AssetDB, DATA, PROJECT, tn

BACKUP = os.path.join(PROJECT, "backup")
OUT = os.path.join(PROJECT, "art", "hat_split")
os.makedirs(OUT, exist_ok=True)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import restyle_ink as R  # noqa: E402
import theme_cbi as T  # noqa: E402

M1_TEX = ("sharedassets15.assets", 71)      # 139x76 -> Vinnie's sprite #229
SYO_TEX = ("resources.assets", 832)         # 139x76 -> villains' sprite #3633

OLD_SPRITE_FILE = "sharedassets15.assets"
OLD_SPRITE_PID = 229
NEW_SPRITE_PID = 3633                        # same file as the renderers

# the six villain renderers that must leave the hero's texture
VILLAIN_SRS = {
    15797: "Gangster1",
    15795: "Frankie",
    15794: "EvilFrankieOnFloor",
    15311: "Goon3",
    15754: "Scientist",
    15808: "Salvatore",
}
# these already point at #3633 and must stay there
KEEP_SRS = {15792: "Gangster2", 15798: "Gangster3",
            15799: "Gangster6", 15802: "BonninoBoss"}
VINNIE_SRS = {15811: "Vinnie", 15757: "VinnieRagdoll", 16505: "VinnieCutScenes"}


# ------------------------------------------------------------------ encoding
def encode_argb32(img):
    """PIL RGBA (top-down) -> Unity ARGB32 raw block (A,R,G,B, rows bottom-up)."""
    a = np.array(img.convert("RGBA"), dtype=np.uint8)[::-1]
    return np.ascontiguousarray(a[..., [3, 0, 1, 2]]).tobytes()


def decode_argb32(raw, w, h):
    a = np.frombuffer(raw, dtype=np.uint8).reshape(h, w, 4)[::-1]
    return Image.fromarray(np.ascontiguousarray(a[..., [1, 2, 3, 0]]), "RGBA")


def pixel_offset(obj, w, h):
    """Start of the pixel block; it sits at the very end of the Texture2D."""
    return int(obj.byte_start) + int(obj.byte_size) - w * h * 4


def read_texture(db, fname, pid):
    obj = db.file_objs(fname).get(pid)
    tt = obj.read_typetree()
    w, h = tt["m_Width"], tt["m_Height"]
    if tt["m_TextureFormat"] != 5:
        raise SystemExit(f"{fname}#{pid}: format {tt['m_TextureFormat']}, "
                         f"expected 5 (RGBA32)")
    with open(os.path.join(DATA, fname), "rb") as fh:
        fh.seek(pixel_offset(obj, w, h))
        return decode_argb32(fh.read(w * h * 4), w, h), obj, tt


# ---------------------------------------------------------------------- art
def camo_net(img, step=7):
    """Diamond camouflage net over the opaque area -- the 昭五式's signature.

    Only alpha-carrying pixels get net, and the alpha channel is restored
    afterwards, so the silhouette and the sprite mesh never move.
    """
    a = np.array(img.convert("RGBA"))
    h, w = a.shape[:2]
    ys, xs = np.nonzero(a[..., 3] > 40)
    if len(xs) == 0:
        return img
    x0, x1, y0, y1 = int(xs.min()), int(xs.max()), int(ys.min()), int(ys.max())
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    col = (20, 17, 15, 110)
    span = (x1 - x0) + (y1 - y0) + 8
    for k in range(0, span, step):
        d.line([(x0 + k, y0 - 2), (x0 + k - (y1 - y0) - 4, y1 + 2)],
               fill=col, width=1)
        d.line([(x0 + k, y1 + 2), (x0 + k - (y1 - y0) - 4, y0 - 2)],
               fill=col, width=1)
    la = np.array(layer)
    la[..., 3] = (la[..., 3].astype(np.float32)
                  * (a[..., 3].astype(np.float32) / 255.0)).astype(np.uint8)
    out = Image.alpha_composite(img.convert("RGBA"), Image.fromarray(la))
    out.putalpha(img.convert("RGBA").getchannel("A"))
    return out


def star(img):
    """Small 朱红 five-point star on the front of the 昭五式 dome."""
    import math
    a = np.array(img.convert("RGBA"))
    h, w = a.shape[:2]
    ys, xs = np.nonzero(a[..., 3] > 200)
    if len(xs) == 0:
        return img
    cx = int(xs.mean() - (xs.max() - xs.min()) * 0.05)
    cy = int(ys.min() + (ys.max() - ys.min()) * 0.32)
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    r_out, r_in = 4.0, 1.6
    pts = []
    for i in range(10):
        r = r_out if i % 2 == 0 else r_in
        ang = -math.pi / 2 + i * math.pi / 5
        pts.append((cx + r * math.cos(ang), cy + r * math.sin(ang)))
    d.polygon(pts, fill=(176, 52, 40, 235))
    out = Image.alpha_composite(img.convert("RGBA"), layer)
    out.putalpha(img.convert("RGBA").getchannel("A"))
    return out


def chin_strap(img):
    """A dark strap across the M1 dome -- how an M1 reads at 40 px."""
    a = np.array(img.convert("RGBA"))
    h, w = a.shape[:2]
    ys, xs = np.nonzero(a[..., 3] > 200)
    if len(xs) == 0:
        return img
    y = int(ys.min() + (ys.max() - ys.min()) * 0.60)
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.line([(int(xs.min()) + 5, y + 3), (int(xs.max()) - 5, y - 3)],
           fill=(28, 24, 20, 165), width=2)
    la = np.array(layer)
    la[..., 3] = (la[..., 3].astype(np.float32)
                  * (a[..., 3].astype(np.float32) / 255.0)).astype(np.uint8)
    out = Image.alpha_composite(img.convert("RGBA"), Image.fromarray(la))
    out.putalpha(img.convert("RGBA").getchannel("A"))
    return out


def build_art():
    """昭五式 (日军士兵) and M1 (远征军), both 139x76."""
    syo_src = Image.open(os.path.join(PROJECT, "art", "gangster1_parts",
                                      "redraw", "30_Hat_Hat.png")).convert("RGBA")
    m1_src = Image.open(os.path.join(PROJECT, "art", "hats",
                                     "Soldier__Hat.png")).convert("RGBA")

    syo = R.restyle(syo_src, slot="hat", faction="人类",
                    role=T.IJA_SOLDIER, seed=7)
    syo = star(camo_net(syo))
    syo.save(os.path.join(OUT, "hat_syo5.png"))

    m1 = R.restyle(m1_src, slot="hat", faction="人类",
                   role=T.EXPEDITIONARY, seed=11)
    m1 = chin_strap(m1)
    m1.save(os.path.join(OUT, "hat_m1.png"))
    return syo, m1


# -------------------------------------------------------------------- patch
def load_db(data_dir):
    return AssetDB(file_map={f: os.path.join(data_dir, f)
                             for f in os.listdir(data_dir)
                             if f.endswith(".assets")})


def write_texture(db, fname, pid, img, dry=True):
    w, h = img.size
    cur, obj, tt = read_texture(db, fname, pid)
    if cur.size != (w, h):
        raise SystemExit(f"{fname}#{pid}: art {img.size} != texture {cur.size}")
    raw = encode_argb32(img)
    if len(raw) != w * h * 4:
        raise SystemExit(f"{fname}#{pid}: encoded {len(raw)} != {w * h * 4}")
    off = pixel_offset(obj, w, h)
    if not dry:
        with open(os.path.join(DATA, fname), "r+b") as fh:
            fh.seek(off)
            fh.write(raw)
    return {"kind": "tex", "file": fname, "path_id": pid, "offset": off,
            "bytes": len(raw), "applied": not dry}


def ext_index(db, owner_fname, target_fname):
    objs = db.file_objs(owner_fname)
    _objs, externals = db.ctx_of(objs[next(iter(objs))])
    for i, e in enumerate(externals, start=1):
        if os.path.basename(getattr(e, "name", str(e))) == target_fname:
            return i
    raise SystemExit(f"{target_fname} not in {owner_fname} externals")


def pptr_offset(db, sr_pid, want_fid, want_pid):
    """Byte offset of m_Sprite inside a SpriteRenderer, verified before use."""
    obj = db.file_objs("resources.assets").get(sr_pid)
    cur = obj.read_typetree().get("m_Sprite") or {}
    if cur.get("m_PathID") != want_pid:
        raise SystemExit(f"SR#{sr_pid}: m_Sprite is {cur}, expected pid {want_pid}")
    with open(os.path.join(DATA, "resources.assets"), "rb") as fh:
        fh.seek(int(obj.byte_start))
        blob = fh.read(int(obj.byte_size))
    pat = struct.pack("<ii", want_fid, want_pid)
    hits = [i for i in range(len(blob) - 7) if blob[i:i + 8] == pat]
    if len(hits) != 1:
        raise SystemExit(f"SR#{sr_pid}: {len(hits)} byte matches for {cur}, "
                         f"refusing to guess")
    return int(obj.byte_start) + hits[0]


def repoint(db, sr_pid, new_fid, new_pid, dry=True):
    old_fid = ext_index(db, "resources.assets", OLD_SPRITE_FILE)
    off = pptr_offset(db, sr_pid, old_fid, OLD_SPRITE_PID)
    if not dry:
        with open(os.path.join(DATA, "resources.assets"), "r+b") as fh:
            fh.seek(off)
            fh.write(struct.pack("<ii", new_fid, new_pid))
    return {"kind": "pptr", "sr": sr_pid, "name": VILLAIN_SRS[sr_pid],
            "offset": off, "from": [old_fid, OLD_SPRITE_PID],
            "to": [new_fid, new_pid], "applied": not dry}


def main():
    dry = "--dry" in sys.argv
    if "--verify" in sys.argv:
        return do_verify()

    print(f"target: {DATA}")
    db = load_db(DATA)

    syo, m1 = build_art()
    print(f"art: 昭五式 {syo.size} (role 日军士兵, 墨+石绿)  "
          f"M1 {m1.size} (role 远征军, 赭石+墨)")

    jobs = [write_texture(db, *M1_TEX, m1, dry=dry),
            write_texture(db, *SYO_TEX, syo, dry=dry)]
    for sr in VILLAIN_SRS:
        jobs.append(repoint(db, sr, 0, NEW_SPRITE_PID, dry=dry))

    for j in jobs:
        if j["kind"] == "pptr":
            print(f"  PPtr SR#{j['sr']} {j['name']:<20} @+{j['offset']}  "
                  f"{j['from']} -> {j['to']}  "
                  f"{'APPLIED' if j['applied'] else 'dry'}")
        else:
            print(f"  TEX  {j['file']}#{j['path_id']} @+{j['offset']} "
                  f"{j['bytes']}B  {'APPLIED' if j['applied'] else 'dry'}")

    with io.open(os.path.join(OUT, "_jobs.json"), "w", encoding="utf-8") as fh:
        json.dump({"dry": dry, "jobs": jobs}, fh, ensure_ascii=False, indent=1)
    print("dry run only -- rerun without --dry to write" if dry else "written")


def do_verify():
    """Re-read the patched files and confirm every claim in the doc."""
    db = load_db(DATA)
    ok = True

    def chk(good, msg):
        nonlocal ok
        ok = bool(ok and good)
        print(f"{'OK  ' if good else 'FAIL'} {msg}")

    for sr, name in VILLAIN_SRS.items():
        sp = db.file_objs("resources.assets").get(sr).read_typetree().get("m_Sprite") or {}
        chk(sp.get("m_FileID") == 0 and sp.get("m_PathID") == NEW_SPRITE_PID,
            f"SR#{sr} {name} -> {sp}")
    for sr, name in KEEP_SRS.items():
        sp = db.file_objs("resources.assets").get(sr).read_typetree().get("m_Sprite") or {}
        chk(sp.get("m_PathID") == NEW_SPRITE_PID, f"SR#{sr} {name} (kept) -> {sp}")
    for sr, name in VINNIE_SRS.items():
        sp = db.file_objs("resources.assets").get(sr).read_typetree().get("m_Sprite") or {}
        chk(sp.get("m_PathID") == OLD_SPRITE_PID, f"SR#{sr} {name} (kept #229) -> {sp}")

    for (fname, pid), art in ((M1_TEX, "hat_m1.png"), (SYO_TEX, "hat_syo5.png")):
        got, _obj, _tt = read_texture(db, fname, pid)
        want = np.array(Image.open(os.path.join(OUT, art)).convert("RGBA"))
        d = int(np.abs(np.array(got).astype(int) - want.astype(int)).max())
        chk(d == 0, f"{fname}#{pid} pixels == {art} (max channel diff {d})")

    # the untouched third Hat texture must still be its original self
    pristine = AssetDB(file_map={f: os.path.join(BACKUP, f)
                                 for f in os.listdir(BACKUP)
                                 if f.endswith(".assets")})
    for fname, pid in (("resources.assets", 906),):
        po = pristine.file_objs(fname).get(pid)
        pt = po.read_typetree()
        w, h = pt["m_Width"], pt["m_Height"]
        with open(os.path.join(BACKUP, fname), "rb") as fh:
            fh.seek(pixel_offset(po, w, h))
            praw = fh.read(w * h * 4)
        with open(os.path.join(DATA, fname), "rb") as fh:
            fh.seek(pixel_offset(db.file_objs(fname).get(pid), w, h))
            nraw = fh.read(w * h * 4)
        chk(praw == nraw, f"{fname}#{pid} (Soldier) untouched")

    print("verify:", "PASS" if ok else "FAIL")
    return ok


if __name__ == "__main__":
    main()
