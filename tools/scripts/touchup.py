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

Run automatically at the end of slice_concept, so a re-slice cannot lose it.

    art/<char>_parts/touchup.json
    {
      "hide": ["02_HoseFlamethrower*"],
      "net": [{"file": "60_HandBack*.png", "cell": 6, "seed": 7}],
      "transplant": [{"from": "ZombieSoldier", "slot": "hat"}]
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


def apply_net(img, cell=6, seed=0):
    """Keep the alpha, replace the pixels with netting."""
    a = np.array(img.convert("RGBA"))
    h, w = a.shape[:2]
    net = camo_net(w, h, cell=cell, seed=seed)
    # the outline stays ink, so the part still reads as a drawn shape
    lum = (0.2126 * a[..., 0] + 0.7152 * a[..., 1] + 0.0722 * a[..., 2])
    edge = (lum < 60) & (a[..., 3] > 8)
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
            netted = apply_net(img, cell=spec.get("cell", 6),
                               seed=spec.get("seed", 0))
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
    return done


if __name__ == "__main__":
    import sys
    char = sys.argv[1] if len(sys.argv) > 1 else "Vinnie"
    n = run(char)
    print(f"touchup {char}: {n} file(s)")
