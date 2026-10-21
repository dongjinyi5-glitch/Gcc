"""Post-slice art fixes, declared per character in touchup.json.

Three problems that are not the concept's fault and must not be fixed by
editing the concept:

1. A stray sprite that the game leaves switched on. HoseFlamethrower is active
   in every character's default pose while FuelTankFlamethrower is not -- a hose
   with no tank. It is one shared texture (sharedassets7#127), referenced by
   Gangster1 and Vinnie only, and both are the same archetype; since it is
   always on, it is not part of the flamethrower weapon at all, and removing it
   changes nothing but the stray tube. Declared with "hide".

2. Several hand sprites stacked a few pixels apart. The original draws them
   consistently so they merge into one hand; a redraw slices each from a
   different place, so the stack shows every set of fingers at once. Declared
   with "net": the redundant ones keep their alpha (the silhouette must not
   move) but their pixels become camo netting, the same material the helmet
   wears. The sprite nearest the magazine is left alone and stays the hand.

3. A garment the concept cannot reach. A fedora is a brim; a steel helmet is a
   dome, and no amount of redrawing inside the fedora's outline grows one.
   The game already owns a steel helmet -- ZombieSoldier's -- so transplant it
   into this character's own Hat texture, keeping that texture's pivot, PPU
   and size. Declared with "transplant".

4. The concept drew the helmet AND its camo net inside the head sprite. Once
   the transplant supplies the helmet, that copy is redundant, and the net
   hanging below the transplant's brim eats the forehead -- the face reads as
   "cut off". The original head sprite has the identical alpha silhouette, so
   its skin mask is the ground truth for where skin belongs: heal every pixel
   the original calls skin and the redraw calls dark. The brim shadow and the
   black left edge stay dark in the original too, so they are left alone.
   Declared with "denet".

Run automatically at the end of slice_concept, so a re-slice cannot lose it.

    art/<char>_parts/touchup.json
    {
      "hide": ["02_HoseFlamethrower*"],
      "net": [{"file": "60_HandBack*.png", "cell": 6, "seed": 7}],
      "transplant": [{"from": "ZombieSoldier", "slot": "hat"}],
      "denet": [{"file": "23_Head_Head.png", "hat": "30_Hat_Hat.png"}]
    }
"""
import fnmatch
import io
import json
import os

import numpy as np
from PIL import Image

# the material the helmet already wears, so netting reads as the same cloth
NET_BASE = (86, 88, 66)
NET_DARK = (34, 32, 26)
NET_LIGHT = (128, 128, 104)
NET_EDGE = (28, 25, 23)

CONFIG = "touchup.json"


