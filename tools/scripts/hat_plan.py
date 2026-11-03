"""Roll the Hat split out to every character -- consolidate, then repaint.

The insight from the Vinnie/Gangster1 split
-------------------------------------------
A Sprite carries its own texture, rect, offset, PPU and mesh.  Two sprites whose
rect / m_Offset / PPU are identical are **interchangeable**: re-pointing a
renderer from one to the other moves nothing by a single pixel.  So instead of
drawing art per character, characters can be *consolidated* onto one canonical
sprite -- and a consolidated character needs **no art at all**, just 8 bytes.

Buckets (all 42 roster characters land in exactly one):

    ALREADY   already on the canonical sprite for its role
    MERGE     geometry-identical to the canonical sprite -> 8-byte PPtr edit
    REPAINT   frame differs -> must repaint its own texture in place
    KEEP_ROLE civilian / rat -> headgear shape is part of the identity
    NO_HAT    the prefab has no Hat GameObject at all

Canonical sprite per role family
--------------------------------
    远征军                 -> sharedassets15#229  (美制 M1,   139x76, ppu 200)
    日军士兵/佐官/将官/军医/海军 -> resources#3633      (昭五式铁帽, 139x76, ppu 200)

Both are 139x76 with m_Offset (-3.9155, -8.9911) and ppu 200, which is exactly
what makes a re-point pixel-neutral.  Both meshes were verified to cover 100% of
the new art's opaque pixels, so nothing is clipped.

Art is procedural (zero credits): `restyle_ink.restyle` with slot **`hat`** and
an explicit **role**, plus a diamond camo net and a 朱红 star for IJA headgear.
The alpha channel is restored from the original after restyling, so the
silhouette -- and therefore the collision box and the sprite mesh -- never moves.

One documented compromise: `resources#1921` is shared by ZombieGun (日军佐官)
and ZombieCop (平民).  Repainting it gives both the 昭五式.  Both are zombies,
so the pairing reads fine; it is listed in the output as `SHARED_TEX`.

Usage
-----
    python hat_plan.py            # classify + print the table (writes nothing)
    python hat_plan.py --apply    # execute MERGE + REPAINT
    python hat_plan.py --verify   # re-read the live files and check
"""
import io
import json
import os
import struct
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ggc_assets import AssetDB, DATA, PROJECT, tn  # noqa: E402
import characters_meta as M  # noqa: E402
import factions  # noqa: E402
import theme_cbi as T  # noqa: E402
import restyle_ink as R  # noqa: E402
from split_hat import camo_net, star  # noqa: E402

BACKUP = os.path.join(PROJECT, "backup")
OUT = os.path.join(PROJECT, "art")
PLAN = os.path.join(OUT, "hat_plan.json")
PRISTINE = {f: os.path.join(BACKUP, f) for f in os.listdir(BACKUP)
            if f.endswith(".assets")}

# canonical sprite per role family: (file, sprite path_id, label)
CANON = {
    T.EXPEDITIONARY: ("sharedassets15.assets", 229, "美制 M1"),
    T.IJA_SOLDIER:   ("resources.assets", 3633, "昭五式铁帽"),
    T.IJA_OFFICER:   ("resources.assets", 3633, "昭五式铁帽"),
    T.IJA_GENERAL:   ("resources.assets", 3633, "昭五式铁帽"),
    T.IJA_MEDIC:     ("resources.assets", 3633, "昭五式铁帽"),
    T.IJA_NAVY:      ("resources.assets", 3633, "昭五式铁帽"),
}
IJA_ROLES = {T.IJA_SOLDIER, T.IJA_OFFICER, T.IJA_GENERAL, T.IJA_MEDIC,
             T.IJA_NAVY}
KEEP_ROLES = {T.CIVILIAN_WORK, T.CIVILIAN_LIGHT, T.RAT}


# ------------------------------------------------------------------ geometry
def geom(meta):
    return (tuple(meta["rect"]), round(meta["pivot_x"], 3),
            round(meta["pivot_y"], 3), round(meta["ppu"], 3))


