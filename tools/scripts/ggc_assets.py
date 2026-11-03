"""Shared access layer for Guns, Gore and Cannoli (Unity 4.3.4f1) assets.

Why this module exists
----------------------
Every earlier bug came from getting PPtr resolution wrong, so the rules are
encoded here once and reused by every script:

  * A PPtr's ``m_FileID`` is an index into the externals of the file that owns
    the *referencing* object -- never the file you happened to start from.
    ``resolve()`` therefore always takes the referencing object and derives the
    context from ``obj.assets_file``.
  * ``m_FileID == 0`` means "same file as the referencing object".
  * UnityPy's ``Sprite.image`` helper asserts on Unity 4.3 mesh data, so sprites
    are decoded by hand: crop the atlas by ``m_RD.textureRect``, then scale to
    the display size given by ``m_Rect``.

Public API
----------
    db = AssetDB()                       # lazy, only loads files on demand
    db.find_go("Vinnie")                 # -> ObjectReader or None
    db.walk(go_obj)                      # -> [Part, ...]  (all children)
    db.sprite_image(sprite_obj)          # -> PIL.Image (native size) or None
    db.texture_image(tex_obj)            # -> PIL.Image RGBA
"""
import os
import struct

import UnityPy
from PIL import Image

DATA = r"D:\BaiduNetdiskDownload\意大利黑1\Guns, Gore and Cannoli\ggc_Data"
PROJECT = r"D:\AI\Guns, Gore and Cannoli from WB"
BACKUP = os.path.join(PROJECT, "backup")


def baseline_map():
    """data-file basename -> pristine 2015 copy under backup/.

    Every .assets file in the live install has already been rewritten by one of
    our passes (character textures, L3 scene textures), so reading "the original"
    out of the game directory silently returns our own output.  Any comparison
    built that way reads as identical and proves nothing -- and a before/after
    table whose "before" is the after is worse than no table.

    Files that have no backup entry fall through to the live path.
    """
    out = {}
    if not os.path.isdir(BACKUP):
        return out
    for n in os.listdir(BACKUP):
        if n.endswith(".assets"):
            out[n] = os.path.join(BACKUP, n)
    return out


# Unity class IDs we care about
CLS_GAMEOBJECT = 4
CLS_TRANSFORM = 4        # same id space as GameObject in m_Component pairs
CLS_MONOBEHAVIOUR = 114
CLS_SPRITERENDERER = 212
CLS_ANIMATOR = 95
CLS_TRANSFORM_ID = 4
CLS_RECTTRANSFORM = 224


def tn(obj):
    """Type name of an ObjectReader, tolerant of missing enum entries."""
    if obj is None:
        return ""
    try:
        return obj.type.name
    except Exception:
        return str(getattr(obj, "type", ""))


class Part:
    """One SpriteRenderer found while walking a prefab hierarchy."""

    __slots__ = ("go_name", "go_path", "active", "order", "depth",
                 "x", "y", "sx", "sy", "sprite", "ctx", "layer")

    def __init__(self, **kw):
        for k in self.__slots__:
            setattr(self, k, kw.get(k))

    def __repr__(self):
        return (f"<Part {self.go_name} active={self.active} order={self.order} "
                f"pos=({self.x:.2f},{self.y:.2f})>")


