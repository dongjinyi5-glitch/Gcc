"""Write the 重彩 textures back into the game's .assets files.

⚠️ 已废弃（DEPRECATED）— 不要运行这个脚本
=========================================
本脚本走 UnityPy 的 ``env.save()`` 路线。实测该路线在 Unity 4.3.4f1 build 上会
破坏 resources.assets：引擎报 ``The file '...resources.assets' is corrupted!`` /
``[Position out of bounds!]`` / ``Mismatched serialization in the builtin class
'TextAsset'. (Read 8800 bytes but expected 8784 bytes)``。dry run 能过，真写就坏。

**请使用 ``patch_textures.py``（定点字节覆盖，8 个文件字节数完全不变）。**

保留本文件仅作为"这条路走过且不通"的记录，避免以后有人再试一遍。

--- 原文档 ---

Two rules that matter
---------------------
1. **Paste by sprite region, not by texture.** Five of Vinnie's parts sit on a
   larger texture (the molotov is a 128x128 sprite on a 512x256 sheet). Replacing
   the whole texture would wipe whatever else that sheet holds, so the restyled
   crop is pasted back at its own ``textureRect``.
2. **The reader handle must be closed before saving** or Windows raises
   WinError 32. That is the same trap the round-trip test hit in M1.

Usage
-----
    python writeback.py Vinnie --dry     # work on temp copies, verify, discard
    python writeback.py Vinnie           # write into the game (backs up first)
"""
import io
import json
import os
import shutil
import sys
import tempfile

import numpy as np
import UnityPy
from PIL import Image

PROJECT = r"D:\AI\DAIGuns, Gore and Cannoli from WB"
DATA = r"D:\BaiduNetdiskDownload\意大利黑1\Guns, Gore and Cannoli\ggc_Data"
BACKUP = os.path.join(PROJECT, "backup")


def load_manifest(char):
    path = os.path.join(PROJECT, "art", f"{char.lower()}_parts", "manifest.json")
    with io.open(path, encoding="utf-8") as fh:
        return json.load(fh)


def restyled_path(char, fname):
    return os.path.join(PROJECT, "art", f"{char.lower()}_parts", "restyled", fname)


def group_by_texture(man, char):
    """{(file, texture_path_id): [job, ...]}"""
    jobs = {}
    for p in man["parts"]:
        key = (p["texture_file"], p["texture_path_id"])
        jobs.setdefault(key, []).append({
            "png": restyled_path(char, p["file"]),
            "atlas": [int(round(v)) for v in p["atlas_rect"]],
            "size": [int(round(v)) for v in p["size"]],
            "rot": int(p.get("rotation") or 0),
            "name": p["texture_name"],
        })
    for f in man["frames"]:
        key = (f["texture_file"], f["texture_path_id"])
        jobs.setdefault(key, []).append({
            "png": restyled_path(char, f["file"]),
            "atlas": [0, 0, int(f["size"][0]), int(f["size"][1])],
            "size": [int(v) for v in f["size"]],
            "rot": 0,
            "name": f["texture_name"],
        })
    return jobs


def apply_to_file(path, jobs, verbose=True):
    """Paste every job into the matching Texture2D, then save in place."""
    env = UnityPy.load(path)
    objs = {o.path_id: o for o in env.objects}
    done = 0
    for tex_pid, joblist in jobs.items():
        obj = objs.get(tex_pid)
        if obj is None:
            print(f"  [miss] texture {tex_pid} not in {os.path.basename(path)}")
            continue
        data = obj.read()
        full = data.image
        if full is None:
            print(f"  [skip] {joblist[0]['name']}: no decodable image")
            continue
        full = full.convert("RGBA")
        changed = False
        for job in joblist:
            if not os.path.isfile(job["png"]):
                print(f"  [skip] missing {job['png']}")
                continue
            img = Image.open(job["png"]).convert("RGBA")
            x, y, w, h = job["atlas"]
            if job["rot"]:
                print(f"  [skip] {job['name']}: rotated atlas not handled")
                continue
            if (img.width, img.height) != (w, h):
                img = img.resize((w, h), Image.LANCZOS)
            box = (x, full.height - y - h, x + w, full.height - y)
            full.paste(img, (box[0], box[1]))
            changed = True
            done += 1
        if changed:
            data.image = full
            data.save()
    # The writer needs to seek back into the reader for untouched objects, so
    # the stream must stay open during save -- which means we cannot write onto
    # the same path (WinError 32). Save beside it, then swap.
    outdir = tempfile.mkdtemp(prefix="ggc_wb_")
    env.save(pack=False, out_path=outdir)
    if hasattr(env.file, "reader") and hasattr(env.file.reader, "stream"):
        env.file.reader.stream.close()
    produced = os.path.join(outdir, os.path.basename(path))
    shutil.move(produced, path)
    shutil.rmtree(outdir, ignore_errors=True)
    if verbose:
        print(f"  wrote {done} texture region(s) -> {os.path.basename(path)}")
    return done


