# -*- coding: utf-8 -*-
"""路线 B 第 2 步：把整层合成图交给模型重绘，再把结果切回各层贴图。

流程
----
1. 读 `out/stack/<level>/scene_flat.png`（scene_stack.py --build 的产物，整关合成图）
2. 横向切块。**必须切**：合成图是 7000×641（约 11:1），而 Gemini / 通义万相这类
   模型只接受固定几档比例（最宽 21:9≈2.33:1），整张喂进去会被强行压扁。
3. 每块上传到 Gitee 拿公网 URL（魔搭要求 image_url 公网可达，不收 base64），
   交给 imgrouter 生成。带重叠，便于拼接时羽化接缝。
4. 按权重把各块结果拼回整张，存 `redrawn.png`。
5. `--slice` 时调用 scene_stack.slice_back，按每层 alpha 切回图集（alpha 逐位不变）。

用法
----
    # 先只跑 1 块，确认美术方向（省钱）
    python redraw_scene.py --level level4 --limit 1

    # 满意后跑全部
    python redraw_scene.py --level level4 --slice

    # 换风格描述
    python redraw_scene.py --level level4 --prompt-file docs/prompt_scene.txt
"""
import argparse
import json
import os
import sys

import numpy as np
from PIL import Image, ImageFilter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import imgrouter as IR          # noqa: E402
import gitee_host as GH         # noqa: E402
import scene_stack as SS        # noqa: E402
from ggc_assets import PROJECT  # noqa: E402

MAX_ASPECT = 21.0 / 9.0        # 模型能接受的最宽比例
BG = (26, 28, 34)              # 透明区填充色（夜景暗底，不让模型把白当成内容）

DEFAULT_PROMPT = (
    "把这张图重绘成中国国画重彩风格：工笔重彩，矿物颜料质感（朱砂、石青、石绿、赭石、蛤白），"
    "墨线勾边，中等粗细笔触，宣纸底色。\n"
    "严格按原图重绘：构图、每个物体的位置、大小比例、轮廓形状全部保持原样，只改变画风与色彩。\n"
    "不要新增任何人物、动物、车辆或建筑；不要删除原图已有的东西；"
    "不要改变画面长宽比；不要把画面重新构图或缩放。\n"
    "不要出现任何文字、印章、水印、签名、边框。"
)

LINE_PROMPT = (
    "给这张白描线稿上色，画成中国工笔重彩。船体用赭石和淡墨，木结构用赭石，"
    "铁件用石青，灯光处用藤黄，水面用石绿，背景用宣纸米白。"
    "保留每一条墨线，所有物体的位置和形状不变。"
)

# 第二版：修掉第一版实测出来的三个毛病
#   1) 赭石重复分配给两个最大面积（船体 + 木结构）→ 整关一片金黄
#   2) "背景用宣纸米白" → 模型把天空/纸面全刷成米黄，暖色占比 83%
#   3) 没提明暗 → 模型当平涂上色，暗部不压、亮部不提，层次全丢
LINE_PROMPT_V2 = (
    "把这张白描线稿上色，画成中国工笔重彩（矿物颜料、墨线勾边）。\n"
    "严格按线稿的明暗关系上色：暗部用淡墨层层积染压深，亮部留白或提亮，"
    "保持原有明暗层次，不要平涂成一片。\n"
    "色彩分配：船体铁壳和吊机钢架用石青、花青（冷调），"
    "木质结构与甲板用赭石、朱砂，灯光与窗户用藤黄并留高光，"
    "水面用石绿与花青，相邻建筑的屋顶用石绿和赭石交替区分。\n"
    "保留每一条墨线，所有物体的位置和形状不变。"
)

NEG_PROMPT = "文字, 汉字, 招牌, 印章, 水印, 签名, 边框, 二维码"


def pick_prompt(args):
    if args.prompt_file and os.path.isfile(args.prompt_file):
        return open(args.prompt_file, encoding="utf-8").read().strip()
    if args.prompt_v == 2:
        return LINE_PROMPT_V2
    return LINE_PROMPT if args.prep in ("line", "toned") else DEFAULT_PROMPT


def load_scene(level):
    d = os.path.join(PROJECT, "out", "stack", level)
    flat = Image.open(os.path.join(d, "scene_flat.png")).convert("RGBA")
    return flat, d


def make_tiles(W, H, tile_w, overlap):
    """横向切块。tile_w 会被压到不超过 21:9；末块贴右边界，避免过窄。"""
    tw = int(min(tile_w, max(64, int(round(H * MAX_ASPECT)))))
    step = max(1, tw - overlap)
    xs = list(range(0, max(1, W - tw) + 1, step))
    if not xs:
        xs = [0]
    if xs[-1] + tw < W:
        xs.append(max(0, W - tw))
    return [(x, min(W, x + tw)) for x in xs], tw


