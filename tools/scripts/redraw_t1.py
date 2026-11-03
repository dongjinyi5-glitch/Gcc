# -*- coding: utf-8 -*-
"""T1 重绘流水线：原图 -> 白描 -> 模型上色 -> 回贴 -> 打分。

一条命令跑完一关的 T1 地标
----------------------------
    python redraw_t1.py --level level9 --max 14 --dry-run
    python redraw_t1.py --level level9 --max 14 --run

流程
----
1. 从 **2015 备份** 取原图（不是游戏目录里的，那个已经被我们的 pass 改过了）
2. 抽白描底稿（lineart.py）
3. 提示词由目标形态生成（make_jobs.py）
4. 调硅基流动 Qwen-Image-Edit 上色（sfimg.py）
5. 回贴：原图 L* + 模型色度 + 原图 alpha（recompose.py）
6. 打分（fidelity.py），不达标的自动标出来，不进版本库

为什么必须打分
--------------
扩散模型不听指令是常态。160 张 T1 如果每张都靠人眼看，一天也看不完，
而且看久了会麻木。打分器能在批量跑的时候自动把"模型自己另画了一张"的
那些挑出来，只让人看可疑的那几张。
"""
import argparse
import io
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PIL import Image

import fidelity as FID
import lineart as LA
import numpy as np
import recompose as RC
from component_taxonomy import LEVEL_CN, classify
from component_tiers import assign
from ggc_assets import AssetDB, PROJECT, baseline_map
from make_jobs import build_job
from redraw_targets import target

ART = os.path.join(PROJECT, "art")
INV = os.path.join(ART, "scene_inventory.json")
OUTROOT = os.path.join(ART, "gen", "t1")

# 通过标准的最低分
PASS_EDGE = 0.40
PASS_PIG = 0.30
PASS_DE = 6.0        # 成品与原图平均 ΔE 下限，防「模型没上色」混过


def load_inventory():
    return json.load(io.open(INV, encoding="utf-8"))


def t1_list(inv, level):
    """该关的 T1 构件，按面积从大到小。"""
    tiers = assign(inv)
    sel = []
    for r in inv:
        if level not in r["levels"]:
            continue
        if tiers.get((r["file"], r["path_id"])) != "T1":
            continue
        sel.append(r)
    sel.sort(key=lambda r: -r["area"])
    return sel


def orig_png(db, r, dst):
    """从备份取原图并存成 PNG。"""
    obj = db.file_objs(r["file"]).get(r["path_id"])
    if obj is None:
        return None
    img = db.texture_image(obj)
    if img is None:
        return None
    img.save(dst)
    return img


# 模型偶尔会把重彩画成淡彩（pigment 掉到 0.1 以下）。追加这段而不是改全局
# STYLE，避免影响已经达标的那些图。
PIGMENT_BOOST = ("用高饱和矿物颜料：石青、石绿、朱砂、赭石、藤黄，色块浓重、"
                 "覆盖力强；不要灰调、不要淡彩、不要水彩晕染")


def roi_crop(img, fill_keep=0.90):
    """把图裁到不透明像素的包围盒。

    为什么必须裁：这个游戏很多精灵是 1024×1024 画布、内容只占角落一小块
    （Harbour_037 只有 6.5% 不透明）。整张做白描＝给模型一张几乎空白的纸，
    它会自己编一张完整的画（实测就是这么翻车的，还带题字）。
    裁到内容再放大到 1024，内容才占满画面，构图才锁得住。

    返回 (base, bbox)。bbox=None 表示本来就已经铺满，没裁。
    """
    a = np.array(img.convert("RGBA"))[..., 3]
    ys, xs = np.where(a > 0)
    if len(xs) == 0:
        return img, None
    x0, x1 = int(xs.min()), int(xs.max()) + 1
    y0, y1 = int(ys.min()), int(ys.max()) + 1
    w, h = x1 - x0, y1 - y0
    if w * h >= fill_keep * img.size[0] * img.size[1]:
        return img, None
    return img.crop((x0, y0, x1, y1)), (x0, y0, w, h)


