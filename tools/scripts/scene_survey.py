"""Survey what the 15 level files actually contain.

Scene art in this build does not live in one place: backgrounds are SpriteRenderers
on parallax layers, props are SpriteRenderers parented to level objects, and some
layers are MeshRenderers driven by Materials.  This walks each level file and
counts object types plus the sprites it references, so the art inventory can be
built from evidence instead of guesswork.
"""
import os
import sys
from collections import Counter, defaultdict

import UnityPy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ggc_assets import DATA

LEVELS = [f"level{i}" for i in range(15)]

for lv in LEVELS:
    p = os.path.join(DATA, lv)
    if not os.path.isfile(p):
        continue
    try:
        env = UnityPy.load(p)
    except Exception as exc:
        print(f"{lv}: load failed {exc}")
        continue
    types = Counter()
    ext = []
    for o in env.objects:
        types[o.type.name] += 1
    try:
        ext = [os.path.basename(e.path) for e in env.files[os.path.basename(p)].externals]
    except Exception:
        pass
    top = ", ".join(f"{k}={v}" for k, v in types.most_common(8))
    print(f"\n=== {lv}  objects={sum(types.values())}")
    print(f"    {top}")
    print(f"    externals: {ext[:10]}")
