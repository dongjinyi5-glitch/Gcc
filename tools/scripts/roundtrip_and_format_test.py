"""
roundtrip_and_format_test.py — 黄金回路往返测试 + 纹理格式分析
1. 加载小 .assets 文件 → 不修改 → 保存 → SHA-256 比对
2. 解析所有 Texture2D 的格式/尺寸/压缩类型
3. 提取一个样本纹理为 PNG 供检查
"""
import UnityPy
import json
import hashlib
import os
import sys
from pathlib import Path
from collections import Counter

GAME_DATA = Path(r"D:\BaiduNetdiskDownload\意大利黑1\Guns, Gore and Cannoli\ggc_Data")
OUTPUT_DIR = Path(r"D:\AI\Guns, Gore and Cannoli from WB")
EXTRACT_DIR = OUTPUT_DIR / "extracted" / "primary"
VALIDATION_DIR = OUTPUT_DIR / "validation"
VALIDATION_DIR.mkdir(parents=True, exist_ok=True)

# Unity TextureFormat 常见值映射
TEXTURE_FORMAT_MAP = {
    1: "Alpha8",
    3: "RGB24",
    4: "RGBA32",
    5: "ARGB32",
    10: "DXT1",
    12: "DXT5",
    13: "RGBA16f",
    25: "BC4",
    27: "BC5",
    29: "DXT1Crunched",
    41: "ETC_RGB4",
    42: "ETC2_RGB",
    43: "ETC2_RGBA1",
    44: "ETC2_RGBA8",
    47: "PVRTC_RGB2",
    50: "ASTC_RGBA_6x6",
}

def sha256_file(filepath):
    """计算文件 SHA-256"""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while True:
            chunk = f.read(65536)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()

def test_roundtrip(filepath):
    """黄金回路往返测试：复制→加载→关闭 reader 句柄→保存→与原始比对。"""
    import shutil
    import tempfile

    result = {"file": os.path.basename(filepath), "size": os.path.getsize(filepath)}
    original_hash = sha256_file(filepath)
    result["original_sha256"] = original_hash

    tmpdir = None
    try:
        tmpdir = tempfile.mkdtemp(prefix="roundtrip_")
        tmp_input = os.path.join(tmpdir, os.path.basename(filepath))
        shutil.copy2(filepath, tmp_input)

        env = UnityPy.load(tmp_input)
        result["original_object_count"] = len(env.objects)
        result["original_types"] = dict(Counter(o.type.name for o in env.objects))

        # 关键：关闭 reader 的文件句柄，否则 save 会报 WinError 32
        if hasattr(env.file, 'reader') and hasattr(env.file.reader, 'stream'):
            env.file.reader.stream.close()

        # UnityPy 4.x save：覆盖原临时文件
        env.save(pack=False)

        output_hash = sha256_file(tmp_input)
        result["output_sha256"] = output_hash
        result["byte_identical"] = (original_hash == output_hash)
        result["output_size"] = os.path.getsize(tmp_input)

        # 语义比对
        env2 = UnityPy.load(tmp_input)
        result["output_object_count"] = len(env2.objects)
        result["object_count_match"] = (len(env2.objects) == len(env.objects))

        types1 = Counter(o.type.name for o in env.objects)
        types2 = Counter(o.type.name for o in env2.objects)
        result["types_match"] = (types1 == types2)
        result["output_types"] = dict(types2)

    except Exception as e:
        result["error"] = str(e)
    finally:
        if tmpdir and os.path.exists(tmpdir):
            shutil.rmtree(tmpdir, ignore_errors=True)

    return result


def test_texture_roundtrip(filepath, max_textures=3):
    """纹理级往返测试：Texture2D → PNG → 重设为 Texture2D → 验证"""
    results = []
    try:
        env = UnityPy.load(str(filepath))
        count = 0
        for obj in env.objects:
            if obj.type.name == "Texture2D":
                try:
                    d = obj.read()
                    name = getattr(d, "m_Name", getattr(d, "name", f"tex_{obj.path_id}"))
                    if not d.image:
                        continue
                    
                    # 保存原始 PNG
                    original_png = VALIDATION_DIR / f"texrt_orig_{count}.png"
                    d.image.save(str(original_png))
                    
                    # 重新加载 PNG 并设为纹理（UnityPy 自动处理）
                    from PIL import Image
                    new_img = Image.open(str(original_png))
                    d.image = new_img
                    
                    # 提取新纹理为 PNG
                    new_png = VALIDATION_DIR / f"texrt_reimport_{count}.png"
                    d.image.save(str(new_png))
                    
                    # 比较原始 PNG 和重新导入后的 PNG
                    h1 = sha256_file(str(original_png))
                    h2 = sha256_file(str(new_png))
                    
                    results.append({
                        "name": name,
                        "original_png": str(original_png),
                        "reimport_png": str(new_png),
                        "sha256_match": (h1 == h2),
                        "original_size": f"{d.m_Width}x{d.m_Height}",
                        "format": TEXTURE_FORMAT_MAP.get(d.m_TextureFormat, f"Unknown({d.m_TextureFormat})")
                    })
                    
                    count += 1
                    if count >= max_textures:
                        break
                except Exception as e:
                    results.append({"name": f"error_{count}", "error": str(e)})
                    count += 1
    except Exception as e:
        return [{"error": str(e)}]
    return results

