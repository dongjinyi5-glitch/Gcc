"""Scene restyle: pigment ramps driven by luminance, after a cast removal.

Why the character restyler cannot be reused
-------------------------------------------
`restyle_ink` picks pigment from a **semantic slot** (garment -> 石青+石绿).  A
scene has no slots: run it on `Riverside_01` and the brick wall becomes a
blue-green mosaic, because the default slot is "garment" and brick is not a
garment.  Semantics were the wrong axis.

Why "nearest pigment" also fails (tried first, kept as a note)
-------------------------------------------------------------
Quantising every pixel's (a*,b*) to the nearest mineral pigment looks principled
and produces a green world.  A night level is lit by a coloured light rig, so
the *global* chroma is a cast -- every surface sits a few degrees green or
blue -- and nearest-pigment faithfully amplifies that cast into 石绿 everywhere:
the crane turned blue, the cargo hold turned green.  The cast has to be removed
before any pigment decision is made.

What works
----------
    1. **Illuminant estimate, gated by luminance.**  The cast is the colour of
       the *light*, estimated as the L*^2-weighted mean (a*,b*), and it is
       subtracted in proportion to L* -- a cast only exists where there is
       light.  (A plain median removes nothing: it is dominated by near-black
       pixels while every *visible* surface is amber.)
    2. **Two ramps, sharpened.**  A cool ramp (墨 -> 花青 -> 石青 -> 纸) and a
       warm ramp (墨 -> 赭石 -> 藤黄 -> 纸), both indexed by L*, blended by
       residual warmth *and* brightness above the frame's own median.  The
       blend is then sharpened (gain), because a linear 50/50 mix of 赭石 and
       石青 is a muddy grey -- that is why every intermediate setting looked
       like either a brown photograph or a blue one, with nothing between.
    3. **L* is never replaced.**  Only a and b come from the ramps, so the light
       map -- including the baked lamp halos -- stays exactly where it was.
       That is the hard constraint from SCENE_PLAN.md.
    4. **Green and red masks**, because a warmth axis cannot tell green from
       blue or red from brown: vegetation and the gas cylinders were coming out
       石青, and the blood in the title splash was coming out 赭石.  Both hues
       are read off the *raw* Lab (green = a* < 0 with b* > 0, red = a* far
       positive), never off the cast-corrected values -- the correction removes
       the amber b* that made them readable in the first place.
    5. Colour wash: blur (a*,b*), never L*, so pigment flattens into washes
       while every contour survives.
    6. Ink edges from an *absolute* gradient threshold on a blurred L*, then
       paper grain.

Alpha is returned bit-identical: the silhouette is the collision/mesh contract.

What it cannot do: produce brushwork.  The output is a render whose palette has
been replaced with mineral pigment -- it reads as painted at a distance and
plainly is not, close up.  See docs/RESTYLE_SCENE.md for the measured limits and
for how this splits the work with ImageGen.

Usage
-----
    python restyle_scene.py preview          # 8 representative L3 textures
    python restyle_scene.py verify           # alpha identity + L* preservation
    python restyle_scene.py palette          # which pigment each ramp stop hits
    python restyle_scene.py one Quay_05      # single texture, full size
    python restyle_scene.py level level3     # every texture the level uses
    python restyle_scene.py sweep Quay_05    # tilt x gain parameter sweep
"""
import io
import json
import os
import sys

import numpy as np
from PIL import Image, ImageFilter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ggc_assets import AssetDB, DATA, PROJECT  # noqa: E402
import restyle_ink as R  # noqa: E402   pigment definitions only

ART = os.path.join(PROJECT, "art")
OUT = os.path.join(ART, "scene_restyle")
INV = os.path.join(ART, "scene_inventory.json")

# The six chromatic pigments plus 墨/纸.  Same sRGB values as the character
# pipeline (restyle_ink.PIGMENTS) so the two passes cannot drift apart.
CHROMATIC = ["朱红", "石青", "石绿", "赭石", "藤黄", "花青"]
NEUTRAL = {"墨": R.PIGMENTS["墨"][0], "纸": R.PIGMENTS["纸"][0]}