def find_hat(db, go_obj):
    """(SpriteRenderer obj, sprite meta, active) of the Hat child, or None."""
    def rec(obj):
        ctx = db.ctx_of(obj)
        gtt = obj.read_typetree()
        comps = [(c[0], (c[1] or {}).get("m_PathID", 0))
                 for c in (gtt.get("m_Component") or [])]
        tr_pid = next((p for c, p in comps if c == 4), None)
        sr_pid = next((p for c, p in comps if c == 212), None)
        found = None
        if sr_pid and (gtt.get("m_Name") or "").lower() == "hat":
            found = (ctx[0].get(sr_pid), gtt)
        if found and found[0] is not None:
            return found
        if not tr_pid:
            return None
        tr = ctx[0].get(tr_pid)
        for ch in (tr.read_typetree().get("m_Children") or []):
            co = ctx[0].get(ch.get("m_PathID", 0))
            if co is None:
                continue
            cgo = (co.read_typetree().get("m_GameObject") or {}).get("m_PathID", 0)
            child = ctx[0].get(cgo) if cgo else None
            if child is None:
                continue
            hit = rec(child)
            if hit:
                return hit
        return None

    hit = rec(go_obj)
    if not hit:
        return None
    sr, gtt = hit
    st = sr.read_typetree()
    sp = db.resolve(st.get("m_Sprite") or {}, db.ctx_of(sr))
    if sp is None or tn(sp) != "Sprite":
        return None
    meta = db.sprite_meta(sp)
    if not meta or "image" not in meta:
        return None
    return sr, meta, bool(gtt.get("m_IsActive", 1))


# --------------------------------------------------------------------- plan
def build_plan():
    db = AssetDB(file_map=PRISTINE)
    canon = {}
    for role, (cf, cspid, label) in CANON.items():
        cm = db.sprite_meta(db.file_objs(cf).get(cspid))
        canon[role] = (geom(cm), cspid, label)

    rows = []
    for ent in M.ROSTER:
        name = ent["prefab"]
        role = T.ROLE_OF.get(name)
        fac = factions.faction_of(name)
        go = db.find_go(name)
        row = {"char": name, "role": role, "faction": fac}
        if go is None:
            row["status"] = "NO_PREFAB"
            rows.append(row)
            continue
        hit = find_hat(db, go)
        if hit is None:
            row["status"] = "NO_HAT"
            rows.append(row)
            continue
        sr, meta, active = hit
        row.update({
            "active": active,
            "sr_pid": sr.path_id,
            "sprite_file": meta["sprite_file"],
            "sprite_pid": meta["sprite_path_id"],
            "tex_file": meta["texture_file"],
            "tex_pid": meta["texture_path_id"],
            "atlas_rect": list(meta["atlas_rect"]),
            "rotation": meta["rotation"],
            "size": list(meta["image"].size),
            "rect": list(meta["rect"]),
            "pivot": [round(meta["pivot_x"], 3), round(meta["pivot_y"], 3)],
            "ppu": meta["ppu"],
        })
        if role in KEEP_ROLES:
            row["status"] = "KEEP_ROLE"
        elif role is None or role not in canon:
            row["status"] = "KEEP_NOROLE"
        else:
            g, cspid, label = canon[role]
            row["canon"] = label
            if meta["sprite_path_id"] == cspid:
                row["status"] = "ALREADY"
            elif geom(meta) == g:
                row["status"] = "MERGE"
                row["target_sprite"] = cspid
            else:
                row["status"] = "REPAINT"
        rows.append(row)

    # flag textures touched by more than one roster character
    users = {}
    for r in rows:
        if "tex_pid" in r:
            users.setdefault((r["tex_file"], r["tex_pid"]), []).append(r["char"])
    for r in rows:
        if "tex_pid" in r:
            u = users[(r["tex_file"], r["tex_pid"])]
            if len(u) > 1:
                r["shared_with"] = u

    with io.open(PLAN, "w", encoding="utf-8") as fh:
        json.dump(rows, fh, ensure_ascii=False, indent=1)
    return rows