def analyze_textures(filepath, max_textures=None):
    """分析 Texture2D 格式/尺寸/压缩"""
    results = []
    try:
        env = UnityPy.load(str(filepath))
        count = 0
        for obj in env.objects:
            if obj.type.name == "Texture2D":
                try:
                    d = obj.read()
                    tex_info = {
                        "name": getattr(d, "m_Name", getattr(d, "name", "unknown")),
                        "width": getattr(d, "m_Width", 0),
                        "height": getattr(d, "m_Height", 0),
                        "format_id": getattr(d, "m_TextureFormat", 0),
                        "format_name": TEXTURE_FORMAT_MAP.get(
                            getattr(d, "m_TextureFormat", 0),
                            f"Unknown({getattr(d, 'm_TextureFormat', 0)})"
                        ),
                        "mip_count": getattr(d, "m_MipCount", getattr(d, "m_MipMapBias", 0)),
                    }
                    results.append(tex_info)
                    count += 1
                    if max_textures and count >= max_textures:
                        break
                except Exception:
                    pass
    except Exception as e:
        return [{"error": str(e)}]
    return results

def extract_sample_texture(filepath, output_dir, max_samples=5):
    """提取样本纹理为 PNG"""
    extracted = []
    try:
        env = UnityPy.load(str(filepath))
        count = 0
        for obj in env.objects:
            if obj.type.name == "Texture2D":
                try:
                    d = obj.read()
                    name = getattr(d, "m_Name", getattr(d, "name", f"tex_{obj.path_id}"))
                    img = d.image  # UnityPy 自动解码为 PIL Image
                    if img and count < max_samples:
                        safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in name)
                        out_path = output_dir / f"{safe_name}.png"
                        img.save(str(out_path))
                        extracted.append({"name": name, "path": str(out_path), 
                                        "size": f"{img.width}x{img.height}"})
                        count += 1
                except Exception:
                    pass
    except Exception as e:
        return [{"error": str(e)}]
    return extracted

