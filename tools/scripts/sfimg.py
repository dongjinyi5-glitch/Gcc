"""SiliconFlow image client -- the replacement for the dead ImageGen route.

Why this exists
---------------
The built-in ImageGen tool is unavailable: every call fails with
``Image model [gpt-image-2.5-sunburst] route config not found``.  SiliconFlow
speaks plain OpenAI-style REST over HTTPS, so no plugin or connector is needed
-- a bearer token and this script are enough.

What it does that a generic client would not
--------------------------------------------
Scene components are not pictures, they are **sprites with a collision
contract**.  `restyle_scene` returns alpha bit-identical on purpose; the alpha
channel is the silhouette the physics boxes were built against.  A diffusion
model that returns a nicely painted 1024x1024 will happily move the outline, so
every generated image is re-masked against the original alpha before it is
allowed near the bundle (``--remask``).  Without that step the art looks right
and the game stops being playable.

Setup
-----
    1. put the token in .secrets/siliconflow.txt   (one line, nothing else)
       or export SILICONFLOW_API_KEY=...
       .secrets/ is in .gitignore; never paste the key into a tracked file.
    2. python sfimg.py --list          # which image models this key can use
    3. python sfimg.py --probe --model <id>   # one cheap image, proves the chain

Usage
-----
    python sfimg.py --list [--sub text-to-image|image-to-image]
    python sfimg.py --probe --model Kwai-Kolors/Kolors --prompt "..."
    python sfimg.py --gen jobs.json [--max 20] [--out art/gen]

Job file: a JSON list, one object per image.

    [{"name": "Quay_05",
      "model": "Kwai-Kolors/Kolors",
      "prompt": "中国重彩国画，码头红砖墙，赭石与朱红，中等粗细笔触，宣纸",
      "negative_prompt": "照片, 3D渲染, 模糊",
      "image": "art/scene_restyle/all/sharedassets4.assets__139.png",
      "alpha_key": "sharedassets4.assets__139",
      "size": "1024x1024", "seed": 1, "steps": 20, "guidance": 7.5}]

`image` triggers image-to-image when the model supports it; `alpha_key` names an
inventory entry whose alpha channel is re-applied to the result.
"""
import argparse
import base64
import io
import json
import os
import sys
import time
import urllib.error
import urllib.request

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ggc_assets import PROJECT  # noqa: E402

API = "https://api.siliconflow.cn/v1"
SECRET = os.path.join(PROJECT, ".secrets", "siliconflow.txt")
INV = os.path.join(PROJECT, "art", "scene_inventory.json")


def token():
    t = os.environ.get("SILICONFLOW_API_KEY", "").strip()
    if t:
        return t
    if os.path.isfile(SECRET):
        t = open(SECRET, encoding="utf-8").read().strip()
        if t:
            return t
    raise SystemExit(
        "没有找到密钥。把令牌写进这一行文件（只放令牌，不要引号不要空格）：\n  %s\n"
        "或者设环境变量 SILICONFLOW_API_KEY。" % SECRET)


def call(path, body=None, method="GET", timeout=180, tries=3):
    url = API + path
    data = json.dumps(body).encode() if body is not None else None
    last = None
    for i in range(tries):
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Authorization", "Bearer " + token())
        req.add_header("Accept", "application/json")
        if data:
            req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            body_txt = e.read().decode("utf-8", "replace")[:400]
            last = "HTTP %d %s" % (e.code, body_txt)
            # 429 / 5xx are worth retrying; 400 / 401 / 403 are not.
            if e.code in (429, 500, 502, 503, 504):
                time.sleep(2 ** i)
                continue
            raise SystemExit(last)
        except Exception as e:
            last = repr(e)
            time.sleep(2 ** i)
    raise SystemExit("重试 %d 次仍失败: %s" % (tries, last))


def cmd_list(args):
    q = "/models?type=image"
    if args.sub:
        q += "&sub_type=" + args.sub
    d = call(q)
    rows = d.get("data") or d.get("models") or []
    if not rows:
        print(json.dumps(d, ensure_ascii=False)[:800])
        return
    print("%d 个图像模型：\n" % len(rows))
    for m in rows:
        mid = m.get("id") or m.get("model")
        sub = m.get("sub_type") or m.get("type") or ""
        print("  %-42s %s" % (mid, sub))
    print("\n选一个做 --probe。免费额度与单价不在这个接口里，"
          "要看 https://cloud.siliconflow.cn/account/ak 的账单页。")


