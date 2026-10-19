"""
asset_inventory.py — 使用 UnityPy 对游戏 .assets 做完整资源清单提取
产出：extracted/primary/asset_inventory.json + asset_inventory.md
依赖：UnityPy (pip install UnityPy)
"""
import UnityPy
import json
import os
import sys
from pathlib import Path
from collections import Counter, defaultdict

GAME_DATA = Path(r"D:\BaiduNetdiskDownload\意大利黑1\Guns, Gore and Cannoli\ggc_Data")
OUTPUT_DIR = Path(r"D:\AI\DAIGuns, Gore and Cannoli from WB\extracted\primary")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def scan_file(filepath):
    """扫描单个 .assets 文件，返回对象清单"""
    results = {
        "file": os.path.basename(filepath),
        "size": os.path.getsize(filepath),
        "unity_version": None,
        "objects": [],
        "type_counts": Counter(),
    }
    try:
        env = UnityPy.load(str(filepath))
        results["unity_version"] = getattr(env, "unity_version", None) or str(getattr(env, "version", "unknown"))
        
        for obj in env.objects:
            entry = {
                "path_id": obj.path_id,
                "type_id": obj.type_id,
                "type_name": obj.type.name if hasattr(obj, 'type') and obj.type else str(getattr(obj, 'type_name', 'Unknown')),
                "byte_size": getattr(obj, 'byte_size', getattr(obj, 'size', 0)),
            }
            # 尝试获取名称
            try:
                if hasattr(obj, 'read'):
                    data = obj.read()
                    if hasattr(data, 'm_Name'):
                        entry["name"] = data.m_Name
                    elif hasattr(data, 'name'):
                        entry["name"] = data.name
            except Exception:
                pass
            results["objects"].append(entry)
            results["type_counts"][entry["type_name"]] += 1
    except Exception as e:
        results["error"] = str(e)
    
    return results

def main():
    files = sorted(list(GAME_DATA.glob("*.assets")) + [GAME_DATA / "mainData"] + list(GAME_DATA.glob("level*")))
    
    all_results = []
    total_type_counts = Counter()
    
    print(f"=== Scanning {len(files)} files ===\n")
    
    for f in files:
        print(f"Scanning: {f.name} ({os.path.getsize(f):,} bytes)...", end=" ")
        result = scan_file(str(f))
        all_results.append(result)
        total_type_counts.update(result["type_counts"])
        
        print(f"{len(result['objects'])} objects, {len(result['type_counts'])} types")
        if result.get("unity_version"):
            print(f"  Unity version: {result['unity_version']}")
        
        # 逐文件保存对象清单
        file_json = OUTPUT_DIR / f"{f.name}_inventory.json"
        with open(file_json, "w", encoding="utf-8") as jf:
            json.dump(result, jf, indent=2, ensure_ascii=False, default=str)
    
    # 汇总
    summary = {
        "total_files": len(files),
        "total_objects": sum(len(r["objects"]) for r in all_results),
        "type_counts": dict(total_type_counts.most_common()),
        "unity_version": next((r["unity_version"] for r in all_results if r.get("unity_version")), "unknown"),
    }
    
    summary_json = OUTPUT_DIR / "asset_inventory.json"
    with open(summary_json, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    
    # 人类可读报告
    report = OUTPUT_DIR / "asset_inventory.md"
    with open(report, "w", encoding="utf-8") as f:
        f.write("# 资源清单 — Guns, Gore and Cannoli\n\n")
        f.write(f"**Unity 版本**: {summary['unity_version']}\n\n")
        f.write(f"**文件总数**: {summary['total_files']}\n\n")
        f.write(f"**对象总数**: {summary['total_objects']}\n\n")
        f.write("## 按类型统计\n\n")
        f.write("| 类型 | 数量 |\n|------|------|\n")
        for t, c in summary["type_counts"].items():
            f.write(f"| {t} | {c} |\n")
        f.write("\n## 各文件详情\n\n")
        for r in all_results:
            f.write(f"### {r['file']} ({r['size']:,} bytes)\n\n")
            if r.get("unity_version"):
                f.write(f"- Unity version: {r['unity_version']}\n")
            f.write(f"- Objects: {len(r['objects'])}\n")
            for t, c in r["type_counts"].items():
                f.write(f"  - {t}: {c}\n")
            f.write("\n")
    
    print(f"\n=== Summary ===")
    print(f"Total objects: {summary['total_objects']}")
    print(f"Unity version: {summary['unity_version']}")
    print(f"\nType counts:")
    for t, c in total_type_counts.most_common():
        print(f"  {t}: {c}")
    print(f"\nReports saved to {OUTPUT_DIR}")

if __name__ == "__main__":
    main()
