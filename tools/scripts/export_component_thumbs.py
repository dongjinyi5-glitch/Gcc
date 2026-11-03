"""Export one thumbnail per scene component, original and restyled.

The component table needs the two shapes side by side for 1450 rows, so the
thumbnails are built once here and reused by `build_component_xlsx.py`; opening
the bundle 1450 times inside the xlsx builder would cost minutes per rebuild.

Keyed by (file, path_id), not by name -- 27 names in this build are shared by two
different textures, and keying by name silently pairs the wrong shapes.

Restyled inputs are the already-written `art/scene_restyle/all/*.png`; originals
are decoded straight from the bundle so the "before" column cannot drift.
"""
import io
import json
import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ggc_assets import AssetDB, PROJECT, baseline_map  # noqa: E402

INV = os.path.join(PROJECT, "art", "scene_inventory.json")
RESTYLED = os.path.join(PROJECT, "art", "scene_restyle", "all")
THUMBS = os.path.join(PROJECT, "art", "component_thumbs")

BOX = (168, 126)        # thumbnail box, W x H
BACKDROP = (206, 201, 192)   # warm grey: reads for both pale paper and night art


def thumb(img):
    """Fit inside BOX on a flat backdrop, so silhouettes stay legible."""
    im = img.convert("RGBA")
    im.thumbnail(BOX, Image.LANCZOS)
    canvas = Image.new("RGB", BOX, BACKDROP)
    canvas.paste(im, ((BOX[0] - im.width) // 2, (BOX[1] - im.height) // 2), im)
    return canvas


def key(r):
    return "%s__%d" % (r["file"], r["path_id"])


def main():
    rows = json.load(io.open(INV, encoding="utf-8"))
    for sub in ("orig", "new"):
        os.makedirs(os.path.join(THUMBS, sub), exist_ok=True)

    db = AssetDB(file_map=baseline_map())   # 原图必须取 2015 备份
    objs = {}
    n_orig = n_new = n_miss = 0
    for i, r in enumerate(rows):
        k = key(r)
        dst_o = os.path.join(THUMBS, "orig", k + ".jpg")
        dst_n = os.path.join(THUMBS, "new", k + ".jpg")

        if not os.path.exists(dst_o):
            if r["file"] not in objs:
                objs[r["file"]] = db.file_objs(r["file"])
            obj = objs[r["file"]].get(r["path_id"])
            if obj is None:
                n_miss += 1
                continue
            try:
                im = db.texture_image(obj)
            except Exception as e:
                print("  fail orig", r["texture"], e)
                n_miss += 1
                continue
            thumb(im).save(dst_o, quality=86)
            n_orig += 1

        if not os.path.exists(dst_n):
            src = os.path.join(RESTYLED, k + ".png")
            if os.path.exists(src):
                thumb(Image.open(src)).save(dst_n, quality=86)
                n_new += 1

        if (i + 1) % 100 == 0:
            print("  %d/%d  orig+%d new+%d miss=%d" % (i + 1, len(rows), n_orig, n_new, n_miss))

    print("done: orig %d, new %d, missing %d" % (n_orig, n_new, n_miss))


if __name__ == "__main__":
    main()
