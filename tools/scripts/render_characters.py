"""Render character previews + metadata from Unity 4.3.4f1 assets.

Correctness notes (learned the hard way):
  * PPtr m_FileID is relative to the file the *referencing object* lives in.
    So every resolution must use that object's own `assets_file.externals`.
  * UnityPy's legacy Sprite.image helper asserts on Unity 4.3 mesh data, so we
    decode sprites ourselves: crop atlas by m_RD.textureRect, scale to m_Rect.
  * Prefabs contain every weapon/pose variant; m_IsActive=False marks the
    variants that are off, so inactive subtrees are skipped.

Outputs:
  extracted/characters/<name>.png
  extracted/characters/roster.json
"""
import os, io, json, math, struct
import UnityPy
from PIL import Image

DATA = r"D:\BaiduNetdiskDownload\意大利黑1\Guns, Gore and Cannoli\ggc_Data"
SRC = os.path.join(DATA, "resources.assets")
OUT = r"D:\AI\DAIGuns, Gore and Cannoli from WB\extracted\characters"
NAMES_DIR = r"D:\AI\DAIGuns, Gore and Cannoli from WB\extracted\names"
os.makedirs(OUT, exist_ok=True)

PPU_OUT = 120.0
PAD = 24

TARGETS = [
    ("Vinnie", "玩家", "Vinnie"),
    ("Gangster1", "人类敌人", "Gangster"), ("Gangster2", "人类敌人", "Gangster"),
    ("Gangster3", "人类敌人", "Gangster"), ("Gangster4", "人类敌人", "Gangster"),
    ("Gangster5", "人类敌人", "Gangster"), ("Gangster6", "人类敌人", "Gangster"),
    ("Scientist", "人类敌人", "Scientist"),
    ("Frankie", "Boss", "Frankie"), ("EvilFrankie", "Boss", "Frankie"),
    ("EvilFrankieOnFloor", "Boss", "Frankie"), ("BonninoBoss", "Boss", "Bonnino"),
    ("ZombieRegular", "僵尸", "Zombie"), ("ZombieBurping", "僵尸", "Zombie"),
    ("ZombieCharger", "僵尸", "Zombie"), ("ZombieCrawler", "僵尸", "Zombie"),
    ("ZombieFloater", "僵尸", "Zombie"), ("ZombieGun", "僵尸", "Zombie"),
    ("ZombieJumper", "僵尸", "Zombie"), ("ZombieCop", "僵尸", "Zombie"),
    ("ZombieOfficer", "僵尸", "Zombie"), ("ZombiePaulie", "僵尸", "Zombie"),
    ("ZombieSailor", "僵尸", "Zombie"), ("ZombieSandwichBoard", "僵尸", "Zombie"),
    ("ZombieSoldier", "僵尸", "Zombie"), ("ZombieStripper", "僵尸", "Zombie"),
    ("ZombieRunner1", "僵尸", "Zombie"), ("ZombieRunner2", "僵尸", "Zombie"),
    ("ZombieRunner3", "僵尸", "Zombie"),
    ("ZombieRat", "鼠怪", "Rat"), ("ZombieRatBoss", "Boss", "Rat"),
    ("ZombieRatJumper", "鼠怪", "Rat"), ("ZombieRatSpitter", "鼠怪", "Rat"),
]
TARGET_NAMES = [t[0] for t in TARGETS]

print("loading resources.assets ...", flush=True)
env = UnityPy.load(SRC)
root = env.file
root_objs = {o.path_id: o for o in env.objects}
print("root objects:", len(root_objs), flush=True)

# ---------------- file registry ----------------
_file_objs = {"resources.assets": root_objs}

def file_objs(name):
    if name in _file_objs:
        return _file_objs[name]
    path = os.path.join(DATA, name)
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

# ---------------- sprite decode ----------------
_sprite_cache = {}

