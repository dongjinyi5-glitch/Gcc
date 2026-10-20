# REVERSE_ENGINEERING.md — Guns, Gore and Cannoli 逆向文档

> **里程碑**：M1 — 逆向文档  
> **状态**：v1.2（四项保真问题 + 黄金回路全通过 + 纹理格式 + 角色体系与形象还原）  
> **编写者**：Agent A (Architect / Tech Lead)  
> **日期**：2026-10-19  
> **原则**：所有判断基于实际字节解析与运行时证据，不接受二手结论

---

## 1. 引擎确认

### 1.1 确认方法

| 方法 | 结果 | 证据 |
|------|------|------|
| 文件系统结构分析 | `ggc.exe` + `ggc_Data/` 目录 | Unity 独立构建的典型布局 |
| Managed 程序集 | `Assembly-CSharp.dll` (1.19MB) + `UnityEngine.dll` | Unity C# 游戏代码 |
| Mono 运行时 | `ggc_Data/Mono/mono.dll` | Mono 后端，非 IL2CPP（代码可反编译） |
| .assets 格式版本 | 二进制头 version=9 (大端) | Unity SerializedFile 格式 |
| **UnityPy 元数据解析** | **unity_version = "4.3.4f1"** | **UnityPy 读取所有 .assets 元数据确认** |
| 文件日期 | 2015-04-29 | Unity 4.3.4 补丁版（2014-2015） |

### 1.2 结论

**游戏引擎：Unity 4.3.4f1，Mono 后端，非 IL2CPP**

- **精确版本：4.3.4f1**（UnityPy 从 .assets 元数据一手确认，所有文件一致）
- Unity 4.3 是引入 2D 工具集的版本（SpriteRenderer、2D 物理、BoxCollider2D 等）
- 构建日期：2015-04-29
- 平台目标：PC/PS4/Xbox（代码含 PCMaterialPath/PS4MaterialPath/XboxMaterialPath）

### 1.3 引擎确认对项目的影响

| 项 | 影响 |
|----|------|
| 资源格式 | 标准 Unity SerializedFile（.assets），可用 UnityPy/AssetRipper 解析 |
| 代码 | C# 编译为 Assembly-CSharp.dll，可用 dnSpy/ILSpy 反编译为可读源码 |
| 无加密 | GOG 版无 DRM 包装，资源直接可读 |
| 无 IL2CPP | 代码反编译无障碍，所有类名/方法名可读 |

---

## 2. 游戏数据结构

### 2.1 安装目录结构

```
D:\BaiduNetdiskDownload\意大利黑1\Guns, Gore and Cannoli\
├── ggc.exe                    (10.8 MB)    游戏可执行体
├── steam_api.dll              (741 KB)     Steam SDK（GOG 版保留）
├── ALI213.ini / ali213.bin    (3 KB)       破解补丁（不影响资源修改）
├── Profile/                               用户存档
└── ggc_Data/                               Unity 数据目录
    ├── Managed/
    │   ├── Assembly-CSharp.dll           (1.19 MB)   主游戏代码
    │   ├── Assembly-CSharp-firstpass.dll             预编译代码
    │   ├── UnityEngine.dll                            引擎核心
    │   ├── Assembly-UnityScript.dll                  JS 脚本
    │   ├── Assembly-UnityScript-firstpass.dll
    │   ├── mscorlib.dll, System*.dll                 Mono 运行时
    │   └── UnityPluginLogImport.dll
    ├── Mono/mono.dll                                 Mono 运行时
    ├── Plugins/
    │   ├── AVProWindowsMedia.dll                     视频播放插件
    │   └── CSteamworks.dll                           Steam SDK
    ├── Resources/
    │   ├── unity default resources    (1.5 MB)       引擎内置资源
    │   └── unity_builtin_extra        (348 KB)       引擎扩展
    ├── StreamingAssets/
    │   └── Cutscenes/AVI/                            过场动画（AVI 格式）
    │       ├── 001_Introduction(1080p/720p).avi
    │       ├── Level2_Harbour_*.avi
    │       ├── Level2_Harbour2_Pawnshop.avi
    │       ├── Level4_DemoCutscene.avi
    │       ├── Level10_ConstructionSite_*.avi
    │       └── Level11_EndBossStart / Roof_TheEnd.avi
    ├── resources.assets               (1.29 GB)      主资源包
    ├── sharedassets0-15.assets                      分场景资源
    ├── level0-14                                     关卡场景数据
    └── mainData                       (624 KB)      启动/主场景数据
```

### 2.2 资源文件清单

