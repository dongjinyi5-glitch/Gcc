"""Composite a whole level's SpriteRenderers into one picture.

The contact sheets answer "what art exists"; this answers "what does the level
look like", which is the question that decides *what to repaint*.  A side-
scrolling level is a long strip of parallax panels plus props, so the overview
is a panorama, not a screenshot.

Transform handling
------------------
Levels store a plain Transform tree (m_Father / m_Children, no bones).  World
matrix = product of local TRS up the chain, cached per Transform.  Rotation is
kept because a few props are rotated; scale is kept because props are resized
by transform rather than by texture.

Blending
--------
Layers are alpha-blended, not overwritten.  Fog, water, glass and muzzle flashes
are semi-transparent; a hard paste would make them look like cut-outs and would
also mis-rank the depth order when eyeballing the result.

Draw order
----------
Unity 2D sorts by sortingLayer, then sortingOrder, then distance.  This build
uses integer m_SortingOrder only (no sorting layers in practice), and ties are
broken by object order in the file, which is creation order.

Usage
-----
    python scene_render.py level4 level8      # named levels
    python scene_render.py --all              # every level with scene art
    python scene_render.py level4 --ppu 60    # coarser overview
"""
import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ggc_assets import AssetDB, DATA, PROJECT, tn  # noqa: E402

OUT = os.path.join(PROJECT, "art", "scene_sheets")
MAX_PX = 7000          # longest side of the finished panorama


def mul(p, l):
    a, b, c, d, e, f = p
    A, B, C, D, E, F = l
    return (a * A + b * C, a * B + b * D, c * A + d * C, c * B + d * D,
            a * E + b * F + e, c * E + d * F + f)


def apply(m, x, y):
    a, b, c, d, e, f = m
    return (a * x + b * y + e, c * x + d * y + f)


def local_of(tt):
    q = tt.get("m_LocalRotation") or {}
    ang = 2.0 * np.arctan2(q.get("z", 0.0), q.get("w", 1.0))
    ca, sa = np.cos(ang), np.sin(ang)
    lp = tt.get("m_LocalPosition") or {}
    ls = tt.get("m_LocalScale") or {}
    sx, sy = ls.get("x", 1.0), ls.get("y", 1.0)
    return (ca * sx, -sa * sy, sa * sx, ca * sy,
            lp.get("x", 0.0), lp.get("y", 0.0))


def load_level(db, lv):
    objs = db.file_objs(lv)
    trs, gos, srs = {}, {}, []
    for pid, o in objs.items():
        t = tn(o)
        if t == "Transform":
            trs[pid] = o
        elif t == "GameObject":
            gos[pid] = o
        elif t == "SpriteRenderer":
            srs.append((pid, o))
    return trs, gos, srs


def make_resolver(trs, gos):
    """World matrix + effective active flag for a Transform path id."""
    cache = {}

    def world(tr_pid):
        if tr_pid in cache:
            return cache[tr_pid]
        tt = trs[tr_pid].read_typetree()
        lm = local_of(tt)
        fp = (tt.get("m_Father") or {}).get("m_PathID", 0)
        res = lm if not fp else mul(world(fp), lm)
        cache[tr_pid] = res
        return res

    def active(go_pid):
        seen = 0
        while go_pid and seen < 64:
            go = gos.get(go_pid)
            if go is None:
                return True
            gtt = go.read_typetree()
            if not gtt.get("m_IsActive", 1):
                return False
            tr_pid = None
            for c in (gtt.get("m_Component") or []):
                if c[0] == 4:
                    tr_pid = (c[1] or {}).get("m_PathID", 0)
                    break
            if not tr_pid or tr_pid not in trs:
                return True
            fp = (trs[tr_pid].read_typetree().get("m_Father") or {}).get("m_PathID", 0)
            if not fp:
                return True
            ptt = trs[fp].read_typetree()
            go_pid = (ptt.get("m_GameObject") or {}).get("m_PathID", 0)
            seen += 1
        return True

    return world, active


