# AGENTS.md — Guns, Gore and Cannoli 美术资产逆向替换项目

> **授权范围**：本目录 `D:\AI\DAIGuns, Gore and Cannoli from WB` 下的所有操作授权**永久有效**；
> 本目录之外的任何操作，需每次单独确认授权。
>
> **强制规则**：后续所有 AI 操作前**必须先阅读本文件**，并严格遵照角色职责与流程执行。

---

## 项目基线

| 项 | 值 | 确认方式 |
|----|----|---------|
| 游戏 | Guns, Gore and Cannoli (GOG 版) | 用户确认 |
| 引擎 | Unity 5.x (2015), Mono 后端, 非 IL2CPP | ggc_Data 结构一手确认 |
| 代码 | Assembly-CSharp.dll (C#, 可 dnSpy/ILSpy 反编译) | Managed 目录确认 |
| 资源 | 标准 .assets 格式 (resources.assets 1.3GB + sharedassets0-15 + level0-14) | 文件系统确认 |
| 平台 | 仅 Windows | 用户确认 |
| 游戏路径 | `D:\BaiduNetdiskDownload\意大利黑1\Guns, Gore and Cannoli` | 用户确认 |
| 美术风格 | 中国国画（水墨五色、留白、笔触肌理） | 用户确认 |
| 工具下载授权 | 授权通过 | 用户确认 |

---

## 不可变约束（逆向确认后锁定，不预设）

以下四项在逆向过程中发现即记录实际实现方式，替换时**保持原样设计与性能效果不变**：

1. **碰撞盒数据位置**（骨骼文件内 / 独立文件）— UnityPy 解析 + dnSpy 反编译确认
2. **调色板动画实现**（Shader / 纹理替换）— RenderDoc GPU 捕获确认
3. **场景分层渲染顺序、Z-Order 编码方式**— RenderDoc + .unity 场景文件解析确认
4. **音频/本地化文件是否同包体**— 保持原样，不影响美术替换但需保留

---

## 替换范围优先级（分阶段）

```
阶段 1: 角色全动作集  ← 当前优先
阶段 2: 场景图层
阶段 3: UI / 粒子（后续）
阶段 4: 调色板动画（暂保留不动）
```

---

## 角色定义与职责边界

每个角色由同一模型在不同任务中切换身份扮演（如必要可用 OpenRouter 下免费胜任大模型模拟对应角色）。
**严格遵守各自职责、权限、输入输出与验收标准，相互独立，不越界。**

| 角色 | 代号 | 核心职责 | 权限边界 | 验收标准 |
|------|------|----------|----------|----------|
| **Architect / Tech Lead** | Agent A | PRD 评审、架构文档、任务拆分、技术风险分析、最终代码审查 | 提出重大设计变更建议，**不擅自决定业务范围** | 架构文档通过评审、任务拆分可执行、风险清单可追踪 |
| **Developer** | Agent B | 按批准任务编写代码、补齐依赖配置、编写单测、提交可复现测试结果 | 仅在已批准任务范围内实现，**不自行扩大范围** | 代码通过测试、单测覆盖达标、测试结果可复现 |
| **QA / Test** | Agent C | 独立执行测试、验证边界条件、检查回归、输出复现步骤+预期/实际结果+日志 | **独立验证**，不参与实现，不接受"测试未通过"无细节汇报 | 测试报告含：步骤、预期、实际、日志、环境、严重级 |
| **Release / Commit** | Agent D | 检查变更清单、构建结果、版本记录、回滚条件，执行受控提交 | Commit 只是操作环节，**不能把"提交成功"当成"项目完成"** | 变更清单匹配任务、构件可复现、回滚方案就绪 |
| **产品负责人 / 最终验收人** | 用户 | 决定功能优先级、确认业务规则、检查实际使用效果、批准重大变更与最终交付 | **唯一业务决策者**，技术方案由 Agent A 提供选项供决策 | 功能完整、性能达标、风格一致、零阻塞 Bug |

---

## 协作流程规范

1. **里程碑驱动**：每个里程碑 = `设计文档 → 实现 → 独立测试 → 受控提交 → 产品验收`
2. **动态确认机制**：
   - 开发前需确认的事项 → 由 Agent A 列清单，产品负责人逐项确认
   - 开发中发现新不确定项 → 立即暂停，记录到 `DECISION_LOG.md`，产品确认后继续
3. **角色切换显式化**：每次回复开头必须声明当前角色（`[Agent A]` 等），输出仅包含该角色职责内产物
4. **文档优先**：任何代码变更前必须有对应设计文档/任务单通过 Agent A 评审
5. **技能预授权**：项目所需 Skill 在里程碑启动前由 Agent A 规划、申请、下载

---

## 工作目录结构

```
D:\AI\DAIGuns, Gore and Cannoli from WB\    ← 唯一主工作目录（全部资料+规则+记录）
├── AGENTS.md              ← 本文件（AI 操作前必读）
├── DECISION_LOG.md        ← 决策日志
├── .gitignore
├── docs/
│   └── REVERSE_ENGINEERING.md   ← M1 逆向文档产出
├── extracted/
│   └── primary/           ← UnityPy 提取输出
├── tools/
│   ├── bin/               ← 下载的工具（AssetRipper/dnSpy 等）
│   ├── scripts/           ← Python 脚本（解析/提取/打包）
│   └── logs/              ← 运行日志
├── art/
│   ├── style-reference/   ← 国画风格参考图
│   └── original-capture/  ← 原版游戏截图/捕获
└── validation/            ← 验证报告
```

---

## 技术路线原则

确认游戏引擎后，选择**最成熟、适用性最广、编译后执行对硬件要求最低**的逆向实现技术与工具链：

| 用途 | 工具 | 理由 |
|------|------|------|
| 资源解析/提取 | **UnityPy** (Python) | 可编程一手字节解析，非黑盒；同时支持提取与重打包 |
| 资源浏览/导出 | **AssetRipper** (GUI+CLI) | 支持 Unity 5-2022，自动识别类型 |
| 资源精细编辑 | **UABE** | 补充旧版本格式，支持重新打包 |
| 代码反编译 | **dnSpy** / **ILSpy** | .NET/Mono 程序集反编译为 C# 源码 |
| GPU 捕获 | **RenderDoc** | 运行时 draw call 截取，确认渲染管线 |
| 美术创作 | **Krita** + **Aseprite** + **DragonBones** | 水墨笔触 + 索引调色板动画 + 2D 骨骼 |

---

## 版本控制规范

- 主分支 `main`，仅 Agent D 经 PR 合并
- Commit message 规范：`[Agent X] <type>: <subject>`（type: feat/fix/docs/refactor/test/chore）
- 二进制资源走 Git LFS（如需要）
- 每里程碑完成时打 tag

---

## 里程碑状态

### M1 — 逆向文档 ✅ 已完成

**目标**：产出 `docs/REVERSE_ENGINEERING.md`，包含完整资源格式规格与四项保真问题的权威回答。

**已完成产出**：
- `docs/REVERSE_ENGINEERING.md` (v1.1)：资源格式规格 + Q1-Q4 保真确认 + 黄金回路往返测试全通过 + 纹理格式分析
- `tools/scripts/asset_inventory.py`：资源清单生成脚本
- `tools/scripts/roundtrip_and_format_test.py`：黄金回路往返测试脚本
- `extracted/primary/`：提取的资源清单 JSON + 样本纹理
- `validation/ROUNDTRIP_REPORT.md`：黄金回路往返验证报告
- `validation/roundtrip_and_format_report.json`：机器可读测试结果

**验证结果**：
- 引擎确认：Unity 4.3.4f1（UnityPy 一手确认）
- 资源清单：108,336 个对象（33 个文件）
- Q1-Q4 保真问题：全部基于 UnityPy 证据确认 ✅
- 黄金回路往返测试：4/4 文件字节一致（含 1.29GB resources.assets）✅
- 纹理级往返测试：3/3 通过 ✅
- 纹理格式：92.4% ARGB32（未压缩），0.8% DXT

**Git Tag**：`m1-complete`

### M2 — 美术管线 ⏳ 进行中

**已确认的产品输入**：
- 替换范围：**全部角色**（33 个，逐一替换）
- 风格：**重彩**
- 笔触：**中等粗细**
- 黄金回路往返测试：**已完成**（4/4 文件字节一致，含 1.29GB resources.assets）

**已完成产出**：
- `extracted/characters/*.png` — 33 个角色形象图（预制体层级拼合渲染）
- `extracted/characters/contact_sheet.png` — 全角色对照总图
- `extracted/characters/roster.json` — 结构化清单（阵营/部件数/脚本/关卡）
- `docs/CHARACTER_ROSTER.html` — 可填写替换描述的对照表（导出 CSV/JSON）
- `docs/CHARACTER_ROSTER.md` — Markdown 版清单
- `art/roster_reply_template.csv` — 回复模板
- `tools/scripts/render_characters.py` — 角色渲染器
- `tools/scripts/build_roster.py` — 清单构建器

**等待产品输入**：逐角色替代形象描述（用户回复 CSV 或文字）

**之后步骤**：
1. 建立重彩国画量化验收基准（墨线宽度区间、朱红/石青/石绿比例、留白率）
2. 按角色逐部件重绘（保持剪影与 Alpha，确保碰撞盒对齐）
3. 逐角色回填 .assets → 游戏内验证 → 截图比对

---

*文件创建于：2026-10-19*
*创建者：Agent A (Architect / Tech Lead)*
*版本：v2.1（M1 完成，M2 待确认）*