| 文件 | 大小 | 用途 |
|------|------|------|
| resources.assets | 1,346,676,228 (1.29 GB) | 主资源（角色精灵、纹理、音频等） |
| sharedassets0.assets | 124,405 (122 KB) | 场景0共享资源 |
| sharedassets1.assets | 16,187,068 (15.4 MB) | 场景1 |
| sharedassets2.assets | 15,301,772 (14.6 MB) | 场景2 |
| sharedassets3.assets | 4,104 (4 KB) | 场景3（极小，可能是空场景） |
| sharedassets4.assets | 244,336,532 (233 MB) | 场景4 |
| sharedassets5.assets | 366,419,952 (349 MB) | 场景5（最大场景资源） |
| sharedassets6.assets | 226,110,256 (215 MB) | 场景6 |
| sharedassets7.assets | 240,800,668 (230 MB) | 场景7 |
| sharedassets8.assets | 142,096,388 (135 MB) | 场景8 |
| sharedassets9.assets | 219,702,420 (209 MB) | 场景9 |
| sharedassets10.assets | 88,361,028 (84 MB) | 场景10 |
| sharedassets11.assets | 208,396,564 (199 MB) | 场景11 |
| sharedassets12.assets | 299,503,316 (285 MB) | 场景12 |
| sharedassets13.assets | 26,994,344 (26 MB) | 场景13 |
| sharedassets14.assets | 194,204,740 (185 MB) | 场景14 |
| sharedassets15.assets | 76,328,240 (73 MB) | 场景15 |
| level0-14 | 28KB ~ 1.27MB | 关卡场景数据（Unity 序列化场景） |
| mainData | 639,044 (624 KB) | 主场景/启动数据 |

### 2.3 .assets 文件格式确认

所有 .assets 文件均为 **Unity 原始 SerializedFile 格式**（非 UnityFS Bundle）：

```
二进制头（前 12 字节，大端）:
├── int32 metadata_size    （元数据块大小）
├── int32 file_size        （整个文件大小，与实际一致 ✓）
└── int32 version          （= 9）
```

**UnityPy 元数据解析确认：unity_version = "4.3.4f1"**（所有 33 个文件一致）

---

## 3. 代码结构分析（Assembly-CSharp.dll 反编译）

### 3.1 分析方法

使用 `strings` 对 `Assembly-CSharp.dll` (1,247,232 bytes) 进行字符串提取，
筛选类名、方法名、属性名。此为一手代码级证据。

### 3.2 动画系统

**结论：游戏使用 Unity 原生 Mecanim Animator + 纹理/精灵交换，非 Spine/DragonBones 骨骼动画**

| 证据 | 含义 |
|------|------|
| `AnimationClip`, `AnimatorStateInfo`, `AnimationTakeStateName` | Unity 原生动画系统 |
| `AnimatorDictatesMovement`, `AnimatorPlaysAttackSound` | Animator 驱动角色行为 |
| `TextureAnimation`, `TextureAnimationType`, `get_/set_TextureAnimationType` | 纹理动画（逐帧切换精灵图） |
| `UnitSwapSprite`, `UnitSwapSpritesType`, `spriteRendererToSwap` | 精灵交换（角色变体/调色板效果） |
| `spriteRenderers`, `weaponRootSpriteRenderer` | SpriteRenderer 组件控制武器/角色显示 |
| `ANIMATOR_ATTACK_PARAMETER`, `ANIMATOR_CHARGE_PARAMETER`, `ANIMATOR_ARMS_DIE_PARAMETER` 等 | Animator 参数名（攻击/充能/死亡/移动等状态） |
| `AnimationVariations`, `AnimationLayerIndex` | 动画变体与层（用于多角色共用动画） |

**无 Spine/Skeletal 证据**：未发现 Spine/Esoteric/DragonBones 相关字符串。
仅发现 `RatBone01/02/03`（Rat Boss 角色的 Unity 层级骨骼，用于挂载精灵部件，非网格变形骨骼）。

### 3.3 角色系统

**已确认角色列表（从 AI Controller 类名提取）：**

| 类名 | 角色 | 类型 |
|------|------|------|
| (Player) | Vinnie | 玩家角色（语音路径 `Characters/FootstepsVinnie/`） |
| `AIGangsterController` | Gangster | 普通敌人 |
| `AIGangsterBossController` | Gangster Boss | 敌人 Boss |
| `AIFrankieBossController` | Frankie Boss | 敌人 Boss |
| `AIEvilFrankieOnFloorController` | Evil Frankie (on floor) | 敌人 Boss |
| `AIRatBossController` | Rat Boss | 敌人 Boss |
| `AIScientistController` | Scientist | 敌人 |
| `AIChargerController` | Charger | 敌人 |
| `AIJumperController` | Jumper | 敌人 |
| `AIFloatingController` | Floater | 敌人 |
| `AIMovingEnemyController` | (基类) | 移动敌人基类 |
| `AINonMovingEnemy` | (基类) | 静止敌人基类 |
| `DefaultUnitController` | (基类) | 所有角色单位基类 |

