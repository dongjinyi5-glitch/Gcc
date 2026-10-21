"""Render character previews with a correct 2D TRS transform chain.

Why v2 exists
-------------
`render_characters.py` composed only local *position* and *scale*, silently
dropping every local rotation.  That is fatal for this game because several
characters are built from long chained part hierarchies:

  * rat tail  = Tail01..Tail14, each a child of the previous, rotated to curl
  * floater   = Rope chain
  * limbs     = Arm/Hand/Leg chains with baked rotations

Dropping rotation stacks all tail segments into one vertical column and turns
the largest segment into a pink/green cone.  v2 composes the full affine
(translate * rotate * scale) per node, then rasterises each sprite quad with
an inverse-affine sample so rotated sprites land exactly where the prefab
puts them.

Same PPtr rule as v1: m_FileID is resolved against the externals of the file
that owns the *referencing* object.

Outputs
  extracted/characters_v2/<name>.png
  extracted/characters_v2/render_report.json
"""
import os, io, json, math, struct
import UnityPy
from PIL import Image

DATA = r"D:\BaiduNetdiskDownload\意大利黑1\Guns, Gore and Cannoli\ggc_Data"
# Pristine copy of every file we have ever patched.  The roster must show the
# ORIGINAL art: Vinnie's textures were already rewritten in-place, so reading
# ggc_Data directly would render the restyled Vinnie (baseline contamination).
ORIG = r"D:\AI\DAIGuns, Gore and Cannoli from WB\backup"


def path_of(name):
    p = os.path.join(ORIG, name)
    return p if os.path.isfile(p) else os.path.join(DATA, name)


SRC = path_of("resources.assets")
OUT = r"D:\AI\DAIGuns, Gore and Cannoli from WB\extracted\characters"
os.makedirs(OUT, exist_ok=True)

PPU_OUT = 140.0
PAD = 28
SS = 2  # supersample factor for the affine sample

# Runtime-only effect subtrees that must not appear in a portrait.  FatCook /
# FatDockworker wrap the whole body under an active GameObject literally named
# "Explosion" whose sprite is a full-screen fire ball (shown when the unit is
# burning).  Rendering it buries the character in orange.
EXCLUDE_PARTS = {"Explosion", "Fire", "Burning"}

TARGETS = [
    "Vinnie", "Gangster1", "Gangster2", "Gangster3", "Gangster4", "Gangster5",
    "Gangster6", "Scientist", "Frankie", "EvilFrankie", "EvilFrankieOnFloor",
    "BonninoBoss", "ZombieRegular", "ZombieBurping", "ZombieCharger",
    "ZombieCrawler", "ZombieFloater", "ZombieGun", "ZombieJumper", "ZombieCop",
    "ZombieOfficer", "ZombiePaulie", "ZombieSailor", "ZombieSandwichBoard",
    "ZombieSoldier", "ZombieStripper", "ZombieRunner1", "ZombieRunner2",
    "ZombieRunner3", "ZombieRat", "ZombieRatBoss", "ZombieRatJumper",
    "ZombieRatSpitter",
    # --- discovered by scanning every GameObject that carries the `Unit`
    # script (42 total).  The original roster was built from a hand-written
    # name list and silently missed these nine combat units.
    "Goon1", "Goon2", "Goon3", "Vito", "Salvatore", "Paulie", "Soldier",
    "FatCook", "FatDockworker",
]

print("loading resources.assets ...", flush=True)
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


# ---------------- 2D affine helpers ----------------
IDENT = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)   # a b c d e f : x' = a x + b y + e


def mul(m, n):
    a, b, c, d, e, f = m
    A, B, C, D, E, F = n
    return (a * A + b * C, a * B + b * D,
            c * A + d * C, c * B + d * D,
            a * E + b * F + e, c * E + d * F + f)


def apply(m, x, y):
    a, b, c, d, e, f = m
    return (a * x + b * y + e, c * x + d * y + f)


def local_matrix(pos, quat, scale):
    qx = quat.get("x", 0.0)
    qy = quat.get("y", 0.0)
    qz = quat.get("z", 0.0)
    qw = quat.get("w", 1.0)
    # 2D rotation only; Unity quaternions here are pure Z
    ang = 2.0 * math.atan2(qz, qw)
    ca, sa = math.cos(ang), math.sin(ang)
    sx = scale.get("x", 1.0)
    sy = scale.get("y", 1.0)
    return (ca * sx, -sa * sy, sa * sx, ca * sy,
            pos.get("x", 0.0), pos.get("y", 0.0))


def invert(m):
    a, b, c, d, e, f = m
    det = a * d - b * c
    if abs(det) < 1e-12:
        return None
    ia, ib = d / det, -b / det
    ic, id_ = -c / det, a / det
    ie = -(ia * e + ib * f)
    if_ = -(ic * e + id_ * f)
    return (ia, ib, ic, id_, ie, if_)


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


def components(go_obj):
    try:
        tt = go_obj.read_typetree()
    except Exception:
        return []
    return [(c[0], (c[1] or {}).get("m_PathID", 0)) for c in (tt.get("m_Component") or [])]


