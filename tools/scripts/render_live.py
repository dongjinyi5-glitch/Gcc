"""Render characters straight from the LIVE data dir (not backup/), so a patch
can be eyeballed.  Uses the full 2D affine chain: local position scaled by the
accumulated parent scale, local rotation applied (matters for tails/hoses)."""
import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ggc_assets import AssetDB, DATA, PROJECT, tn

db = AssetDB(data_dir=DATA)


def comp_of(go_obj, cls):
    ctx = db.ctx_of(go_obj)
    gtt = go_obj.read_typetree()
    for c in (gtt.get("m_Component") or []):
        if c[0] == cls:
            return ctx[0].get((c[1] or {}).get("m_PathID", 0)), ctx
    return None, ctx


def collect(go_obj, parent=(1, 0, 0, 1, 0, 0), active=True, out=None):
    if out is None:
        out = []
    gtt = go_obj.read_typetree()
    active = active and bool(gtt.get("m_IsActive", 1))
    tr, ctx = comp_of(go_obj, 4)
    if tr is None:
        return out
    tt = tr.read_typetree()
    q = tt.get("m_LocalRotation") or {}
    ang = 2.0 * np.arctan2(q.get("z", 0.0), q.get("w", 1.0))
    ca, sa = np.cos(ang), np.sin(ang)
    lp = tt.get("m_LocalPosition") or {}
    ls = tt.get("m_LocalScale") or {}
    sx, sy = ls.get("x", 1.0), ls.get("y", 1.0)
    lm = (ca * sx, -sa * sy, sa * sx, ca * sy,
          lp.get("x", 0.0), lp.get("y", 0.0))
    a, b, c, d, e, f = parent
    A, B, C, D, E, F = lm
    m = (a * A + b * C, a * B + b * D, c * A + d * C, c * B + d * D,
         a * E + b * F + e, c * E + d * F + f)

    sr, _ctx = comp_of(go_obj, 212)
    if sr is not None and active:
        st = sr.read_typetree()
        sp = st.get("m_Sprite") or {}
        if sp.get("m_PathID"):
            obj = db.resolve(sp, ctx)
            if obj is not None and tn(obj) == "Sprite":
                meta = db.sprite_meta(obj)
                if meta and "image" in meta:
                    out.append((m, meta, int(st.get("m_SortingOrder", 0))))
    for ch in (tt.get("m_Children") or []):
        co = ctx[0].get(ch.get("m_PathID", 0))
        if co is None:
            continue
        cgo = (co.read_typetree().get("m_GameObject") or {}).get("m_PathID", 0)
        child = ctx[0].get(cgo) if cgo else None
        if child is not None:
            collect(child, m, active, out)
    return out


def apply(m, x, y):
    a, b, c, d, e, f = m
    return (a * x + b * y + e, c * x + d * y + f)


def render(name, ppu_out=200.0, scale=1.0):
    go = db.find_go(name)
    if go is None:
        print(name, "not found")
        return None
    quads = collect(go)
    quads.sort(key=lambda t: t[2])
    imgs, pts = [], []
    for m, meta, order in quads:
        img = meta["image"]
        h = img.height
        pivx, pivy, ppu = meta["pivot_x"], meta["pivot_y"], meta["ppu"]
        corners = [apply(m, (px - pivx) / ppu, (h - pivy - py) / ppu)
                   for px, py in ((0, 0), (img.width, 0),
                                  (img.width, h), (0, h))]
        imgs.append((img, corners))
        pts.extend(corners)
    if not pts:
        print(name, "no quads")
        return None
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    minx, maxy = min(xs), max(ys)
    W = int((max(xs) - minx) * ppu_out) + 20
    H = int((maxy - min(ys)) * ppu_out) + 20
    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    for img, corners in imgs:
        dst = [((cx - minx) * ppu_out + 10, (maxy - cy) * ppu_out + 10)
               for cx, cy in corners]
        src = [(0, 0), (img.width, 0), (img.width, img.height),
               (0, img.height)]
        A, b = [], []
        for (sx_, sy_), (dx, dy) in zip(src, dst):
            A.append([sx_, sy_, 1, 0, 0, 0]); b.append(dx)
            A.append([0, 0, 0, sx_, sy_, 1]); b.append(dy)
        coef, *_ = np.linalg.lstsq(np.array(A, float), np.array(b, float),
                                   rcond=None)
        # A was built as rows [sx, sy, 1, 0, 0, 0] -> dx and
        # [0, 0, 0, sx, sy, 1] -> dy, so the affine is
        #   dx = c0*sx + c1*sy + c2 ,  dy = c3*sx + c4*sy + c5
        # i.e. M = [[c0, c1], [c3, c4]] and t = (c2, c5).  Unpacking these as
        # (a, b, c, d, e, f) with c/f as the translation -- the other common
        # convention -- inverts the wrong matrix and yields a blank canvas.
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
        XX, YY = np.meshgrid(np.arange(x0, x1), np.arange(y0, y1))
        sxv = ia * XX + ib * YY + ie
        syv = ic * XX + id_ * YY + if_
        ok = ((sxv >= 0) & (sxv < img.width - 1)
              & (syv >= 0) & (syv < img.height - 1))
        if not ok.any():
            continue
        arr = np.array(img.convert("RGBA"))
        xi = np.clip(sxv.astype(int), 0, img.width - 1)
        yi = np.clip(syv.astype(int), 0, img.height - 1)
        vals = arr[yi, xi]
        ca = np.array(canvas)
        sub = ca[y0:y1, x0:x1]
        msk = ok & (vals[..., 3] > 0)
        sub[msk] = vals[msk]
        canvas = Image.fromarray(ca)
    if scale != 1.0:
        canvas = canvas.resize((int(canvas.width * scale),
                                int(canvas.height * scale)), Image.LANCZOS)
    return canvas


if __name__ == "__main__":
    names = sys.argv[1:] or ["Vinnie", "Gangster1", "Soldier"]
    outs = []
    for n in names:
        im = render(n)
        if im is not None:
            p = os.path.join(PROJECT, "art", f"_after_{n}.png")
            im.save(p)
            outs.append((n, im))
            print(f"{n}: {im.size} -> {p}")
    if outs:
        S = 0.55
        ims = [(n, i.resize((int(i.width * S), int(i.height * S)), Image.LANCZOS))
               for n, i in outs]
        W = sum(i.width for _, i in ims) + 20 * (len(ims) + 1)
        H = max(i.height for _, i in ims) + 50
        sheet = Image.new("RGBA", (W, H), (46, 46, 52, 255))
        from PIL import ImageDraw
        d = ImageDraw.Draw(sheet)
        x = 20
        for n, i in ims:
            sheet.alpha_composite(i, (x, 34))
            d.text((x, 12), n, fill=(240, 240, 240, 255))
            x += i.width + 20
        sheet.convert("RGB").save(os.path.join(PROJECT, "art", "_after_sheet.png"))
        print("sheet ->", os.path.join(PROJECT, "art", "_after_sheet.png"))