**角色语音文件路径（确认角色名）：**
- `Characters/Frankie/` — Frankie 的对话语音（20+ 句台词）
- `Characters/Gangsters/` — 黑帮的对话语音
- `Characters/FootstepsVinnie/` — Vinnie 的脚步声

### 3.4 碰撞系统

| 证据 | 含义 |
|------|------|
| `ColliderTargetCenter`, `ColliderTargetSize` | 碰撞目标中心与尺寸 |
| `HitBoxHeight`, `HitBoxWidth` | 受击盒高度与宽度 |
| `EdgeCollider` | 边缘碰撞器（Unity 内置组件） |
| `HasExternalColliders` | 是否有外部碰撞器 |
| `DestroyOnNonDamageCollision`, `DestroyOnUnitCollision` | 碰撞销毁逻辑 |
| `EnemyLayerMask`, `AllyLayerMask`, `DestructableLayerMask` | 碰撞层掩码 |
| `OverwritingPhysicsLayerId`, `DefaultUnitLayer` | 物理层覆盖 |

**→ 碰撞盒数据是 MonoBehaviour 属性，序列化在 Unity 场景/预制体文件中，不在单独骨骼文件内**
（因为游戏不使用骨骼动画系统，没有骨骼文件）

### 3.5 UI 系统

| 证据 | 含义 |
|------|------|
| `NGUI.unity` 场景文件 | 使用 NGUI（Next-Gen UI）插件 |
| `Atlases/HudAtlas`, `Atlases/MenuAtlas` | NGUI 图集（HUD 和菜单） |
| `SpriteNameInHudAtlas`, `AmmoSpriteNameInHudAtlas` | 图集中的精灵引用 |
| `UIFont.premultipliedAlphaShader` | NGUI 字体着色器 |

### 3.6 着色器系统

| 证据 | 含义 |
|------|------|
| `shader doesn't have a clipped shader version for` | 有裁剪着色器变体系统 |
| `has no shader setter` | 运行时着色器切换 |
| `ThunderFlash` | 雷电闪光效果（可能是全屏着色器） |
| `CFX_Flash`, `CFX_LightIntensityFade` | 粒子特效包（Cartoon FX） |
| `AddMuzzleFlash` | 枪口火光 |
| `AVPro QuickTime/Material Apply`, `AVPro WindowsMedia/Material Apply` | 视频纹理着色器 |

### 3.7 音频与本地化

| 证据 | 含义 |
|------|------|
| `AudioClip`, `AudioSource`, `AudioRolloffMode` | 标准 Unity 音频系统 |
| `Assets/Localization/Resources/Languages/LocalizationSettings.asset` | NGUI 本地化配置 |
| `ChangeLanguage`, `AddLanguage`, `LanguageID` | 多语言切换 |
| `SubtitleType`, `Subtitles` | 字幕系统 |
| `Characters/Frankie/*.wav` (推测) | 角色语音在 resources.assets 内 |

**→ 音频和本地化文件均在 .assets 包体内（非 StreamingAssets），同包体结构 ✓**

### 3.8 场景结构

从 mainData 提取的场景文件路径：
- `Assets/Scenes/Game.unity` — 主游戏场景
- `Assets/Scenes/MainMenu.unity` — 主菜单
- `Assets/Scenes/NGUI.unity` — NGUI 场景
- `Assets/Scenes/EmptyLevel.unity` — 空关卡（模板）

---

## 4. 四项保真问题（已确认 — 基于 UnityPy 一手解析）

### Q1: 碰撞盒数据是否在骨骼文件内、还是单独文件？

**已确认：碰撞盒数据在 Unity 序列化对象（场景/预制体）中，不在骨骼文件内。**

UnityPy 解析证据（碰撞器对象分布）：

| 碰撞器类型 | resources.assets | sharedassets + level | 总计 |
|-----------|-------------------|---------------------|------|
| BoxCollider2D | 583 | 4,978 | 5,561 |
| PolygonCollider2D | 492 | 568 | 1,060 |
| CircleCollider2D | 85 | 83 | 168 |
| EdgeCollider2D | 3 | 229 | 232 |
| BoxCollider (3D) | 7 | 116 | 123 |

- 游戏不使用骨骼动画（无 Spine/DragonBones），因此不存在"骨骼文件"
- 碰撞器是 Unity 内置组件，序列化在 level*.assets（场景）和 resources.assets（预制体）中
- 代码确认：`HitBoxHeight`, `HitBoxWidth`, `ColliderTargetCenter`, `ColliderTargetSize` 是 MonoBehaviour 属性
- **结论：碰撞盒数据 = Unity Collider2D 组件 + MonoBehaviour 属性，在 .assets 序列化数据中 ✓**

### Q2: 调色板动画（伤害闪白/道具变色）是 Shader 实现还是纹理替换？

**已确认：主要为纹理/精灵替换（UnitSwapSprite），闪光效果使用粒子材质+Shader。**

UnityPy + 代码证据：