def walk(go_obj, parent_m, depth, acc):
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
    m = mul(parent_m, local_matrix(tt.get("m_LocalPosition") or {},
                                   tt.get("m_LocalRotation") or {},
                                   tt.get("m_LocalScale") or {}))

    if sr_pid and gtt.get("m_Name", "") not in EXCLUDE_PARTS:
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
                        "m": m,
                        "sprite": sp_ref,
                        "part": gtt.get("m_Name", ""),
                        "color": col,
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
            walk(root_objs.get(cgo), m, depth + 1, acc)


def tint(img, col):
    r = col.get("r", 1.0); g = col.get("g", 1.0)
    b = col.get("b", 1.0); a = col.get("a", 1.0)
    if abs(r - 1) < 0.01 and abs(g - 1) < 0.01 and abs(b - 1) < 0.01 and a > 0.99:
        return img
    px = img.load()
    w, h = img.size
    for y in range(h):
        for x in range(w):
            pr, pg, pb, pa = px[x, y]
            px[x, y] = (int(pr * r), int(pg * g), int(pb * b), int(pa * a))
    return img


def render(name, go_obj):
    parts = []
    walk(go_obj, IDENT, 0, parts)
    if not parts:
        return None, 0, "no sprite renderers"
    parts.sort(key=lambda p: (p["order"], p["depth"]))

    quads = []
    minx = miny = 1e9
    maxx = maxy = -1e9
    for p in parts:
        sp = resolve(p["sprite"], ctx_of(go_obj))
        if sp is None or tn(sp) != "Sprite":
            continue
        s = sprite_image(sp)
        if not s:
            continue
        img, pivx, pivy, ppu = s
        w, h = img.size
        # sprite pixel -> local units -> world
        # local: lx = (px - pivx)/ppu ; ly = (h - pivy - py)/ppu
        corners = []
        for px, py in ((0, 0), (w, 0), (0, h), (w, h)):
            lx = (px - pivx) / ppu
            ly = (h - pivy - py) / ppu
            wx, wy = apply(p["m"], lx, ly)
            corners.append((wx, wy))
            minx = min(minx, wx); maxx = max(maxx, wx)
            miny = min(miny, wy); maxy = max(maxy, wy)
        quads.append((p, img, pivx, pivy, ppu, corners))

    if not quads:
        return None, len(parts), "no decodable sprites"

    W = int(math.ceil((maxx - minx) * PPU_OUT)) + PAD * 2
    H = int(math.ceil((maxy - miny) * PPU_OUT)) + PAD * 2
    if not (0 < W <= 4000 and 0 < H <= 4000):
        return None, len(parts), f"bad bounds {W}x{H}"

    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    for p, img, pivx, pivy, ppu, corners in quads:
        w, h = img.size
        # image pixel -> world -> canvas pixel
        to_world = mul(p["m"], (1.0 / ppu, 0.0, 0.0, -1.0 / ppu,
                                -pivx / ppu, (h - pivy) / ppu))
        to_canvas = (PPU_OUT, 0.0, 0.0, -PPU_OUT,
                     -minx * PPU_OUT + PAD, maxy * PPU_OUT + PAD)
        fwd = mul(to_canvas, to_world)
        inv = invert(fwd)
        if inv is None:
            continue
        # sample at supersampled resolution then downscale for clean edges
        layer = img.convert("RGBA")
        big = (W * SS, H * SS)
        # PIL AFFINE data order is (a, b, c, d, e, f) with c/f = translation:
        #   x_in = a*x_out + b*y_out + c ;  y_in = d*x_out + e*y_out + f
        # output coords are supersampled, so the linear part is divided by SS.
        ia, ib, ic, id_, ie, if_ = inv
        scaled = (ia / SS, ib / SS, ie, ic / SS, id_ / SS, if_)
        layer = layer.transform(big, Image.AFFINE, scaled, resample=Image.BICUBIC)
        if SS != 1:
            layer = layer.resize((W, H), Image.LANCZOS)
        col = p.get("color") or {}
        if col and (col.get("r", 1) < 0.99 or col.get("g", 1) < 0.99
                    or col.get("b", 1) < 0.99 or col.get("a", 1) < 0.99):
            layer = tint(layer, col)
        canvas.alpha_composite(layer)

    path = os.path.join(OUT, f"{name}.png")
    canvas.save(path)
    return path, len(quads), None


go_by_name = {}
for o in env.objects:
    if tn(o) != "GameObject":
        continue
    nm = go_name(o)
    if nm in TARGETS:
        go_by_name.setdefault(nm, o.path_id)

print("found:", len(go_by_name), "/", len(TARGETS), flush=True)
report = {}
for name in TARGETS:
    pid = go_by_name.get(name)
    if not pid:
        report[name] = {"error": "GameObject not found"}
        print(f"[MISS] {name}", flush=True)
        continue
    path, n, err = render(name, root_objs[pid])
    report[name] = {"file": os.path.basename(path) if path else None,
                    "parts": n, "error": err}
    print(f"[{'OK' if path else 'FAIL'}] {name} parts={n} {err or ''}", flush=True)

with io.open(os.path.join(OUT, "render_report.json"), "w", encoding="utf-8") as fh:
    json.dump(report, fh, indent=2, ensure_ascii=False)
print("DONE")