# representative L3 textures: skyline, crane, quay, steel plate, hold, radio
# room, engine room, upper deck -- one per material family
PREVIEW = ["HarbourParallax1_03", "Crane-small_01", "Quay_05", "Romp02",
           "BoatRuim3", "Boat010b", "Boat008a", "Wheelhouse_01"]


# ------------------------------------------------------------------- colour
def srgb_to_lab(rgb):
    """rgb float 0..1 (...,3) -> L* (0..100), a*, b* (D65)."""
    m = np.array([[0.4124564, 0.3575761, 0.1804375],
                  [0.2126729, 0.7151522, 0.0721750],
                  [0.0193339, 0.1191920, 0.9503041]], np.float32)
    lin = np.where(rgb <= 0.04045, rgb / 12.92, ((rgb + 0.055) / 1.055) ** 2.4)
    xyz = lin @ m.T
    xyz = xyz / np.array([0.95047, 1.0, 1.08883], np.float32)
    d = 6.0 / 29.0
    f = np.where(xyz > d ** 3, np.cbrt(xyz), xyz / (3 * d * d) + 4.0 / 29.0)
    L = 116.0 * f[..., 1] - 16.0
    a = 500.0 * (f[..., 0] - f[..., 1])
    b = 200.0 * (f[..., 1] - f[..., 2])
    return L, a, b


def lab_to_srgb(L, a, b):
    fy = (L + 16.0) / 116.0
    fx = fy + a / 500.0
    fz = fy - b / 200.0
    d = 6.0 / 29.0
    f = np.stack([fx, fy, fz], -1)
    xyz = np.where(f > d, f ** 3, 3 * d * d * (f - 4.0 / 29.0))
    xyz = xyz * np.array([0.95047, 1.0, 1.08883], np.float32)
    m = np.array([[3.2404542, -1.5371385, -0.4985314],
                  [-0.9692660, 1.8760108, 0.0415560],
                  [0.0556434, -0.2040259, 1.0572252]], np.float32)
    lin = xyz @ m.T
    lin = np.clip(lin, 0.0, 1.0)
    out = np.where(lin <= 0.0031308, lin * 12.92,
                   1.055 * np.power(lin, 1 / 2.4) - 0.055)
    return np.clip(out, 0.0, 1.0)


def pigment_ab():
    """(names, a*, b*) of the chromatic pigments, plus 墨/纸 for the neutrals."""
    names, ab = [], []
    for n in CHROMATIC:
        c = np.array(R.PIGMENTS[n][0], np.float32) / 255.0
        L, a, b = srgb_to_lab(c.reshape(1, 1, 3))
        names.append(n)
        ab.append((float(a[0, 0]), float(b[0, 0])))
    for n, c in NEUTRAL.items():
        c = np.array(c, np.float32) / 255.0
        L, a, b = srgb_to_lab(c.reshape(1, 1, 3))
        names.append(n)
        ab.append((float(a[0, 0]), float(b[0, 0])))
    return names, np.array(ab, np.float32)


PIG_NAMES, PIG_AB = pigment_ab()
CHROMA_IDX = [PIG_NAMES.index(n) for n in CHROMATIC]
PIG_AB_OF = {n: PIG_AB[i] for i, n in enumerate(PIG_NAMES)}