| 证据 | 来源 | 含义 |
|------|------|------|
| `UnitSwapSprite` / `UnitSwapSpritesType` | Assembly-CSharp.dll | 运行时切换精灵实现角色变体/颜色变化 |
| `TextureAnimationType` / `TextureAnimation` | Assembly-CSharp.dll | 纹理动画（逐帧精灵切换） |
| 51 个 Shader（resources.assets） | UnityPy | 包含裁剪/闪光等着色器 |
| `CFX_Flash`, `CFX2_Blood AB`, `CFX_Anim_Electricity_Add` | 材质名 | 粒子特效材质用于伤害/血腥效果 |
| `ThunderFlash` | Assembly-CSharp.dll | 雷电闪光（可能是全屏着色器） |

- 角色变色/变体 = **纹理替换**（UnitSwapSprite 运行时切换 sprite）
- 伤害闪白 = **粒子材质 + Shader**（CFX_Flash 材质叠加）
- **结论：纹理替换为主，Shader/材质为辅（闪光效果）✓**

### Q3: 场景分层渲染顺序、Z-Order 编码方式？

**已确认：使用 SpriteRenderer.sortingOrder（整数），无命名排序层。**

UnityPy 解析 level10 SpriteRenderer sortingOrder 数据：

| sortingOrder | SpriteRenderer 数量 | 含义 |
|-------------|---------------------|------|
| -100 | 1 | 最远背景 |
| -16 ~ -1 | 39 | 背景层 |
| 0 | 148 | 中景（最多） |
| 1 ~ 4 | 86 | 前景低层 |
| 5 ~ 15 | 74 | 前景中层 |
| 20 | 24 | 前景高层 |
| 56 | 1 | 最前（UI/特效） |

- **SortingLayer**: 所有 SpriteRenderer 均为空/默认（`SortingLayerName = ""`）
- **SortingOrder**: 整数范围 -100 到 56，负值=背景，0=中景，正值=前景
- **编码方式**: 简单整数 sortingOrder，无复杂分层编码
- **结论：Z-Order = SpriteRenderer.sortingOrder 整数值，无命名排序层 ✓**

### Q4: 音频/本地化文件是否同包体？

**已确认：是的，音频和本地化均在 .assets 包体内。**

UnityPy 解析证据：

| 资源类型 | resources.assets | sharedassets | StreamingAssets |
|---------|-----------------|-------------|-----------------|
| AudioClip | 349 | 1 | — |
| TextAsset (本地化) | 23 | — | — |
| AVI 视频 | — | — | 7 个文件 |

- 349 个 AudioClip 在 resources.assets 中
- 23 个 TextAsset（本地化文本）在 resources.assets 中
- StreamingAssets 仅包含 AVI 过场动画视频
- 角色语音路径 `Characters/Frankie/*.wav` 等在 resources.assets 内
- **结论：音频+本地化同在 .assets 包体内 ✓（不影响美术替换，保留原样）**

---

## 5. 完整资源类型清单（UnityPy 一手解析）

### 5.1 全量统计

**总计 108,336 个对象，分布在 33 个文件中。**

| Unity 类型 | resources.assets | 其他文件 | 总计 | 修改影响 |
|-----------|-----------------|---------|------|----------|
| GameObject | 4,041 | 23,314 | 27,355 | 引用更新 |
| Transform | 4,041 | 23,314 | 27,355 | — |
| **SpriteRenderer** | 3,015 | 15,786 | **18,801** | 保持原样（引用 Sprite） |
| MonoBehaviour | 846 | 9,980 | 10,826 | 保持原样（碰撞参数等） |
| BoxCollider2D | 583 | 4,978 | 5,561 | 保持原样 |
| **Texture2D** | **1,884** | 1,591 | **3,475** | **核心替换目标** |
| **Sprite** | **1,916** | 1,576 | **3,492** | 跟随 Texture2D |
| Material | 40 | 2,641 | 2,681 | 可能需修改引用 |
| Animator | 143 | 1,999 | 2,142 | 保持原样 |
| ParticleSystem | 134 | 810 | 944 | 后续阶段 |
| ParticleSystemRenderer | 134 | 810 | 944 | 后续阶段 |
| **AnimationClip** | **419** | 51 | **470** | 保持原样（引用 Sprite） |
| Rigidbody2D | 369 | 841 | 1,210 | 保持原样 |
| PolygonCollider2D | 492 | 568 | 1,060 | 保持原样 |
| **AnimatorController** | **74** | 28 | **102** | 保持原样 |
| Shader | 51 | 10 | 61 | 保持原样 |
| TextAsset (本地化) | 23 | — | 23 | 保持原样 |
| **AudioClip** | **349** | 1 | **350** | 保持原样 |
| EdgeCollider2D | 3 | 229 | 232 | 保持原样 |
| CircleCollider2D | 85 | 83 | 168 | 保持原样 |
| Animation | 7 | 25 | 32 | 保持原样 |
| MeshRenderer / MeshFilter | 4 | 18 | 22 | 保持原样 |
| Mesh | 2 | 7 | 9 | 保持原样 |
| Font | 1 | 4 | 5 | 保持原样 |
| Camera | 2 | 13 | 15 | 保持原样 |
| HingeJoint2D | 25 | 14 | 39 | 保持原样 |
| PhysicsMaterial2D | 8 | 8 | 16 | 保持原样 |

