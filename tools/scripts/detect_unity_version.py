"""
detect_unity_version.py — 读取 .assets 文件二进制头，检测 Unity 引擎版本
不依赖 UnityPy，直接读字节。用于 M1 逆向文档的引擎版本确认。
"""
import struct
import sys
import os
import json
from pathlib import Path

GAME_DATA = Path(r"D:\BaiduNetdiskDownload\意大利黑1\Guns, Gore and Cannoli\ggc_Data")

def read_assets_header(filepath):
    """读取 Unity .assets 文件头部信息"""
    info = {"file": os.path.basename(filepath), "size": os.path.getsize(filepath)}
    try:
        with open(filepath, "rb") as f:
            header = f.read(256)
            # 检查 magic / 格式标识
            # Unity 5.x+ 用 "UnityFS" (bundle) 或直接是 .assets 原始格式
            # 原始 .assets 格式: [metadata_size(4)] [file_size(4)] [version(4)] [data_offset(4)]
            magic = header[:7]
            info["magic_ascii"] = magic.decode("ascii", errors="replace")

            if magic[:6] == b"UnityFS":
                info["format"] = "UnityFS (Bundle)"
                # Bundle format: UnityFS + version + ... 
                # 读版本字符串
                f.seek(0)
                f.read(7)  # UnityFS\0
                version_bytes = f.read(4)
                info["bundle_version"] = struct.unpack(">i", version_bytes)[0]
                # 读 Unity 版本字符串
                unity_ver_len = struct.unpack(">i", f.read(4))[0]
                unity_ver = f.read(unity_ver_len).decode("utf-8", errors="replace")
                info["unity_version"] = unity_ver
            else:
                info["format"] = "Raw .assets"
                # 原始 assets 格式
                # 尝试读取 metadata
                # header: int32 metadata_size, int32 file_size, int32 version, ...
                if len(header) >= 16:
                    metasize, filesize, version = struct.unpack(">III", header[:12])
                    info["metadata_size"] = metasize
                    info["file_size_field"] = filesize
                    info["version_field"] = version
                    # 试试 little-endian
                    metasize_le, filesize_le, version_le = struct.unpack("<III", header[:12])
                    info["version_field_le"] = version_le

            # 搜索所有可读字符串中的版本号
            with open(filepath, "rb") as f2:
                data = f2.read(4096)  # 只读前 4KB 找版本
                for i in range(len(data) - 20):
                    chunk = data[i:i+20]
                    try:
                        s = chunk.decode("ascii")
                        if "201" in s and "." in s:
                            # 找类似 2017.x.xfx 的版本
                            import re
                            m = re.search(r"(201[0-9]\.\d+\.\d+[a-z]\d+|5\.\d+\.\d+[a-z]\d+)", s)
                            if m:
                                info["found_version_string"] = m.group(1)
                                break
                    except:
                        pass
    except Exception as e:
        info["error"] = str(e)
    return info

def main():
    results = []
    # 检查所有 .assets 文件
    assets_files = sorted(GAME_DATA.glob("*.assets"))
    # 也检查 level 文件和 mainData
    other_files = [GAME_DATA / "mainData"]
    other_files += sorted(GAME_DATA.glob("level*"))

    all_files = assets_files + other_files

    print(f"=== Scanning {len(all_files)} files ===\n")
    for f in all_files:
        info = read_assets_header(str(f))
        results.append(info)
        print(f"File: {info['file']} ({info['size']:,} bytes)")
        for k, v in info.items():
            if k not in ("file", "size"):
                print(f"  {k}: {v}")
        print()

    # 输出 JSON
    out_path = Path(r"D:\AI\Guns, Gore and Cannoli from WB\extracted\primary\version_detection.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\n=== JSON saved to {out_path} ===")

if __name__ == "__main__":
    main()
