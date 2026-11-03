"""Redraw a weapon family from one generated concept image.

Pipeline (same discipline as redraw_parts.py, different registration)
--------------------------------------------------------------------
    1. weapon_layout.py already built a 1:1 native reference composite from
       the ORIGINAL sprites at their real relative geometry.
    2. the concept comes back from the model on a padded paper-tone canvas,
       so a bbox fit is the honest first guess: match the concept's opaque
       bbox to the reference's opaque bbox with ONE uniform scale.
    3. refine that guess with a small IoU search (silhouette lock).
    4. slice every part back out of the registered concept through that
       part's own alpha mask, then bleed painted colour into the holes the
       new art does not cover.
    5. every part keeps its exact native size and alpha, so the prefab
       assembly is bit-compatible -- the silhouette never moves.

Why the registration differs from the character pass
----------------------------------------------------
redraw_parts._apply() resizes the concept to the canvas size first, which is
fine when the concept already has the subject's aspect.  Weapon concepts are
padded to 3:2 or 1:1, so resizing to a 345x125 canvas would shear the gun.
Fitting the opaque bbox instead keeps the weapon's proportions.

Usage
-----
    python redraw_weapons.py tommygun --concept <png>      # slice only
    python redraw_weapons.py tommygun --concept <png> --patch   # + byte patch
    python redraw_weapons.py --roundtrip                   # self-test, no credits
"""
import io
import json
import os
import sys

import numpy as np
from PIL import Image

from ggc_assets import PROJECT

REFS = os.path.join(PROJECT, "art", "weapon_refs")
REDRAW = os.path.join(REFS, "redraw")
os.makedirs(REDRAW, exist_ok=True)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from redraw_parts import _bleed_colors  # noqa: E402


def load_family(fam):
    with io.open(os.path.join(REFS, f"{fam}_layout.json"),
                 encoding="utf-8") as fh:
        layout = json.load(fh)
    ref = Image.open(os.path.join(REFS, f"{fam}_ref.png")).convert("RGBA")
    return layout, ref


def opaque_bbox(img, thr=16):
    a = np.array(img.convert("RGBA"))[..., 3]
    ys, xs = np.nonzero(a > thr)
    if len(xs) == 0:
        return None
    return (int(xs.min()), int(ys.min()), int(xs.max()) + 1,
            int(ys.max()) + 1)


def fit_bbox(concept, target_box):
    """Uniform-scale the concept so its opaque bbox matches target_box."""
    cb = opaque_bbox(concept)
    if cb is None:
        raise SystemExit("concept image is fully transparent")
    sx = (target_box[2] - target_box[0]) / max(1, cb[2] - cb[0])
    sy = (target_box[3] - target_box[1]) / max(1, cb[3] - cb[1])
    s = min(sx, sy)  # uniform: a non-uniform fit would distort the weapon
    nw = max(1, int(round(concept.width * s)))
    nh = max(1, int(round(concept.height * s)))
    scaled = concept.resize((nw, nh), Image.LANCZOS)
    tx = int(round((target_box[0] + target_box[2]) / 2 - nw / 2 - cb[0] * s))
    ty = int(round((target_box[1] + target_box[3]) / 2 - nh / 2 - cb[1] * s))
    fitted = Image.new("RGBA", concept.size, (0, 0, 0, 0))
    fitted.paste(scaled, (tx, ty))
    return fitted, s, (tx, ty)