# The two ramps, written as "which pigment, at which L*" rather than as raw
# numbers -- the a*/b* values are the palette's own, so the ramps cannot drift
# away from the character pipeline.
#
# Two things about the shape:
#   * 花青 has to appear LOW (L* 12).  A night level is almost entirely L* 4..30,
#     so a ramp whose only blue sits at L* 55 leaves every shadow pixel neutral
#     and the frame comes out brown no matter how the blend is tuned.
#   * pigment chroma must not taper toward black.  An earlier version
#     interpolated a* and b* toward 墨 as L* fell, on the assumption that dark
#     = desaturated.  That is true of a photograph, not of a pigment: 花青 at
#     L* 12 is as blue as 石青 at L* 46.  The taper was why every output looked
#     like a washed-out colour grade (mean chroma 3-9) instead of 重彩.
COOL_STOPS = [("墨", 0), ("花青", 12), ("石青", 46), ("石青", 70), ("纸", 100)]
WARM_STOPS = [("墨", 0), ("赭石", 16), ("赭石", 40), ("藤黄", 62),
              ("纸", 88), ("纸", 100)]
# Two more ramps, for the two hues the cool/warm axis cannot reach.  Without
# them the whole game has a defect that is visible in the panoramas: vegetation
# turns 石青 blue (L9's riverbank, L5's treeline) and the blood in the title
# splash turns 赭石 brown.  Both are recoverable because the *source* is
# unambiguously green or red -- Lab gives that away for free (green = a* < 0
# with b* > 0, red = a* strongly positive), so no semantic guess is involved.
GREEN_STOPS = [("墨", 0), ("石绿", 18), ("石绿", 52), ("纸", 100)]
RED_STOPS = [("墨", 0), ("朱红", 26), ("朱红", 62), ("纸", 100)]


def _ramp_lut(stops):
    ls = np.array([p[1] for p in stops], np.float32)
    aa = np.array([PIG_AB_OF[p[0]][0] for p in stops], np.float32)
    bb = np.array([PIG_AB_OF[p[0]][1] for p in stops], np.float32)
    x = np.arange(101, dtype=np.float32)
    return (np.interp(x, ls, aa).astype(np.float32),
            np.interp(x, ls, bb).astype(np.float32))


COOL_A, COOL_B = _ramp_lut(COOL_STOPS)
WARM_A, WARM_B = _ramp_lut(WARM_STOPS)
GREEN_A, GREEN_B = _ramp_lut(GREEN_STOPS)
RED_A, RED_B = _ramp_lut(RED_STOPS)


# ------------------------------------------------------------------ helpers
def blur_f(img, radius):
    """Gaussian blur on a float 2-D array via PIL (no scipy in this env).

    Only safe when the input range is wide (L* is 0..100).  PIL has no
    float-mode blur, so the array is quantised to uint8 on the way in --
    that is 0.4 L* per step, invisible.  For a* / b*, whose useful range is
    +-60, the same trick costs 0.5 per step and also *clips* to the array's
    own min/max, so use `box_blur` there instead.
    """
    lo, hi = float(img.min()), float(img.max())
    if hi - lo < 1e-6:
        return img.copy()
    u8 = ((img - lo) / (hi - lo) * 255.0).astype(np.uint8)
    b = Image.fromarray(u8).filter(ImageFilter.GaussianBlur(radius))
    return np.asarray(b, np.float32) / 255.0 * (hi - lo) + lo