def b64img(path, size="1024x1024"):
    """Prepare an input image for image-to-image.

    Two things had to be fixed here after the first Edit test came back as a
    white sheet with two floating lanterns:

    * **Alpha must not flatten onto white.**  A night scene with a big
      transparent cutout becomes 90% white pixels; the model reads that white as
      *content* and paints a white picture.  Flatten onto the median colour of
      the opaque pixels instead, so the transparent area reads as "same
      material, no detail" rather than as a blank canvas.
    * **Aspect must be preserved.**  Sending 1024x624 into a 1024x1024 request
      either stretches the art or makes the model invent the missing band.
      Pad to the target ratio with the same median colour instead.
    """
    im = Image.open(path)
    im.load()
    im = im.convert("RGBA")
    px = list(im.getdata())
    opaque = [p[:3] for p in px if p[3] > 200]
    bg = tuple(sorted(c[i] for c in opaque)[len(opaque) // 2] for i in range(3)) \
        if opaque else (110, 105, 100)

    flat = Image.new("RGB", im.size, bg)
    flat.paste(im, (0, 0), im)

    tw, th = (int(v) for v in size.lower().split("x"))
    scale = min(tw / flat.width, th / flat.height)
    nw, nh = max(1, round(flat.width * scale)), max(1, round(flat.height * scale))
    flat = flat.resize((nw, nh), Image.LANCZOS)
    canvas = Image.new("RGB", (tw, th), bg)
    canvas.paste(flat, ((tw - nw) // 2, (th - nh) // 2))

    buf = io.BytesIO()
    canvas.save(buf, "PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


WM_BOX = (0.79, 0.885, 1.0, 1.0)   # 水印占右下角的比例，实测固定不动


def strip_watermark(im):
    """Paint out the "AI生成" mark every SiliconFlow image carries.

    It sits in the bottom-right at a fixed place on every model (Kolors and
    Qwen-Image alike) and is a deal-breaker for game art -- a semi-transparent
    caption baked into a texture that tiles across a wall.

    The fix is a horizontal mirror patch: take the band immediately to the left
    of the mark, flip it, and feather it in.  For painterly output this is
    invisible; for flat colour it is exact.  Cropping instead would change the
    aspect ratio, which the caller relies on.
    """
    w, h = im.size
    x0, y0, x1, y1 = (int(WM_BOX[0] * w), int(WM_BOX[1] * h),
                      int(WM_BOX[2] * w), int(WM_BOX[3] * h))
    bw, bh = x1 - x0, y1 - y0
    if bw < 4 or bh < 4 or x0 - bw < 0:
        return im
    src = im.crop((x0 - bw, y0, x0, y1)).transpose(Image.FLIP_LEFT_RIGHT)
    patch = Image.new("RGB", (bw, bh))
    patch.paste(src, (0, 0))
    # 上下左右四边都羽化，否则接缝在平涂区域会显形
    mask = Image.new("L", (bw, bh), 255)
    from PIL import ImageDraw
    d = ImageDraw.Draw(mask)
    fe = max(2, bw // 4)
    for i in range(fe):
        v = int(255 * i / fe)
        d.line([(i, 0), (i, bh)], fill=v)
        d.line([(bw - 1 - i, 0), (bw - 1 - i, bh)], fill=v)
    fv = max(2, bh // 4)
    for j in range(fv):
        v = int(255 * j / fv)
        d.line([(0, j), (bw, j)], fill=min(v, 255))
        d.line([(0, bh - 1 - j), (bw, bh - 1 - j)], fill=min(v, 255))
    out = im.copy()
    out.paste(patch, (x0, y0), mask)
    return out


def load_alpha(key):
    """Original alpha for a component, read from the pristine backup."""
    from ggc_assets import AssetDB, baseline_map
    rows = json.load(open(INV, encoding="utf-8"))
    for r in rows:
        if "%s__%d" % (r["file"], r["path_id"]) == key:
            db = AssetDB(file_map=baseline_map())
            obj = db.file_objs(r["file"]).get(r["path_id"])
            return db.texture_image(obj)
    raise SystemExit("alpha_key 不在清单里: " + key)


def generate(job, outdir):
    body = {
        "model": job["model"],
        "prompt": job["prompt"],
        "image_size": job.get("size", "1024x1024"),
        "batch_size": 1,
        "num_inference_steps": job.get("steps", 20),
        "guidance_scale": job.get("guidance", 7.5),
    }
    if job.get("negative_prompt"):
        body["negative_prompt"] = job["negative_prompt"]
    if job.get("seed") is not None:
        body["seed"] = job["seed"]
    if job.get("image"):
        body["image"] = b64img(job["image"], body["image_size"])

    t0 = time.time()
    d = call("/images/generations", body, method="POST")
    imgs = d.get("images") or []
    if not imgs:
        raise SystemExit("返回里没有 images: " + json.dumps(d, ensure_ascii=False)[:400])

    url = imgs[0]["url"] if isinstance(imgs[0], dict) else imgs[0]
    # Signed URLs expire in about an hour -- save immediately, never link.
    raw = urllib.request.urlopen(url, timeout=120).read()
    im = Image.open(io.BytesIO(raw)).convert("RGB")
    if not job.get("keep_watermark"):
        im = strip_watermark(im)

    stem = "%s_%s" % (job["name"], job.get("seed", d.get("seed", 0)))
    os.makedirs(outdir, exist_ok=True)
    plain = os.path.join(outdir, stem + ".png")
    im.save(plain)

    rec = {"name": job["name"], "file": plain, "model": job["model"],
           "seed": d.get("seed", job.get("seed")), "size": im.size,
           "seconds": round(time.time() - t0, 1),
           "prompt": job["prompt"]}

    if job.get("alpha_key"):
        src = load_alpha(job["alpha_key"])
        masked = im.resize(src.size, Image.LANCZOS).convert("RGBA")
        masked.putalpha(src.convert("RGBA").split()[3])
        mp = os.path.join(outdir, stem + "_alpha.png")
        masked.save(mp)
        rec["file_alpha"] = mp

    print("  %-24s %5.1fs  %s" % (job["name"], rec["seconds"], os.path.basename(plain)))
    return rec


def cmd_gen(args):
    jobs = json.load(open(args.gen, encoding="utf-8"))
    if args.max:
        jobs = jobs[:args.max]
    print("共 %d 个任务，输出到 %s\n" % (len(jobs), args.out))
    recs = []
    for i, j in enumerate(jobs, 1):
        print("[%d/%d]" % (i, len(jobs)))
        try:
            recs.append(generate(j, args.out))
        except SystemExit as e:
            print("  跳过:", e)
        if i < len(jobs):
            time.sleep(args.gap)
    man = os.path.join(args.out, "manifest.json")
    old = []
    if os.path.exists(man):
        old = json.load(open(man, encoding="utf-8"))
    json.dump(old + recs, open(man, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("\n完成 %d/%d，清单 %s" % (len(recs), len(jobs), man))


def cmd_balance(args):
    """余额与免费额度，避免跑到一半 403（余额不足）。"""
    try:
        d = call("/user/info")
    except SystemExit as e:
        print("查不到余额（接口可能变了，不影响生图）:", e)
        return
    for k in ("balance", "chargeBalance", "totalBalance", "name", "email"):
        if k in d:
            print("  %-14s %s" % (k, d[k]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true", help="列出可用图像模型")
    ap.add_argument("--balance", action="store_true", help="查余额")
    ap.add_argument("--sub", help="text-to-image / image-to-image")
    ap.add_argument("--probe", action="store_true", help="试生成一张")
    ap.add_argument("--model", default="Kwai-Kolors/Kolors")
    ap.add_argument("--prompt", default="中国重彩国画，夜间江边码头，赭石与花青，宣纸质感")
    ap.add_argument("--gen", help="任务 JSON 文件")
    ap.add_argument("--max", type=int, default=0, help="本次最多生成几张，防误刷")
    ap.add_argument("--gap", type=float, default=2.0, help="任务间隔秒数")
    ap.add_argument("--out", default=os.path.join(PROJECT, "art", "gen"))
    args = ap.parse_args()

    if args.list:
        return cmd_list(args)
    if args.balance:
        return cmd_balance(args)
    if args.probe:
        d = generate({"name": "probe", "model": args.model, "prompt": args.prompt,
                      "size": "1024x1024", "seed": 1}, args.out)
        print(json.dumps(d, ensure_ascii=False, indent=1))
        return
    if args.gen:
        return cmd_gen(args)
    ap.print_help()


if __name__ == "__main__":
    main()
