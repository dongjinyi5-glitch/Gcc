"""Give a character a real steel helmet by transplanting an in-game sprite.

The gangster-type Hat texture is a 139x76 strip shaped for a fedora, and the
first reaction was "there is no room for a helmet dome in it". That was wrong:
the fedora spends all 139 px of width on a brim, but a helmet does not need the
width. At the same 76 px of height there is plenty of room for a dome -- it just
has to be narrower. ZombieSoldier's own Hat sprite (132x89) IS a WWII steel
helmet, so instead of drawing one or generating one, scale it into the
destination sprite.

Why this beats re-pointing the SpriteRenderer: the helmet sprite's pivot sits
at 51% of its height while the fedora's sits at 38%, so a re-pointed sprite
would hang about 7 px lower and cover the eyes. Keeping the destination's own
texture, pivot and PPU means the transform never has to move, which keeps this
a pure pixel edit -- and an equal-length one.

Writes art/<char>_parts/redraw/<HatFile>.png, so it composes into route B.

Usage:
    python transplant_hat.py Gangster1 [--from ZombieSoldier]
"""
import io
import json
import os
import sys

import numpy as np
from PIL import Image

from ggc_assets import PROJECT

HATS = os.path.join(PROJECT, "art", "hats")


def transplant(char, src="ZombieSoldier", slot="hat", base=None):
    """Scale the source's headgear into this character's own Hat texture.

    Returns a stats dict, or None when the character has no such part. The
    destination file is written into the character's ``redraw`` folder, which
    is where route B composes from.
    """
    base = base or os.path.join(PROJECT, "art", char.lower() + "_parts")
    man_path = os.path.join(base, "manifest.json")
    if not os.path.isfile(man_path):
        raise SystemExit(f"no manifest for {char} -- run extract_parts.py first")
    with io.open(man_path, encoding="utf-8") as fh:
        man = json.load(fh)

    # the Hat sprite of this character, native size, from pristine backup
    hats = [p for p in man["parts"]
            if (p.get("slot") or "").lower().startswith(slot.lower())]
    if not hats:
        return None
    dst_name = hats[0]["file"]
    dst = Image.open(os.path.join(base, "original", dst_name)).convert("RGBA")
    W, H = dst.size

    src_file = f"{src}__{hats[0]['slot']}.png"
    src_path = os.path.join(HATS, src_file)
    if not os.path.isfile(src_path):
        raise SystemExit(f"{src_file} not found -- run survey_hats.py first")
    hel = Image.open(src_path).convert("RGBA")

    # scale to the destination's height so the brim lands where the fedora's did
    nw = max(1, int(round(hel.width * H / hel.height)))
    hs = hel.resize((nw, H), Image.LANCZOS)

    # centre on the fedora's own opaque centroid: that is where the player reads
    # the hat as sitting, and it is what the pivot was authored against
    a = np.array(dst)
    m = a[..., 3] > 8
    colsum = m.sum(axis=0)
    cx = float((np.arange(m.shape[1]) * colsum).sum() / max(1, colsum.sum()))
    x0 = int(round(cx - nw / 2))
    x0 = max(0, min(W - nw, x0))

    out = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    out.paste(hs, (x0, 0), hs)

    redraw = os.path.join(base, "redraw")
    os.makedirs(redraw, exist_ok=True)
    dst_path = os.path.join(redraw, dst_name)
    out.save(dst_path)

    # how much of the original silhouette this keeps, so the alpha gate is honest
    sa = np.array(dst)[..., 3] > 8
    sb = np.array(out)[..., 3] > 8
    inter = np.logical_and(sa, sb).sum()
    union = np.logical_or(sa, sb).sum()
    return {
        "file": dst_name,
        "src": src,
        "size": [W, H],
        "scaled": [nw, H],
        "x0": x0,
        "centroid": round(cx, 1),
        "alpha_iou": round(float(inter) / max(1, int(union)), 4),
        "opaque": [int(sa.sum()), int(sb.sum())],
        "path": dst_path,
    }


def main():
    args = sys.argv[1:]
    char = next((a for a in args if not a.startswith("--")), "Vinnie")
    src = args[args.index("--from") + 1] if "--from" in args else "ZombieSoldier"

    st = transplant(char, src)
    if st is None:
        raise SystemExit(f"{char} has no Hat part")
    print(f"{char}: {st['file']} {st['size'][0]}x{st['size'][1]} <- "
          f"{st['src']} scaled {st['scaled'][0]}x{st['scaled'][1]} "
          f"at x={st['x0']} (centroid {st['centroid']})")
    print(f"wrote {st['path']}")
    print(f"alpha IoU vs fedora: {st['alpha_iou']} "
          f"(kept {st['opaque'][0]} -> {st['opaque'][1]} opaque px)")


if __name__ == "__main__":
    main()