class AssetDB:
    def __init__(self, data_dir=DATA, root_file="resources.assets", file_map=None):
        """``file_map`` redirects individual data files to another path.

        Needed because once a texture has been patched in place, the live
        game file no longer holds the original pixels. Composing a "before"
        image from it silently returns the restyled art — the baseline
        comparison then reads ~0 difference and proves nothing. Point the
        baseline DB at ``backup/`` via ``file_map`` instead.
        """
        self.data_dir = data_dir
        self.file_map = dict(file_map or {})
        self.root_path = self.file_map.get(
            root_file, os.path.join(data_dir, root_file))
        print(f"[AssetDB] loading {root_file} ...", flush=True)
        self.env = UnityPy.load(self.root_path)
        self.root_name = self.env.file.name
        self._files = {self.root_name: {o.path_id: o for o in self.env.objects}}
        print(f"[AssetDB] {self.root_name}: {len(self._files[self.root_name])} objects",
              flush=True)

    # ------------------------------------------------------------------ files
    def file_objs(self, name):
        """Objects of a data file by basename, loaded once and cached."""
        if name in self._files:
            return self._files[name]
        path = self.file_map.get(name, os.path.join(self.data_dir, name))
        if not os.path.isfile(path):
            self._files[name] = {}
            return {}
        e = UnityPy.load(path)
        d = {o.path_id: o for o in e.objects}
        self._files[name] = d
        return d

    def ctx_of(self, obj):
        """(objects, externals) of the file that owns ``obj``."""
        af = obj.assets_file
        return (self.file_objs(af.name), af.externals)

    # -------------------------------------------------------------- pointers
    def resolve(self, pptr, ctx):
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
        return self.file_objs(externals[fid - 1].name).get(pid)

    def resolve_in(self, pptr, owner):
        return self.resolve(pptr, self.ctx_of(owner))

    # ------------------------------------------------------------ gameobject
    def find_go(self, name, exact=True):
        """First GameObject whose name matches. Searches every loaded file."""
        for fname in list(self._files):
            for o in self._files[fname].values():
                if tn(o) != "GameObject":
                    continue
                try:
                    nm = o.read().m_Name or ""
                except Exception:
                    continue
                if (nm == name) if exact else (name in nm):
                    return o
        return None

    def all_gos(self, prefix=""):
        out = []
        for fname in list(self._files):
            for o in self._files[fname].values():
                if tn(o) != "GameObject":
                    continue
                try:
                    nm = o.read().m_Name or ""
                except Exception:
                    continue
                if nm.startswith(prefix):
                    out.append((nm, o))
        return out

    def components(self, go_obj):
        try:
            tt = go_obj.read_typetree()
        except Exception:
            return []
        return [(c[0], (c[1] or {}).get("m_PathID", 0))
                for c in (tt.get("m_Component") or [])]

    # ---------------------------------------------------------------- walking
    def walk(self, go_obj, include_inactive=True):
        """Walk a prefab hierarchy and return every SpriteRenderer as a Part.

        Transform math mirrors Unity: local position is scaled by the parent's
        accumulated scale before being added, which is how the game composes
        body parts.
        """
        out = []
        ctx = self.ctx_of(go_obj)
        self._walk(go_obj, (0.0, 0.0, 1.0, 1.0), 0, "", include_inactive, out, ctx)
        return out

    def _walk(self, go_obj, parent, depth, path, include_inactive, out, ctx):
        try:
            gtt = go_obj.read_typetree()
        except Exception:
            return
        active = bool(gtt.get("m_IsActive", True))
        if not active and not include_inactive:
            return
        name = gtt.get("m_Name", "")
        here = f"{path}/{name}" if path else name

        comps = [(c[0], (c[1] or {}).get("m_PathID", 0))
                 for c in (gtt.get("m_Component") or [])]
        tr_pid = next((p for c, p in comps if c in (4, CLS_RECTTRANSFORM)), None)
        sr_pid = next((p for c, p in comps if c == CLS_SPRITERENDERER), None)

        if tr_pid:
            tr = ctx[0].get(tr_pid)
            if tr is not None:
                try:
                    tt = tr.read_typetree()
                except Exception:
                    tt = {}
                lp = tt.get("m_LocalPosition") or {}
                ls = tt.get("m_LocalScale") or {}
                x = parent[0] + lp.get("x", 0) * parent[2]
                y = parent[1] + lp.get("y", 0) * parent[3]
                sx = parent[2] * ls.get("x", 1)
                sy = parent[3] * ls.get("y", 1)

                if sr_pid:
                    so = ctx[0].get(sr_pid)
                    if so is not None:
                        try:
                            st = so.read_typetree()
                        except Exception:
                            st = None
                        if st:
                            col = st.get("m_Color") or {}
                            sp_ref = st.get("m_Sprite") or {}
                            if sp_ref.get("m_PathID") and col.get("a", 1) > 0.01:
                                out.append(Part(
                                    go_name=name, go_path=here, active=active,
                                    order=st.get("m_SortingOrder", 0), depth=depth,
                                    x=x, y=y, sx=sx, sy=sy,
                                    sprite=sp_ref, ctx=ctx,
                                    layer=st.get("m_SortingLayer", 0),
                                ))

                for ch in (tt.get("m_Children") or []):
                    cpid = ch.get("m_PathID", 0)
                    co = ctx[0].get(cpid)
                    if co is None:
                        continue
                    try:
                        cgo = (co.read_typetree().get("m_GameObject") or {}).get("m_PathID", 0)
                    except Exception:
                        continue
                    child = ctx[0].get(cgo) if cgo else None
                    if child is not None:
                        self._walk(child, (x, y, sx, sy), depth + 1, here,
                                   include_inactive, out, ctx)

    # ----------------------------------------------------------------- images
    _sprite_cache = {}

    def texture_image(self, tex_obj):
        img = tex_obj.read().image
        return img.convert("RGBA") if img is not None else None

    def sprite_meta(self, sp_obj):
        """Decoded sprite description: cropped image plus geometry."""
        key = (sp_obj.assets_file.name, sp_obj.path_id)
        if key in self._sprite_cache:
            return self._sprite_cache[key]
        res = None
        try:
            tt = sp_obj.read_typetree()
            ctx = self.ctx_of(sp_obj)
            rd = tt.get("m_RD") or {}
            trect = rd.get("textureRect") or {}
            tex_obj = self.resolve(rd.get("texture") or {}, ctx)
            if tn(tex_obj) == "Texture2D":
                timg = self.texture_image(tex_obj)
                if timg is not None:
                    x = int(round(trect.get("x", 0)))
                    y = int(round(trect.get("y", 0)))
                    w = max(1, int(round(trect.get("width", timg.width))))
                    h = max(1, int(round(trect.get("height", timg.height))))
                    settings = rd.get("settingsRaw", 0) or 0
                    rot = (settings >> 4) & 0x3
                    if rot in (1, 2, 3):
                        box = (x, timg.height - y - w, x + h, timg.height - y)
                        crop = timg.crop(box)
                        crop = (crop.rotate(-90, expand=True) if rot == 1
                                else crop.rotate(90, expand=True))
                    else:
                        box = (x, timg.height - y - h, x + w, timg.height - y)
                        crop = timg.crop(box)
                    rect = tt.get("m_Rect") or {}
                    rw = rect.get("width", w) or w
                    rh = rect.get("height", h) or h
                    if abs(crop.width - rw) > 1 or abs(crop.height - rh) > 1:
                        crop = crop.resize((max(1, int(round(rw))),
                                            max(1, int(round(rh)))), Image.LANCZOS)
                    off = tt.get("m_Offset") or {}
                    ppu = tt.get("m_PixelsToUnits") or 100.0
                    res = {
                        "image": crop,
                        "pivot_x": rw / 2.0 + off.get("x", 0),
                        "pivot_y": rh / 2.0 + off.get("y", 0),
                        "ppu": ppu,
                        "rect": (rw, rh),
                        "atlas_rect": (x, y, w, h),
                        "rotation": rot,
                        "texture_name": tex_obj.read().m_Name,
                        "texture_path_id": tex_obj.path_id,
                        "texture_file": tex_obj.assets_file.name,
                        "texture_size": (timg.width, timg.height),
                        "sprite_name": tt.get("m_Name", ""),
                        "sprite_path_id": sp_obj.path_id,
                        "sprite_file": sp_obj.assets_file.name,
                    }
        except Exception as exc:  # noqa: BLE001
            res = {"error": f"{type(exc).__name__}: {exc}"}
        self._sprite_cache[key] = res
        return res

    def sprite_image(self, sp_obj):
        m = self.sprite_meta(sp_obj)
        return m.get("image") if m else None

    # ------------------------------------------------------------------ misc
    def mono_script_class(self, mb_obj):
        """Class name of a MonoBehaviour, read from m_Script.

        Raw layout of a MonoBehaviour in this build:
            m_GameObject(8) | m_Enabled(1)+pad(3) | m_Script(8) | ...
        so m_Script starts at byte offset 12.
        """
        try:
            raw = mb_obj.get_raw_data()
        except Exception:
            return ""
        if len(raw) < 24:
            return ""
        fid, pid = struct.unpack("<ii", raw[12:20])
        script = self.resolve({"m_FileID": fid, "m_PathID": pid},
                              self.ctx_of(mb_obj))
        if script is None:
            return ""
        try:
            return script.read_typetree().get("m_ClassName", "") or ""
        except Exception:
            return ""


if __name__ == "__main__":
    db = AssetDB()
    go = db.find_go("Vinnie")
    parts = db.walk(go)
    print(f"Vinnie parts (incl. inactive): {len(parts)}")
    for p in parts[:8]:
        m = db.sprite_meta(db.resolve(p.sprite, p.ctx))
        print(f"  {p.go_name:16s} active={p.active} order={p.order} "
              f"sprite={m.get('sprite_name')} tex={m.get('texture_name')} "
              f"texsize={m.get('texture_size')} rect={m.get('rect')}")
