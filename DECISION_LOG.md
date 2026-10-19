# 决策日志 — Guns, Gore and Cannoli 美术资产逆向替换

---

## 2026-10-19 22:08 - [Agent A] 项目初始化与基线确认

### 背景
用户发起项目：将 Guns, Gore and Cannoli 的角色与场景替换为中国国画（水墨）风格。要求按顶尖专家标准执行，建立多角色协作，以逆向文档为第一个里程碑。

### 产品决定

| # | 决策项 | 产品决定 |
|---|--------|----------|
| 1 | 游戏安装路径 | `D:\BaiduNetdiskDownload\意大利黑1\Guns, Gore and Cannoli` |
| 2 | 目标平台 | 仅 Windows |
| 3 | 游戏引擎 | 通过实际程序解析确认 → **Unity 5.x (2015), Mono 后端, 非 IL2CPP** |
| 4 | 替换范围优先级 | 角色全动作集 → 场景图层 → UI/粒子 → 调色板动画（暂不动） |
| 5 | 目标美术风格 | 中国国画风格（水墨五色、留白、笔触肌理） |
| 6 | 工具下载授权 | 授权通过 |
| 7 | 工作目录 | `D:\AI\DAIGuns, Gore and Cannoli from WB`（全部资料） |
| 8 | 规则目录 | `D:\AI\Guns, Gore and Cannoli on China`（AI Agent 规则） |
| 9 | 目录内授权 | 永久有效；目录外每次确认 |

### 引擎确认证据（一手）
```
ggc_Data/
├── Managed/
│   ├── Assembly-CSharp.dll      # Unity 主游戏代码（C#，可反编译）
│   ├── Assembly-CSharp-firstpass.dll
│   ├── UnityEngine.dll
│   └── mscorlib.dll, System*.dll
├── Mono/mono.dll                # Mono 运行时（非 IL2CPP）
├── resources.assets (1.3 GB)    # Unity 主资源包
├── sharedassets0-15.assets      # 分场景资源
├── level0-14                    # 关卡场景数据
├── mainData
├── StreamingAssets/
├── Plugins/ (CSteamworks.dll, AVProWindowsMedia.dll)
└── Resources/
```

### 不可变四项（逆向确认后锁定）
1. 碰撞盒数据位置 → 逆向时发现即记录
2. 调色板动画实现 → 逆向时发现即记录
3. 场景分层渲染顺序/Z-Order → 逆向时发现即记录
4. 音频/本地化同包体 → 保持

### 技术路线
选择最成熟、适用性最广、编译后硬件要求最低的逆向工具链：
- 资源解析：UnityPy（Python，一手字节解析）
- 资源浏览：AssetRipper
- 代码反编译：dnSpy/ILSpy
- GPU 捕获：RenderDoc
- 美术创作：Krita + Aseprite + DragonBones

### 影响范围
- M1 逆向文档里程碑立即启动
- 所有格式判断基于实际字节解析，不接受二手结论
- 黄金回路往返测试作为修改前的强制前置门

---

## 2026-10-19 23:25 - [Agent A] M2 美术管线启动：风格/范围确认 + 角色清单交付

### 产品决定（本次确认）

| # | 决策项 | 产品决定 |
|---|--------|----------|
| 1 | 角色替换范围 | **全部角色**（不抽样，逐一替换） |
| 2 | 国画风格偏好 | **重彩**（非纯水墨、非淡彩） |
| 3 | 笔触粗细 | **中等** |
| 4 | 前置门 | 先完成黄金回路往返测试，再进入美术阶段 → **已满足**（4/4 文件 SHA-256 字节一致） |
| 5 | 清单交付形式 | 名称 + 形象图 + 出场关卡 + 部件数 + 行为脚本，由用户逐项回复替代形象描述 |

### 事实更正（对早期条目的修订）

| 原记录 | 实际确认 | 依据 |
|--------|----------|------|
| "Unity 5.x (2015)" | **Unity 4.3.4f1** | UnityPy 读取全部 33 个 .assets 的 `unity_version` 字段 |
| 规则目录 `D:\AI\Guns, Gore and Cannoli on China` | 该目录属另一平台，本项目**不使用**；全部资料仅在 `D:\AI\DAIGuns, Gore and Cannoli from WB` | 用户 22:34 明确说明 |

### 角色清单产出（一手解析）

- 角色总数：**33**（玩家 1 / 人类敌人 8 / 僵尸 20 / 鼠怪 3 / Boss 4，含重叠分类）
- 形象图生成方式：读取预制体 `GameObject → Transform → SpriteRenderer → Sprite → Texture2D`
  层级，按 `m_LocalPosition/m_LocalScale` 变换与 `sortingOrder` 合成，**非游戏截图**
- 关键技术障碍与解法：
  1. `m_Sprite` 常指向**外部 sharedassets**，PPtr 的 `m_FileID` 必须用**引用方所在文件**的
     `externals` 解析，否则会取到同 path_id 的错误对象（曾导致形象图出现皮肤色乱块）
  2. UnityPy 的 `Sprite.image` 在 Unity 4.3 网格数据上断言失败 → 改为按 `m_RD.textureRect`
     裁切图集、按 `m_Rect` 还原显示尺寸
  3. 预制体同时包含全部武器/姿势变体，用 `m_IsActive=False` 跳过非激活子树
  4. `MonoBehaviour.m_Script` 位于原始字节 **offset 12**（非 8），指向 `sharedassets0.assets`
     中的 MonoScript，可读出 `Unit` / `UnitSpike` 等脚本类名

### 已知限制

- HP / 伤害值**不在预制体序列化字段中**（已扫描角色层级全部 MonoBehaviour 原始浮点，无命中），
  属代码常量，需反编译 `Assembly-CSharp.dll` 才能取得。当前以"出场关卡"作为等级依据。

---

*记录者：Agent A (Architect / Tech Lead)*
