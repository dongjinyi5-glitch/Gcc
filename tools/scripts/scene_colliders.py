"""Which scene textures sit on a GameObject that carries a Collider2D.

This is the number that decides how freely the scene art can be redrawn.  A
texture on a collider-bearing object defines where the player stands and bumps,
so its silhouette is part of the gameplay contract; a texture on a plain
SpriteRenderer is pure decoration and can be redrawn into anything that fits the
same rect.

Colliders in this build are separate components (BoxCollider2D 4977,
PolygonCollider2D 568, EdgeCollider2D 229, CircleCollider2D 83) -- they are not
derived from the sprite, which is why "change the picture, keep the physics" is
possible at all.  The risk runs the other way: redraw a platform's silhouette
and the player will hit an invisible wall.

Writes `collider: true|false` into art/scene_inventory.json.
"""
import io
import json
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ggc_assets import AssetDB, DATA, PROJECT, tn  # noqa: E402

INV = os.path.join(PROJECT, "art", "scene_inventory.json")
LEVELS = ["level0"] + [f"level{i}" for i in range(3, 15)]
COLL = {"BoxCollider2D", "PolygonCollider2D", "EdgeCollider2D", "CircleCollider2D"}


def main():
    db = AssetDB(data_dir=DATA)
    hits = defaultdict(bool)
    type_count = defaultdict(int)

    for lv in LEVELS:
        objs = db.file_objs(lv)
        # which GameObjects carry a collider
        with_col = set()
        for pid, o in objs.items():
            if tn(o) != "GameObject":
                continue
            gtt = o.read_typetree()
            for c in (gtt.get("m_Component") or []):
                comp = objs.get((c[1] or {}).get("m_PathID", 0))
                if comp is not None and tn(comp) in COLL:
                    with_col.add(pid)
                    type_count[tn(comp)] += 1
                    break
        for pid, o in objs.items():
            if tn(o) != "SpriteRenderer":
                continue
            st = o.read_typetree()
            ctx = db.ctx_of(o)
            sp = db.resolve(st.get("m_Sprite") or {}, ctx)
            if sp is None or tn(sp) != "Sprite":
                continue
            meta = db.sprite_meta(sp)
            if not meta or "image" not in meta:
                continue
            key = (meta["texture_file"], meta["texture_path_id"])
            gid = (st.get("m_GameObject") or {}).get("m_PathID", 0)
            if gid in with_col:
                hits[key] = True
            else:
                hits.setdefault(key, False)

    rows = json.load(io.open(INV, encoding="utf-8"))
    for r in rows:
        r["collider"] = bool(hits.get((r["file"], r["path_id"]), False))
    json.dump(rows, io.open(INV, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    n_col = sum(1 for r in rows if r["collider"])
    tot = sum(r["painted"] for r in rows)
    p_col = sum(r["painted"] for r in rows if r["collider"])
    print("collider components:", dict(type_count))
    print(f"textures on a collider object: {n_col} / {len(rows)} "
          f"({n_col / len(rows) * 100:.0f}%)")
    print(f"painted area with collider: {p_col / 1e6:.1f} / {tot / 1e6:.1f} Mpx "
          f"({p_col / tot * 100:.1f}%)")


if __name__ == "__main__":
    main()
