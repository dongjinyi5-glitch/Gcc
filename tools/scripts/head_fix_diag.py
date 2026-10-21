"""Diagnose what the head sprite wastes on headwear the Hat sprite already draws.

The concept drew helmet + camo net INSIDE the head sprite, and the transplanted
steel helmet (Hat, order 17) paints on top of the head (order 16). So the head
sprite's own helmet is invisible where the transplant covers it, but the netting
that hangs below the transplant's brim is still visible and eats the forehead.

This prints the overlap so the fix is measured, not guessed:
  hat_cov  - head-sprite pixels the Hat sprite already paints over
  net      - head-sprite pixels that read as camo netting
"""
import io
import json
import os
import sys

import numpy as np
from PIL import Image

BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "art")


def load(base):
    with io.open(os.path.join(base, "placement.json"), encoding="utf-8") as fh:
        man = json.load(fh)
    parts = {p["slot"]: p for p in man["parts"] if p.get("slot")}
    head = Image.open(os.path.join(base, "redraw", parts["Head"]["file"])).convert("RGBA")
    hat = Image.open(os.path.join(base, "redraw", parts["Hat"]["file"])).convert("RGBA")
    return parts, head, hat


def map_mask(shape, src_img, src_rect, dst_rect):
    """Sample src alpha into dst-pixel space. Both rects are [x,y,w,h] concept."""
    dh, dw = shape
    sx, sy, sw, sh = src_rect
    dx, dy, dw_, dh_ = dst_rect
    hx = np.arange(dw)[None, :]
    hy = np.arange(dh)[:, None]
    # dst pixel -> concept
    cx = dx + hx * (dw_ / float(dw))
    cy = dy + hy * (dh_ / float(dh))
    # concept -> src pixel
    tx = (cx - sx) * (src_img.width / float(sw))
    ty = (cy - sy) * (src_img.height / float(sh))
    txi = np.clip(np.round(tx), 0, src_img.width - 1).astype(np.intp)
    tyi = np.clip(np.round(ty), 0, src_img.height - 1).astype(np.intp)
    return np.array(src_img)[..., 3][tyi, txi] > 8


def net_mask(a):
    """Camo netting reads olive: green at least as strong as red, mid-dark."""
    r, g, b = a[..., 0].astype(np.int16), a[..., 1].astype(np.int16), a[..., 2].astype(np.int16)
    op = a[..., 3] > 127
    olive = (g >= r - 6) & (g > b + 8) & (r > 40) & (r < 210)
    return op & olive


def main():
    char = sys.argv[1] if len(sys.argv) > 1 else "Gangster1"
    base = os.path.join(BASE, char.lower() + "_parts")
    parts, head, hat = load(base)
    hr = parts["Head"]["canvas_rect"]
    tr = parts["Hat"]["canvas_rect"]
    a = np.array(head)
    cov = map_mask(a.shape[:2], hat, tr, hr)
    net = net_mask(a)
    below = net & ~cov                      # netting the transplant does NOT cover
    print(f"head {head.size} hat {hat.size}")
    print(f"hat covers {cov.sum():5d} px of the head sprite")
    print(f"net-like  {net.sum():5d} px, of which {below.sum():5d} stick out below the brim")

    # where does the sticking-out netting sit?
    if below.any():
        ys, xs = np.nonzero(below)
        print(f"stray net bbox x {xs.min()}-{xs.max()}  y {ys.min()}-{ys.max()} "
              f"(head is {head.width}x{head.height})")
        rows = np.nonzero(below.any(axis=1))[0]
        print("rows with stray net:", rows.min(), "-", rows.max())

    # visual: original | hat_cov in blue | stray net in red
    vis = np.array(head.convert("RGB")).copy()
    tint = np.zeros(vis.shape, dtype=np.uint8)
    tint[cov] = (40, 90, 220)
    tint[below] = (230, 40, 40)
    out = np.where((tint.sum(axis=2, keepdims=True) > 0),
                   (vis.astype(np.int16) * 0.35 + tint).astype(np.uint8), vis)
    Image.fromarray(out).resize((head.width * 4, head.height * 4), Image.NEAREST) \
        .save(os.path.join(BASE, "_head_fix_diag.png"))
    print("wrote art/_head_fix_diag.png  (blue = hat already covers, red = stray net)")


if __name__ == "__main__":
    main()
