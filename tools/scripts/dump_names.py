"""Dump all object names from Unity .assets files for character roster discovery.

Writes:
  extracted/names/<file>.names.txt   — one line per object: type<TAB>path_id<TAB>name
  extracted/names/all_textures.txt   — all Texture2D names (deduped, sorted)
  extracted/names/all_gameobjects.txt— all GameObject names (deduped, sorted)
"""
import os, sys, json, io
import UnityPy

GAME = r"D:\BaiduNetdiskDownload\意大利黑1\Guns, Gore and Cannoli"
DATA = os.path.join(GAME, "ggc_Data")
OUT = r"D:\AI\DAIGuns, Gore and Cannoli from WB\extracted\names"
os.makedirs(OUT, exist_ok=True)

files = []
for f in sorted(os.listdir(DATA)):
    if f.endswith(".assets"):
        files.append(os.path.join(DATA, f))
# mainData and level* are also serialized files
for f in sorted(os.listdir(DATA)):
    if f.startswith("level") and os.path.isfile(os.path.join(DATA, f)):
        files.append(os.path.join(DATA, f))
md = os.path.join(DATA, "mainData")
if os.path.isfile(md):
    files.append(md)

all_tex = set()
all_go = set()
summary = {}

for path in files:
    name = os.path.basename(path)
    rows = []
    tex_names = []
    go_names = []
    try:
        env = UnityPy.load(path)
        for obj in env.objects:
            tn = obj.type.name if hasattr(obj.type, "name") else str(obj.type)
            try:
                data = obj.read()
                nm = getattr(data, "m_Name", None) or getattr(data, "name", None) or ""
            except Exception:
                nm = ""
            rows.append(f"{tn}\t{obj.path_id}\t{nm}")
            if tn == "Texture2D" and nm:
                tex_names.append(nm)
                all_tex.add(nm)
            elif tn == "GameObject" and nm:
                go_names.append(nm)
                all_go.add(nm)
        try:
            if hasattr(env.file, "reader") and hasattr(env.file.reader, "stream"):
                env.file.reader.stream.close()
        except Exception:
            pass
    except Exception as e:
        print(f"[ERR] {name}: {e}")
        summary[name] = {"error": str(e)}
        continue

    with io.open(os.path.join(OUT, name + ".names.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(rows))
    summary[name] = {"objects": len(rows), "textures": len(tex_names), "gameobjects": len(go_names)}
    print(f"[OK] {name}: {len(rows)} objects, {len(tex_names)} textures, {len(go_names)} GOs")

with io.open(os.path.join(OUT, "all_textures.txt"), "w", encoding="utf-8") as fh:
    fh.write("\n".join(sorted(all_tex)))
with io.open(os.path.join(OUT, "all_gameobjects.txt"), "w", encoding="utf-8") as fh:
    fh.write("\n".join(sorted(all_go)))

with io.open(os.path.join(OUT, "summary.json"), "w", encoding="utf-8") as fh:
    json.dump({"files": summary, "unique_textures": len(all_tex), "unique_gameobjects": len(all_go)}, fh, indent=2, ensure_ascii=False)

print(f"\nUNIQUE textures={len(all_tex)} gameobjects={len(all_go)}")
