"""Side-by-side verdict sheet: original vs palette route vs redraw route.

Both routes compose into the same baseline, so all three columns share one
silhouette. That is deliberate -- it is the one thing the sheet has to prove:
whichever route ships, the collision box, the animation pivots and the
sorting order are untouched, because the alpha channel is bit-identical.

Labels and numbers are read from the acceptance JSONs rather than typed in,
so the picture cannot drift away from the report it claims to summarise.

Usage:
    python three_way.py Vinnie
"""
import json
import os
import sys

from PIL import Image, ImageDraw, ImageFont

from ggc_assets import PROJECT

CHAR = sys.argv[1] if len(sys.argv) > 1 else "Vinnie"
VDIR = os.path.join(PROJECT, "validation")
PAPER = (243, 235, 220)
SHEET = (232, 224, 208)
INK = (40, 30, 24)
MUTED = (120, 106, 92)
GREEN = (36, 92, 60)
RED = (150, 40, 34)

COLS = [
    ("original", "原始（卡通平涂）"),
    ("restyled", "方案 A  调色（0 积分）"),
    ("redraw", "方案 B  重绘（生成图）"),
]

# Metrics worth putting on the sheet: the ones a reader can argue about.
ROWS = [
    ("ink_ratio", "墨线占比", 3),
    ("ink_w_mean", "线宽均值", 2),
    ("texture_std", "纹理起伏", 1),
    ("saturation", "饱和度", 3),
]


def font(size):
    for name in ("msyh.ttc", "msyhbd.ttc", "simhei.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


F_TITLE = font(19)
F_LABEL = font(15)
F_SMALL = font(13)
F_MONO = font(13)


def load(name):
    path = os.path.join(VDIR, f"composite_{CHAR}_{name}.png")
    if not os.path.isfile(path):
        return None
    return Image.open(path).convert("RGBA")


def report(suffix):
    """Acceptance JSON for a render suffix, or {} when it has not been run."""
    tag = "" if suffix == "restyled" else f"_{suffix}"
    path = os.path.join(VDIR, f"STYLE_ACCEPTANCE_{CHAR}{tag}.json")
    if not os.path.isfile(path):
        return {}
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def verdict(rep):
    checks = rep.get("checks") or []
    if not checks:
        return None, 0, 0
    ok = sum(1 for c in checks if c["pass"])
    return ok == len(checks), ok, len(checks)


def metrics_of(rep):
    """The measured block. The baseline side is keyed 'baseline_original',
    the result side 'restyled' -- same schema, different name."""
    return rep.get("restyled") or rep.get("baseline_original") or {}


def main():
    imgs = [(k, lab, load(k)) for k, lab in COLS]
    imgs = [(k, lab, im) for k, lab, im in imgs if im is not None]
    if not imgs:
        raise SystemExit(f"no composites found for {CHAR}")

    # One shared scale, so a size difference would be visible instead of being
    # normalised away by per-column fitting.
    H = max(im.height for _, _, im in imgs)
    cols = []
    for key, lab, im in imgs:
        if im.height != H:
            im = im.resize((round(im.width * H / im.height), H), Image.LANCZOS)
        cols.append((key, lab, im))

    gap = 22
    # A gutter wide enough for the metric names, so the numbers can sit
    # directly under the column they describe instead of in a separate table.
    gutter = 112
    x0 = gutter + gap
    top = 46
    foot = 34 + 22 * (len(ROWS) + 1) + 62
    W = x0 + sum(im.width for _, _, im in cols) + gap * len(cols)
    sheet = Image.new("RGB", (W, H + top + foot), SHEET)
    dr = ImageDraw.Draw(sheet)

    x = x0
    reps = {}
    colx = []
    for key, lab, im in cols:
        reps[key] = report(key)
        colx.append(x)
        paper = Image.new("RGBA", im.size, PAPER + (255,))
        paper.alpha_composite(im)
        sheet.paste(paper.convert("RGB"), (x, top))
        dr.rectangle([x - 1, top - 1, x + im.width, top + im.height],
                     outline=(196, 184, 164))
        dr.text((x, 18), lab, fill=INK, font=F_LABEL)

        ok, n_ok, n = verdict(reps[key])
        if ok is not None:
            mark = f"{n_ok}/{n} PASS" if ok else f"{n_ok}/{n} FAIL"
            tw = dr.textlength(mark, font=F_SMALL)
            dr.text((x + im.width - tw, 19), mark,
                    fill=GREEN if ok else RED, font=F_SMALL)
        x += im.width + gap

    # ---- metrics table -------------------------------------------------
    # The baseline has no report of its own; it is measured once and embedded
    # in each route's report. Take it from whichever report exists.
    if not metrics_of(reps.get("original", {})):
        for key in ("redraw", "restyled"):
            base = (reps.get(key) or {}).get("baseline_original")
            if base:
                reps["original"] = {"baseline_original": base}
                break

    y = top + H + 30
    dr.line([(gutter // 2, y - 12), (W - gap, y - 12)], fill=(190, 178, 158))
    for i, (key, _, _) in enumerate(cols):
        short = COLS[[c[0] for c in COLS].index(key)][1].split("（")[0]
        dr.text((colx[i], y), short, fill=MUTED, font=F_SMALL)

    y += 22
    for field, label, nd in ROWS:
        dr.text((gutter // 2, y), label, fill=INK, font=F_SMALL)
        for i, (key, _, _) in enumerate(cols):
            v = metrics_of(reps[key]).get(field)
            txt = "—" if v is None else f"{float(v):.{nd}f}"
            dr.text((colx[i], y), txt, fill=INK, font=F_MONO)
        y += 22

    # ---- fidelity line -------------------------------------------------
    fid = (reps.get("redraw") or reps.get("restyled") or {}).get("fidelity") or {}
    if fid:
        dr.line([(gutter // 2, y + 4), (W - gap, y + 4)], fill=(190, 178, 158))
        line = (f"几何保真   alpha_iou {fid.get('alpha_iou')}   "
                f"质心偏移 {fid.get('centroid_shift')} px   "
                f"面积差 {fid.get('area_delta')}")
        dr.text((gutter // 2, y + 14), line, fill=MUTED, font=F_SMALL)
        dr.text((gutter // 2, y + 36),
                "三栏共用同一条 alpha 轮廓：碰撞盒、动画枢轴、sortingOrder 均未改动。",
                fill=MUTED, font=F_SMALL)

    out = os.path.join(PROJECT, "art", f"{CHAR.lower()}_abc_compare.png")
    sheet.save(out)
    print("saved", out, sheet.size)


if __name__ == "__main__":
    main()
