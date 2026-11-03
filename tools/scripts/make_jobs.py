# -*- coding: utf-8 -*-
"""T1 重绘作业生成器 —— 把「目标形态」写成能直接用的提示词。

为什么提示词是中文
------------------
Qwen-Image-Edit 对中文语义的理解远好于英文，而且我们要的题材
（惠通桥、远征军、松山坑道）本来就是中文美术史里的东西。英文提示词会把它
推向"西方概念画"的路子，中文才可能落到重彩国画上。

三段式提示词
------------
1. **画什么** —— 目标形态句（来自 redraw_targets.py，已过用户确认）
2. **怎么画** —— 重彩国画规格：笔触、颜料、纸、留白
3. **不许动什么** —— 构图与剪影锁定（这是白描底稿的用途）

"不许动"这一段是关键。模型在 Qwen-Image-Edit 上默认会重新构图，
必须显式说"严格保持这张白描线稿的轮廓、位置、比例不变"，否则底稿就白做了。
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 重彩国画的通用规格（用户 2026-10-19 定：重彩、笔触中等粗细）
STYLE = ("中国重彩国画风格，工笔重彩，宣纸底色，"
         "笔触中等粗细，线条劲挺有骨，"
         "用石青、石绿、赭石、朱砂、花青、藤黄、墨色层层罩染，"
         "墨线勾勒轮廓并有浓淡干湿变化，"
         "暗部用淡墨积染，亮处留白透出纸色")

NEGATIVE = ("照片, 3D渲染, 油画厚涂, 动漫, 卡通, 线稿, 黑白, "
            "现代建筑, 现代车辆, 英文, 文字, 水印, 签名, "
            "变形, 错位, 模糊, 过曝, 纯白背景")

# 不许动：白描底稿存在的全部理由
LOCK = ("严格保持这张白描线稿的轮廓、位置、比例、结构完全不变，"
        "只按线稿上色，不要重新构图，不要增删任何形体，"
        "不要移动任何线条")


def prompt_for(goal, extra=""):
    """目标形态句 -> 完整提示词。"""
    parts = [goal]
    if extra:
        parts.append(extra)
    parts.append(STYLE)
    parts.append(LOCK)
    return "。".join(p for p in parts if p) + "。"


# 逐个构件的具体描述（关卡 × 构件）。
# 键是 (关卡, 构件名)；写不到的就用 redraw_targets 的类别句。
SPECIFIC = {
    ("level9", "bridge01"): "1942年5月5日被日军炸断的惠通桥单孔钢桁桥："
                           "炸弯的铆接钢桁梁从桥墩上断裂垂落，"
                           "断口处钢板卷边翘起，一段桥面板坠入江中，"
                           "桥面铺板散落，桥墩为混凝土圆墩，"
                           "墩下堆着崩塌的碎石",
    ("level9", "bridge08"): "惠通桥炸断后的钢桁梁特写：铆接腹杆与断口卷边",
    ("level9", "bridge07"): "惠通桥钢桁桥的桥面与栏杆残骸",
    ("level9", "bridge09"): "惠通桥炸桥后坠落的钢构与江面激浪",
    ("level9", "bridge03"): "惠通桥桥台与引桥残段",
    ("level9", "bridge03Front"): "惠通桥断口正面的钢桁梁阵",
}


def build_job(level, name, goal, model="Qwen/Qwen-Image-Edit-2509",
              size="1024x1024", seed=7, steps=30, guidance=7.0,
              image=None, alpha_key=None):
    """一个构件 -> 一个生图任务。"""
    p = prompt_for(goal, SPECIFIC.get((level, name), ""))
    job = {"name": name, "model": model, "prompt": p,
           "negative_prompt": NEGATIVE, "size": size, "seed": seed,
           "steps": steps, "guidance": guidance}
    if image:
        job["image"] = image
    if alpha_key:
        job["alpha_key"] = alpha_key
    return job


def main():
    # 用法： python make_jobs.py <level> <name> <goal> <lineart_png>
    if len(sys.argv) < 6:
        print(__doc__)
        print("用法: make_jobs.py <level> <name> <goal> <lineart.png> "
              "[out.json] [alpha_key]")
        return
    level, name, goal, lineart = sys.argv[1:5]
    out = sys.argv[5] if len(sys.argv) > 5 else "art/gen/jobs.json"
    akey = sys.argv[6] if len(sys.argv) > 6 else None
    job = build_job(level, name, goal, image=lineart, alpha_key=akey)
    json.dump([job], open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("job ->", out)
    print(job["prompt"])


if __name__ == "__main__":
    main()