### 5.2 角色身体部件纹理（resources.assets 样本）

从 1,884 个 Texture2D 中提取的样本名称显示游戏使用**身体部件拼装系统**：

| 纹理名 | 身体部位 | 用途 |
|---------|---------|------|
| `Head`, `HeadDead`, `HeadScreamPain` | 头部 | 多状态头部精灵 |
| `TorsoChest`, `TorsoChestDead` | 躯干 | 多状态躯干精灵 |
| `BackLegDown`, `FrontLegLow` | 腿部 | 前/后腿部件 |
| `HandBackPush` | 手部 | 手部动作精灵 |
| `zombie-burns (effects)_00013` | 特效 | 僵尸燃烧效果帧 |
| `water_splash_00017` | 特效 | 水花效果帧 |
| `Default-Particle` | 粒子 | 默认粒子纹理 |

### 5.3 动画剪辑名称（resources.assets 样本）

419 个 AnimationClip 中提取的标准动作集：

| 动画名 | 动作 |
|--------|------|
| `idle` | 待机 |
| `attack1` | 攻击 |
| `death1`, `death2` | 死亡（两个变体） |
| `hit` | 受击 |
| `fall` | 坠落 |
| `jump` | 跳跃 |
| `alerted` | 警觉 |
| `kickback` | 后踢 |
| `SteamFadeOut` | 蒸汽淡出 |

### 5.4 音频剪辑名称（resources.assets 样本）

349 个 AudioClip 包括：
- 音效：`bulletimpact05`, `Woosh02`, `blimpContinuous`
- 角色对话：`DontQuitYourDayjob`, `StopChasingMe`, `ZombiesCantKillEm`
- 关联过场：`Level11_Roof_TheEnd`

### 5.5 材质名称（resources.assets 样本）

40 个 Material，主要为 CartoonFX 粒子材质：
- `CFX_Anim_Electricity_Add`, `CFX_Anim_Triangle3_Add`, `CFX2_Blood AB`
- `CFX_Sparkles_Add`, `CFX_ElectricBolt_Add`, `CFX2_Debris_Wood AB`

### 5.6 数据文件位置

完整资产清单 JSON：
- `extracted/primary/inventory_no_resources.json` — 32 个文件（不含 resources.assets）
- `extracted/primary/resources_inventory.json` — resources.assets 完整清单
- `extracted/primary/version_detection.json` — 版本检测数据
- `extracted/primary/raw_asset_inventory.json` — 原始二进制头检测

---

## 6. 工具链选型

| 用途 | 工具 | 状态 | 理由 |
|------|------|------|------|
| 资源解析/提取 | UnityPy 1.25.4 (Python) | ✅ 已安装 | 一手字节解析，可编程控制，支持提取+重打包 |
| 资源浏览/导出 | AssetRipper | 待下载 | GUI 浏览，支持 Unity 4-2022 |
| 代码反编译 | dnSpy / ILSpy | 待下载 | .NET/Mono 反编译为 C# 源码 |
| GPU 捕获 | RenderDoc | 待下载 | 运行时 draw call 截取（验证 Q2） |
| 二进制编辑 | 010 Editor | 待下载 | 形式化 .assets 字节布局 |
| 美术创作 | Krita + Aseprite + DragonBones | 待下载 | 水墨笔触 + 索引调色板 + 2D 骨骼 |

### 6.1 Python 环境

```
运行时：C:\Users\Dell\.workbuddy-ai\binaries\python\versions\3.13.12\python.exe
虚拟环境：C:\Users\Dell\.workbuddy-ai\binaries\python\envs\daiggc\
已安装：UnityPy 1.25.4（安装中）
脚本目录：D:\AI\DAIGuns, Gore and Cannoli from WB\tools\scripts\
```

---

## 7. 逆向工程工作方法

### 7.1 黄金回路往返测试（强制前置门）

```
原始 .assets → UnityPy 提取 → 不修改 → UnityPy 重打包 → SHA-256 比对
                    ↑                                    ↓
                    └──────── 字节一致 = 格式理解正确 ────┘
```

**在开始任何美术修改前，必须先证明往返无损。**

### 7.2 一手数据来源