def main():
    print("=" * 60)
    print("M1: 黄金回路往返测试 + 纹理格式分析")
    print("=" * 60)

    # === 1. 往返测试（使用小文件） ===
    print("\n=== 1. 黄金回路往返测试 ===\n")
    test_files = [
        GAME_DATA / "sharedassets1.assets",   # 15MB, 15 objects
        GAME_DATA / "sharedassets3.assets",    # 4KB, 1 object
        GAME_DATA / "sharedassets10.assets",   # 88MB, 73 objects
    ]
    
    roundtrip_results = []
    for f in test_files:
        if not f.exists():
            continue
        print(f"Testing: {f.name} ({os.path.getsize(f):,} bytes)...")
        result = test_roundtrip(str(f))
        roundtrip_results.append(result)
        print(f"  SHA-256 match: {result.get('byte_identical', 'N/A')}")
        if not result.get("byte_identical", True):
            print(f"  Object count match: {result.get('object_count_match', 'N/A')}")
            print(f"  Types match: {result.get('types_match', 'N/A')}")
        for k, v in result.items():
            if k not in ("file", "size", "original_sha256", "output_sha256"):
                print(f"  {k}: {v}")

    # === 1b. 纹理级往返测试 ===
    print("\n=== 1b. 纹理级往返测试 (Texture2D → PNG → re-import) ===\n")
    texture_rt_results = test_texture_roundtrip(
        str(GAME_DATA / "resources.assets"),
        max_textures=3
    )
    for r in texture_rt_results:
        if "name" in r:
            print(f"Texture: {r['name']} ({r.get('original_size', 'n/a')})")
            print(f"  SHA-256 match after PNG re-import: {r.get('sha256_match', 'N/A')}")
        else:
            print(f"Error: {r}")

    # === 2. 纹理格式分析 ===
    print("\n=== 2. 纹理格式分析 ===\n")
    
    # 分析 resources.assets 和几个 sharedassets
    tex_analysis_files = [
        ("resources.assets", GAME_DATA / "resources.assets"),
        ("sharedassets4.assets", GAME_DATA / "sharedassets4.assets"),
        ("sharedassets11.assets", GAME_DATA / "sharedassets11.assets"),
    ]
    
    all_tex_info = []
    format_counts = Counter()
    
    for label, f in tex_analysis_files:
        if not f.exists():
            continue
        print(f"Analyzing textures in {f.name}...")
        texs = analyze_textures(str(f), max_textures=200)
        print(f"  Found {len(texs)} textures")
        for t in texs:
            all_tex_info.append({"source": f.name, **t})
            format_counts[t["format_name"]] += 1
    
    print(f"\nTexture format distribution:")
    for fmt, c in format_counts.most_common():
        print(f"  {fmt}: {c}")
    
    # 尺寸统计
    sizes = [(t["width"], t["height"]) for t in all_tex_info if t["width"] > 0]
    if sizes:
        size_counts = Counter(sizes)
        print(f"\nTexture size distribution (top 15):")
        for (w, h), c in size_counts.most_common(15):
            print(f"  {w}x{h}: {c}")

    # === 3. 提取样本纹理 ===
    print("\n=== 3. 提取样本纹理 ===\n")
    
    sample_dir = EXTRACT_DIR / "sample_textures"
    sample_dir.mkdir(parents=True, exist_ok=True)
    
    # 从 resources.assets 提取
    samples = extract_sample_texture(
        str(GAME_DATA / "resources.assets"),
        sample_dir,
        max_samples=10
    )
    print(f"Extracted {len(samples)} sample textures:")
    for s in samples:
        if "name" in s:
            print(f"  {s['name']} ({s['size']}) -> {s['path']}")

    # === 保存结果 ===
    size_dist = Counter((t["width"], t["height"]) for t in all_tex_info if t["width"] > 0).most_common(20)
    size_dist_serializable = {f"{w}x{h}": c for (w, h), c in size_dist}

    report = {
        "roundtrip_tests": roundtrip_results,
        "texture_roundtrip": texture_rt_results,
        "texture_analysis": {
            "total_analyzed": len(all_tex_info),
            "format_distribution": dict(format_counts.most_common()),
            "size_distribution": size_dist_serializable,
            "samples": all_tex_info[:50],
        },
        "extracted_samples": samples,
    }
    
    report_path = VALIDATION_DIR / "roundtrip_and_format_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False, default=str)
    
    # 人类可读报告
    md_path = VALIDATION_DIR / "ROUNDTRIP_REPORT.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# 黄金回路往返测试 + 纹理格式分析报告\n\n")
        f.write(f"**日期**: 2026-10-19\n")
        f.write(f"**执行者**: Agent B (Developer) + Agent C (QA)\n\n")
        
        f.write("## 1. 黄金回路往返测试\n\n")
        f.write("| 文件 | 原始大小 | 字节一致 | 对象数一致 | 类型一致 |\n")
        f.write("|------|----------|---------|-----------|---------|\n")
        for r in roundtrip_results:
            f.write(f"| {r['file']} | {r['size']:,} | {'✅' if r.get('byte_identical') else '❌'} | "
                    f"{'✅' if r.get('object_count_match') else '—'} | "
                    f"{'✅' if r.get('types_match') else '—'} |\n")
        f.write("\n")
        for r in roundtrip_results:
            f.write(f"### {r['file']}\n\n")
            for k, v in r.items():
                f.write(f"- {k}: `{v}`\n")
            f.write("\n")
        
        f.write("## 1b. 纹理级往返测试\n\n")
        f.write("| 纹理名 | 尺寸 | 格式 | PNG 重导入一致 |\n")
        f.write("|--------|------|------|----------------|\n")
        for r in texture_rt_results:
            if "name" in r:
                f.write(f"| {r['name']} | {r.get('original_size', '')} | {r.get('format', '')} | "
                        f"{'✅' if r.get('sha256_match') else '❌'} |\n")
        f.write("\n")

        f.write("## 2. 纹理格式分析\n\n")
        f.write(f"**分析纹理总数**: {len(all_tex_info)}\n\n")
        f.write("### 格式分布\n\n")
        f.write("| 格式 | 数量 |\n|------|------|\n")
        for fmt, c in format_counts.most_common():
            f.write(f"| {fmt} | {c} |\n")
        f.write("\n### 尺寸分布 (Top 20)\n\n")
        f.write("| 尺寸 | 数量 |\n|------|------|\n")
        for (w, h), c in size_dist:
            f.write(f"| {w}x{h} | {c} |\n")
        
        f.write("\n## 3. 提取的样本纹理\n\n")
        f.write("| 名称 | 尺寸 | 路径 |\n|------|------|------|\n")
        for s in samples:
            if "name" in s:
                f.write(f"| {s['name']} | {s['size']} | {s['path']} |\n")
    
    print(f"\n=== Reports saved ===")
    print(f"  JSON: {report_path}")
    print(f"  MD: {md_path}")

if __name__ == "__main__":
    main()
