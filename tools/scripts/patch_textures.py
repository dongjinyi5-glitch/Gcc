"""Patch restyled textures into .assets **in place**, byte for byte.

Why not let UnityPy re-save the file?
-------------------------------------
It was tried. ``env.save()`` rewrites the whole SerializedFile, and on this
Unity 4.3.4f1 build it re-serialised the TextAssets with a different length
("Read 8800 bytes but expected 8784 bytes"), after which the engine reported
``resources.assets is corrupted``. The object table, offsets and sizes must not
move at all.

What this does instead
----------------------
Every target texture is ARGB32 with no mipmaps, so its pixel block is exactly
``width * height * 4`` bytes and lives at the very end of the object. We encode
the new pixels in Unity's native layout (BGRA, rows bottom-up), overwrite those
bytes through a file handle, and never touch anything else. File size, object
count, offsets and all other objects stay bit-identical.

Usage
-----
    python patch_textures.py Vinnie --check    # verify encoder + report offsets
    python patch_textures.py Vinnie            # patch in place

``--dir`` picks the source folder: ``restyled`` (the deterministic palette
recolor) or ``redraw`` (plan B). It defaults to ``restyled`` so existing
commands keep working.
"""
import io
import json
import os
import sys

import numpy as np
import UnityPy
from PIL import Image

PROJECT = r"D:\AI\DAIGuns, Gore and Cannoli from WB"
DATA = r"D:\BaiduNetdiskDownload\意大利黑1\Guns, Gore and Cannoli\ggc_Data"


def opt(flag, default=None):
    return sys.argv[sys.argv.index(flag) + 1] if flag in sys.argv else default


def encode_argb32(img):
    """PIL RGBA (top-down) -> Unity ARGB32 raw block.

    Verified empirically against the stored bytes of 110 textures: Unity 4.3
    stores format 5 as **A,R,G,B per pixel with rows bottom-up** (not BGRA).
    Guessing BGRA silently produced files the engine rejected, so this was
    established by brute-forcing all 24 channel permutations against a known
    texture and keeping the one that matched 100%.
    """
    a = np.array(img.convert("RGBA"), dtype=np.uint8)
    a = a[::-1]                       # rows bottom-up
    argb = a[..., [3, 0, 1, 2]]       # A,R,G,B
    return np.ascontiguousarray(argb).tobytes()


def load_jobs(char, folder="restyled"):
    path = os.path.join(PROJECT, "art", f"{char.lower()}_parts", "manifest.json")
    with io.open(path, encoding="utf-8") as fh:
        man = json.load(fh)
    base = os.path.join(PROJECT, "art", f"{char.lower()}_parts", folder)
    jobs = {}
    for p in man["parts"]:
        key = (p["texture_file"], p["texture_path_id"])
        jobs.setdefault(key, []).append({
            "png": os.path.join(base, p["file"]),
            "atlas": [int(round(v)) for v in p["atlas_rect"]],
            "name": p["texture_name"],
            "rot": int(p.get("rotation") or 0),
        })
    for f in man["frames"]:
        key = (f["texture_file"], f["texture_path_id"])
        jobs.setdefault(key, []).append({
            "png": os.path.join(base, f["file"]),
            "atlas": [0, 0, int(f["size"][0]), int(f["size"][1])],
            "name": f["texture_name"],
            "rot": 0,
        })
    return jobs


def process_file(fname, jobs, apply=False):
    path = os.path.join(DATA, fname)
    env = UnityPy.load(path)
    objs = {o.path_id: o for o in env.objects}
    results = []
    for tex_pid, joblist in jobs.items():
        obj = objs.get(tex_pid)
        if obj is None:
            results.append((joblist[0]["name"], "missing", 0))
            continue
        data = obj.read()
        fmt = int(data.m_TextureFormat)
        w, h = int(data.m_Width), int(data.m_Height)
        if fmt != 5:
            results.append((joblist[0]["name"], f"format {fmt} not ARGB32", 0))
            continue
        full = data.image.convert("RGBA")
        raw_old = encode_argb32(full)
        expected = w * h * 4
        if len(raw_old) != expected:
            results.append((joblist[0]["name"], "encoder size mismatch", 0))
            continue

        # the pixel block is the last field of the object
        obj_bytes = obj.get_raw_data()
        if len(obj_bytes) < expected:
            results.append((joblist[0]["name"], "object smaller than pixels", 0))
            continue
        rel = len(obj_bytes) - expected
        if obj_bytes[rel:] != raw_old:
            # fall back to a search; report if even that fails
            idx = obj_bytes.find(raw_old[:256])
            if idx < 0:
                results.append((joblist[0]["name"], "pixel block not located", 0))
                continue
            rel = idx

        new_full = full.copy()
        for job in joblist:
            if job["rot"]:
                continue
            if not os.path.isfile(job["png"]):
                continue
            img = Image.open(job["png"]).convert("RGBA")
            x, y, aw, ah = job["atlas"]
            if (img.width, img.height) != (aw, ah):
                img = img.resize((aw, ah), Image.LANCZOS)
            # textureRect y is measured from the bottom
            new_full.paste(img, (x, h - y - ah))

        raw_new = encode_argb32(new_full)
        if len(raw_new) != len(raw_old):
            results.append((joblist[0]["name"], "length changed, skipped", 0))
            continue

        if apply:
            with open(path, "r+b") as fh:
                fh.seek(int(obj.byte_start) + rel)
                fh.write(raw_new)
        results.append((joblist[0]["name"], "ok", int(obj.byte_start) + rel))
    return results


def main():
    args = sys.argv[1:]
    char = next((a for a in args if not a.startswith("-")), "Vinnie")
    folder = opt("--dir", "restyled")
    if folder not in ("restyled", "redraw"):
        raise SystemExit(f"--dir must be restyled or redraw, got {folder!r}")
    apply = "--apply" in args
    check = "--check" in args or not apply

    jobs = load_jobs(char, folder)
    by_file = {}
    for (fname, tex_pid), joblist in jobs.items():
        by_file.setdefault(fname, {})[tex_pid] = joblist

    print(f"{char} [{folder}]: {len(jobs)} texture(s) across "
          f"{len(by_file)} file(s) ({'APPLY' if apply else 'CHECK'})")
    ok = bad = 0
    for fname, jl in by_file.items():
        res = process_file(fname, jl, apply=apply)
        good = sum(1 for r in res if r[1] == "ok")
        ok += good
        bad += len(res) - good
        print(f"- {fname}: {good}/{len(res)} ok")
        for name, status, off in res:
            if status != "ok":
                print(f"    [skip] {name}: {status}")
    print(f"RESULT: {ok} ok, {bad} skipped")
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