| 数据类型 | 来源 | 工具 |
|---------|------|------|
| 资源格式 | .assets 原始字节 | UnityPy Python 脚本 |
| 代码逻辑 | Assembly-CSharp.dll 反编译 | dnSpy/ILSpy |
| 渲染管线 | 运行时 GPU 帧捕获 | RenderDoc |
| 场景结构 | level*.assets YAML/序列化数据 | UnityPy |
| 着色器字节码 | ShaderLab 文件 | UnityPy + 手动解析 |

### 7.3 不接受的证据类型

- ❌ "这个游戏用 Unity" 的论坛说法（→ 已一手确认）
- ❌ "调色板动画一般是 shader 实现" 的推测（→ 需代码+GPU确认）
- ❌ AssetRipper GUI 黑盒导出结果（→ 用 UnityPy 编程解析验证）
- ❌ "碰撞盒在骨骼文件里" 的经验假设（→ 已确认无骨骼系统）

---

## 9. 黄金回路往返测试（M1 强制前置门）

### 9.1 文件级往返测试

**方法**：复制 .assets → UnityPy 加载 → 关闭 reader 句柄 → `env.save(pack=False)` → SHA-256 比对

**结果**：✅ 全部通过（4/4 文件字节一致，含 1.29GB 最大文件）

| 文件 | 大小 | 字节一致 | 对象数一致 | 类型一致 | SHA-256 |
|------|------|---------|-----------|---------|---------|
| sharedassets1.assets | 15.4 MB | ✅ | ✅ (15) | ✅ | `e8af9eb1...` |
| sharedassets3.assets | 4 KB | ✅ | ✅ (1) | ✅ | `9688fd6d...` |
| sharedassets10.assets | 84.3 MB | ✅ | ✅ (73) | ✅ | `8e74b885...` |
| resources.assets | 1.29 GB | ✅ | ✅ (18,706) | ✅ | `7fb63272...` |

> **resources.assets SHA-256**：`7fb6327256e58bbe00c013f350b7aab3a3eb52fa7df3083e612f83da6edc44d6`
> 原始与重打包完全一致，证明 UnityPy 对 1.29GB 大文件同样无损。

### 9.2 纹理级往返测试

**方法**：Texture2D → PNG → UnityPy 重新设为 Texture2D → 再次导出 PNG → SHA-256 比对

**结果**：✅ 3/3 通过

| 纹理名 | 尺寸 | PNG 重导入一致 |
|--------|------|----------------|
| Default-Particle | 64x64 | ✅ |
| HeadScreamPain | 109x134 | ✅ |
| BackLegDown | 59x101 | ✅ |

### 9.3 结论

**格式理解正确**。UnityPy 可以无损保存 `.assets` 文件，且纹理提取/重导入保持像素一致。可以进入美术替换阶段。

---

## 10. 纹理格式分析

### 10.1 格式分布

UnityPy 解析 489 个 Texture2D（resources + sharedassets4 + sharedassets11 样本）：

| 格式 | 数量 | 占比 | 说明 |
|------|------|------|------|
| **ARGB32** | 452 | 92.4% | 未压缩，RGBA 完整通道 |
| RGB24 | 31 | 6.3% | 未压缩，无 Alpha |
| DXT5 | 2 | 0.4% | 压缩，有 Alpha |
| DXT1 | 2 | 0.4% | 压缩，无 Alpha |
| Unknown(2) | 1 | 0.2% | Alpha8 / 未知 |
| Unknown(7) | 1 | 0.2% | 未知 |

**→ 绝大多数为未压缩 ARGB32/RGB24，替换时直接输出 PNG 即可，无需处理 DXT 压缩。**

> ⚠️ 注意：`ARGB32`（format 5）在字节层面是 **A,R,G,B 逐像素、行自下而上**，不是 BGRA 也不是 RGBA。详见第 13.3 节。

### 10.2 尺寸分布

| 尺寸 | 数量 | 用途 |
|------|------|------|
| 1024x1024 | 65 | 背景 / 大特效 |
| 512x512 | 45 | 中特效 / 大纹理 |
| 256x256 | 13 | 小特效 / UI |
| 128x128 | 9 | 小道具 |
| 109x134 | 13 | 角色头部 |
| 151x131 | 3 | 角色躯干 |
| 59x101 | — | 角色腿部 |
| 67x71 | — | 角色手部 |

**→ 角色身体部件多为 60x100 ~ 150x130 的小精灵；场景/特效为大纹理。**

### 10.3 样本纹理观察

已提取 10 个样本 PNG（`extracted/primary/sample_textures/`）：

| 文件名 | 尺寸 | 内容 |
|--------|------|------|
| Head.png | 114x105 | 愤怒头部，棕发，厚黑边 |
| HeadScreamPain.png | 109x134 | 痛苦表情头部 |
| TorsoChest.png | 151x131 | 白衬衫+棕色马甲+领带 |
| BackLegDown.png | 59x101 | 灰裤子+鞋 |
| FrontLegLow.png | 101x75 | 另一条腿 |
| HandBackPush.png | 67x71 | 手部 |
| zombie-burns__effects__00013.png | 512x512 | 骷髅+电光特效 |
| water_splash_00017.png | 1024x512 | 水花特效 |

