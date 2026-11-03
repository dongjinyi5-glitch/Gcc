"""Patch restyled scene textures into .assets in place, byte for byte.

Same contract as patch_textures.py (characters), applied to scene art:

* ``env.save()`` is forbidden -- it rewrites the SerializedFile and this
  Unity 4.3.4f1 build comes back with "resources.assets is corrupted".
* Every target texture is ARGB32 (format 5) with no mipmaps, so its pixel
  block is exactly ``w*h*4`` bytes sitting at the end of the object.  We
  overwrite exactly those bytes and nothing else: file size, object table,
  offsets and every other object stay bit-identical.
* Encoding is **A,R,G,B per pixel, rows bottom-up**, established by
  brute-forcing all 24 channel permutations against a known texture.

Why the scene pass needs no atlas maths
---------------------------------------
The character pass had to paste crops back at their ``textureRect`` because
several parts share one sheet.  Scene textures are one-sprite-per-texture
(1176/1450 full-rect, 274 padded, 1 multi-sprite) and ``restyle_scene`` runs on
the whole Texture2D, so the unit written back is the unit that was read.

Usage
-----
    python patch_scene.py level3 --check      # report only, touches nothing
    python patch_scene.py level3 --apply      # back up, then patch
    python patch_scene.py all --apply         # every level (1450 textures)
    python patch_scene.py sharedassets4.assets --audit <pre-patch copy>

    python patch_scene.py --rollback                  # undo the scene patch only
    python patch_scene.py --rollback --from backup/pre_scene_20261022_2327
    python patch_scene.py --rollback --pristine       # back to 2015, loses weapon art

Rollback uses absolute paths derived from PROJECT/DATA, so it works from any
working directory -- unlike a bare `copy backup\...`, which silently resolves
against whatever directory the shell happens to be sitting in.
"""
import io
import json
import os
import shutil
import sys
import time

import numpy as np
import UnityPy
from PIL import Image

PROJECT = r"D:\AI\Guns, Gore and Cannoli from WB"
DATA = r"D:\BaiduNetdiskDownload\意大利黑1\Guns, Gore and Cannoli\ggc_Data"
CACHE = os.path.join(PROJECT, "art", "scene_restyle", "all")
BACKUP = os.path.join(PROJECT, "backup")
INV = os.path.join(PROJECT, "art", "scene_inventory.json")


def opt(flag, default=None):
    return sys.argv[sys.argv.index(flag) + 1] if flag in sys.argv else default


def encode_argb32(img):
    """PIL RGBA (top-down) -> Unity ARGB32 raw block (A,R,G,B, bottom-up)."""
    a = np.array(img.convert("RGBA"), dtype=np.uint8)
    a = a[::-1]
    argb = a[..., [3, 0, 1, 2]]
    return np.ascontiguousarray(argb).tobytes()


def encode_rgb24(img):
    """PIL RGBA -> Unity RGB24 raw block (R,G,B, bottom-up).

    16 of L3's textures are format 3, not format 5 -- the character pass never
    met one, so "everything is ARGB32" was true there and false here.  The byte
    order was established the same way (brute-force the six permutations
    against the stored block): plain R,G,B, rows bottom-up, 3 bytes per pixel.
    """
    a = np.array(img.convert("RGB"), dtype=np.uint8)
    return np.ascontiguousarray(a[::-1]).tobytes()


ENC = {5: (encode_argb32, 4), 3: (encode_rgb24, 3)}


def jobs_for(level):
    rows = json.load(io.open(INV, encoding="utf-8"))
    sel = rows if level == "all" else [r for r in rows if level in r["levels"]]
    by_file = {}
    for r in sel:
        png = os.path.join(CACHE, f"{r['file']}__{r['path_id']}.png")
        by_file.setdefault(r["file"], []).append({
            "pid": int(r["path_id"]), "png": png, "name": r["texture"],
        })
    return by_file


