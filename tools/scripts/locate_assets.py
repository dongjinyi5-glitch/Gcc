"""Locate every character's sprite/atlas assets inside the AssetStudio dump.

For each of the 33 roster prefabs this walks the transform tree (skipping
inactive variants, exactly like render_characters.py), resolves each
SpriteRenderer to its Sprite and then to its source Texture2D, and records
whether that Texture2D exists as a PNG in the user-supplied dump
(`D:\\BaiduNetdiskDownload\\意大利黑1\\image\\Texture2D`).

Output: extracted/characters/asset_locations.json
"""
import os, io, json, struct
import UnityPy

DATA = r"D:\BaiduNetdiskDownload\意大利黑1\Guns, Gore and Cannoli\ggc_Data"
ORIG = r"D://AI//DAIGuns, Gore and Cannoli from WB//backup"


def path_of(name):
    p = os.path.join(ORIG, name)
    return p if os.path.isfile(p) else os.path.join(DATA, name)


SRC = path_of("resources.assets")
OUT = r"D:\AI\DAIGuns, Gore and Cannoli from WB\extracted\characters"
DUMP_TEX = r"D:\BaiduNetdiskDownload\意大利黑1\image\Texture2D"
DUMP_SPR = r"D:\BaiduNetdiskDownload\意大利黑1\image\Sprite"

import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from characters_meta import ROSTER
TARGETS = [e["prefab"] for e in ROSTER]

env = UnityPy.load(SRC)
root_objs = {o.path_id: o for o in env.objects}

_file_objs = {"resources.assets": root_objs}

def file_objs(name):
    if name in _file_objs:
        return _file_objs[name]
    path = path_of(name)
    if not os.path.isfile(path):
        _file_objs[name] = {}
        return {}
    e = UnityPy.load(path)
    d = {o.path_id: o for o in e.objects}
    _file_objs[name] = d
    return d

def ctx_of(obj):
    af = obj.assets_file
    return (file_objs(af.name), af.externals)

def resolve(pptr, ctx):
    if not pptr:
        return None
    fid = pptr.get("m_FileID", 0)
    pid = pptr.get("m_PathID", 0)
    if not pid:
        return None
    objs, externals = ctx
    if fid == 0:
        return objs.get(pid)
    if fid - 1 >= len(externals):
        return None
    return file_objs(externals[fid - 1].name).get(pid)

def tn(o):
    return o.type.name if hasattr(o.type, "name") else str(o.type)

def safe_name(o):
    try:
        return o.read().m_Name or ""
    except Exception:
        return ""

def components(go_obj):
    try:
        tt = go_obj.read_typetree()
    except Exception:
        return []
    return [(c[0], (c[1] or {}).get("m_PathID", 0)) for c in (tt.get("m_Component") or [])]

def walk(go_obj, acc, depth=0):
    try:
        gtt = go_obj.read_typetree()
    except Exception:
        return
    if not gtt.get("m_IsActive", True):
        return
    comps = components(go_obj)
    tr_pid = next((p for c, p in comps if c == 4), None)
    sr_pid = next((p for c, p in comps if c == 212), None)
    if not tr_pid:
        return
    tr = root_objs.get(tr_pid)
    if tr is None:
        return
    try:
        tt = tr.read_typetree()
    except Exception:
        return
    if sr_pid:
        so = root_objs.get(sr_pid)
        if so is not None:
            try:
                st = so.read_typetree()
                sp_ref = st.get("m_Sprite") or {}
                if sp_ref.get("m_PathID"):
                    acc.append({
                        "slot": gtt.get("m_Name", ""),
                        "sprite": sp_ref,
                        "order": st.get("m_SortingOrder", 0),
                        "depth": depth,
                    })
            except Exception:
                pass
    for ch in (tt.get("m_Children") or []):
        co = root_objs.get(ch.get("m_PathID", 0))
        if co is None:
            continue
        try:
            cgo = (co.read_typetree().get("m_GameObject") or {}).get("m_PathID", 0)
        except Exception:
            continue
        if cgo:
            walk(root_objs.get(cgo), acc, depth + 1)

# ---- dump index (case-insensitive) ----
dump_tex = {}
if os.path.isdir(DUMP_TEX):
    for f in os.listdir(DUMP_TEX):
        dump_tex[f.lower()] = os.path.join(DUMP_TEX, f)
dump_spr = {}
if os.path.isdir(DUMP_SPR):
    for f in os.listdir(DUMP_SPR):
        dump_spr[f.lower()] = os.path.join(DUMP_SPR, f)

go_by_name = {}
for o in env.objects:
    if tn(o) != "GameObject":
        continue
    nm = safe_name(o)
    if nm in TARGETS:
        go_by_name.setdefault(nm, o.path_id)

report = {}
for name in TARGETS:
    pid = go_by_name.get(name)
    if not pid:
        report[name] = {"error": "GameObject not found"}
        continue
    go_obj = root_objs[pid]
    acc = []
    walk(go_obj, acc)
    parts = []
    textures = []
    for p in acc:
        sp = resolve(p["sprite"], ctx_of(go_obj))
        if sp is None or tn(sp) != "Sprite":
            continue
        sp_name = safe_name(sp)
        tex_name = ""
        try:
            rd = sp.read_typetree().get("m_RD") or {}
            tex = resolve(rd.get("texture") or {}, ctx_of(sp))
            if tex is not None and tn(tex) == "Texture2D":
                tex_name = safe_name(tex)
        except Exception:
            pass
        parts.append({
            "slot": p["slot"],
            "sprite": sp_name,
            "texture": tex_name,
            "order": p["order"],
            "in_dump_texture": os.path.basename(dump_tex[tex_name.lower() + ".png"]) if tex_name.lower() + ".png" in dump_tex else None,
            "in_dump_sprite": os.path.basename(dump_spr[sp_name.lower() + ".png"]) if sp_name.lower() + ".png" in dump_spr else None,
        })
        if tex_name and tex_name not in textures:
            textures.append(tex_name)
    report[name] = {"parts": parts, "textures": textures}

with io.open(os.path.join(OUT, "asset_locations.json"), "w", encoding="utf-8") as fh:
    json.dump(report, fh, indent=2, ensure_ascii=False)

for name in TARGETS:
    r = report[name]
    if "error" in r:
        print(f"{name}: MISS")
        continue
    hit = sum(1 for p in r["parts"] if p["in_dump_texture"])
    print(f"{name}: parts={len(r['parts'])} textures={len(r['textures'])} dump_hit={hit}")
    print("    " + ", ".join(r["textures"][:14]) + (" ..." if len(r["textures"]) > 14 else ""))
print("WROTE", os.path.join(OUT, "asset_locations.json"))