def run_one(db, r, level, outdir, model, seed, steps, guidance, dry=False,
            pigment=0, roi=True, backend=None):
    name = r["texture"]
    os.makedirs(outdir, exist_ok=True)
    orig_path = os.path.join(outdir, "%s_orig.png" % name)
    orig = orig_png(db, r, orig_path)
    if orig is None:
        return {"name": name, "verdict": "取不到原图"}

    # 1) 白描 —— 先裁到内容包围盒，否则大片空白会让模型自己编
    base, bb = roi_crop(orig) if roi else (orig, None)
    la, info = LA.build_lineart(base)
    la_path = os.path.join(outdir, "%s_lineart.png" % name)
    la.save(la_path)
    canvas, box = LA.prepare_for_model(la, 1024)
    model_in = os.path.join(outdir, "%s_lineart_model.png" % name)
    canvas.save(model_in)

    cat, _ = classify(name)
    goal = target(level, cat, "T1")
    if pigment:
        goal = goal + "。" + PIGMENT_BOOST
    job = build_job(level, name, goal, model=model, seed=seed,
                    steps=steps, guidance=guidance,
                    image=model_in, alpha_key=None)
    if backend:
        job["backend"] = backend
    jobs_path = os.path.join(outdir, "_jobs.json")
    json.dump([job], io.open(jobs_path, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    if dry:
        return {"name": name, "file": r["file"], "path_id": r["path_id"],
                "level": level, "verdict": "dry-run", "goal": goal,
                "size": orig.size, "ink": info.get("ink_cover")}

    # 2) 生成 —— 走多通道调度：百炼 / Google / 魔搭 / 硅基流动，
    #    某家当天额度用尽会自动落到下一家（账本在 .secrets/quota.json）
    import imgrouter
    out_png = None
    try:
        rec = imgrouter.generate(job, outdir)
        out_png = rec["file"]
        backend = rec.get("backend")
    except SystemExit as e:
        return {"name": name, "verdict": "生成失败: %s" % e}

    gen = Image.open(out_png)

    # 3) 回贴（在裁出来的 ROI 上做，再贴回原画布）
    comp_small = RC.compose(base, gen, crop_box=box)
    if bb:
        comp = Image.new("RGBA", orig.size, (0, 0, 0, 0))
        comp.paste(comp_small, (bb[0], bb[1]))
    else:
        comp = comp_small
    comp_path = os.path.join(outdir, "%s_G1.png" % name)
    comp.save(comp_path)
    same, diff = RC.alpha_identical(orig, comp)

    # 4) 打分 —— 用「裁回原尺寸」的图打分，和原图 / 白描同分辨率
    gsc = gen.convert("RGB")
    if box:
        x0, y0, cw, ch = box
        gsc = gsc.crop((x0, y0, x0 + cw, y0 + ch))
    gsc = gsc.resize(base.size, Image.LANCZOS)
    sc = FID.score(la, gsc, base, composite=comp_small)
    ok = (sc["edge"] >= PASS_EDGE and sc["pigment"] >= PASS_PIG
          and (sc["holes"] is None or sc["holes"] <= 0.06)
          and (sc.get("delta_e") is None or sc["delta_e"] >= PASS_DE))
    sc["alpha_identical"] = same
    sc["alpha_diff"] = diff
    sc["passed"] = ok
    sc["name"] = name
    sc["file"] = comp_path
    sc["rfile"] = r["file"]
    sc["rpath_id"] = r["path_id"]
    sc["level"] = level
    sc["seed"] = seed
    sc["gen_file"] = out_png
    sc["goal"] = goal
    sc["size"] = orig.size
    sc["crop_box"] = box
    sc["roi"] = bb
    sc["backend"] = backend
    if not same:
        sc["verdict"] = "alpha 被改动，不可入包"
    elif not ok:
        sc["verdict"] = "未达标：" + sc["verdict"]
    return sc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--level", default="level9")
    ap.add_argument("--max", type=int, default=14)
    ap.add_argument("--model", default="Qwen/Qwen-Image-Edit-2509")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--steps", type=int, default=30)
    ap.add_argument("--guidance", type=float, default=7.0)
    ap.add_argument("--pigment-boost", type=int, default=0,
                    help="1 = 提示词追加高饱和矿物颜料，用于 pigment 掉到 0.1 以下的图")
    ap.add_argument("--no-roi", action="store_true",
                    help="不裁到内容包围盒（默认会裁：低不透明占比的精灵不裁必翻车）")
    ap.add_argument("--backend",
                    help="指定生图通道顺序，逗号分隔：dashscope,google,modelscope,siliconflow"
                         "（默认按这个顺序自动切换，额度耗尽自动跳到下一家）")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--only", help="只跑这几个构件名，逗号分隔")
    ap.add_argument("--out", help="输出目录")
    ap.add_argument("--resume", action="store_true",
                    help="跳过报告中已达标（passed 且 alpha 一致）的构件")
    ap.add_argument("--skip-registered", action="store_true",
                    help="跳过版本库里已是 G* 的构件（共享贴图跨关复用，别重跑覆盖）")
    args = ap.parse_args()

    inv = load_inventory()
    sel = t1_list(inv, args.level)
    if args.only:
        want = {s.strip() for s in args.only.split(",")}
        sel = [r for r in sel if r["texture"] in want]
    # 共享贴图跨关复用：已经在版本库里升到 G* 的，换个种子重跑只会把
    # 已评审过的 G1 顶掉，没有任何收益，直接跳过。
    if args.skip_registered:
        reg_p = os.path.join(ART, "component_versions.json")
        if os.path.exists(reg_p):
            reg = json.load(io.open(reg_p, encoding="utf-8")).get("components", {})
            keep = []
            for r in sel:
                k = "%s__%s" % (r["file"], r["path_id"])
                cur = str((reg.get(k) or {}).get("current") or "")
                if cur.startswith("G"):
                    print("跳过 %s：版本库已是 %s（共享贴图，不重跑）"
                          % (r["texture"], cur))
                else:
                    keep.append(r)
            sel = keep
    sel = sel[:args.max]

    cn = LEVEL_CN.get(args.level, args.level)
    outdir = args.out or os.path.join(OUTROOT, args.level)
    os.makedirs(outdir, exist_ok=True)
    print("关卡 %s (%s)  T1 构件 %d 个  ->  %s\n"
          % (args.level, cn, len(sel), outdir))

    db = AssetDB(file_map=baseline_map())
    man = os.path.join(outdir, "t1_report.json")
    results = []
    done = set()
    # 无论有没有 --resume 都先读回旧报告：--only 只该「改一行」，
    # 不该把整关 19 行覆盖成 1 行（2026-10-26 踩过两次）。
    if os.path.exists(man):
        try:
            results = json.load(io.open(man, encoding="utf-8"))
        except Exception as e:
            print("警告：旧报告读不出来，按空处理（%s）" % e)
            results = []
    if args.resume:
        for x in results:
            if x.get("passed") and x.get("alpha_identical"):
                done.add(x["name"])
        print("resume: 已达标 %d 个，跳过 %s" % (len(done), sorted(done)))

    for i, r in enumerate(sel, 1):
        if r["texture"] in done:
            print("[%d/%d] %s  跳过(已达标)" % (i, len(sel), r["texture"]))
            continue
        print("[%d/%d] %s  (%.2f Mpx) %s"
              % (i, len(sel), r["texture"], r["area"] / 1e6, r["size"]))
        t0 = time.time()
        res = run_one(db, r, args.level, outdir, args.model, args.seed,
                      args.steps, args.guidance, args.dry_run,
                      args.pigment_boost, not args.no_roi, args.backend)
        res["seconds"] = round(time.time() - t0, 1)
        # 同名重跑要顶掉旧记录，否则报告里同一个构件会出现两行，
        # 登记器会按第一行（旧失败结果）判定
        results = [x for x in results if x.get("name") != res.get("name")]
        results.append(res)
        # 增量写盘：单个构件崩了不丢前面的成果。
        # dry-run 绝不写盘 —— 之前一次 `--dry-run` 就把整关报告覆盖成一条记录。
        if not args.dry_run:
            json.dump(results, io.open(man, "w", encoding="utf-8"),
                      ensure_ascii=False, indent=1)
        if "edge" in res:
            print("     edge=%.3f sil=%s pig=%.3f alpha一致=%s  -> %s  (%.0fs)"
                  % (res["edge"], res["silhouette"], res["pigment"],
                     res["alpha_identical"], res["verdict"], res["seconds"]))
        else:
            print("     %s" % res["verdict"])

    print("\n清单 -> %s" % man)
    print("\n清单 -> %s" % man)
    if not args.dry_run:
        ok = [x for x in results if x.get("passed")]
        bad = [x for x in results if "edge" in x and not x.get("passed")]
        print("达标 %d / %d" % (len(ok), len([x for x in results if "edge" in x])))
        for x in bad:
            print("  未达标: %-18s %s" % (x["name"], x["verdict"]))


if __name__ == "__main__":
    main()
