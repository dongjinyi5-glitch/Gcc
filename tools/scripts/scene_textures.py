"""Inventory of every texture the level files actually put on screen.

Scene art is SpriteRenderers inside level0..level14.  A level file holds no
pixels itself -- it references sharedassetsN via externals -- so the resolver
must follow each PPtr through the *level's* externals list.

Output: art/scene_inventory.json, one row per texture with the levels and
GameObject names that use it, sorted by pixel area (the big ones are the
parallax backgrounds).
"""
import io
import json
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ggc_assets import AssetDB, DATA, PROJECT, tn

LEVELS = [f"level{i}" for i in range(15)]
OUT = os.path.join(PROJECT, "art")


def main():
    db = AssetDB(data_dir=DATA)
    tex = defaultdict(lambda: {"levels": set(), "names": set(), "count": 0,
                               "size": None, "path": None, "order": set()})

    for lv in LEVELS:
        objs = db.file_objs(lv)
        if not objs:
            continue
        n_sr = 0
        for pid, o in objs.items():
            if tn(o) != "SpriteRenderer":
                continue
            try:
                st = o.read_typetree()
            except Exception:
                continue
            ctx = db.ctx_of(o)
            sp = db.resolve(st.get("m_Sprite") or {}, ctx)
            if sp is None or tn(sp) != "Sprite":
                continue
            meta = db.sprite_meta(sp)
            if not meta or "image" not in meta:
                continue
            key = (meta["texture_file"], meta["texture_path_id"])
            rec = tex[key]
            rec["levels"].add(lv)
            rec["count"] += 1
            rec["size"] = meta["texture_size"]
            rec["path"] = meta["texture_file"]
            rec["name"] = meta["texture_name"]
            rec["order"].add(int(st.get("m_SortingOrder", 0)))
            # owning GameObject name
            gid = (st.get("m_GameObject") or {}).get("m_PathID", 0)
            go = ctx[0].get(gid) if gid else None
            if go is not None:
                try:
                    rec["names"].add(go.read_typetree().get("m_Name", "?"))
                except Exception:
                    pass
            n_sr += 1
        print(f"{lv}: {n_sr} sprite renderers")

    rows = []
    for (f, pid), r in tex.items():
        w, h = r["size"]
        rows.append({
            "texture": r["name"], "file": f, "path_id": pid,
            "size": [w, h], "area": w * h,
            "renderers": r["count"], "levels": sorted(r["levels"]),
            "orders": sorted(r["order"]),
            "go_names": sorted(r["names"])[:12],
        })
    rows.sort(key=lambda x: -x["area"])
    with io.open(os.path.join(OUT, "scene_inventory.json"), "w",
                 encoding="utf-8") as fh:
        json.dump(rows, fh, ensure_ascii=False, indent=1)

    print(f"\n{len(rows)} distinct scene textures, "
          f"{sum(r['renderers'] for r in rows)} renderer instances")
    print(f"{'size':>11} {'area':>10} {'sr':>5} {'lv':>3}  name / go names")
    for r in rows[:45]:
        print(f"{r['size'][0]:>5}x{r['size'][1]:<5} {r['area']:>10} "
              f"{r['renderers']:>5} {len(r['levels']):>3}  {r['texture'][:28]:<28} "
              f"{','.join(r['go_names'][:3])[:44]}")
    return rows


if __name__ == "__main__":
    main()
