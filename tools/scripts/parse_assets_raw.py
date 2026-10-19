"""
parse_assets_raw.py — 不依赖 UnityPy 的 .assets 对象表解析器
直接读取 Unity SerializedFile 二进制格式，提取对象类型与数量。
用于 UnityPy 安装完成前的初步资源清单。
"""
import struct
import os
import json
from pathlib import Path
from collections import Counter

GAME_DATA = Path(r"D:\BaiduNetdiskDownload\意大利黑1\Guns, Gore and Cannoli\ggc_Data")
OUTPUT_DIR = Path(r"D:\AI\DAIGuns, Gore and Cannoli from WB\extracted\primary")

# Unity Class ID -> Type Name 映射（常见类型）
CLASS_ID_MAP = {
    1: "GameObject",
    4: "Transform",
    21: "Material",
    28: "Texture2D",
    48: "Shader",
    49: "TextAsset",
    74: "AnimationClip",
    83: "AudioClip",
    114: "MonoBehaviour",
    115: "MonoScript",
    128: "Font",
    142: "AssetBundleInfo",
    150: "PreloadData",
    184: "Sprite",
    199: "SpriteAtlas",
    212: "SpriteRenderer",
    221: "AnimatorController",
    224: "RectTransform",
    225: "Canvas",
    238: "AudioListener",
    254: "Mesh",
    1024: "MeshCollider",
    1025: "BoxCollider",
    1027: "Rigidbody",
    1028: "EdgeCollider",
    1029: "PolygonCollider2D",
    1040: "PhysicsMaterial2D",
    1045: "Animator",
    1046: "Animation",
    1084: "SortingGroup",
    1090: "SpriteMask",
    1180: "SpriteAtlas",
}

