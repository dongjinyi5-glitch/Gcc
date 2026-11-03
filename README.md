# Guns, Gore and Cannoli — 国画重彩资产替换

把《Guns, Gore and Cannoli》（GOG 版，Unity 4.3.4f1，Mono 后端）的角色与场景美术，
在**不改动游戏逻辑、不改变文件长度**的前提下，替换成重彩国画风格，并把题材改造为
中国远征军 / 二战日军（面部全部虚构，不使用任何真实人物相貌）。

- 42 个战斗单位，1,112 张贴图
- 12 个战役关卡 + 主菜单动态背景，按关卡分 13 批（`level3`–`level14` 为战役关卡，`level0` 为菜单背景），按图层逐层处理
- 所有写入都是**定点字节覆盖**：`.assets` 文件长度永远不变

> **操作前必读**：`AGENTS.md`（10 条硬约束 + 角色职责）和 `docs/REVERSE_ENGINEERING.md`（逆向结论）。
> 违反其中任何一条都会静默产出错误结果——不报错，只是画错。

---

## 目录结构

```
.
├── AGENTS.md                  AI 操作前必读：硬约束、角色职责、里程碑
├── DECISION_LOG.md            决策日志（每个决定的依据）
├── README.md                  本文件
├── requirements.txt           Python 依赖（4 个包，实测版本）
│
├── docs/                      文档（索引见 docs/README.md）
│   ├── README.md              36 份文档的主题索引
│   ├── CAP-014_INDEX.md       CAP-014 防护方案：版本链、权威版本与状态
│   ├── REVERSE_ENGINEERING.md 引擎与 .assets 格式的逆向结论
│   ├── STYLE_SPEC.md          重彩量化验收基准
│   └── CAP-014_P1_PLAN_v6 … v8.3_CANDIDATE   计划文档全代次（原地保留）
│
├── tools/                     脚本（索引与职责分类见 tools/README.md）
│   ├── scripts/               91 个 .py + 2 个 .ps1，全部脚本都在这里
│   ├── bin/                   外部工具二进制（不入库）
│   └── logs/                  运行日志（不入库）
│
├── tests/                     安全测试（只读，无副作用）
│
├── art/                       美术产物
│   ├── <char>_parts/          每个角色的部件提取 + 重绘（交付物，入库）
│   ├── hats/                  Hat 贴图
│   ├── scene_shots/           实机截图＝验收证据（不可再生，入库）
│   ├── chapter_cards/         章节卡（可能作为交付物，入库）
│   ├── l3_brief/              L3 简报参考图
│   ├── scene_restyle/         场景重绘产物（可再生，不入库）
│   ├── scene_sheets/          整层合成图（可再生，不入库）
│   ├── component_thumbs/      构件缩略图（可再生，不入库）
│   └── gen/                   生图模型原始输出（不入库）
│
├── extracted/                 UnityPy 提取输出
├── validation/                验收报告与度量 JSON
├── backup/                    原始 .assets 备份与结构回滚快照（不入库）
├── out/                       探针与临时产物（可再生，不入库）
└── coordination/              任务状态
```

---

## 环境依赖

**Python 3.13** + 4 个包（版本见 `requirements.txt`，均为实测值，未做升级）：

| 包 | 版本 | 用途 |
|---|---|---|
| `Pillow` | 13.0.0 | 图像处理（58 个脚本用到） |
| `numpy` | 2.5.4 | 数组运算（31 个） |
| `UnityPy` | 1.25.4 | .assets 解析（13 个）。**只能读，不能 `env.save()`** |
| `openpyxl` | 3.1.5 | 表格读写（8 个） |

本项目使用的解释器：

```
C:\Users\Dell\.workbuddy-ai\binaries\python\envs\daiggc\Scripts\python.exe
```

安装：

```bash
python -m pip install -r requirements.txt
```

---

## 已知限制

**游戏路径与项目路径是硬编码的**，写在 `tools/scripts/ggc_assets.py` 顶部的常量里：

```python
DATA    = r"D:\BaiduNetdiskDownload\意大利黑1\Guns, Gore and Cannoli\ggc_Data"
PROJECT = r"D:\AI\Guns, Gore and Cannoli from WB"
BACKUP  = os.path.join(PROJECT, "backup")
```

- 换机器 / 换盘符时必须手工改这几行，**没有环境变量或配置文件覆盖机制**
- 另有 14 个脚本各自硬编码了游戏路径，未统一到 `ggc_assets`
- 本轮整理**只记录、未修改**这套路径逻辑（改它属于业务改动，需单独授权与回归验证）

---

## 常用工作流

### A. 角色：提取 → 重绘 → 回填 → 验收