def _box1d(a, k, axis):
    n = a.shape[axis]
    pad = [(0, 0), (0, 0)]
    pad[axis] = (k // 2, k // 2)
    c = np.cumsum(np.pad(a.astype(np.float64), pad, mode="reflect"), axis=axis)
    z = list(c.shape)
    z[axis] = 1
    c = np.concatenate([np.zeros(z, np.float64), c], axis=axis)
    hi = [slice(None), slice(None)]
    hi[axis] = slice(k, k + n)
    lo = [slice(None), slice(None)]
    lo[axis] = slice(0, n)
    return ((c[tuple(hi)] - c[tuple(lo)]) / k).astype(np.float32)


def box_blur(a, radius, passes=3):
    """Exact 3-pass box blur -- a good Gaussian, no quantisation, no clipping.

    Needed for the local white balance: subtracting a blurred (a*,b*) field is
    the whole point, so a 0.5-per-step error in that field becomes a 0.5
    colour error in the output.
    """
    k = max(1, int(round(radius))) * 2 + 1
    if k < 3:
        return a.astype(np.float32)
    out = a.astype(np.float32)
    for _ in range(passes):
        out = _box1d(_box1d(out, k, 0), k, 1)
    return out


def gradient_mag(L, norm="p995"):
    """Gradient magnitude of a 2-D array.

    norm="p995"  normalise so the 99.5th percentile maps to 1 -- use this when
                 the caller wants a *relative* edge map (the character
                 pipeline does).
    norm=None    return raw L*-per-pixel units, so the caller can apply a
                 physical threshold instead.
    """
    gx = np.zeros_like(L)
    gy = np.zeros_like(L)
    gx[:, 1:-1] = (L[:, 2:] - L[:, :-2]) * 0.5
    gy[1:-1, :] = (L[2:, :] - L[:-2, :]) * 0.5
    g = np.sqrt(gx * gx + gy * gy)
    if norm is None:
        return g
    p = np.percentile(g, 99.5) if g.size else 1.0
    return np.clip(g / max(p, 1e-6), 0.0, 1.0)


# ------------------------------------------------------------------- restyle
def restyle_scene(img, chroma=0.85, cool=1.0, warm=1.0, green=1.0, red=1.0,
                  cast=0.85, tilt=0.30, gain=2.2, wash=2.5, ink=0.55,
                  ink_g=4.5, ink_width=1.2, paper=0.70, tone=0.15, seed=0):
    """One scene texture -> 重彩.  Alpha is returned bit-identical.

    chroma  how far (a*,b*) is pulled from the cast-corrected original onto the
            blended ramp; 0 keeps the original colour, 1 is pure ramp
    cool    multiplier on the cool ramp (花青/石青 side)
    warm    multiplier on the warm ramp (赭石/藤黄 side)
    green   0 disables the 石绿 branch (vegetation, anything genuinely green)
    red     0 disables the 朱红 branch (blood, red paint)
    cast    how much of the illuminant estimate to subtract; 0 disables the
            white balance, 1 fully neutralises the light rig's tint
    tilt    how strongly darkness pushes a pixel toward the cool ramp.  This is
            the single most important parameter: see the note below.
    gain    contrast of the cool/warm decision; 1 is a linear blend (muddy),
            2-3 gives flat pigment areas with a soft seam
    wash    radius, in pixels, of the (a*,b*) smoothing that turns colour into
            washes; L* is not touched, so edges survive
    ink     edge darkening strength
    ink_g   gradient magnitude, in L* per pixel, that counts as a full ink line
    ink_width  blur radius before the gradient -- this is the brush width
    paper   grain amplitude
    tone    shadow-floor lift; 0 keeps the original L*, 1 is a strong lift

    Why `tilt` exists
    -----------------
    Selecting the ramp from residual b* alone floods the frame with 赭石: a
    night level is mostly warm-lit, so after the cast removal most pixels are
    still slightly warm and every one of them picks the warm ramp.  The result
    is a sepia photograph, not 重彩.  But 工笔重彩 has an actual convention for
    this -- 以墨为骨，暗部用花青，受光处敷赭石藤黄 -- so darkness, not just
    chroma, is allowed to choose the ramp.  That single term is what puts 石青
    into the shadows and keeps 藤黄 on the lamps.

    The one invariant: L* is never *replaced*, only lifted and inked, so the
    baked light map -- lamp halos, window glow, the fire in level8 -- stays
    exactly where it was.  That is the hard constraint from SCENE_PLAN.md.
    """
    arr = np.asarray(img.convert("RGBA"), np.float32) / 255.0
    alpha = arr[..., 3].copy()

    L, A, B = srgb_to_lab(arr[..., :3])
    opaque = alpha > 0.5

    # 1. white balance.  The cast estimator has to be an *illuminant* estimate,
    #    not a median: a night level is mostly near-black pixels, so the median
    #    chroma is ~neutral while every *visible* surface is amber.  Subtracting
    #    the median therefore removes nothing and the frame stays sepia.
    #    Weighting by L*^2 picks up the colour of the light itself, and what
    #    survives the subtraction is genuine relative warmth -- brick vs steel
    #    vs lamp glow.
    if opaque.any():
        wgt = (L / 100.0) ** 2 * opaque
        tot = float(wgt.sum())
        if tot > 1e-6:
            ill_a = float((A * wgt).sum() / tot)
            ill_b = float((B * wgt).sum() / tot)
        else:
            ill_a = ill_b = 0.0
    else:
        ill_a = ill_b = 0.0
    # 1b. the correction must scale with luminance.  A flat subtraction takes
    #     the *bright* surfaces' amber (b* ~ +13) off the *dark* pixels too,
    #     which have almost no chroma to begin with, and drives them to b* -9:
    #     that is what turned the shadows pure 石青 on the first attempt.  A
    #     cast only exists where there is light, so gate it by L*.
    lit = np.clip(L / 42.0, 0.0, 1.0)
    Ar = A - cast * ill_a * lit
    Br = B - cast * ill_b * lit

    # 2. two cues pick the ramp: residual warmth (material) and brightness
    #    (the 暗部用花青 convention).  18 is roughly the b* distance between
    #    赭石 and 花青, so +-18 spans the range without saturating.
    #
    #    The brightness pivot is the *frame's own* median L*, not a constant.
    #    A night texture has a median L* of 4-13, so pivoting on a fixed 42
    #    puts every pixel below the pivot and the whole picture goes cool --
    #    which is exactly what happened with a fixed 42.  Pivoting on the
    #    median makes the rule "brighter than this frame is lit, darker is in
    #    shadow", which is the statement we actually want.
    lmid = float(np.median(L[opaque])) if opaque.any() else 40.0
    w = 0.5 + Br / 18.0 + tilt * (L - lmid) / 40.0

    # 2b. sharpen the blend.  A linear 50/50 mix of 赭石 and 石青 is a muddy
    #     grey -- which is why every intermediate setting looked like either
    #     "brown photograph" or "blue photograph" with nothing in between.
    #     重彩 is flat pigment areas meeting at a soft edge, so push w toward
    #     its extremes and keep only a narrow transition band.
    w = np.clip((w - 0.5) * gain + 0.5, 0.0, 1.0)

    # 3. ramp chroma indexed by L*.  L* itself is untouched here.
    li = np.clip(L, 0.0, 100.0).astype(np.int32)
    ta = COOL_A[li] * cool * (1.0 - w) + WARM_A[li] * warm * w
    tb = COOL_B[li] * cool * (1.0 - w) + WARM_B[li] * warm * w

    # 3c. green and red branches.  The cool/warm axis is a *warmth* axis, so it
    #     cannot tell green from blue or red from brown -- vegetation came out
    #     石青 and the title splash's blood came out 赭石.  Both hues are
    #     readable straight off Lab: green is a* < 0 with b* > 0, red is a* far
    #     positive.
    #
    #     These masks use the *raw* A/B, not the cast-corrected Ar/Br.  The
    #     correction subtracts the amber light (b* -12), which is exactly the
    #     b* that makes a green read as green: on the first attempt the gas
    #     cylinders' b* fell from +13 to +3 and the mask went to 0.03, so they
    #     came out pale mint instead of 石绿.  Cast removal exists to normalise
    #     *warmth* for the cool/warm choice; hue identity is not its job.
    if green > 0:
        # The luminance taper matters: a mercury-vapour lamp is a *green light*,
        # and without it the lamp head and its pool were painted 石绿 -- which
        # is why the quay's lamp turned emerald next to its warm neighbours.
        # Above L* 70 the pigment is 纸/藤黄 territory anyway.
        g0 = green * (np.clip((-A - 3.0) / 8.0, 0.0, 1.0)
                      * np.clip((B - 3.0) / 8.0, 0.0, 1.0)
                      * np.clip((70.0 - L) / 25.0, 0.0, 1.0))
        ta = ta * (1.0 - g0) + GREEN_A[li] * g0
        tb = tb * (1.0 - g0) + GREEN_B[li] * g0
    if red > 0:
        r0 = red * (np.clip((A - 13.0) / 18.0, 0.0, 1.0)
                    * np.clip((B - 7.0) / 14.0, 0.0, 1.0))
        ta = ta * (1.0 - r0) + RED_A[li] * r0
        tb = tb * (1.0 - r0) + RED_B[li] * r0

    # 3a. gamut gate.  A dark saturated pigment is not representable in sRGB:
    #     L* 4 with b* -22 has a negative blue channel, lab_to_srgb clips it,
    #     and the round trip comes back *lighter*.  That was the +3.6 L* drift
    #     on the night sky -- not the tone lift.  Taper chroma below L* 11 so
    #     near-black stays 墨, which is also what 国画 does.
    ta = ta * np.clip((L - 1.0) / 10.0, 0.0, 1.0)
    tb = tb * np.clip((L - 1.0) / 10.0, 0.0, 1.0)
    A2 = Ar * (1.0 - chroma) + ta * chroma
    B2 = Br * (1.0 - chroma) + tb * chroma

    # 3b. colour wash.  Smoothing (a*,b*) while leaving L* alone flattens the
    #     colour into washes and kills the chroma noise, but every edge that
    #     lives in luminance -- and that is all of them -- survives untouched.
    #     This is what separates "paint laid inside a contour" from "a colour
    #     LUT applied to a render".
    if wash > 0:
        A2 = box_blur(A2, wash)
        B2 = box_blur(B2, wash)

    # 4. luminance: keep the structure, lift the floor off pure black
    L2 = L.copy()
    if tone > 0:
        # A narrow lift right at the bottom.  The first version used sigma 14
        # and strength 9, which reached up into the night sky (L* 3..20) and
        # turned a deep navy panorama into pale steel blue -- the level lost
        # its night.  Sigma 8 confines the lift to the true blacks.
        L2 = L2 + tone * 7.0 * np.exp(-((L2 - 1.0) / 8.0) ** 2)
    L2 = np.clip(L2, 1.5, 99.0)

    # 5. ink edges.  An *absolute* threshold in L* per pixel, not a percentile:
    #    a percentile always makes exactly 0.5% of the frame "maximally inked",
    #    so on a soft, hazy texture it silently inks nothing at all and on a
    #    crisp one it inks the whole frame.  ink_g = 6 L*/px is a real edge.
    g = gradient_mag(blur_f(L2, ink_width), norm=None)
    L2 = L2 * (1.0 - ink * np.clip(g / max(ink_g, 1e-6), 0.0, 1.0))

    # 6. paper grain -- multiply, so it is invisible in the deep shadows and
    #    reads as fibre only where there is pigment to sit on
    if paper > 0:
        rng = np.random.default_rng(seed)
        n = blur_f(rng.normal(0.0, 1.0, L.shape).astype(np.float32), 0.6)
        n /= max(float(np.std(n)), 1e-6)
        L2 = L2 * (1.0 + paper * 0.045 * n)

    out = lab_to_srgb(np.clip(L2, 0, 100), A2, B2)
    rgba = np.concatenate([out, alpha[..., None]], axis=-1)
    return Image.fromarray((np.clip(rgba, 0, 1) * 255).round().astype(np.uint8),
                           "RGBA")


# ---------------------------------------------------------------------- io
def load(db, name):
    rows = json.load(io.open(INV, encoding="utf-8"))
    for r in rows:
        if r["texture"] == name:
            obj = db.file_objs(r["file"]).get(r["path_id"])
            return db.texture_image(obj), r
    raise SystemExit(f"{name} not found")


def sheet(pairs, path, cols=4, box=420):
    """Before/after grid: top row original, bottom row restyled."""
    from PIL import ImageDraw, ImageFont
    F = ImageFont.truetype("C:/Windows/Fonts/consola.ttf", 13)
    Fh = ImageFont.truetype("C:/Windows/Fonts/msyhbd.ttc", 20)
    cw, ch = box + 10, box + 34
    rows = (len(pairs) + cols - 1) // cols
    W = cols * cw + 20
    H = 56 + rows * ch * 2 + 20
    cv = Image.new("RGB", (W, H), (24, 24, 28))
    d = ImageDraw.Draw(cv)
    d.text((12, 12), "restyle_scene — 上：原图　下：重彩化", font=Fh,
           fill=(232, 232, 238))
    for i, (name, a, b) in enumerate(pairs):
        r, c = divmod(i, cols)
        for k, im in enumerate((a, b)):
            y = 56 + (r * 2 + k) * ch
            x = 10 + c * cw
            t = im.copy()
            t.thumbnail((box, box), Image.LANCZOS)
            bg = Image.new("RGB", (t.width, t.height), (46, 46, 52))
            bg.paste(t, (0, 0), t)
            cv.paste(bg, (x + (cw - 10 - t.width) // 2, y))
            d.text((x + 2, y + t.height + 4), name if k == 0 else "", font=F,
                   fill=(150, 152, 162))
    cv.save(path, optimize=True)
    print(f"  -> {path} {cv.size}")


def main():
    os.makedirs(OUT, exist_ok=True)
    db = AssetDB(data_dir=DATA)
    cmd = sys.argv[1] if len(sys.argv) > 1 else "preview"

    if cmd == "preview":
        pairs = []
        for name in PREVIEW:
            src, _r = load(db, name)
            out = restyle_scene(src, seed=abs(hash(name)) % 9973)
            out.save(os.path.join(OUT, f"{name}_scene.png"), optimize=True)
            pairs.append((name, src, out))
        sheet(pairs, os.path.join(OUT, "_preview.png"))

    elif cmd == "one":
        name = sys.argv[2]
        src, r = load(db, name)
        out = restyle_scene(src, seed=7)
        p = os.path.join(OUT, f"{name}_scene.png")
        out.save(p, optimize=True)
        print(f"{name}: {src.size} -> {p}")

    elif cmd == "stats":
        import style_metrics as SM
        print(f"{'texture':<22}{'paper':>7}{'texstd':>8}{'sat':>7}  pigments")
        for name in PREVIEW:
            p = os.path.join(OUT, f"{name}_scene.png")
            if not os.path.isfile(p):
                continue
            m = SM.measure(p)
            pig = m.get("pigments") or {}
            top = sorted(pig.items(), key=lambda kv: -kv[1])[:3]
            print(f"{name:<22}{m.get('paper_ratio', 0):>7.3f}"
                  f"{m.get('texture_std', 0):>8.2f}{m.get('saturation', 0):>7.3f}  "
                  + " ".join(f"{k}:{v:.2f}" for k, v in top))

    elif cmd == "verify":
        # The two invariants this pass must never break, plus the numbers that
        # say whether the result is actually 重彩 and not just colour-graded.
        #   alpha  must be bit-identical: the silhouette is the collision and
        #          mesh contract.
        #   L*     must stay where it was except for the shadow lift and the
        #          ink lines.  A large dL means the light map moved, which
        #          SCENE_PLAN.md forbids.
        print(f"{'texture':<20}{'alpha=':>7}{'dL mean':>9}{'dL p99':>8}"
              f"{'ink%':>7}{'chr in':>8}{'chr out':>9}{'warm%':>7}")
        bad = 0
        for name in PREVIEW:
            src, _r = load(db, name)
            out = restyle_scene(src, seed=abs(hash(name)) % 9973)
            a = np.asarray(src.convert("RGBA"))
            b = np.asarray(out.convert("RGBA"))
            same = bool(np.array_equal(a[..., 3], b[..., 3]))
            if not same:
                bad += 1
            L1, A1, B1 = srgb_to_lab(a[..., :3].astype(np.float32) / 255.0)
            L2, A2, B2 = srgb_to_lab(b[..., :3].astype(np.float32) / 255.0)
            op = a[..., 3] > 128
            d = (L2 - L1)[op]
            inkpct = 100.0 * float((d < -8).mean())
            c1 = np.sqrt(A1 ** 2 + B1 ** 2)[op].mean()
            c2 = np.sqrt(A2 ** 2 + B2 ** 2)[op].mean()
            warm = 100.0 * float((B2[op] > 6).mean())
            print(f"{name:<20}{'ok' if same else 'DIFF':>7}{d.mean():>9.1f}"
                  f"{np.percentile(np.abs(d), 99):>8.1f}{inkpct:>7.1f}"
                  f"{c1:>8.1f}{c2:>9.1f}{warm:>7.1f}")
        print(f"\nalpha identical on {len(PREVIEW) - bad}/{len(PREVIEW)} textures")

    elif cmd == "level":
        # Restyle every texture a level uses, keyed by (file, path_id) -- never
        # by name, because 27 textures share a normalised name and a name-keyed
        # cache would silently paint the wrong one.
        #
        # `level all` walks the whole inventory once (1450 unique textures)
        # instead of once per level (2466 level-slots), so the 389 shared
        # textures are not restyled twice.  That cache is what every level's
        # panorama is then composited against.
        import time
        lv = sys.argv[2] if len(sys.argv) > 2 else "level3"
        rows = json.load(io.open(INV, encoding="utf-8"))
        sel = rows if lv == "all" else [r for r in rows if lv in r["levels"]]
        d = os.path.join(OUT, lv)
        os.makedirs(d, exist_ok=True)
        t0 = time.time()
        px = 0
        for i, r in enumerate(sel, 1):
            src = db.texture_image(db.file_objs(r["file"]).get(r["path_id"]))
            if src is None:
                print(f"  ! {r['texture']} {r['file']}#{r['path_id']} unreadable")
                continue
            out = restyle_scene(src, seed=r["path_id"] % 9973)
            out.save(os.path.join(d, f"{r['file']}__{r['path_id']}.png"),
                     optimize=True)
            px += src.width * src.height
            if i % 50 == 0 or i == len(sel):
                print(f"  {i}/{len(sel)}  {px / 1e6:.0f} Mpx  "
                      f"{time.time() - t0:.0f}s", flush=True)
        print(f"{lv}: {len(sel)} textures -> {d}")

    elif cmd == "sweep":
        name = sys.argv[2] if len(sys.argv) > 2 else "Quay_05"
        src, _r = load(db, name)
        pairs = []
        for tilt, gain in ((0.15, 1.0), (0.15, 2.2), (0.15, 3.5),
                           (0.30, 1.0), (0.30, 2.2), (0.30, 3.5),
                           (0.45, 2.2), (0.45, 3.5)):
            o = restyle_scene(src, tilt=tilt, gain=gain, seed=7)
            pairs.append((f"tilt{tilt} gain{gain}", src, o))
        sheet(pairs, os.path.join(OUT, f"_sweep_{name}.png"), cols=4, box=380)

    elif cmd == "palette":
        # Which mineral pigment is each ramp stop actually closest to?  This is
        # the sanity check that the ramps describe 国画 and not a random
        # gradient -- it prints the nearest of the seven pigments per stop.
        print(f"{'ramp':<6}{'L*':>5}   {'a*':>6}{'b*':>6}   pigment   nearest")
        for tag, stops in (("cool", COOL_STOPS), ("warm", WARM_STOPS),
                           ("green", GREEN_STOPS), ("red", RED_STOPS)):
            for pig, L in stops:
                a, b = PIG_AB_OF[pig]
                d = ((PIG_AB[:, 0] - a) ** 2 + (PIG_AB[:, 1] - b) ** 2)
                near = PIG_NAMES[int(d.argmin())]
                print(f"{tag:<6}{L:>5}   {a:>6.1f}{b:>6.1f}   {pig:<6}  {near}")


if __name__ == "__main__":
    main()