def patch_file(fname, jobs, apply=False):
    path = os.path.join(DATA, fname)
    env = UnityPy.load(path)
    objs = {o.path_id: o for o in env.objects}
    out = []
    for job in jobs:
        obj = objs.get(job["pid"])
        if obj is None:
            out.append((job["name"], "object missing", 0))
            continue
        data = obj.read()
        fmt = int(data.m_TextureFormat)
        w, h = int(data.m_Width), int(data.m_Height)
        if fmt not in ENC:
            out.append((job["name"], f"format {fmt} unsupported", 0))
            continue
        enc, bpp = ENC[fmt]
        if not os.path.isfile(job["png"]):
            out.append((job["name"], "png missing", 0))
            continue
        new_full = Image.open(job["png"]).convert("RGBA")
        if (new_full.width, new_full.height) != (w, h):
            out.append((job["name"], f"size {new_full.size} != {(w, h)}", 0))
            continue

        expected = w * h * bpp
        cur = data.image.convert("RGBA")
        raw_old = enc(cur)
        raw_new = enc(new_full)
        if len(raw_old) != expected or len(raw_new) != expected:
            out.append((job["name"], "encoder size mismatch", 0))
            continue

        obj_bytes = obj.get_raw_data()
        if len(obj_bytes) < expected:
            out.append((job["name"], "object smaller than pixels", 0))
            continue
        rel = len(obj_bytes) - expected
        if obj_bytes[rel:] != raw_old:
            idx = obj_bytes.find(raw_old[:256])
            if idx < 0:
                out.append((job["name"], "pixel block not located", 0))
                continue
            rel = idx

        if apply:
            with open(path, "r+b") as fh:
                fh.seek(int(obj.byte_start) + rel)
                fh.write(raw_new)
        out.append((job["name"], "ok", int(obj.byte_start) + rel))
    return out


def backup(fnames):
    """One timestamped copy per file, never overwriting the pristine backup."""
    stamp = time.strftime("%Y%m%d_%H%M")
    d = os.path.join(BACKUP, f"pre_scene_{stamp}")
    os.makedirs(d, exist_ok=True)
    for fn in fnames:
        src = os.path.join(DATA, fn)
        dst = os.path.join(d, fn)
        if os.path.isfile(dst) and os.path.getsize(dst) == os.path.getsize(src):
            continue
        print(f"  backing up {fn} ({os.path.getsize(src) / 1e6:.0f} MB) -> {dst}")
        shutil.copy2(src, dst)
    return d


def audit(fname, backup_path):
    """Prove the patch touched nothing but texture pixel blocks.

    Reads the patched file and a pre-patch copy, then asserts every differing
    byte index falls inside some texture's pixel block.  This is the check that
    replaces "it looked fine when I opened the level": if a single byte outside
    a pixel block had moved, the object table or an offset would have shifted and
    the engine would eventually report a corrupted file.
    """
    cur = open(os.path.join(DATA, fname), "rb").read()
    old = open(backup_path, "rb").read()
    print(f"size {len(old)} -> {len(cur)} ({'unchanged' if len(old) == len(cur) else 'CHANGED'})")
    if len(old) != len(cur):
        return 1
    idx = np.flatnonzero(np.frombuffer(cur, np.uint8) != np.frombuffer(old, np.uint8))
    print(f"differing bytes: {len(idx)} ({100.0 * len(idx) / len(cur):.2f}%)")
    env = UnityPy.load(os.path.join(DATA, fname))
    spans = []
    for o in env.objects:
        try:
            d = o.read()
        except Exception:
            continue
        fmt = getattr(d, "m_TextureFormat", None)
        w, h = int(getattr(d, "m_Width", 0) or 0), int(getattr(d, "m_Height", 0) or 0)
        if fmt not in ENC or not w or not h:
            continue
        exp = w * h * ENC[fmt][1]
        rb = o.get_raw_data()
        if len(rb) < exp:
            continue
        start = int(o.byte_start) + len(rb) - exp
        spans.append((start, start + exp))
    spans.sort()
    lo = np.array([s[0] for s in spans])
    hi = np.array([s[1] for s in spans])
    j = np.searchsorted(lo, idx, side="right") - 1
    inside = (j >= 0) & (idx < hi[np.maximum(j, 0)])
    outside = int((~inside).sum())
    print(f"texture pixel blocks in file: {len(spans)}")
    print(f"diffs inside a pixel block: {int(inside.sum())}")
    print(f"diffs OUTSIDE a pixel block: {outside}  <-- must be 0")
    return 0 if outside == 0 else 1