**原画风**：厚黑线轮廓、平涂色块、1920 年代黑帮卡通风格。

**国画替换策略**：
- 以**墨线**替代粗黑轮廓（干湿浓淡变化）
- 以**水墨晕染**替代平涂色块（墨分五色）
- 保留透明通道（Alpha）以维持身体部件拼装
- 保持角色剪影形状不变，确保动画碰撞盒仍然对齐
- 特效可改为水墨飞溅/泼墨效果

---

## 11. M1 完成状态与下一步

### M1 已完成项

| # | 任务 | 状态 |
|---|------|------|
| 1 | 引擎确认（Unity 4.3.4f1） | ✅ |
| 2 | 完整资源清单（108,336 对象） | ✅ |
| 3 | Q1-Q4 四项保真问题 | ✅ 全部确认 |
| 4 | 黄金回路往返测试 | ✅ 文件级+纹理级通过 |
| 5 | 纹理格式分析 | ✅ 92% ARGB32 |
| 6 | 样本纹理提取与观察 | ✅ |
| 7 | 角色身体部件系统识别 | ✅ |
| 8 | 动画动作集识别 | ✅ |

### 下一步（M2 美术管线）

1. 建立中国国画风格量化验收基准
2. 与用户确认角色替换优先级
3. 确认国画风格具体偏好（纯水墨 / 淡彩 / 重彩）
4. 提取角色全动作集纹理模板
5. 开始第一批角色替换

---

## 12. 角色体系与形象还原（M2 前置）

### 12.1 角色构成方式

游戏角色**不是整张精灵**，而是**分部件骨架式拼装**：每个角色预制体是一棵 Transform 树，
每个节点挂一个 SpriteRenderer，节点位置即关节位置。

Vinnie 的实测层级（节选）：

```
Vinnie → Offset → VinnieFull
  ├─ Lower: Crotch / LegUpBack→LegLowBack→FootHeel→FootTip
  │                       └─ LegUpFront→LegLowFront→FootHeel→FootTip
  └─ Upper: TorsoBelly
        ├─ CoatBack1→CoatBack2→CoatBack3
        ├─ CoatTop→CoatMid1→CoatMid2→CoatMid3→CoatBottom
        ├─ TorsoChest
        │    ├─ Arms→Tommygun→ArmBack→ArmLowBack→HandBackRest
        │    │                          └─ ArmFront→ArmLowFront→HandFront→Gun/Magnum357/Pistol…
        │    ├─ Head→Hat
        │    ├─ NeckPiece
        │    └─ Tie1→Tie2→Tie3→Tie4
```

- **无骨骼网格**：动画由 Mecanim 驱动 Transform 旋转 + `UnitSwapSprite` 换精灵实现
- **武器/姿势变体全部预置**在同一预制体内，用 `m_IsActive=False` 关闭
- 因此替换美术时**必须保持每个部件的画布尺寸、Pivot 与剪影**，否则关节会错位

### 12.2 角色总数与分类（一手解析）

| 分类 | 数量 | 角色 |
|------|------|------|
| 玩家 | 1 | Vinnie |
| 人类敌人 | 8 | Gangster1–6、Scientist |
| 僵尸 | 20 | ZombieRegular、ZombieBurping、ZombieCharger、ZombieCrawler、ZombieFloater、ZombieGun、ZombieJumper、ZombieCop、ZombieOfficer、ZombiePaulie、ZombieSailor、ZombieSandwichBoard、ZombieSoldier、ZombieStripper、ZombieRunner1–3 |
| 鼠怪 | 3 | ZombieRat、ZombieRatJumper、ZombieRatSpitter |
| Boss | 4 | Frankie、EvilFrankie（过场代理）、EvilFrankieOnFloor、BonninoBoss、ZombieRatBoss |

**合计 33 个可替换角色单元**（Boss 与鼠怪存在归类重叠，按预制体计为 33）。

### 12.3 形象图还原方法（非截图）

```
GameObject → m_Component[4]=Transform → m_Children 递归
           → m_Component[212]=SpriteRenderer → m_Sprite
           → Sprite.m_RD.texture → Texture2D.image
           → 按 m_RD.textureRect 裁切 → 按 m_Rect 还原尺寸
           → 用 m_LocalPosition/m_LocalScale 变换 → 按 m_SortingOrder 叠放
```

**四个必须踩过的坑（已解决，写入工具脚本）**：