def print_plan(rows):
    buckets = {}
    for r in rows:
        buckets.setdefault(r["status"], []).append(r)
    for st in ("ALREADY", "MERGE", "REPAINT", "KEEP_ROLE", "KEEP_NOROLE",
               "NO_HAT", "NO_PREFAB"):
        v = buckets.get(st, [])
        print(f"\n=== {st}  ({len(v)})")
        for r in v:
            if "sprite_pid" in r:
                extra = ""
                if r.get("shared_with"):
                    extra = f"  SHARED_TEX={r['shared_with']}"
                print(f"  {r['char']:<22} {str(r['role']):<8} {r['size']} "
                      f"tex={r['tex_file'].replace('.assets', '')}#{r['tex_pid']} "
                      f"sprite#{r['sprite_pid']} "
                      f"piv=({r['pivot'][0]},{r['pivot'][1]}){extra}")
            else:
                print(f"  {r['char']:<22} {r.get('role')}")


# --------------------------------------------------------------- live access
def tex_read(db, fname, pid):
    obj = db.file_objs(fname).get(pid)
    tt = obj.read_typetree()
    w, h = tt["m_Width"], tt["m_Height"]
    if tt["m_TextureFormat"] != 5:
        raise SystemExit(f"{fname}#{pid}: format {tt['m_TextureFormat']} != 5")
    off = int(obj.byte_start) + int(obj.byte_size) - w * h * 4
    with open(os.path.join(DATA, fname), "rb") as fh:
        fh.seek(off)
        raw = fh.read(w * h * 4)
    a = np.frombuffer(raw, np.uint8).reshape(h, w, 4)[::-1]
    return Image.fromarray(np.ascontiguousarray(a[..., [1, 2, 3, 0]]), "RGBA")


def tex_write(fname, obj, img):
    a = np.array(img.convert("RGBA"), dtype=np.uint8)[::-1]
    raw = np.ascontiguousarray(a[..., [3, 0, 1, 2]]).tobytes()
    w, h = img.size
    if len(raw) != w * h * 4:
        raise SystemExit(f"{fname}: encoded {len(raw)} != {w * h * 4}")
    off = int(obj.byte_start) + int(obj.byte_size) - w * h * 4
    with open(os.path.join(DATA, fname), "r+b") as fh:
        fh.seek(off)
        fh.write(raw)
    return off


def repoint(db, sr_pid, new_pid, dry):
    obj = db.file_objs("resources.assets").get(sr_pid)
    cur = obj.read_typetree().get("m_Sprite") or {}
    fid, pid = cur.get("m_FileID", 0), cur.get("m_PathID", 0)
    if pid == new_pid and fid == 0:
        return None
    with open(os.path.join(DATA, "resources.assets"), "rb") as fh:
        fh.seek(int(obj.byte_start))
        blob = fh.read(int(obj.byte_size))
    pat = struct.pack("<ii", fid, pid)
    hits = [i for i in range(len(blob) - 7) if blob[i:i + 8] == pat]
    if len(hits) != 1:
        raise SystemExit(f"SR#{sr_pid}: {len(hits)} byte matches for "
                         f"({fid},{pid}), refusing to guess")
    off = int(obj.byte_start) + hits[0]
    if not dry:
        with open(os.path.join(DATA, "resources.assets"), "r+b") as fh:
            fh.seek(off)
            fh.write(struct.pack("<ii", 0, new_pid))
    return off, (fid, pid)


# --------------------------------------------------------------------- apply
def apply_plan(rows, dry=False):
    db = AssetDB(data_dir=DATA)
    jobs = []

    for r in rows:
        if r["status"] != "MERGE":
            continue
        res = repoint(db, r["sr_pid"], r["target_sprite"], dry)
        if res is None:
            continue
        off, old = res
        jobs.append({"kind": "pptr", "char": r["char"], "sr": r["sr_pid"],
                     "offset": off, "from": list(old),
                     "to": [0, r["target_sprite"]], "applied": not dry})
        print(f"  PPtr {r['char']:<22} SR#{r['sr_pid']:<6} @+{off}  "
              f"{list(old)} -> [0, {r['target_sprite']}]  "
              f"{'APPLIED' if not dry else 'dry'}")

    # one art build per distinct texture
    done = set()
    for r in rows:
        if r["status"] != "REPAINT":
            continue
        key = (r["tex_file"], r["tex_pid"])
        if key in done:
            continue
        done.add(key)
        if r["rotation"]:
            raise SystemExit(f"{r['char']}: rotated sprite, not handled")
        fname, pid = key
        obj = db.file_objs(fname).get(pid)
        tex = tex_read(db, fname, pid)
        x, y, w, h = r["atlas_rect"]
        top = tex.height - y - h
        crop = tex.crop((x, top, x + w, top + h))
        art = R.restyle(crop, slot="hat", faction=r["faction"] or "人类",
                        role=r["role"], seed=7)
        if r["role"] in IJA_ROLES:
            art = star(camo_net(art))
        art.putalpha(crop.getchannel("A"))   # silhouette is sacred
        new = tex.copy()
        new.paste(art, (x, top))
        off = None if dry else tex_write(fname, obj, new)
        jobs.append({"kind": "tex", "file": fname, "path_id": pid,
                     "char": r["char"], "atlas_rect": [x, y, w, h],
                     "applied": not dry})
        print(f"  TEX  {r['char']:<22} {fname.replace('.assets', '')}#{pid} "
              f"rect={w}x{h}@{x},{y}  {'APPLIED' if not dry else 'dry'}"
              f"{'  (shared with ' + ','.join(r['shared_with']) + ')' if r.get('shared_with') else ''}")

    with io.open(os.path.join(OUT, "hat_plan_jobs.json"), "w",
                 encoding="utf-8") as fh:
        json.dump({"dry": dry, "jobs": jobs}, fh, ensure_ascii=False, indent=1)
    return jobs