def _snapshots():
    """Timestamped pre-patch snapshot dirs, oldest first (the names sort)."""
    if not os.path.isdir(BACKUP):
        return []
    return [os.path.join(BACKUP, n) for n in sorted(os.listdir(BACKUP))
            if n.startswith("pre_scene_") and os.path.isdir(os.path.join(BACKUP, n))]


def rollback(src_dir, label):
    """Copy .assets files from src_dir back into the game.

    There are two *different* levels of undo here and mixing them up is how work
    gets lost:

      * a `pre_scene_*` snapshot is "the state just before the scene patch".
        It still contains every earlier change -- the 5 weapon textures
        (Tommygun / Lupara / LuparaBarrels / TommygunDrum / TommygunTop) that
        were repainted into sharedassets4 long before the scenes were.
        Rolling back to it undoes *only* the scene restyle.
      * the pristine 2015 files sitting directly in backup/ are "nothing was
        ever changed".  Rolling back to those also throws away the weapon art.
    """
    files = [f for f in sorted(os.listdir(src_dir)) if f.endswith(".assets")]
    if not files:
        print(f"no .assets in {src_dir}")
        return 1
    print(f"rollback source : {src_dir}")
    print(f"                : {label}")
    print(f"{len(files)} file(s) -> {DATA}")
    bad = 0
    for fn in files:
        s = os.path.join(src_dir, fn)
        d = os.path.join(DATA, fn)
        try:
            shutil.copy2(s, d)
        except PermissionError:
            print(f"  [LOCKED] {fn} -- close the game first, the file is in use")
            bad += 1
            continue
        same = os.path.getsize(s) == os.path.getsize(d)
        print(f"  {fn}: {os.path.getsize(d):,} B  {'ok' if same else 'SIZE MISMATCH'}")
        bad += 0 if same else 1
    print(f"RESULT: {len(files) - bad} restored, {bad} failed")
    return 0 if bad == 0 else 1


def main():
    args = sys.argv[1:]
    if "--rollback" in args:
        if "--pristine" in args:
            return rollback(BACKUP, "pristine 2015 originals (also reverts weapon art)")
        pick = opt("--from")
        if pick:
            d = pick if os.path.isabs(pick) else os.path.join(PROJECT, pick)
        else:
            snaps = _snapshots()
            if not snaps:
                print("no pre_scene_* snapshot under backup/")
                return 1
            d = snaps[-1]
        return rollback(d, "pre-scene snapshot (keeps earlier character/weapon art)")
    if "--audit" in args:
        bk = opt("--audit")
        fname = next((a for a in args if a.endswith(".assets")), "sharedassets4.assets")
        return audit(fname, bk)
    level = next((a for a in args if not a.startswith("-")), "level3")
    apply = "--apply" in args
    by_file = jobs_for(level)
    total = sum(len(v) for v in by_file.values())
    print(f"{level}: {total} texture(s) across {len(by_file)} file(s) "
          f"({'APPLY' if apply else 'CHECK'})")
    if apply:
        backup(sorted(by_file))
    ok = bad = 0
    for fname, jobs in sorted(by_file.items()):
        before = os.path.getsize(os.path.join(DATA, fname))
        res = patch_file(fname, jobs, apply=apply)
        good = sum(1 for r in res if r[1] == "ok")
        ok += good
        bad += len(res) - good
        after = os.path.getsize(os.path.join(DATA, fname))
        flag = "size CHANGED" if after != before else "size unchanged"
        print(f"- {fname}: {good}/{len(res)} ok, {flag} ({after} B)")
        for name, status, _off in res:
            if status != "ok":
                print(f"    [skip] {name}: {status}")
    print(f"RESULT: {ok} ok, {bad} skipped")
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
