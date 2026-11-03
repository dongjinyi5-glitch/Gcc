"""Measure how much art is really there: alpha coverage per scene texture.

W*H is a bad effort proxy.  A 1024x1024 page can be a full-frame backdrop (1.0
coverage) or a door handle on transparency (0.03).  This pass decodes every
texture once and records

    fill       fraction of pixels with alpha > 8
    painted    fill * W * H, i.e. the pixels an artist actually has to draw

into art/scene_inventory.json, and prints the concentration curve -- how much
of the total painted area sits in the biggest N textures.  That curve is what
decides whether the scene pass is "paint 50 backdrops" or "paint 1450 props".

The decode is the expensive part (~50 s for all 1450), so the result is cached
in the JSON and re-running is cheap: existing `fill` values are kept unless
--force is given.
"""
import io
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ggc_assets import AssetDB, DATA, PROJECT, tn  # noqa: E402

INV = os.path.join(PROJECT, "art", "scene_inventory.json")


def coverage(img):
    a = np.asarray(img.convert("RGBA"))[..., 3]
    return float((a > 8).mean())


def write_csv(rows):
    """Flat list for review in a spreadsheet: one row per texture."""
    import csv
    path = os.path.join(PROJECT, "art", "scene_inventory.csv")
    cols = ["texture", "file", "path_id", "w", "h", "fill", "painted",
            "renderers", "levels", "orders", "go_names"]
    with io.open(path, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(cols)
        for r in sorted(rows, key=lambda x: -x.get("painted", 0)):
            w.writerow([r["texture"], r["file"], r["path_id"],
                        r["size"][0], r["size"][1], r.get("fill", ""),
                        r.get("painted", ""), r["renderers"],
                        " ".join(r["levels"]), " ".join(str(o) for o in r["orders"]),
                        " | ".join(r["go_names"])])
    print(f"-> {path}")


def main(force=False):
    db = AssetDB(data_dir=DATA)
    rows = json.load(io.open(INV, encoding="utf-8"))
    todo = [r for r in rows if force or "fill" not in r]
    print(f"{len(rows)} textures, {len(todo)} need decoding")

    for i, r in enumerate(todo, 1):
        obj = db.file_objs(r["file"]).get(r["path_id"])
        if obj is None or tn(obj) != "Texture2D":
            r["fill"] = 0.0
            continue
        try:
            img = db.texture_image(obj)
            r["fill"] = round(coverage(img), 4) if img is not None else 0.0
        except Exception as e:
            print(f"  ! {r['texture']}: {e}")
            r["fill"] = 0.0
        w, h = r["size"]
        r["painted"] = int(round(r["fill"] * w * h))
        if i % 100 == 0:
            print(f"  {i}/{len(todo)}", flush=True)

    for r in rows:
        w, h = r["size"]
        r.setdefault("painted", int(round(r.get("fill", 0) * w * h)))

    json.dump(rows, io.open(INV, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    write_csv(rows)

    tot = sum(r["painted"] for r in rows)
    by = sorted(rows, key=lambda x: -x["painted"])
    print(f"\ntotal painted {tot / 1e6:.1f} Mpx over {len(rows)} textures")
    acc = 0
    for n in (10, 25, 50, 100, 200, 400, 800):
        acc = sum(r["painted"] for r in by[:n])
        print(f"  top {n:>4}: {acc / 1e6:>7.1f} Mpx  {acc / tot * 100:>5.1f}%")
    print("\nbiggest painted:")
    for r in by[:20]:
        print(f"  {r['size'][0]:>5}x{r['size'][1]:<5} fill {r['fill']:.2f} "
              f"{r['painted'] / 1e6:>6.2f}M  {r['texture']}")


if __name__ == "__main__":
    main("--force" in sys.argv)