```bash
# 1. 提取角色全部件（含未激活变体）—— 角色名是位置参数
python tools/scripts/extract_parts.py Vinnie

# 2. 重绘（逐像素改色 + 笔触，改不了轮廓）
python tools/scripts/restyle_ink.py preview     # 代表部件出对照表
python tools/scripts/restyle_ink.py batch       # 全部件 + 烘焙帧

# 3. 门禁：风格指标 + 几何保真（越界退出码 1）
python tools/scripts/acceptance.py Vinnie --faction 人类 --role 远征军

# 4. 回填：默认是 CHECK，加 --apply 才写（定点字节覆盖）
python tools/scripts/patch_textures.py Vinnie --check
python tools/scripts/patch_textures.py Vinnie --apply

# 5. 从打完补丁的游戏文件渲染，作为实机证据
python tools/scripts/render_ingame.py Vinnie
```

### B. 场景：整层合成 → 重绘 → 按层切回（路线 B）

```bash
python tools/scripts/scene_stack.py --level level4 --build     # 合成整层图
python tools/scripts/scene_stack.py --level level4 --verify    # 零成本自检
python tools/scripts/scene_stack.py --level level4 --slice out/stack/level4/redrawn.png
python tools/scripts/preview_sliced.py --level level4          # 复算"游戏里会看到的样子"
```

### C. 场景：程序化重彩（路线 A，不调模型）

```bash
python tools/scripts/restyle_scene.py preview        # 代表贴图出对照表
python tools/scripts/restyle_scene.py level level4   # 某关卡全部贴图（level 子命令）
python tools/scripts/restyle_scene.py stats          # 出图后复算指标
```

> 脚本的职责分类、依赖关系与入口清单见 `tools/README.md`。
> 分类目前**只是文档**，脚本物理上仍全部位于 `tools/scripts/`。

---

## 运行验证

**安全测试**（只读：不写文件、不联网、不读 `.secrets/`、不加载大型游戏资源）：

```bash
python -m unittest discover -s tests -v
```

覆盖内容：42 单位身份表、兵种颜料表一致性、构件分档、白描 Sobel 算子、
单元格富文本往返，以及**目录结构完整性**（每个脚本的本地 `import` 都能解析到
`tools/scripts/` 下的真实文件、`tools/` 下无残留分类目录）。

**不要**用跑业务脚本来"验证"——多数脚本会写文件或调外部服务。
特别注意：部分脚本**不解析命令行参数**（例如 `asset_inventory.py`），
传 `--help` 也会照常跑完并写文件，不能用 `--help` 当探针。

---

## 不应提交的内容

已在 `.gitignore` 中，**不要**手动 `git add -f`：

| 路径 | 原因 |
|---|---|
| `.secrets/` | API 密钥（生图通道 token + 额度账本） |
| `backup/` | 原始 `.assets` 备份与结构快照，约 6 GB，仅本地回滚用 |
| `out/`、`.tmp/`、`.workbuddy-ai/` | 探针产物、临时文件、会话数据 |
| `art/gen/`、`art/scene_restyle/`、`art/scene_sheets/`、`art/component_thumbs/` | 可再生生成物（已逐目录核实） |
| `tools/bin/*.exe`、`tools/bin/*.dll` | 外部工具二进制 |
| `tools/logs/*.log`、`__pycache__/`、`*.pyc` | 运行日志与字节码 |
| `extracted/primary/**/*.png|tga|dds|wav|ogg|avi` | 原始资源提取物 |

**需要提交的**：`docs/`、`validation/`（验收证据）、`tools/scripts/*.py`、`tests/`、
`art/*_parts/`（部件产物）、`art/scene_shots/`（实机证据）、`AGENTS.md`、`DECISION_LOG.md`。

---

## 当前状态

| 项 | 状态 |
|---|---|
| 逆向与黄金回路 | ✅ 完成（4/4 文件字节一致） |
| 重彩验收基准 | ✅ 三阵营 PASS 17/17 |
| 角色替换 | 🔄 进行中（Vinnie / Gangster1 全链路已通，其余待推进） |
| 场景替换 | 🔄 路线 B 脚手架已通（level4 / level9 有产出） |
| CAP-014 P1 防护方案 | ⛔ **纯设计文本，106 条用例全部 `NOT EXECUTED`，`WRITE_PERMITTED = NO`** |

CAP-014 是"真实批量写入前的安全防护方案"，当前处于**待人工审查**状态
（BLK-1 … BLK-5 共 5 项**设计阻塞**仍未决策；这 5 项与审查发现里的 P0 是两回事——F-01…F-06 已修）。**它不构成写入授权**，详见 `docs/CAP-014_INDEX.md`。

---

*项目创建于 2026-10-19。本 README 于 2026-10-31 更新，内容取自实际文件树与实测数据。*