# -------------------------------------------------------------------- verify
def verify(rows):
    db = AssetDB(data_dir=DATA)
    pristine = AssetDB(file_map=PRISTINE)
    ok = True

    def chk(good, msg):
        nonlocal ok
        ok = bool(ok and good)
        print(f"{'OK  ' if good else 'FAIL'} {msg}")

    for r in rows:
        if r["status"] == "MERGE":
            st = db.file_objs("resources.assets").get(r["sr_pid"]).read_typetree()
            sp = st.get("m_Sprite") or {}
            chk(sp.get("m_FileID") == 0
                and sp.get("m_PathID") == r["target_sprite"],
                f"{r['char']:<22} SR#{r['sr_pid']} -> {sp}")
        elif r["status"] == "ALREADY":
            st = db.file_objs("resources.assets").get(r["sr_pid"]).read_typetree()
            sp = st.get("m_Sprite") or {}
            chk(sp.get("m_PathID") == r["sprite_pid"],
                f"{r['char']:<22} SR#{r['sr_pid']} unchanged -> {sp}")

    # every REPAINT texture: alpha must be byte-identical to pristine, and the
    # region outside the sprite's atlas rect must be untouched
    for r in rows:
        if r["status"] != "REPAINT":
            continue
        fname, pid = r["tex_file"], r["tex_pid"]
        now = tex_read(db, fname, pid)
        po = pristine.file_objs(fname).get(pid)
        pt = po.read_typetree()
        w, h = pt["m_Width"], pt["m_Height"]
        off = int(po.byte_start) + int(po.byte_size) - w * h * 4
        with open(os.path.join(BACKUP, fname), "rb") as fh:
            fh.seek(off)
            praw = fh.read(w * h * 4)
        pim = Image.fromarray(np.ascontiguousarray(
            np.frombuffer(praw, np.uint8).reshape(h, w, 4)[::-1][..., [1, 2, 3, 0]]),
            "RGBA")
        da = int(np.abs(np.array(now.getchannel("A")).astype(int)
                        - np.array(pim.getchannel("A")).astype(int)).max())
        x, y, aw, ah = r["atlas_rect"]
        top = h - y - ah
        mask = np.ones((h, w), bool)
        mask[top:top + ah, x:x + aw] = False
        if mask.any():
            dout = int(np.abs(np.array(now).astype(int)
                              - np.array(pim).astype(int))[mask].max())
        else:
            dout = 0      # the sprite covers the whole texture, nothing outside
        chk(da == 0 and dout == 0,
            f"{r['char']:<22} {fname.replace('.assets', '')}#{pid} "
            f"alpha_diff={da} outside_rect_diff={dout}")

    print("verify:", "PASS" if ok else "FAIL")
    return ok


def main():
    if "--verify" in sys.argv:
        rows = json.load(io.open(PLAN, encoding="utf-8"))
        return verify(rows)
    rows = build_plan()
    print_plan(rows)
    if "--apply" in sys.argv:
        print("\n--- applying")
        apply_plan(rows)
    return rows


if __name__ == "__main__":
    main()