def sprite_image(sp_obj):
    key = (sp_obj.assets_file.name, sp_obj.path_id)
    if key in _sprite_cache:
        return _sprite_cache[key]
    res = None
    try:
        tt = sp_obj.read_typetree()
        ctx = ctx_of(sp_obj)
        rd = tt.get("m_RD") or {}
        trect = rd.get("textureRect") or {}
        tex_obj = resolve(rd.get("texture") or {}, ctx)
        if tex_obj is not None and tn(tex_obj) == "Texture2D":
            timg = tex_obj.read().image
            if timg is not None:
                timg = timg.convert("RGBA")
                x = int(round(trect.get("x", 0)))
                y = int(round(trect.get("y", 0)))
                w = max(1, int(round(trect.get("width", timg.width))))
                h = max(1, int(round(trect.get("height", timg.height))))
                settings = rd.get("settingsRaw", 0) or 0
                rot = (settings >> 4) & 0x3
                if rot in (1, 2, 3):
                    box = (x, timg.height - y - w, x + h, timg.height - y)
                    crop = timg.crop(box)
                    crop = crop.rotate(-90, expand=True) if rot == 1 else crop.rotate(90, expand=True)
                else:
                    box = (x, timg.height - y - h, x + w, timg.height - y)
                    crop = timg.crop(box)
                rect = tt.get("m_Rect") or {}
                rw = rect.get("width", w) or w
                rh = rect.get("height", h) or h
                # Unity semantics: displayed size is m_Rect, atlas region is textureRect
                if abs(crop.width - rw) > 1 or abs(crop.height - rh) > 1:
                    crop = crop.resize((max(1, int(round(rw))), max(1, int(round(rh)))), Image.LANCZOS)
                off = tt.get("m_Offset") or {}
                ppu = tt.get("m_PixelsToUnits") or 100.0
                pivx = rw / 2.0 + off.get("x", 0)
                pivy = rh / 2.0 + off.get("y", 0)
                res = (crop, pivx, pivy, ppu)
    except Exception:
        res = None
    _sprite_cache[key] = res
    return res

# ---------------- hierarchy ----------------
def go_name(o):
    try:
        return o.read().m_Name or ""
    except Exception:
        return ""

go_by_name = {}
for o in env.objects:
    if tn(o) != "GameObject":
        continue
    nm = go_name(o)
    if nm in TARGET_NAMES:
        go_by_name.setdefault(nm, o.path_id)

print("found:", len(go_by_name), "/", len(TARGET_NAMES), flush=True)

def components(go_obj):
    try:
        tt = go_obj.read_typetree()
    except Exception:
        return []
    return [(c[0], (c[1] or {}).get("m_PathID", 0)) for c in (tt.get("m_Component") or [])]

def walk(go_obj, parent, depth, acc):
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
    lp = tt.get("m_LocalPosition") or {}
    ls = tt.get("m_LocalScale") or {}
    x = parent[0] + lp.get("x", 0) * parent[2]
    y = parent[1] + lp.get("y", 0) * parent[3]
    sx = parent[2] * ls.get("x", 1)
    sy = parent[3] * ls.get("y", 1)

    if sr_pid:
        so = root_objs.get(sr_pid)
        if so is not None:
            try:
                st = so.read_typetree()
                col = st.get("m_Color") or {}
                sp_ref = st.get("m_Sprite") or {}
                if sp_ref.get("m_PathID") and col.get("a", 1) > 0.01:
                    acc.append({
                        "order": st.get("m_SortingOrder", 0),
                        "depth": depth,
                        "x": x, "y": y, "sx": sx, "sy": sy,
                        "sprite": sp_ref,
                        "part": gtt.get("m_Name", ""),
                    })
            except Exception:
                pass

    for ch in (tt.get("m_Children") or []):
        cpid = ch.get("m_PathID", 0)
        co = root_objs.get(cpid)
        if co is None:
            continue
        try:
            cgo = (co.read_typetree().get("m_GameObject") or {}).get("m_PathID", 0)
        except Exception:
            continue
        if cgo:
            walk(root_objs.get(cgo), (x, y, sx, sy), depth + 1, acc)

# ---------------- MonoBehaviour script class ----------------
def mb_script_class(mb_obj):
    try:
        raw = mb_obj.get_raw_data()
    except Exception:
        return ""
    if len(raw) < 24:
        return ""
    # layout: m_GameObject(8) | m_Enabled(1)+pad(3) | m_Script(8) | m_Name
    fid, pid = struct.unpack("<ii", raw[12:20])
    ctx = ctx_of(mb_obj)
    script = resolve({"m_FileID": fid, "m_PathID": pid}, ctx)
    if script is None:
        return ""
    try:
        return script.read_typetree().get("m_ClassName", "") or ""
    except Exception:
        return ""