def place(concept, canvas_size, s, t):
    """Paste a scaled concept onto a canvas of the reference's size."""
    W, H = canvas_size
    base = concept.convert("RGBA")
    nw = max(1, int(round(W * s)))
    nh = max(1, int(round(H * s)))
    scaled = base.resize((nw, nh), Image.LANCZOS)
    out = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    out.paste(scaled, ((W - nw) // 2 + t[0], (H - nh) // 2 + t[1]))
    return out


def register(concept, ref):
    """bbox fit + small IoU refinement. Returns (iou, s, (dx, dy))."""
    W, H = ref.size
    tgt = (np.array(ref)[..., 3] > 8)
    tb = opaque_bbox(ref)

    def iou_of(s, off):
        dx, dy = off
        m = (np.array(place(concept, (W, H), s, (dx, dy)))[..., 3] > 8)
        inter = np.logical_and(m, tgt).sum()
        if inter == 0:
            return 0.0
        return inter / np.logical_or(m, tgt).sum()

    fitted, s0, _ = fit_bbox(concept, tb)
    # s0 is expressed against the concept's own size; convert to the canvas
    # scale used by place(): place scales the concept by (nw/W) where the
    # concept was already fitted.  Simpler: search in canvas-scale units
    # around the fitted placement.
    s_canvas = fitted.width / float(W)
    best = (iou_of(s_canvas, (0, 0)), s_canvas, (0, 0))
    for ds in (-0.04, -0.02, 0.0, 0.02, 0.04):
        for dy in range(-10, 11, 4):
            for dx in range(-10, 11, 4):
                s = s_canvas * (1.0 + ds)
                v = iou_of(s, (dx, dy))
                if v > best[0]:
                    best = (v, s, (dx, dy))
    # refine
    _, s1, (dx1, dy1) = best
    for ds in (-0.01, 0.0, 0.01):
        for dy in range(dy1 - 3, dy1 + 4, 2):
            for dx in range(dx1 - 3, dx1 + 4, 2):
                s = s1 * (1.0 + ds)
                v = iou_of(s, (dx, dy))
                if v > best[0]:
                    best = (v, s, (dx, dy))
    return best


def slice_family(fam, concept_path, patch=False, bleed=160):
    layout, ref = load_family(fam)
    concept = Image.open(concept_path).convert("RGBA")
    iou, s, (dx, dy) = register(concept, ref)
    reg = place(concept, ref.size, s, (dx, dy))
    print(f"{fam}: registered iou={iou:.4f} scale={s:.4f} offset=({dx},{dy})")

    reg_arr = np.array(reg)
    outdir = os.path.join(REDRAW, fam)
    os.makedirs(outdir, exist_ok=True)
    report = []
    for p in layout["parts"]:
        x, y, w, h = p["canvas_rect"]
        mask = np.array(Image.open(os.path.join(REFS, p["mask"]))
                        .convert("L")).astype(np.float32) / 255.0
        if mask.shape != (h, w):
            raise SystemExit(f"{fam}/{p['sprite_name']}: mask {mask.shape} "
                             f"!= rect {(h, w)}")
        crop = reg_arr[y:y + h, x:x + w].copy()
        # painted colour only where the part's own alpha lives; bleed the rest
        crop[..., 3] = (crop[..., 3] * mask).astype(np.uint8)
        img = _bleed_colors(Image.fromarray(crop), iters=bleed)
        img.putalpha(Image.fromarray((mask * 255).astype(np.uint8)))
        name = f"{p['sprite_name']}.png"
        img.save(os.path.join(outdir, name))
        report.append({"part": p["sprite_name"], "png": name,
                       "canvas_rect": p["canvas_rect"],
                       "atlas_rect": p["atlas_rect"],
                       "texture_file": p["texture_file"],
                       "texture_path_id": p["texture_path_id"],
                       "texture_name": p["texture_name"],
                       "rotation": p["rotation"]})
        print(f"   {p['sprite_name']}: {w}x{h} -> redraw/{fam}/{name}")

    with io.open(os.path.join(outdir, "_jobs.json"), "w",
                 encoding="utf-8") as fh:
        json.dump({"family": fam, "iou": iou, "parts": report}, fh,
                  ensure_ascii=False, indent=1)

    # a composite of the redrawn family, for eyeballing
    comp = Image.new("RGBA", ref.size, (0, 0, 0, 0))
    for p, r in zip(layout["parts"], report):
        img = Image.open(os.path.join(outdir, r["png"]))
        comp.alpha_composite(img, tuple(p["canvas_rect"][:2]))
    comp.save(os.path.join(REDRAW, f"{fam}_redraw.png"))

    if patch:
        patch_family(fam, report)
    return report


def encode_argb32(img):
    """PIL RGBA (top-down) -> Unity ARGB32 raw block (A,R,G,B rows bottom-up)."""
    a = np.array(img.convert("RGBA"), dtype=np.uint8)
    a = a[::-1]
    argb = a[..., [3, 0, 1, 2]]
    return np.ascontiguousarray(argb).tobytes()


def patch_family(fam, report, apply=False):
    """Byte-overwrite each part's texture in place (equal length only)."""
    import UnityPy
    DATA = os.path.join(PROJECT, "backup")  # default target dir override below
    from ggc_assets import DATA as GAME_DATA
    jobs = {}
    for r in report:
        if r["rotation"]:
            print(f"   !! {r['part']} rotated sprite, skipped")
            continue
        jobs.setdefault((r["texture_file"], r["texture_path_id"]), []).append(r)
    for (fname, tex_pid), rs in jobs.items():
        path = os.path.join(GAME_DATA, fname)
        env = UnityPy.load(path)
        objs = {o.path_id: o for o in env.objects}
        obj = objs.get(tex_pid)
        if obj is None:
            print(f"   !! {fname}#{tex_pid} missing")
            continue
        data = obj.read()
        fmt = int(data.m_TextureFormat)
        w, h = int(data.m_Width), int(data.m_Height)
        if fmt != 5:
            print(f"   !! {fname}#{tex_pid} format {fmt}, not ARGB32")
            continue
        full = data.image.convert("RGBA")
        raw_old = encode_argb32(full)
        if len(raw_old) != w * h * 4:
            print(f"   !! {fname}#{tex_pid} size mismatch")
            continue
        obj_bytes = obj.get_raw_data()
        rel = len(obj_bytes) - len(raw_old)
        if obj_bytes[rel:] != raw_old:
            idx = obj_bytes.find(raw_old[:256])
            if idx < 0:
                print(f"   !! {fname}#{tex_pid} pixel block not located")
                continue
            rel = idx
        new_full = full.copy()
        for r in rs:
            img = Image.open(os.path.join(REDRAW, fam, r["png"]))
            x, y, aw, ah = r["atlas_rect"]
            if (img.width, img.height) != (aw, ah):
                img = img.resize((aw, ah), Image.LANCZOS)
            new_full.paste(img, (x, h - y - ah))
        raw_new = encode_argb32(new_full)
        if len(raw_new) != len(raw_old):
            print(f"   !! {fname}#{tex_pid} length changed, skipped")
            continue
        if apply:
            with open(path, "r+b") as fh:
                fh.seek(int(obj.byte_start) + rel)
                fh.write(raw_new)
            print(f"   {fname}#{tex_pid} ({rs[0]['texture_name']}): patched "
                  f"{len(rs)} part(s) at +{int(obj.byte_start) + rel}")
        else:
            print(f"   {fname}#{tex_pid} ({rs[0]['texture_name']}): dry-run ok "
                  f"({len(rs)} part(s), {len(raw_new)} bytes)")
    return True


def roundtrip():
    """Self-test: concept == reference, so the produced parts must be exact.

    The test runs the REAL slice arithmetic (crop -> alpha *= mask ->
    putalpha(mask)) and compares the result against the pristine sprite:

    * alpha must match bit-for-bit everywhere -- the produced alpha is the
      original alpha by construction, so any difference is a bug.
    * rgb is compared only where the part is SOLID (mask == 255) and NOT
      covered by a later part.  Two reasons:
        - parts are stacked (drum over receiver, slide over pistol), so the
          composite holds the TOP part's colour in the overlap; the under
          part's pixels there are never seen in game either.
        - the reference composite is anti-aliased, so at a part's own soft
          edge the composite colour is a blend of it and whatever is behind.
      A generated concept has neither problem: it is one painting, and the
      slice takes that painting's colour through the part's own mask.
    """
    from ggc_assets import AssetDB
    BACKUP = os.path.join(PROJECT, "backup")
    pristine = {f: os.path.join(BACKUP, f) for f in os.listdir(BACKUP)
                if f.endswith(".assets")} if os.path.isdir(BACKUP) else {}
    db = AssetDB(file_map=pristine)
    fams = [f[:-12] for f in os.listdir(REFS) if f.endswith("_layout.json")]
    ok = True
    for fam in sorted(fams):
        layout, ref = load_family(fam)
        iou, s, (dx, dy) = register(ref, ref)
        reg_arr = np.array(place(ref, ref.size, s, (dx, dy)))
        parts = layout["parts"]
        worst_a = worst_rgb = 0
        solid_px = 0
        for i, p in enumerate(parts):
            x, y, w, h = p["canvas_rect"]
            mask = np.array(Image.open(os.path.join(REFS, p["mask"]))
                            .convert("L")).astype(np.float32) / 255.0
            # exactly what slice_family() does
            crop = reg_arr[y:y + h, x:x + w].copy()
            crop[..., 3] = (crop[..., 3] * mask).astype(np.uint8)
            crop[..., 3] = (mask * 255).astype(np.uint8)

            so = db.file_objs(p["sprite_file"]).get(p["sprite_path_id"])
            orig = np.array(db.sprite_meta(so)["image"].convert("RGBA"))
            if orig.shape[:2] != (h, w):
                raise SystemExit(f"{fam}/{p['sprite_name']}: orig "
                                 f"{orig.shape} != rect {(h, w)}")
            worst_a = max(worst_a, int(np.abs(
                crop[..., 3].astype(int) - orig[..., 3].astype(int)).max()))

            # solid, and not hidden by anything painted later
            sel = (mask >= 1.0)
            for q in parts[i + 1:]:
                qx, qy, qw, qh = q["canvas_rect"]
                qm = np.array(Image.open(os.path.join(REFS, q["mask"]))
                              .convert("L")) > 0
                ox0, oy0 = max(x, qx), max(y, qy)
                ox1, oy1 = min(x + w, qx + qw), min(y + h, qy + qh)
                if ox1 <= ox0 or oy1 <= oy0:
                    continue
                sel[oy0 - y:oy1 - y, ox0 - x:ox1 - x] &= ~qm[
                    oy0 - qy:oy1 - qy, ox0 - qx:ox1 - qx]
            solid_px += int(sel.sum())
            if sel.any():
                d = np.abs(crop[..., :3].astype(int)[sel]
                           - orig[..., :3].astype(int)[sel]).max()
                worst_rgb = max(worst_rgb, int(d))
        good = worst_a == 0 and worst_rgb == 0 and solid_px > 0
        ok = ok and good
        print(f"{'OK  ' if good else 'FAIL'} {fam}: iou={iou:.4f} "
              f"solid_px={solid_px} alpha_diff={worst_a} rgb_diff={worst_rgb}")
    print("round-trip:", "PASS" if ok else "FAIL")
    return ok


def main():
    args = sys.argv[1:]
    if "--roundtrip" in args:
        roundtrip()
        return
    fam = next((a for a in args if not a.startswith("--")), None)
    if fam is None:
        raise SystemExit(__doc__)
    concept = args[args.index("--concept") + 1] if "--concept" in args else None
    if not concept:
        raise SystemExit("need --concept <png>")
    slice_family(fam, concept, patch="--patch" in args)


if __name__ == "__main__":
    main()
