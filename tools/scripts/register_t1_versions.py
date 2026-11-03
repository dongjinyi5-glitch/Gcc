# -*- coding: utf-8 -*-
"""把通过的 T1 重绘登记进版本库 art/component_versions.json。

流程
----
1. 读某关的 t1_report.json（redraw_t1.py 的产物）。
2. 只认 passed=True 且 alpha_identical=True 的条目。
3. 解析它的身份键：优先用报告里的 rfile/rpath_id；没有就按
   (构件名, 尺寸, 关卡) 在 inventory 里反查 —— 因为同一关里 27 个
   归一化名碰撞是按 (file, path_id) 区分的，不能只靠名字。
4. 在版本库里给该构件追加一条 G1 / redraw 版本，并把 current 改成 G1。
   已存在 G1 就原地覆盖文件与说明，不重复追加。
5. 顺手生成 art/component_thumbs/new/<key>.jpg，让总表「现版」一栏能显示重绘。

用法
----
    python register_t1_versions.py --level level9
    python register_t1_versions.py --report art/gen/t1/level9/t1_report.json
"""
import argparse
import datetime
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ggc_assets import PROJECT  # noqa: E402
from PIL import Image  # noqa: E402

ART = os.path.join(PROJECT, "art")
INV = os.path.join(ART, "scene_inventory.json")
VERSIONS = os.path.join(ART, "component_versions.json")
THUMBS_NEW = os.path.join(ART, "component_thumbs", "new")


def load_json(p, default=None):
    if os.path.exists(p):
        return json.load(io.open(p, encoding="utf-8"))
    return default if default is not None else {}


def resolve_key(report_entry, inv, level):
    """报告条目 -> 版本库键 'file__path_id'。

    优先用报告自带身份；否则按 (name, size, level) 反查并断言唯一。
    """
    rf, rp = report_entry.get("rfile"), report_entry.get("rpath_id")
    if rf is not None and rp is not None:
        return "%s__%d" % (rf, rp), None

    name = report_entry["name"]
    size = report_entry["size"]  # [w, h]
    hits = []
    for r in inv:
        if r["texture"] != name:
            continue
        if list(r["size"]) != list(size):
            continue
        if level not in r["levels"]:
            continue
        hits.append(r)
    if len(hits) == 1:
        r = hits[0]
        return "%s__%d" % (r["file"], r["path_id"]), None
    if not hits:
        return None, "inventory 里找不到 %s %s @%s" % (name, size, level)
    return None, ("%s 在 %s 有 %d 个 (file,path_id) 候选，需人工指定"
                  % (name, level, len(hits)))


def make_thumb(src_png, key):
    os.makedirs(THUMBS_NEW, exist_ok=True)
    dst = os.path.join(THUMBS_NEW, key + ".jpg")
    try:
        im = Image.open(src_png).convert("RGBA")
        bg = Image.new("RGB", im.size, (247, 244, 238))
        bg.paste(im, (0, 0), im)
        bg.save(dst, "JPEG", quality=82)
        return dst
    except Exception as e:
        return "缩略图失败: %s" % e


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--level", default="level9")
    ap.add_argument("--report", default=None)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    report = args.report or os.path.join(ART, "gen", "t1", args.level,
                                        "t1_report.json")
    if not os.path.exists(report):
        print("报告不存在:", report)
        return
    entries = load_json(report)
    inv = load_json(INV, [])

    ver = load_json(VERSIONS)
    if not ver.get("components"):
        print("版本库为空或不存在；请先跑 build_component_xlsx.py 建库")
        return

    today = datetime.date.today().isoformat()
    n_pass = n_reg = n_skip = n_fail = 0
    for e in entries:
        if not e.get("passed"):
            n_fail += 1
            continue
        if not e.get("alpha_identical"):
            n_fail += 1
            print("  ✗ alpha 不一致，跳过:", e.get("name"))
            continue
        n_pass += 1
        key, err = resolve_key(e, inv, e.get("level") or args.level)
        if err:
            n_skip += 1
            print("  ⚠ 无法登记 %s: %s" % (e.get("name"), err))
            continue
        comp = ver["components"].get(key)
        if comp is None:
            n_skip += 1
            print("  ⚠ 版本库无此键，跳过:", key)
            continue

        g1 = e.get("file")  # art/gen/t1/.../<name>_G1.png
        rel = os.path.relpath(g1, PROJECT).replace(os.sep, "/")
        note = ("T1 白描底稿 + Qwen-Image-Edit 上色，回贴原图 L* 与 alpha；"
                "edge=%.3f sil=%.3f pig=%.3f"
                % (e.get("edge", 0), e.get("silhouette") or 0,
                   e.get("pigment", 0)))
        # 去重：已有 G1 就覆盖
        existing = [v for v in comp["versions"] if v["v"] == "G1"]
        if existing:
            existing[0]["date"] = today
            existing[0]["file"] = rel
            existing[0]["note"] = note
            existing[0]["seed"] = e.get("seed")
        else:
            comp["versions"].append({
                "v": "G1", "date": today, "kind": "redraw",
                "file": rel, "note": note, "seed": e.get("seed"),
                "score": {"edge": e.get("edge"), "silhouette": e.get("silhouette"),
                          "pigment": e.get("pigment")},
            })
        comp["current"] = "G1"
        thumb = make_thumb(g1, key)
        n_reg += 1
        print("  ✓ %-18s -> %s  (thumb: %s)" % (e.get("name"), key,
                                                "ok" if not str(thumb).startswith("缩略") else thumb))

    if args.dry_run:
        print("\n[DRY-RUN] 不写盘。通过 %d / 登记 %d / 跳过 %d / 未达标 %d"
              % (n_pass, n_reg, n_skip, n_fail))
        return

    json.dump(ver, io.open(VERSIONS, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("\n版本库已更新 ->", VERSIONS)
    print("通过 %d / 登记 %d / 跳过 %d / 未达标 %d"
          % (n_pass, n_reg, n_skip, n_fail))


if __name__ == "__main__":
    main()