def read_serialized_file(filepath):
    """解析 Unity SerializedFile 格式（version 9, Unity 5.x）"""
    info = {"file": os.path.basename(filepath), "size": os.path.getsize(filepath)}
    
    with open(filepath, "rb") as f:
        # === Header ===
        header = f.read(20)
        metadata_size, file_size, version, data_offset = struct.unpack(">IIII", header[:16])
        endianness = header[16] if len(header) > 16 else 1
        
        info["metadata_size"] = metadata_size
        info["version"] = version
        info["data_offset"] = data_offset
        info["endianness"] = endianness  # 0=big, 1=little
        
        if version != 9:
            info["warning"] = f"Expected version 9, got {version}"
            return info
        
        # === Metadata block ===
        # 元数据从 header 之后开始（offset ~20 or 16）
        # 尝试在 offset 16 处读
        f.seek(16)
        # 读 endianness flag + reserved
        endian_flag = struct.unpack("B", f.read(1))[0]
        reserved = f.read(3)
        metadata_start = f.tell()
        
        # 解析 TypeTree（如果有）
        # 对于 version 9, 先读 TypeTree enabled flag 或直接读类型数量
        objects = []
        type_counts = Counter()
        
        try:
            # 尝试读取对象信息表
            # 在 Unity 5.x 中, metadata 结构:
            # 1. TypeTree (如果存在): int32 type_count, 然后每个类型定义
            # 2. ObjectInfo: int32 object_count, 然后每个: alignedInt(pathID), int(offset), int(size), int(typeID), int(classID), int(script_type)
            
            # 先尝试读取类型树
            # 在有 TypeTree 的情况下，需要跳过整个类型树
            # 尝试直接跳到对象表（搜索模式）
            
            # 方法：在 metadata 区域搜索对象表
            # 对象表以一个 int32 (对象数量) 开头，后面跟着对象条目
            # 我们尝试从 metadata_start 开始读类型数量
            
            f.seek(metadata_start)
            type_count = struct.unpack(">i", f.read(4))[0]
            
            if type_count < 0 or type_count > 100000:
                # 可能没有类型树，直接是对象表
                # 或者格式不同，尝试其他偏移
                info["parse_status"] = "type_tree_skipped"
                # 尝试直接搜索对象表
                # 跳过整个 metadata 块，记录文件大小
                pass
            else:
                info["type_count"] = type_count
                # 尝试跳过类型树
                # 每个类型定义的大小不固定，需要逐个解析
                # 这里用简化方法：扫描 metadata 区域找对象表
                
                # 保存当前位置
                pos = f.tell()
                # 读取剩余 metadata
                remaining_meta = metadata_size - (pos - metadata_start)
                meta_data = f.read(remaining_meta)
                
                # 在 metadata 中搜索对象表
                # 对象表: int32 count, 然后 count 个条目
                # 每个条目在 version 9 中: int64 pathID + int32 offset + int32 size + int32 typeID(+classID?)
                # 条目大小 = 8 + 4 + 4 + 4 + 4 = 24 bytes (version 9 with script type)
                # 或 8 + 4 + 4 + 4 = 20 bytes (无 script type)
                
                # 尝试在元数据末尾附近找对象表
                # 对象表通常在元数据的最后部分
                for try_offset in range(len(meta_data) - 4, 0, -4):
                    try:
                        count = struct.unpack(">i", meta_data[try_offset:try_offset+4])[0]
                        if 1 <= count <= 1000000:
                            # 验证：后面的数据是否像对象条目
                            test_pos = try_offset + 4
                            if test_pos + 20 <= len(meta_data):
                                # 读第一个条目
                                entry = meta_data[test_pos:test_pos+24]
                                if len(entry) >= 20:
                                    path_id = struct.unpack(">q", entry[:8])[0]
                                    offset = struct.unpack(">I", entry[8:12])[0]
                                    size = struct.unpack(">I", entry[12:16])[0]
                                    type_id = struct.unpack(">i", entry[16:20])[0]
                                    
                                    # 验证合理性
                                    if offset < file_size and size < file_size and 0 <= type_id < 50000:
                                        # 可能找到了对象表
                                        objects_start = try_offset
                                        info["objects_found_at"] = metadata_start + objects_start
                                        
                                        # 读取所有对象
                                        f.seek(metadata_start + objects_start)
                                        obj_count = struct.unpack(">i", f.read(4))[0]
                                        
                                        for i in range(obj_count):
                                            entry_bytes = f.read(24)  # 尝试24字节条目
                                            if len(entry_bytes) < 20:
                                                break
                                            pid = struct.unpack(">q", entry_bytes[:8])[0]
                                            off = struct.unpack(">I", entry_bytes[8:12])[0]
                                            sz = struct.unpack(">I", entry_bytes[12:16])[0]
                                            tid = struct.unpack(">i", entry_bytes[16:20])[0]
                                            cid = struct.unpack(">i", entry_bytes[20:24])[0] if len(entry_bytes) >= 24 else tid
                                            
                                            type_name = CLASS_ID_MAP.get(cid, CLASS_ID_MAP.get(tid, f"TypeID_{tid}"))
                                            objects.append({
                                                "path_id": pid,
                                                "offset": off,
                                                "size": sz,
                                                "type_id": tid,
                                                "class_id": cid,
                                                "type_name": type_name,
                                            })
                                            type_counts[type_name] += 1
                                        
                                        info["object_count"] = len(objects)
                                        info["type_counts"] = dict(type_counts.most_common())
                                        break
                    except:
                        continue
                
                if not objects:
                    info["parse_status"] = "object_table_not_found"
        except Exception as e:
            info["error"] = str(e)
    
    return info

def main():
    files = sorted(list(GAME_DATA.glob("*.assets")) + [GAME_DATA / "mainData"])
    
    print(f"=== Parsing {len(files)} files (raw binary, no UnityPy) ===\n")
    
    all_results = []
    total_counts = Counter()
    
    for f in files:
        print(f"Parsing: {f.name} ({os.path.getsize(f):,} bytes)...", end=" ")
        result = read_serialized_file(str(f))
        all_results.append(result)
        
        if "type_counts" in result:
            total_counts.update(Counter(result["type_counts"]))
            print(f"{result.get('object_count', 0)} objects")
        else:
            print(f"status: {result.get('parse_status', result.get('error', 'unknown'))}")
    
    # 汇总
    print(f"\n=== Summary ===")
    print(f"Total objects: {sum(r.get('object_count', 0) for r in all_results)}")
    print(f"\nType counts:")
    for t, c in total_counts.most_common():
        print(f"  {t}: {c}")
    
    # 保存 JSON
    out = OUTPUT_DIR / "raw_asset_inventory.json"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as jf:
        json.dump(all_results, jf, indent=2, ensure_ascii=False, default=str)
    print(f"\nSaved to {out}")

if __name__ == "__main__":
    main()
