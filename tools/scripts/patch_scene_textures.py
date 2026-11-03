# -*- coding: utf-8 -*-
"""把路线 B 切回后的图集**定点写进游戏包**（字节数不变，不用 UnityPy 保存）。

为什么不用 UnityPy 的 save()
----------------------------
`env.save()` 会重写整个 SerializedFile，在这个 Unity 4.3.4f1 build 上会把
TextAsset 重新序列化成长度不同的版本，引擎直接报 resources.assets 损坏
（见 writeback.py 顶部记录）。所以只能做**等长字节覆盖**：
每张贴图是 ARGB32 无 mipmap，像素块恰好 width*height*4 字节，且位于对象末尾。
定位到那段字节、原地覆盖，文件大小/对象表/偏移全部不变。

与 patch_textures.py 的区别
---------------------------
patch_textures 是按角色的 manifest 逐块贴回 sprite 区域；
这里是路线 B，`slice_back` 给出的**已经是整张图集**，所以整块像素直接替换，
不需要再按 atlas_rect 贴。alpha 会再和原图集比对一次，不一致就拒绝写入。

用法
----
    # 只检查，不写（默认）
    python tools/scripts/patch_scene_textures.py --level level4 \
        --redrawn out/redraw/level4_V2/redrawn.png

    # 真写（会先备份到 backup/pre_scene_<时间戳>/）
    python tools/scripts/patch_scene_textures.py --level level4 \
        --redrawn out/redraw/level4_V2/redrawn.png --apply

    # 回滚
    cp backup/pre_scene_<时间戳>/*.assets "D:/BaiduNetdiskDownload/意大利黑1/Guns, Gore and Cannoli/ggc_Data/"
"""
import argparse
import os
import shutil
import sys
import time

import numpy as np
import UnityPy
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import scene_stack as SS          # noqa: E402
from ggc_assets import DATA, BACKUP, PROJECT   # noqa: E402
from patch_textures import encode_argb32       # noqa: E402


def locate_pixel_block(obj, raw_old):
    """返回像素块在对象内的相对偏移；定位失败返回 None。"""
    expected = len(raw_old)
    obj_bytes = obj.get_raw_data()
    if len(obj_bytes) < expected:
        return None
    rel = len(obj_bytes) - expected
    if obj_bytes[rel:] == raw_old:
        return rel
    idx = obj_bytes.find(raw_old[:256])
    return idx if idx >= 0 else None


def _cands(arr):
    """给一个 HxWx4 的 uint8 数组，产出所有可能的原始字节排布。"""
    out = {}
    for rows in ("up", "down"):                 # up = 正序，down = 上下翻转
        a = arr if rows == "up" else arr[::-1]
        for order in ("ARGB", "BGRA", "RGBA", "RGB", "BGR"):
            idx = [{"A": 3, "R": 0, "G": 1, "B": 2}[c] for c in order]
            out[(rows, order)] = np.ascontiguousarray(a[..., idx]).tobytes()
    return out


def detect_encoder(full, obj):
    """用**现有字节**反推这张贴图的编码方式。

    不靠猜格式号：把解码后的图按所有通道排列/行序排一遍，谁和对象末尾的
    字节完全一致，谁就是这套编码。返回 (encode_fn, rel) 或 (None, None)。
    """
    arr = np.array(full, np.uint8)
    cands = _cands(arr)
    obj_bytes = obj.get_raw_data()
    for key, raw in sorted(cands.items(), key=lambda kv: len(kv[1])):
        if not raw:
            continue
        rel = len(obj_bytes) - len(raw)
        if rel < 0:
            continue
        if obj_bytes[rel:] == raw:
            rows, order = key

            def enc(img, _rows=rows, _order=order):
                a = np.array(img.convert("RGBA"), np.uint8)
                if _rows == "down":
                    a = a[::-1]
                idx = [{"A": 3, "R": 0, "G": 1, "B": 2}[c] for c in _order]
                return np.ascontiguousarray(a[..., idx]).tobytes()
            return enc, rel
    return None, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--level", default="level4")
    ap.add_argument("--redrawn", required=True)
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()

    redrawn = Image.open(a.redrawn).convert("RGB")
    db = SS.AssetDB(data_dir=DATA)
    items, W, H, atlases = SS.build_items(db, a.level)
    if redrawn.size != (W, H):
        print("重绘尺寸 %s 与画布 %s 不一致，终止" % (redrawn.size, (W, H)))
        return 1
    layers = SS.slice_back(items, atlases, redrawn, W, H)

    by_file = {}
    for (fname, pid), lay in layers.items():
        by_file.setdefault(fname, {})[pid] = lay["image"]
    print("%s: %d 张图集，分布在 %d 个文件" % (a.level, len(layers), len(by_file)))

    if a.apply:
        stamp = time.strftime("pre_scene_%Y%m%d_%H%M")
        bdir = os.path.join(BACKUP, stamp)
        os.makedirs(bdir, exist_ok=True)
        for fname in by_file:
            shutil.copy2(os.path.join(DATA, fname), os.path.join(bdir, fname))
        print("已备份到 %s" % bdir)

    ok = bad = 0
    for fname, jobs in sorted(by_file.items()):
        path = os.path.join(DATA, fname)
        env = UnityPy.load(path)
        objs = {o.path_id: o for o in env.objects}
        for pid, img in sorted(jobs.items()):
            obj = objs.get(pid)
            if obj is None:
                print("  [skip] %s:%s 对象不存在" % (fname, pid))
                bad += 1
                continue
            data = obj.read()
            fmt = int(data.m_TextureFormat)
            w, h = int(data.m_Width), int(data.m_Height)
            full = data.image.convert("RGBA")
            if full.size != (w, h):
                print("  [skip] %s:%s 尺寸异常 %s vs %s"
                      % (fname, pid, full.size, (w, h)))
                bad += 1
                continue

            enc, rel = detect_encoder(full, obj)
            if enc is None:
                print("  [skip] %s:%s 无法反推像素编码（格式 %d）" % (fname, pid, fmt))
                bad += 1
                continue

            new = img.convert("RGBA")
            if new.size != (w, h):
                new = new.resize((w, h), Image.LANCZOS)
            a_new = np.array(new, np.uint8)
            a_old = np.array(full, np.uint8)
            # alpha 是碰撞契约：带 alpha 的格式必须和原图集逐位一致，不一致就拒绝写
            if fmt == 5 and not np.array_equal(a_new[..., 3], a_old[..., 3]):
                print("  [skip] %s:%s alpha 与原图集不一致" % (fname, pid))
                bad += 1
                continue
            a_new[..., 3] = a_old[..., 3]

            raw_old = enc(full)
            raw_new = enc(Image.fromarray(a_new, "RGBA"))
            if len(raw_new) != len(raw_old):
                print("  [skip] %s:%s 编码长度变了" % (fname, pid))
                bad += 1
                continue
            if a.apply:
                with open(path, "r+b") as fh:
                    fh.seek(int(obj.byte_start) + rel)
                    fh.write(raw_new)
            ok += 1

    print("RESULT: %d 张%s，%d 张跳过%s"
          % (ok, "已写入" if a.apply else "可写", bad,
             "" if a.apply else "（这是检查模式，加 --apply 才真写）"))
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