def char_scripts(go_obj):
    out = []
    for cid, pid in components(go_obj):
        if cid == 114 and pid:
            o = root_objs.get(pid)
            if o is not None:
                n = mb_script_class(o)
                if n and n not in out:
                    out.append(n)
    return out

# ---------------- level keyword scan ----------------
def level_hits(keyword):
    hits = []
    for f in sorted(os.listdir(NAMES_DIR)):
        if not f.startswith("level") or not f.endswith(".names.txt"):
            continue
        try:
            with io.open(os.path.join(NAMES_DIR, f), encoding="utf-8") as fh:
                txt = fh.read()
        except Exception:
            continue
        if keyword.lower() in txt.lower():
            hits.append(f.split(".")[0])
    return hits

# ---------------- render ----------------
def render(name, go_obj):
    parts = []
    walk(go_obj, (0.0, 0.0, 1.0, 1.0), 0, parts)
    if not parts:
        return None, 0, "no sprite renderers"
    parts.sort(key=lambda p: (p["order"], p["depth"]))
    resolved = []
    minx = miny = 1e9
    maxx = maxy = -1e9
    part_names = []
    for p in parts:
        sp = resolve(p["sprite"], ctx_of(go_obj))
        if sp is None or tn(sp) != "Sprite":
            continue
        s = sprite_image(sp)
        if not s:
            continue
        img, pivx, pivy, ppu = s
        lx = p["x"] - (pivx / ppu) * p["sx"]
        ly = p["y"] - (pivy / ppu) * p["sy"]
        ux = lx + (img.width / ppu) * p["sx"]
        uy = ly + (img.height / ppu) * p["sy"]
        minx = min(minx, lx); maxx = max(maxx, ux)
        miny = min(miny, ly); maxy = max(maxy, uy)
        resolved.append((lx, ly, ux, uy, img))
        part_names.append(p["part"])
    if not resolved:
        return None, len(parts), "no decodable sprites"

    W = int(math.ceil((maxx - minx) * PPU_OUT)) + PAD * 2
    H = int(math.ceil((maxy - miny) * PPU_OUT)) + PAD * 2
    if not (0 < W <= 3000 and 0 < H <= 3000):
        return None, len(parts), f"bad bounds {W}x{H}"
    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    for lx, ly, ux, uy, img in resolved:
        px = (lx - minx) * PPU_OUT + PAD
        py = (maxy - uy) * PPU_OUT + PAD
        pw = max(1, int(round((ux - lx) * PPU_OUT)))
        ph = max(1, int(round((uy - ly) * PPU_OUT)))
        canvas.alpha_composite(img.resize((pw, ph), Image.LANCZOS),
                               (int(round(px)), int(round(py))))
    path = os.path.join(OUT, f"{name}.png")
    canvas.save(path)
    return path, len(resolved), None, part_names

roster = []
for name, faction, kw in TARGETS:
    pid = go_by_name.get(name)
    entry = {"name": name, "faction": faction}
    if not pid:
        entry["error"] = "GameObject not found"
        roster.append(entry)
        print(f"[MISS] {name}", flush=True)
        continue
    go_obj = root_objs[pid]
    out = render(name, go_obj)
    if len(out) == 4:
        path, nparts, err, part_names = out
    else:
        path, nparts, err = out
        part_names = []
    entry["sprite_parts"] = nparts
    if err:
        entry["error"] = err
    if path:
        entry["file"] = os.path.basename(path)
    entry["part_slots"] = part_names
    entry["scripts"] = char_scripts(go_obj)
    entry["levels"] = level_hits(kw)
    roster.append(entry)
    print(f"[{'OK' if path else 'FAIL'}] {name} parts={nparts} scripts={entry['scripts']} levels={entry['levels']}", flush=True)

# EvilFrankie prefab is a cutscene proxy (no SpriteRenderers) — reuse the floor variant art
have = {e["name"] for e in roster if e.get("file")}
for e in roster:
    if e["name"] == "EvilFrankie" and "EvilFrankieOnFloor" in have:
        e["file"] = "EvilFrankieOnFloor.png"
        e["note"] = "预制体为过场代理，无精灵渲染器；外观共用 EvilFrankieOnFloor"

with io.open(os.path.join(OUT, "roster.json"), "w", encoding="utf-8") as fh:
    json.dump(roster, fh, indent=2, ensure_ascii=False)

print("DONE")
