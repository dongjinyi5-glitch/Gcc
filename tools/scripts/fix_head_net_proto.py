"""Prototype: strip the camo net off Gangster1's forehead.

The concept drew helmet + net inside the head sprite. The transplanted steel
helmet (Hat, order 17) covers the dome, but the net that hangs below its brim
still eats the forehead, which is what makes the face read as "cut off".

The original head sprite has the identical alpha silhouette, so its skin mask
is the ground truth for where skin belongs: net over skin = original says
skin, redraw says dark. The helmet brim shadow and the black left edge stay
dark in the original too, so they are left alone; only the ear is carved out,
because the redraw shadows it hard.

A plain diffusion fills the hole but averages the brush strokes away, so the
healed patch is re-textured with the face's own high-frequency detail and then
colour-matched to the cheek -- a forehead that continues the painting instead
of a smooth sticker.
"""
import io
import json
import os

import numpy as np
from PIL import Image

BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "art",
                    "gangster1_parts")
GMIN = 112          # redraw skin is ~138 gray, net is ~78


def hat_cov(head, hat, hr, tr):
    dh, dw = head.height, head.width
    sx, sy, sw, sh = tr
    dx, dy, dw_, dh_ = hr
    hx = np.arange(dw)[None, :]
    hy = np.arange(dh)[:, None]
    cx = dx + hx * (dw_ / float(dw))
    cy = dy + hy * (dh_ / float(dh))
    tx = np.clip(np.round((cx - sx) * (hat.width / float(sw))), 0, hat.width - 1).astype(np.intp)
    ty = np.clip(np.round((cy - sy) * (hat.height / float(sh))), 0, hat.height - 1).astype(np.intp)
    return np.array(hat)[..., 3][ty, tx] > 8


def skin_mask(a):
    R, G, B = a[..., 0], a[..., 1], a[..., 2]
    return (a[..., 3] > 127) & (R > 150) & (R - B > 55) & (R - G > 25)


def blur(a, k):
    if k <= 1:
        return a.astype(np.float32)
    p = np.pad(a.astype(np.float32), ((k // 2, k // 2), (k // 2, k // 2), (0, 0)), mode="reflect")
    c = np.cumsum(np.cumsum(p, 0), 1)
    c = np.pad(c, ((1, 0), (1, 0), (0, 0)))
    return (c[k:, k:] - c[:-k, k:] - c[k:, :-k] + c[:-k, :-k]) / float(k * k)


def diffuse(rgb, fix, seed, iters=500):
    """Fill `fix` pixels from `seed` pixels, averaging known neighbours."""
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


def main():
    with io.open(os.path.join(BASE, "placement.json"), encoding="utf-8") as fh:
        man = json.load(fh)
    parts = {p["slot"]: p for p in man["parts"] if p.get("slot")}
    head = Image.open(os.path.join(BASE, "redraw", parts["Head"]["file"])).convert("RGBA")
    hat = Image.open(os.path.join(BASE, "redraw", parts["Hat"]["file"])).convert("RGBA")
    orig = Image.open(os.path.join(BASE, "original", parts["Head"]["file"])).convert("RGBA")
    a = np.array(head).astype(np.float32)
    rgb, al = a[..., :3], a[..., 3]
    h, w = al.shape
    xs = np.arange(w)[None, :]
    ys = np.arange(h)[:, None]

    cov = hat_cov(head, hat, parts["Head"]["canvas_rect"], parts["Hat"]["canvas_rect"])
    op = al > 127
    gray = rgb.mean(axis=2)
    orig_skin = skin_mask(np.array(orig).astype(np.float32))
    ear = (xs >= 4) & (xs <= 33) & (ys >= 44) & (ys <= 82)

    fix = orig_skin & ~cov & (gray < GMIN) & ~ear & op
    seed = op & (gray >= 118) & ~fix
    print(f"fix {int(fix.sum())} px, seed {int(seed.sum())} px")

    base = diffuse(rgb, fix, seed)

    # the face's own brush detail, lifted from the cheek below the hole and
    # re-centred over it, so the patch keeps the painting's tooth
    src = np.zeros((h, w), bool)
    src[66:100, 42:102] = True
    src &= op
    detail = rgb - blur(rgb, 11)
    tgt_mean = rgb[src].mean(axis=0) * 0.94

    fy, fx_ = np.nonzero(fix)
    cy0, cx0 = int(fy.mean()), int(fx_.mean())
    sy0, sx0 = 66 + (100 - 66) // 2, 42 + (102 - 42) // 2
    dy, dx = cy0 - sy0, cx0 - sx0
    det = np.roll(detail, (dy, dx), axis=(0, 1))

    healed = base + 0.9 * det
    # colour-match the healed patch to the cheek (mean and spread)
    fx = fix
    cur = healed[fx]
    for c in range(3):
        mu, sd = cur[:, c].mean(), cur[:, c].std()
        tmu, tsd = tgt_mean[c], rgb[src][:, c].std() * 0.8
        healed[fx, c] = (healed[fx, c] - mu) * (tsd / max(sd, 1e-3)) + tmu

    # brim shadow: the helmet darkens the top of the healed band
    t = np.clip((ys - 24) / 36.0, 0, 1)
    shade = (0.86 + 0.14 * t)[..., None]
    healed = healed * shade

    # feather the boundary so the patch does not stamp a hard edge
    wgt = blur(fix.astype(np.float32)[..., None], 5)[..., 0]
    wgt = np.clip(wgt * 1.6, 0, 1)
    out = a.copy()
    out[..., :3] = np.clip(rgb * (1 - wgt[..., None]) + healed * wgt[..., None], 0, 255)
    img = Image.fromarray(out.astype(np.uint8))
    img.save(os.path.join(BASE, "..", "_head_netfix.png"))
    img.resize((w * 5, h * 5), Image.NEAREST) \
        .save(os.path.join(BASE, "..", "_head_netfix_5x.png"))
    px = out[..., :3][fix]
    print(f"healed mean=({px[:, 0].mean():.0f},{px[:, 1].mean():.0f},{px[:, 2].mean():.0f}) "
          f"std=({px[:, 0].std():.0f},{px[:, 1].std():.0f},{px[:, 2].std():.0f})")
    print(f"cheek  mean=({rgb[src][:, 0].mean():.0f},{rgb[src][:, 1].mean():.0f},"
          f"{rgb[src][:, 2].mean():.0f}) std=({rgb[src][:, 0].std():.0f},"
          f"{rgb[src][:, 1].std():.0f},{rgb[src][:, 2].std():.0f})")
    print("wrote art/_head_netfix.png and _head_netfix_5x.png")


if __name__ == "__main__":
    main()