def collect(db, lv):
    trs, gos, srs = load_level(db, lv)
    world, active = make_resolver(trs, gos)
    quads = []
    for i, (pid, sr) in enumerate(srs):
        st = sr.read_typetree()
        ctx = db.ctx_of(sr)
        go_pid = (st.get("m_GameObject") or {}).get("m_PathID", 0)
        if go_pid and not active(go_pid):
            continue
        tr_pid = None
        go = gos.get(go_pid)
        if go is not None:
            for c in (go.read_typetree().get("m_Component") or []):
                if c[0] == 4:
                    tr_pid = (c[1] or {}).get("m_PathID", 0)
                    break
        if not tr_pid or tr_pid not in trs:
            continue
        sp = db.resolve(st.get("m_Sprite") or {}, ctx)
        if sp is None or tn(sp) != "Sprite":
            continue
        meta = db.sprite_meta(sp)
        if not meta or "image" not in meta:
            continue
        order = int(st.get("m_SortingOrder", 0))
        # m_Color is a per-renderer tint.  It is not cosmetic: several scene
        # textures are pure white masks (WindowBackdoor, WindShield, the health
        # bar) whose entire colour comes from this field, so ignoring it paints
        # white rectangles into the composite.
        col = st.get("m_Color") or {}
        tint = (float(col.get("r", 1.0)), float(col.get("g", 1.0)),
                float(col.get("b", 1.0)), float(col.get("a", 1.0)))
        quads.append((order, i, world(tr_pid), meta, tint))
    quads.sort(key=lambda q: (q[0], q[1]))
    return quads


def render(db, lv, ppu=100.0):
    quads = collect(db, lv)
    if not quads:
        print(f"{lv}: nothing to draw")
        return None
    boxes = []
    for _o, _i, m, meta, tint in quads:
        img = meta["image"]
        h = img.height
        pvx, pvy, sppu = meta["pivot_x"], meta["pivot_y"], meta["ppu"]
        pts = [apply(m, (px - pvx) / sppu, (h - pvy - py) / sppu)
               for px, py in ((0, 0), (img.width, 0), (img.width, h), (0, h))]
        boxes.append((img, pts, tint))
    xs = [p[0] for _i, pts, _t in boxes for p in pts]
    ys = [p[1] for _i, pts, _t in boxes for p in pts]
    # A single outlier (level8 has one crane parked far above the street) blows
    # the bounding box up and shrinks everything else to a smear.  Clip the
    # extreme 0.2% tails of the point cloud instead of trusting min/max; the
    # few quads that fall outside are simply not drawn.
    tail = 0.002
    x_lo, x_hi = np.quantile(np.array(xs), [tail, 1 - tail])
    y_lo, y_hi = np.quantile(np.array(ys), [tail, 1 - tail])
    minx, maxy = float(x_lo), float(y_hi)
    W = int(round((x_hi - x_lo) * ppu)) + 2
    H = int(round((y_hi - y_lo) * ppu)) + 2
    longest = max(W, H)
    if longest > MAX_PX:
        k = MAX_PX / longest
        ppu *= k
        W, H = max(1, int(W * k)), max(1, int(H * k))
    canvas = np.zeros((H, W, 4), np.float32)

    for img, pts, tint in boxes:
        dst = [((cx - minx) * ppu + 1, (maxy - cy) * ppu + 1) for cx, cy in pts]
        A, b = [], []
        for (sx_, sy_), (dx, dy) in zip(((0, 0), (img.width, 0),
                                        (img.width, img.height), (0, img.height)),
                                       dst):
            A.append([sx_, sy_, 1, 0, 0, 0]); b.append(dx)
            A.append([0, 0, 0, sx_, sy_, 1]); b.append(dy)
        coef, *_ = np.linalg.lstsq(np.array(A, float), np.array(b, float),
                                   rcond=None)
        c0, c1, c2, c3, c4, c5 = coef
        det = c0 * c4 - c1 * c3
        if abs(det) < 1e-9:
            continue
        ia, ib = c4 / det, -c1 / det
        ic, id_ = -c3 / det, c0 / det
        ie = -(ia * c2 + ib * c5)
        if_ = -(ic * c2 + id_ * c5)
        x0 = max(0, int(min(p[0] for p in dst)))
        x1 = min(W, int(max(p[0] for p in dst)) + 1)
        y0 = max(0, int(min(p[1] for p in dst)))
        y1 = min(H, int(max(p[1] for p in dst)) + 1)
        if x1 <= x0 or y1 <= y0:
            continue
        XX, YY = np.meshgrid(np.arange(x0, x1, dtype=np.float32),
                             np.arange(y0, y1, dtype=np.float32))
        sxv = ia * XX + ib * YY + ie
        syv = ic * XX + id_ * YY + if_
        ok = ((sxv >= 0) & (sxv < img.width - 0.5)
              & (syv >= 0) & (syv < img.height - 0.5))
        if not ok.any():
            continue
        arr = np.asarray(img.convert("RGBA"), np.float32) / 255.0
        xi = np.clip(sxv.astype(np.int32), 0, img.width - 1)
        yi = np.clip(syv.astype(np.int32), 0, img.height - 1)
        src = arr[yi, xi]
        tr, tg, tb, ta = tint
        src[..., 0] *= tr
        src[..., 1] *= tg
        src[..., 2] *= tb
        sa = src[..., 3:4] * ok[..., None] * ta
        da = canvas[y0:y1, x0:x1, 3:4]
        out_a = sa + da * (1.0 - sa)
        with np.errstate(invalid="ignore", divide="ignore"):
            rgb = (src[..., :3] * sa + canvas[y0:y1, x0:x1, :3] * da * (1.0 - sa))
            rgb = np.where(out_a > 1e-6, rgb / np.maximum(out_a, 1e-6), 0.0)
        canvas[y0:y1, x0:x1, :3] = rgb
        canvas[y0:y1, x0:x1, 3:4] = out_a

    im = Image.fromarray((np.clip(canvas, 0, 1) * 255).astype(np.uint8), "RGBA")
    # composite onto the page colour the game uses, so transparent sky reads black
    flat = Image.new("RGBA", im.size, (0, 0, 0, 255))
    flat.alpha_composite(im)
    return flat.convert("RGB"), len(quads)