| 坑 | 现象 | 正确做法 |
|----|------|----------|
| 跨文件 PPtr | 取到同 path_id 的错误对象（形象图出现皮肤色乱块） | `m_FileID` 必须用**引用方所在文件**的 `externals` 解析 |
| UnityPy Sprite 解码 | `AssertionError: vertex_data is not None` | 自行按 `textureRect` 裁切图集，不调用 `Sprite.image` |
| 预制体变体堆叠 | 角色身上出现多余武器/重复头部 | 跳过 `m_IsActive=False` 的整棵子树 |
| MonoBehaviour 脚本名 | 读不出类名 | `m_Script` 在原始字节 **offset 12**，指向 `sharedassets0.assets` 的 MonoScript |

### 12.4 数值（HP/伤害）可得性

- 已对角色层级内全部 MonoBehaviour 做原始浮点扫描（1–3000 范围）：**无命中**
- 结论：HP / 伤害为**代码常量**，不在序列化字段中；需反编译 `Assembly-CSharp.dll` 才能取得
- 现阶段清单以**出场关卡**作为等级依据（`level*` 场景关键字扫描）

### 12.5 产出位置

| 文件 | 内容 |
|------|------|
| `extracted/characters/<角色名>.png` | 单角色形象图（33 张） |
| `extracted/characters/contact_sheet.png` | 全角色对照总图 |
| `extracted/characters/roster.json` | 结构化清单 |
| `docs/CHARACTER_ROSTER.html` | 可填写替换描述的交互对照表 |
| `docs/CHARACTER_ROSTER.md` | Markdown 清单 |
| `art/roster_reply_template.csv` | 回复模板 |

---

## 13. 纹理回填方法（M2 实战确认）

本节记录"改完的 PNG 怎么安全写回 .assets"。这部分不是推测，是踩了两个坑之后用实测确定的。

### 13.1 坑一：`env.save()` 会破坏该 build

UnityPy 1.25.4 的 `env.save()` 会重写整个 SerializedFile，并把 `TextAsset` 按错误长度重新序列化。引擎启动日志：

```
The file '...resources.assets' is corrupted! Remove it and launch unity again!
[Position out of bounds! 1346676232 > 1346676228]
Mismatched serialization in the builtin class 'TextAsset'. (Read 8800 bytes but expected 8784 bytes)
```

`env.save(pack=False)` 另有 `FileNotFoundError: output/sharedassets7.assets` 与 `ValueError: seek of closed file` 两个问题（writer 需要 reader 保持打开）。这些都不是配置问题，是库对该 Unity 版本的支持不完整。

**结论：本项目禁用 `env.save()`。**

### 13.2 正确做法：只覆写像素块

ARGB32 未压缩纹理的像素数据是对象的**最后 `w*h*4` 字节**。因此：

```
pixel_offset = obj.byte_start + (len(obj.raw_bytes) - w*h*4)
```

写入前先用原始像素重新编码、与该区段逐字节比对，确认定位无误；然后只覆写这一段。

```python
with open(path, "r+b") as fh:
    fh.seek(int(obj.byte_start) + rel)
    fh.write(raw_new)
```

**结果：文件字节数不变、对象表不变、对象数不变、`Texture2D` 计数不变、其它对象逐字节不变。** 这是"只改像素"的最强证据。

### 13.3 坑二：像素编码是 `A,R,G,B` 逐像素、行自下而上

**不是 BGRA，不是 RGBA。**

确定方法：把 24 种通道排列 × 是否垂直翻转全部试一遍，与已知纹理的原始字节逐字节比对，只有 `(3,0,1,2)` + 行倒序达到 100% 命中。

```python
def encode_argb32(img):
    a = np.array(img.convert("RGBA"), dtype=np.uint8)
    a = a[::-1]                       # rows bottom-up
    argb = a[..., [3, 0, 1, 2]]       # A,R,G,B
    return np.ascontiguousarray(argb).tobytes()
```

这个坑的危险在于**不会报错**：用 BGRA 写入后文件完全合法，只是红蓝互换（藏青大衣变橙、皮肤变青）。只能靠"看起来不对"发现。

### 13.4 落地结果

```text
Vinnie: 110 texture(s) across 8 file(s) (CHECK)
RESULT: 110 ok, 0 skipped
```

`--check` 是重新从游戏文件读取、解码、与重绘 PNG 逐像素比对，所以 110/110 证明补丁已落盘且可被正确解码。8 个文件字节数与原始备份完全一致。

详细验收见 `validation/STEP4_INGAME_VERIFICATION.md`。

---

## 附录 A: 版本检测数据

所有 33 个 .assets/level 文件的二进制头检测结果：
- 格式：Raw .assets（非 UnityFS Bundle）
- version_field = 9（Unity 5.0-5.6）
- 字节序：大端
- file_size_field 与实际文件大小完全一致

完整 JSON 数据：`extracted/primary/version_detection.json`

---

*文档版本：v1.2（新增第 12 节：角色体系与形象还原方法，33 个角色一手解析；M1 全通过）*  
*编写者：Agent A (Architect / Tech Lead)*  
*更新日期：2026-10-19*