def camo_net(w, h, cell=6, seed=0):
    """Hessian-style netting: a jittered grid of squares over an olive ground."""
    rng = np.random.RandomState(seed)
    nch, ncw = h // cell + 2, w // cell + 2
    # one jitter per cell, per axis, broadcast to full resolution through the
    # cell index maps -- so the grid wobbles like cloth instead of graph paper
    jx = rng.uniform(0, cell, size=(nch, ncw))
    jy = rng.uniform(0, cell, size=(nch, ncw))
    yy, xx = np.mgrid[0:h, 0:w]
    cy = np.clip(yy // cell, 0, nch - 1).astype(np.intp)
    cx = np.clip(xx // cell, 0, ncw - 1).astype(np.intp)
    gx = (xx - jx[cy, cx]) % cell
    gy = (yy - jy[cy, cx]) % cell

    out = np.zeros((h, w, 4), np.uint8)
    out[..., :3] = NET_BASE
    out[..., 3] = 255

    line = (gx < 1.2) | (gy < 1.2)
    # every few cells, swap the square's tone so the net is not uniform
    tone = (cx + cy) % 3
    out[..., :3][tone == 1] = NET_LIGHT
    out[..., :3][tone == 2] = (70, 70, 54)
    out[..., :3][line] = NET_DARK
    # a little thread noise
    noise = rng.normal(0, 6, size=(h, w, 1))
    out[..., :3] = np.clip(out[..., :3].astype(np.int16) + noise, 0, 255)
    return out


def apply_net(img, cell=6, seed=0, edge_src=None):
    """Keep the alpha, replace the pixels with netting.

    ``edge_src`` supplies the luminance the ink outline is read from. It must
    be the PRISTINE part: the net's own grid lines are dark, so reading them
    off an already-netted sprite would let the outline creep on every re-run.
    Passing the original keeps the op idempotent.
    """
    a = np.array(img.convert("RGBA"))
    h, w = a.shape[:2]
    net = camo_net(w, h, cell=cell, seed=seed)
    # the outline stays ink, so the part still reads as a drawn shape
    lum_src = a if edge_src is None else np.array(edge_src.convert("RGBA"))
    lum = (0.2126 * lum_src[..., 0] + 0.7152 * lum_src[..., 1]
           + 0.0722 * lum_src[..., 2])
    edge = (lum < 60) & (lum_src[..., 3] > 8)
    net[..., :3][edge] = NET_EDGE
    net[..., 3] = a[..., 3]
    return Image.fromarray(net)


def keeper_hole(root, keep_pattern, target_file, target_size):
    """Bool mask over the target's texture: True where the keeper shows through.

    The redundant hands in a foregrip stack paint ON TOP of the keeper, so
    netting them would bury the very hand that is meant to survive. Punch the
    netting open wherever the keeper is opaque and the result is the kept hand
    with netting draped over everything around it.

    Both parts are located through placement.json's canvas_rect, so the mapping
    survives the different canvas/texture scales the two parts were sliced at.
    """
    man_path = os.path.join(root, "placement.json")
    if not os.path.isfile(man_path):
        return None
    with io.open(man_path, encoding="utf-8") as fh:
        man = json.load(fh)
    keep_p = None
    tgt_p, best = None, -1
    for p in man["parts"]:
        f = p.get("file") or ""
        if keep_p is None and fnmatch.fnmatch(f, keep_pattern):
            keep_p = p
        if fnmatch.fnmatch(f, target_file):
            area = p["canvas_rect"][2] * p["canvas_rect"][3]
            if area > best:
                best, tgt_p = area, p
    if keep_p is None or tgt_p is None:
        return None
    keep_path = os.path.join(root, "redraw", keep_p["file"])
    if not os.path.isfile(keep_path):
        return None
    kop = np.array(Image.open(keep_path).convert("RGBA"))[..., 3] > 8
    kx, ky, kw, kh = keep_p["canvas_rect"]
    tx, ty, tw, th = tgt_p["canvas_rect"]
    tw_t, th_t = target_size
    if min(kw, kh, tw, th) <= 0 or kop.size == 0:
        return None
    # target texture -> canvas -> keeper texture, sampled at pixel centres
    ys, xs = np.mgrid[0:th_t, 0:tw_t]
    cx = tx + (xs + 0.5) * (tw / float(tw_t))
    cy = ty + (ys + 0.5) * (th / float(th_t))
    ku = (cx - kx) * (kop.shape[1] / float(kw))
    kv = (cy - ky) * (kop.shape[0] / float(kh))
    kui = np.clip(np.round(ku).astype(np.intp), 0, kop.shape[1] - 1)
    kvi = np.clip(np.round(kv).astype(np.intp), 0, kop.shape[0] - 1)
    return kop[kvi, kui]


def punch_holes(img, hole):
    """Zero the alpha where the mask is True, leaving the pixels alone."""
    if hole is None:
        return img
    a = np.array(img.convert("RGBA"))
    a[..., 3][hole] = 0
    return Image.fromarray(a)


def box_blur(a, k):
    """Separable box blur, reflect-padded. scipy is not in this venv."""
    if k <= 1:
        return a.astype(np.float32)
    p = np.pad(a.astype(np.float32), ((k // 2, k // 2), (k // 2, k // 2), (0, 0)),
               mode="reflect")
    c = np.cumsum(np.cumsum(p, 0), 1)
    c = np.pad(c, ((1, 0), (1, 0), (0, 0)))
    return (c[k:, k:] - c[:-k, k:] - c[k:, :-k] + c[:-k, :-k]) / float(k * k)


def part_rect(man, pattern):
    """The part entry whose file matches, preferring the largest canvas_rect."""
    best, area = None, -1
    for p in man["parts"]:
        f = p.get("file") or ""
        if not fnmatch.fnmatch(f, pattern):
            continue
        a = p["canvas_rect"][2] * p["canvas_rect"][3]
        if a > area:
            best, area = p, a
    return best


def map_alpha(shape, src_img, src_rect, dst_rect):
    """Sample src alpha into dst-texture space. Rects are [x,y,w,h] canvas."""
    dh, dw = shape
    sx, sy, sw, sh = src_rect
    dx, dy, dw_, dh_ = dst_rect
    hx = np.arange(dw)[None, :]
    hy = np.arange(dh)[:, None]
    cx = dx + hx * (dw_ / float(dw))
    cy = dy + hy * (dh_ / float(dh))
    tx = np.clip(np.round((cx - sx) * (src_img.width / float(sw))),
                 0, src_img.width - 1).astype(np.intp)
    ty = np.clip(np.round((cy - sy) * (src_img.height / float(sh))),
                 0, src_img.height - 1).astype(np.intp)
    return np.array(src_img)[..., 3][ty, tx] > 8


def skin_mask(arr):
    """Warm bright flesh. The original's palette is flat enough for a hard rule."""
    R, G, B = arr[..., 0], arr[..., 1], arr[..., 2]
    return (arr[..., 3] > 127) & (R > 150) & (R - B > 55) & (R - G > 25)


def diffuse(rgb, fix, seed, iters=500):
    """Fill `fix` pixels from `seed` pixels by averaging known neighbours."""
    h, w = fix.shape
    u = np.where(seed[..., None], rgb, 0.0).astype(np.float32)
    k = seed.astype(np.float32)
    for _ in range(iters):
        pu = np.pad(u, ((1, 1), (1, 1), (0, 0)), mode="edge")
        pk = np.pad(k, ((1, 1), (1, 1)), mode="edge")
        acc = np.zeros_like(u)
        wsum = np.zeros((h, w, 1), dtype=np.float32)
        for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            su = pu[1 + dy:1 + dy + h, 1 + dx:1 + dx + w]
            sk = pk[1 + dy:1 + dy + h, 1 + dx:1 + dx + w]
            acc += su * sk[..., None]
            wsum += sk[..., None]
        newu = np.where(wsum > 0, acc / np.maximum(wsum, 1e-6), u)
        u = np.where(fix[..., None], newu, u)
        k = np.maximum(k, fix.astype(np.float32))
    return u


def denet(img, orig, hat, rect, orig_rect, hat_rect, spec):
    """Heal the net the Hat sprite now covers, back to forehead skin.

    ``spec`` keys: gray_max (net/skin divider), y_max (how far down the head
    the net can hang -- the face's own dark outlines and the collar read dark
    too, and healing those would erase the eye and the uniform), ear
    [x0,y0,x1,y1] box left alone, detail [y0,y1,x0,x1] where the face's brush
    detail is lifted from, shade_top (helmet brim shadow at the top of the
    healed band).
    """
    a = np.array(img.convert("RGBA")).astype(np.float32)
    rgb, al = a[..., :3], a[..., 3]
    h, w = al.shape
    xs = np.arange(w)[None, :]
    ys = np.arange(h)[:, None]

    cov = map_alpha((h, w), hat, hat_rect, rect)
    op = al > 127
    gray = rgb.mean(axis=2)
    oskin = skin_mask(np.array(orig.convert("RGBA")).astype(np.float32))

    ex0, ey0, ex1, ey1 = spec.get("ear", [4, 44, 33, 82])
    ear = (xs >= ex0) & (xs <= ex1) & (ys >= ey0) & (ys <= ey1)
    fix = (oskin & ~cov & (gray < spec.get("gray_max", 112)) & ~ear & op
           & (ys < spec.get("y_max", 62)))
    if not fix.any():
        return img, 0
    seed = op & (gray >= 118) & ~fix

    base = diffuse(rgb, fix, seed)

    # re-texture with the face's own brush detail, re-centred over the hole
    dy0, dy1, dx0, dx1 = spec.get("detail", [66, 100, 42, 102])
    src = np.zeros((h, w), bool)
    src[dy0:dy1, dx0:dx1] = True
    src &= op
    if src.any():
        detail = rgb - box_blur(rgb, 11)
        fy, fx_ = np.nonzero(fix)
        oy, ox = (dy0 + dy1) // 2, (dx0 + dx1) // 2
        det = np.roll(detail, (int(fy.mean()) - oy, int(fx_.mean()) - ox), axis=(0, 1))
        healed = base + 0.9 * det
        # colour-match the patch to that same region, mean and spread
        tmean = rgb[src].mean(axis=0) * 0.94
        tstd = rgb[src].std(axis=0) * 0.8
        cur = healed[fix]
        for c in range(3):
            mu, sd = cur[:, c].mean(), cur[:, c].std()
            healed[fix, c] = (healed[fix, c] - mu) * (tstd[c] / max(sd, 1e-3)) + tmean[c]
    else:
        healed = base

    # brim shadow: the helmet darkens the top of the healed band
    t = np.clip((ys - 24) / 36.0, 0, 1)
    healed = healed * (spec.get("shade_top", 0.86) + (1 - spec.get("shade_top", 0.86)) * t)[..., None]

    # the healed pixels must read as skin on the next pass too, otherwise a
    # re-run finds them dark again and drifts; scale the luminance up (keeping
    # the hue) rather than clipping channels, because the test is on the mean.
    # Applied AFTER the feather blend, which can otherwise drag an edge pixel
    # back below the divider.
    fl = spec.get("floor", 118)
    # feather INSIDE the region only: a ring outside would blend dark pixels
    # back in and escape the floor, so the next pass would find them again
    wgt = np.where(fix, np.clip(box_blur(fix.astype(np.float32)[..., None], 3)[..., 0], 0, 1), 0.0)
    out = a.copy()
    fin = rgb * (1 - wgt[..., None]) + healed * wgt[..., None]
    g = fin[fix].mean(axis=1)
    scale = np.where(g < fl, fl / np.maximum(g, 1e-3), 1.0).astype(np.float32)
    fin[fix] = fin[fix] * scale[:, None]
    out[..., :3] = np.clip(fin, 0, 255)
    return Image.fromarray(out.astype(np.uint8)), int(fix.sum())


def run(char, base=None):
    """Apply the character's declared fixes. Returns the number of ops run.

    ``base`` is the character's parts root (``art/<char>_parts``); the part
    PNGs live one level down in ``redraw``, which is what route B composes from.
    """
    root = base or os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "art", char.lower() + "_parts")
    cfg_path = os.path.join(root, CONFIG)
    if not os.path.isfile(cfg_path):
        return 0
    with io.open(cfg_path, encoding="utf-8") as fh:
        cfg = json.load(fh)

    parts = os.path.join(root, "redraw")
    if not os.path.isdir(parts):
        print(f"  [touchup] no redraw folder under {root} -- nothing to fix")
        return 0

    done = 0
    for pattern in cfg.get("hide", []):
        for f in sorted(os.listdir(parts)):
            if not fnmatch.fnmatch(f, pattern):
                continue
            path = os.path.join(parts, f)
            if not os.path.isfile(path) or not f.lower().endswith(".png"):
                continue
            ref = Image.open(path)
            Image.new("RGBA", ref.size, (0, 0, 0, 0)).save(path)
            print(f"  [touchup] hid {f}")
            done += 1

    for spec in cfg.get("net", []):
        pattern = spec["file"]
        keep = spec.get("keep")
        for f in sorted(os.listdir(parts)):
            if not fnmatch.fnmatch(f, pattern):
                continue
            path = os.path.join(parts, f)
            if not os.path.isfile(path) or not f.lower().endswith(".png"):
                continue
            img = Image.open(path)
            # the ink outline is read from the pristine part, never from the
            # current file, so re-running over an already-netted sprite is a
            # no-op instead of letting the outline creep
            orig_path = os.path.join(root, "original", f)
            edge_src = Image.open(orig_path) if os.path.isfile(orig_path) else None
            netted = apply_net(img, cell=spec.get("cell", 6),
                               seed=spec.get("seed", 0), edge_src=edge_src)
            if keep:
                hole = keeper_hole(root, keep, f, img.size)
                netted = punch_holes(netted, hole)
                if hole is None:
                    print(f"  [touchup] netted {f} (no keeper hole: "
                          f"{keep} not located)")
                else:
                    print(f"  [touchup] netted {f}, {int(hole.sum())} px "
                          f"opened for {keep}")
            else:
                print(f"  [touchup] netted {f}")
            netted.save(path)
            done += 1

    for spec in cfg.get("transplant", []):
        import transplant_hat
        st = transplant_hat.transplant(
            char, src=spec.get("from", "ZombieSoldier"),
            slot=spec.get("slot", "hat"), base=root)
        if st is None:
            print(f"  [touchup] no {spec.get('slot', 'hat')} part to transplant "
                  f"into")
            continue
        print(f"  [touchup] {st['file']} <- {st['src']} "
              f"{st['scaled'][0]}x{st['scaled'][1]} at x={st['x0']} "
              f"(alpha IoU {st['alpha_iou']})")
        done += 1

    for spec in cfg.get("denet", []):
        man_path = os.path.join(root, "placement.json")
        if not os.path.isfile(man_path):
            print("  [touchup] denet needs placement.json -- skipped")
            continue
        with io.open(man_path, encoding="utf-8") as fh:
            man = json.load(fh)
        head_p = part_rect(man, spec["file"])
        hat_p = part_rect(man, spec.get("hat", "*Hat*.png"))
        if head_p is None or hat_p is None:
            print(f"  [touchup] denet: {spec['file']} or its hat not located")
            continue
        path = os.path.join(parts, head_p["file"])
        opath = os.path.join(root, "original", head_p["file"])
        if not (os.path.isfile(path) and os.path.isfile(opath)):
            print(f"  [touchup] denet: {head_p['file']} or its original missing")
            continue
        out, n = denet(Image.open(path), Image.open(opath),
                       Image.open(os.path.join(parts, hat_p["file"])),
                       head_p["canvas_rect"], head_p["canvas_rect"],
                       hat_p["canvas_rect"], spec)
        out.save(path)
        print(f"  [touchup] de-netted {head_p['file']}: {n} px healed to skin")
        done += 1
    return done


if __name__ == "__main__":
    import sys
    char = sys.argv[1] if len(sys.argv) > 1 else "Vinnie"
    n = run(char)
    print(f"touchup {char}: {n} file(s)")