def verify(path, jobs, verbose=True):
    """Re-read the saved file and confirm the pixels actually changed."""
    env = UnityPy.load(path)
    objs = {o.path_id: o for o in env.objects}
    ok = 0
    bad = 0
    for tex_pid, joblist in jobs.items():
        obj = objs.get(tex_pid)
        if obj is None:
            continue
        full = obj.read().image
        if full is None:
            continue
        full = np.array(full.convert("RGBA"), dtype=np.int16)
        for job in joblist:
            if not os.path.isfile(job["png"]):
                continue
            img = np.array(Image.open(job["png"]).convert("RGBA"), dtype=np.int16)
            x, y, w, h = job["atlas"]
            if (img.shape[1], img.shape[0]) != (w, h):
                continue
            top = full.shape[0] - y - h
            region = full[top:top + h, x:x + w]
            diff = np.abs(region - img).max()
            if diff <= 2:
                ok += 1
            else:
                bad += 1
                if verbose:
                    print(f"  [verify-fail] {job['name']} max diff {diff}")
    if verbose:
        print(f"  verify: {ok} region(s) match the restyled PNG, {bad} mismatch")
    return ok, bad


def main():
    char = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("-") else "Vinnie"
    dry = "--dry" in sys.argv

    man = load_manifest(char)
    grouped = group_by_texture(man, char)
    by_file = {}
    for (fname, tex_pid), joblist in grouped.items():
        by_file.setdefault(fname, {})[tex_pid] = joblist

    print(f"{char}: {len(man['parts'])} parts + {len(man['frames'])} frames "
          f"across {len(by_file)} file(s), {len(grouped)} unique texture(s)")

    if dry:
        tmpdir = tempfile.mkdtemp(prefix="ggc_writeback_")
        print(f"DRY RUN -> {tmpdir}")
        total_ok = total_bad = 0
        for fname, jobs in by_file.items():
            src = os.path.join(DATA, fname)
            dst = os.path.join(tmpdir, fname)
            shutil.copy2(src, dst)
            print(f"- {fname}")
            apply_to_file(dst, jobs)
            ok, bad = verify(dst, jobs)
            total_ok += ok
            total_bad += bad
        print(f"DRY RESULT: {total_ok} verified, {total_bad} failed")
        return 0 if total_bad == 0 else 1

    # real run: back up every file we are about to touch
    os.makedirs(BACKUP, exist_ok=True)
    for fname in by_file:
        src = os.path.join(DATA, fname)
        dst = os.path.join(BACKUP, fname)
        if not os.path.isfile(dst):
            print(f"backup {fname} ({os.path.getsize(src) / 1048576:.1f} MB)")
            shutil.copy2(src, dst)
        else:
            print(f"backup exists: {fname}")

    total_ok = total_bad = 0
    for fname, jobs in by_file.items():
        print(f"- {fname}")
        path = os.path.join(DATA, fname)
        apply_to_file(path, jobs)
        ok, bad = verify(path, jobs)
        total_ok += ok
        total_bad += bad
    print(f"WRITEBACK RESULT: {total_ok} verified, {total_bad} failed")
    return 0 if total_bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
