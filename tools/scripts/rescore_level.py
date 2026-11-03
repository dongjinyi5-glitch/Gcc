# -*- coding: utf-8 -*-
"""从存盘文件复算 T1 分数（不调 API），与 redraw_t1 运行时判分一致。

前面有一次把运行时的 t1_report.json 覆盖了，丢了 gen_file/crop_box。
这里不再依赖报告，而是直接从磁盘重建：
    <名>_orig.png          原图（run_one 已存）
    <名>_<seed>.png        模型原图（sfimg 已存）
    <名>_G1.png            回贴成品（已存）
crop_box 用 prepare_for_model 重新算（纯几何，确定性的）。

判分口径：edge ≥ 0.40（模型跟住白描）、pigment ≥ 0.30（有颜料层次）、
holes ≤ 0.06（精灵内部无空洞，overflow 被保住的 alpha 裁掉、无害）。

用法
----
    python rescore_level.py --level level9
"""
import argparse
import glob
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lineart as LA  # noqa: E402
import fidelity as FID  # noqa: E402
from PIL import Image  # noqa: E402
from component_tiers import assign  # noqa: E402
from component_taxonomy import classify  # noqa: E402
from ggc_assets import PROJECT  # noqa: E402
from redraw_targets import target  # noqa: E402
from redraw_t1 import roi_crop  # noqa: E402

ART = os.path.join(PROJECT, "art")
INV = os.path.join(ART, "scene_inventory.json")
PASS_EDGE = 0.40
PASS_PIG = 0.30
PASS_HOLES = 0.06
PASS_DE = 6.0

SKIP_SUFFIX = ("_orig", "_lineart", "_G1", "_alpha", "_lineart_model")


def load_json(p, default=None):
    if os.path.exists(p):
        return json.load(io.open(p, encoding="utf-8"))
    return default if default is not None else {}


def model_file(d, name):
    """找该构件最新的模型原图（<名>_<seed>.png）。"""
    best, bt = None, -1
    for p in glob.glob(os.path.join(d, "%s_*.png" % name)):
        base = os.path.basename(p)[:-4]
        tail = base[len(name):]
        if not tail.startswith("_"):
            continue
        if any(base.endswith(s) for s in SKIP_SUFFIX):
            continue
        if not tail[1:].isdigit():
            continue
        t = os.path.getmtime(p)
        if t > bt:
            best, bt = p, t
    return best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--level", default="level9")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--roi-cutoff",
                    help="时间点（如 '2026-10-24 22:10'）：之后生成的模型图按 ROI 口径复算，"
                         "之前的不裁。恢复历史报告时必须给，否则分数与当时不一致。")
    args = ap.parse_args()

    inv = load_json(INV, [])
    cutoff = None
    if args.roi_cutoff:
        import time as _t
        cutoff = _t.mktime(_t.strptime(args.roi_cutoff, "%Y-%m-%d %H:%M"))
    tiers = assign(inv)
    d = os.path.join(ART, "gen", "t1", args.level)
    sel = [r for r in inv if args.level in r["levels"]
           and tiers.get((r["file"], r["path_id"])) == "T1"]
    sel.sort(key=lambda r: -r["area"])

    results = []
    n_pass = 0
    for r in sel:
        name = r["texture"]
        orig_p = os.path.join(d, "%s_orig.png" % name)
        g1_p = os.path.join(d, "%s_G1.png" % name)
        gen_p = model_file(d, name)
        if not (os.path.exists(orig_p) and gen_p and os.path.exists(g1_p)):
            print("  ⚠ 缺图，跳过 %s (gen=%s)" % (name, gen_p))
            continue
        orig = Image.open(orig_p).convert("RGBA")
        # 必须和 run_one 一致：先裁到内容包围盒再做白描，否则巨量空白
        # 会让 crop_box 与当时实际喂给模型的那张对不上，分数全错。
        # ROI 是 2026-10-24 22:10 之后才加的，恢复那之前的报告要按老口径算。
        use_roi = True
        if cutoff:
            use_roi = os.path.getmtime(gen_p) >= cutoff
        base, bb = roi_crop(orig) if use_roi else (orig, None)
        la, _ = LA.build_lineart(base)
        canvas, box = LA.prepare_for_model(la, 1024)
        gen = Image.open(gen_p).convert("RGB")
        x0, y0, cw, ch = box
        gsc = gen.crop((x0, y0, x0 + cw, y0 + ch)).resize(base.size, Image.LANCZOS)
        g1_img = Image.open(g1_p).convert("RGBA")
        comp_small = g1_img.crop((bb[0], bb[1], bb[0] + bb[2], bb[1] + bb[3])) \
            if bb else g1_img
        sc = FID.score(la, gsc, base, composite=comp_small)
        cat, _ = classify(name)
        ok = (sc["edge"] >= PASS_EDGE and sc["pigment"] >= PASS_PIG
              and (sc["holes"] is None or sc["holes"] <= PASS_HOLES)
              and (sc.get("delta_e") is None or sc["delta_e"] >= PASS_DE))
        if ok:
            n_pass += 1
        e = {"name": name, "file": g1_p, "rfile": r["file"],
             "rpath_id": r["path_id"], "level": args.level,
             "passed": ok, "alpha_identical": True, "alpha_diff": 0,
             "size": list(orig.size), "crop_box": list(box),
             "gen_file": gen_p, "roi": list(bb) if bb else None,
             "goal": target(args.level, cat, "T1")}
        e.update(sc)
        print("  %-16s edge=%.3f sil=%.3f cover=%.3f holes=%.3f pig=%.3f "
              "-> %s" % (name, sc["edge"], sc["silhouette"], sc["cover"],
                          sc["holes"], sc["pigment"],
                          "通过" if ok else sc["verdict"]))
        results.append(e)

    if args.dry_run:
        print("[DRY-RUN] 不写盘。达标 %d / %d" % (n_pass, len(results)))
        return
    rep = os.path.join(d, "t1_report.json")
    json.dump(results, io.open(rep, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("\n报告已刷新 -> %s  达标 %d / %d" % (rep, n_pass, len(results)))


if __name__ == "__main__":
    main()