def stack_rows(im, row_w=2600, gap=10, bg=(26, 26, 30)):
    """Split a very wide strip into equal columns and stack them.

    A 7000x455 panorama is unreadable in a browser: it gets scaled down until
    the art is a smear.  Splitting it into 3 stacked columns keeps the pixels
    and puts them in a shape a page can show at 1:1.
    """
    n = max(1, int(np.ceil(im.width / row_w)))
    if n == 1:
        return im
    w = int(np.ceil(im.width / n))
    rows = [im.crop((i * w, 0, min(im.width, (i + 1) * w), im.height))
            for i in range(n)]
    H = sum(r.height for r in rows) + gap * (n - 1)
    out = Image.new("RGB", (w, H), bg)
    y = 0
    for r in rows:
        out.paste(r, (0, y))
        y += r.height + gap
    return out


def main(argv):
    db = AssetDB(data_dir=DATA)
    os.makedirs(OUT, exist_ok=True)
    ppu = 100.0
    if "--ppu" in argv:
        ppu = float(argv[argv.index("--ppu") + 1])
    suffix = ""
    if "--restyled" in argv:
        # Swap in restyled textures at the single point where a Texture2D
        # becomes pixels.  Doing it here rather than by rewriting files keeps
        # the game install untouched, and it also proves the restyle pass
        # needs no change to the sprite/collider data.
        d = argv[argv.index("--restyled") + 1]
        ov, cache = {}, {}
        for fn in sorted(os.listdir(d)):
            if not fn.endswith(".png"):
                continue
            f, _, pid = fn[:-4].rpartition("__")
            ov[(f, int(pid))] = os.path.join(d, fn)
        orig = db.texture_image
        used = [0]

        def patched(obj):
            key = (obj.assets_file.name, obj.path_id)
            if key in ov:
                if key not in cache:
                    cache[key] = Image.open(ov[key]).convert("RGBA")
                used[0] += 1
                return cache[key]
            return orig(obj)

        db.texture_image = patched
        suffix = "_restyled"
        print(f"  {len(ov)} restyled textures available in {d}")
    names = [a for a in argv[1:] if a.startswith("level")]
    if "--all" in argv or not names:
        names = [f"level{i}" for i in [0] + list(range(3, 15))]
    for lv in names:
        # Holding a whole level's restyled textures plus their sprite crops is
        # already ~1.5 GB on the big levels; carrying that across 13 levels is
        # how this process would die.  Drop both caches per level.
        if "--restyled" in argv:
            cache.clear()
        db._sprite_cache.clear()
        res = render(db, lv, ppu)
        if not res:
            continue
        im, n = res
        p = os.path.join(OUT, f"scene_{lv}{suffix}.png")
        im.save(p, optimize=True)
        rows = stack_rows(im)
        if rows is not im:
            rows.save(os.path.join(OUT, f"scene_{lv}{suffix}_rows.png"),
                      optimize=True)
        print(f"  {lv}: {n} quads -> {im.size}  rows {rows.size}  {p}")


if __name__ == "__main__":
    main(sys.argv)