def feather(n, ramp):
    """一维权重：两端斜坡、中间满值。用于拼接时消除接缝。"""
    w = np.ones(n, np.float32)
    r = max(1, min(ramp, n // 2))
    rampv = np.linspace(0.0, 1.0, r, dtype=np.float32)
    w[:r] = rampv
    w[-r:] = rampv[::-1]
    return w


def flatten_for_model(crop):
    """RGBA 压到暗底，避免模型把透明区当白纸。"""
    bg = Image.new("RGB", crop.size, BG)
    bg.paste(crop, (0, 0), crop)
    return bg


def prep_tile(crop, mode="lift"):
    """把合成图处理成「模型能看清结构」的样子。

    为什么必须处理：整关合成图是夜景暗图（大面积接近纯黑）。实测直接喂，
    模型会无视输入、另画一张亮调插画并把构图整个换掉（这是踩过的铁律）。
    所以要先把暗部提上来，让结构在输入里"看得见"。

    flat  原样（对照用，会失败）
    lift  暗部提亮 + 轻微降饱和（默认，保留全部结构信息）
    line  边缘线稿（白底黑线，构图锁得最死，但会丢明暗）
    toned 线稿 + 淡明暗（白底、墨线、暗部压灰）

          为什么需要 toned：实测 `line` 把明暗信息丢光之后，模型只能**平涂**，
          成品整体拉到中间调、暗部不暗、亮部不亮，层次全丢。toned 在保留
          结构线的同时把原图的大块明暗以淡墨形式叠回去，模型才有东西可"渲染"。
    """
    rgb = flatten_for_model(crop)
    if mode == "flat":
        return rgb
    a = np.asarray(rgb, np.float32) / 255.0
    if mode == "lift":
        # 只抬暗部：y^0.42 让 0.02 变成 0.21，0.8 基本不动
        out = np.power(np.clip(a, 0, 1), 0.42)
        # 压一点饱和，避免把噪点/色偏一起放大
        g = out.mean(axis=2, keepdims=True)
        out = np.clip(g + (out - g) * 0.75, 0, 1)
        return Image.fromarray((out * 255).round().astype(np.uint8), "RGB")
    if mode in ("line", "toned"):
        gray = rgb.convert("L")
        e = gray.filter(ImageFilter.FIND_EDGES)
        ea = np.asarray(e, np.float32) / 255.0
        # FIND_EDGES 黑底白边；归一化后反相得到白底黑线
        ea = np.clip(ea / max(1e-3, np.percentile(ea, 99.0)), 0, 1)
        paper = 1.0 - ea * 0.92
        if mode == "line":
            return Image.fromarray((paper * 255).round().astype(np.uint8), "L").convert("RGB")
        # toned：把提亮后的灰阶**拉伸**后乘进纸面，暗部变灰、亮部仍白
        # 直接乘原始灰阶没用——夜景本来就低对比，乘出来是一片均匀浅灰。
        # 所以先按 5%~95% 分位拉伸，再映射到 0.28~1.0，模型才看得出"哪里暗"。
        g0 = np.power(np.clip(np.asarray(gray, np.float32) / 255.0, 0, 1), 0.42)
        lo, hi = np.percentile(g0, [5.0, 95.0])
        g = np.clip((g0 - lo) / max(1e-3, hi - lo), 0, 1)
        shade = 0.28 + 0.72 * g
        out = paper * shade
        return Image.fromarray((np.clip(out, 0, 1) * 255).round().astype(np.uint8),
                               "L").convert("RGB")
    return rgb


def tile_path(odir, level, i):
    """imgrouter.generate 的落盘命名是 {job.name}_{seed}.png，seed 缺省 0。"""
    return os.path.join(odir, "%s_t%02d_0.png" % (level, i))


def stitch(tiles, odir, level, W, H, overlap, blend=24):
    """把各块结果拼回整张：色调统一 → 按内容选缝 → 窄带过渡。

    为什么不再用大范围羽化
    ----------------------
    最初的做法是重叠区整段线性羽化。实测不行：模型对每块的**理解**不同，
    同一栋楼在相邻两块里画得略有位移，400px 的羽化把两张画叠在一起，
    接缝处出现明显的"重影/半透明叠影"（在 5000~6400 三块重叠处最明显）。

    现在的做法：
    1. **色调统一**：把每块的均值和标准差都匹配到第一块（只补均值不够，
       模型每块的对比度也不同，补完均值仍留竖向深浅带）；
    2. **按内容选缝**：在相邻块的重叠区里，逐列算两块的差异，取差异最小
       （最平滑、最接近天空/空处）的那一列作为切分点——硬切，不叠影；
    3. 只在切缝两侧各 blend/2 像素做窄带过渡，盖掉残余色阶。
    """
    arrs = []
    for i, (x0, x1) in tiles:
        p = tile_path(odir, level, i)
        if not os.path.isfile(p):
            print("  缺块 %s，跳过" % os.path.basename(p))
            continue
        gen = Image.open(p).convert("RGB")
        if gen.size != (x1 - x0, H):
            gen = gen.resize((x1 - x0, H), Image.LANCZOS)
        arrs.append([x0, x1, np.asarray(gen, np.float32)])
    if not arrs:
        return None, None

    # 1) 色调统一到第一块
    ref = arrs[0][2].reshape(-1, 3)
    m_ref, s_ref = ref.mean(0), ref.std(0)
    for k in range(1, len(arrs)):
        a = arrs[k][2]
        m, s = a.reshape(-1, 3).mean(0), a.reshape(-1, 3).std(0)
        gain = s_ref / np.maximum(s, 1e-3)
        arrs[k][2] = np.clip((a - m) * gain + m_ref, 0, 255)

    # 2) 按内容选缝
    #    两个必须处理的坑：
    #    * 模型会在每块的外侧边缘多刷一条亮边/白边（实测 tile4 右缘 5366~5398
    #      是一条 32px 的亮带）。所以每块外侧 MARGIN 像素一律不用。
    #    * 平滑差异曲线时不能用 np.convolve(..., 'same')：它两端补零，会把
    #      边缘的差异值压低，argmin 永远落在重叠区的端点上（实测确实如此）。
    #      改成两端用边界值填充后再卷积。
    MARGIN = 48
    us = []
    for x0, x1, _a in arrs:
        us.append((x0 + (MARGIN if x0 > 0 else 0),
                   x1 - (MARGIN if x1 < W else 0)))
    cuts = []
    for k in range(len(arrs) - 1):
        x0a, x1a, a = arrs[k]
        x0b, x1b, b = arrs[k + 1]
        lo = max(us[k][0], us[k + 1][0])
        hi = min(us[k][1], us[k + 1][1])
        if hi - lo < 16:                      # 可用重叠太小，退回重叠区中点
            lo, hi = max(x0a, x0b), min(x1a, x1b)
            cuts.append((lo + hi) // 2)
            continue
        d = np.abs(a[:, lo - x0a:hi - x0a] - b[:, lo - x0b:hi - x0b]).mean(axis=(0, 2))
        pad = 15
        dp = np.pad(d, pad, mode="edge")
        ds = np.convolve(dp, np.ones(2 * pad + 1, np.float32) / (2 * pad + 1),
                         mode="valid")
        cuts.append(lo + int(np.argmin(ds)))

    # 3) 硬切落位 + 窄带过渡
    out = np.zeros((H, W, 3), np.float32)
    cov = np.zeros((H, W), bool)
    for k, (x0, x1, a) in enumerate(arrs):
        s = x0 if k == 0 else cuts[k - 1]
        e = x1 if k == len(arrs) - 1 else cuts[k]
        s, e = max(s, x0), min(e, x1)
        if e <= s:
            continue
        out[:, s:e] = a[:, s - x0:e - x0]
        cov[:, s:e] = True
    # 窄带过渡：只在缝两侧各 blend/2 像素做线性混合
    half = max(1, blend // 2)
    for c in cuts:
        lo, hi = max(0, c - half), min(W, c + half)
        if hi - lo < 2:
            continue
        # 找出跨这条缝的左右两块
        left = next((v for v in arrs if v[0] < c <= v[1]), None)
        right = next((v for v in arrs if v[0] <= c < v[1] and v is not left), None)
        if left is None or right is None:
            continue
        t = np.linspace(0.0, 1.0, hi - lo, dtype=np.float32)[None, :, None]
        la = left[2][:, lo - left[0]:hi - left[0]]
        ra = right[2][:, lo - right[0]:hi - right[0]]
        if la.shape[1] != hi - lo or ra.shape[1] != hi - lo:
            continue
        out[:, lo:hi] = la * (1 - t) + ra * t
    return out, cov


def run(args):
    flat, sdir = load_scene(args.level)
    W, H = flat.size
    tiles, tw = make_tiles(W, H, args.tile, args.overlap)
    # 带上原始序号：--only 只跑指定块做 A/B，落盘名仍按整关编号，便于对照
    tiles = list(enumerate(tiles))
    if args.only:
        want = [int(v) for v in args.only.split(",") if v.strip()]
        tiles = [t for t in tiles if t[0] in want]
    if args.limit:
        tiles = tiles[:args.limit]
    prompt = pick_prompt(args)

    odir = os.path.join(PROJECT, "out", "redraw", args.level + (args.tag or ""))
    os.makedirs(odir, exist_ok=True)
    print("%s 合成图 %dx%d（%.2f:1）-> %d 块，块宽 %d，重叠 %d"
          % (args.level, W, H, W / float(H), len(tiles), tw, args.overlap))

    owner = None
    if args.use_gitee:
        owner, _ = GH.whoami()
    if args.restich:
        print("只重新拼接（复用已有各块结果，不调用模型）")
    else:
        for i, (x0, x1) in tiles:
            crop = flat.crop((x0, 0, x1, H))
            src = prep_tile(crop, args.prep)
            tp = os.path.join(odir, "tile_%02d_in.png" % i)
            src.save(tp)
            job = {"name": "%s_t%02d" % (args.level, i),
                   "prompt": prompt,
                   "negative_prompt": None if args.no_neg else NEG_PROMPT,
                   "image": tp,
                   "size": "%dx%d" % (src.width, src.height),
                   "aspect": IR.best_aspect(src.width, src.height),
                   "backend": args.backend}
            if args.use_gitee:
                job["image_url_public"] = GH.upload(
                    owner, args.repo, tp, "stack/%s/tile_%02d.png" % (args.level, i))
            if args.model:
                job["model"] = args.model
            print("  [块%d] x=%d..%d %s" % (i, x0, x1,
                                           "上传 Gitee" if args.use_gitee else "base64 内联"))
            rec = IR.generate(job, odir)
            gp = rec.get("file") or rec.get("path")
            if not gp or not os.path.isfile(gp):
                print("     ! 这块没出图，跳过：%s" % rec)

    out, covered = stitch(tiles, odir, args.level, W, H, args.overlap)
    if out is None:
        print("没有任何块成功出图。")
        return 1
    img = Image.fromarray(np.clip(out, 0, 255).round().astype(np.uint8), "RGB")
    op = os.path.join(odir, "redrawn.png")
    img.save(op)
    print("拼接完成：%s（覆盖 %.1f%%）" % (op, 100.0 * covered.mean()))

    if args.slice:
        db = SS.AssetDB(data_dir=SS.DATA)
        items, W2, H2, atlases = SS.build_items(db, args.level)
        if (W2, H2) != (W, H):
            print("画布尺寸不一致 %s vs %s，终止切回" % ((W2, H2), (W, H)))
            return 1
        rep = {}
        layers = SS.slice_back(items, atlases, img, W, H, report=rep)
        sd = os.path.join(odir, "sliced")
        os.makedirs(sd, exist_ok=True)
        for (f, pid), lay in sorted(layers.items(), key=lambda kv: kv[1]["name"]):
            safe = "".join(c if c.isalnum() or c in "._-" else "_" for c in lay["name"])
            lay["image"].save(os.path.join(sd, "%s_%s.png" % (safe, pid)))
        print("切回 %d 张图集 -> %s" % (len(layers), sd))
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--level", default="level4")
    ap.add_argument("--tile", type=int, default=1400, help="块宽上限（会被压到 21:9 以内）")
    ap.add_argument("--overlap", type=int, default=120)
    ap.add_argument("--limit", type=int, default=0, help="只跑前 N 块（0=全部）")
    ap.add_argument("--only", default=None,
                    help="只跑指定块号（逗号分隔），用于 A/B 对比，例如 3 或 0,3")
    ap.add_argument("--tag", default=None,
                    help="输出目录后缀，例如 _A -> out/redraw/level4_A（A/B 不互相覆盖）")
    ap.add_argument("--prep", default="lift", choices=["flat", "lift", "line", "toned"],
                    help="输入预处理：lift 提亮暗部 / line 纯线稿 / toned 线稿+淡明暗 / flat 原样")
    ap.add_argument("--prompt-v", type=int, default=1, choices=[1, 2],
                    help="提示词版本：1 旧版（赭石主导）/ 2 新版（冷调铁件 + 明暗层次）")
    ap.add_argument("--no-neg", action="store_true", help="不传负向提示词（A/B 用）")
    ap.add_argument("--backend", default="modelscope")
    ap.add_argument("--model", default=None)
    ap.add_argument("--repo", default=GH.DEFAULT_REPO)
    ap.add_argument("--use-gitee", action="store_true",
                    help="改用 Gitee 公网 URL 而不是 base64（默认 base64，无需图床）")
    ap.add_argument("--prompt-file", default=None)
    ap.add_argument("--slice", action="store_true", help="出图后按层切回图集")
    ap.add_argument("--restich", action="store_true",
                    help="只重新拼接已有各块结果（不调用模型，零成本）")
    a = ap.parse_args()
    return run(a)


if __name__ == "__main__":
    sys.exit(main())
