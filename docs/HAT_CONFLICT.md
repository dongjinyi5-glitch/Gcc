# Hat 冲突：是什么、为什么、怎么解

> 结论先行：冲突只发生在 **1 个贴图**（`sharedassets15.assets#71`）上，
> 涉及 **9 个预制体、3 个主角 vs 6 个敌人**。游戏本来就有一张**几何完全等价**的
> 第二张 Hat sprite（`resources#3633`，同帧同轴心同 PPU），所以不需要新建任何对象：
> **2 次等长贴图覆盖 + 6 次 8 字节 PPtr 改指**即可拆开。
> **已实施并通过校验与验收门**（见 §4）。

---

## 1. 冲突是什么

Unity 的 `Sprite` = 贴图 + 图内矩形 + 轴心 + 网格。**同一个 Sprite 被多个角色共用时，
它的外观只有一个版本**——你不可能让它对 A 角色显示 A 的帽子、对 B 角色显示 B 的帽子。

本作 29 个角色身上共出现 **19 组不同的 (贴图, Sprite)**。其中 17 组是单人独占，
**只有 2 组是多角色共用**：

| # | 贴图 | Sprite | 尺寸 | 用户数 | 用户 | 冲突？ |
|---|---|---|---|---|---|---|
| 1 | `sharedassets15.assets#71` | `#229` | 139×76 | **9** | **Vinnie、VinnieRagdoll、VinnieCutScenes** / Gangster1、Frankie、EvilFrankieOnFloor、Goon3、Scientist、Salvatore | **是** |
| 2 | `resources.assets#832` | `#3633` | 139×76 | 4 | Gangster2、Gangster3、Gangster6、BonninoBoss | 否（全是日军） |

其余 17 组各 1–2 个用户，互不相干。

### 所以冲突的定义是

> **远征军主角（Vinnie ×3 个预制体）和日军反派（6 个预制体）共用同一张礼帽贴图。
> 一张贴图只能画一个样子，于是"Vinnie 戴美制 M1"和"Gangster1 戴昭五式铁帽"
> 在数据层面互相排斥。**

不是"帽子太多"，也不是"每个角色都要单独处理"——**是 1 张图被 9 个预制体共用，
而这 9 个里既有主角又有敌人。**

### 附带的第二个事实（很重要）

游戏**自己就有一张钢盔 sprite**：`resources.assets#3707`，139×76，轴心偏移
(−5.77, −6.80)，9 顶点网格，贴图 `resources#906` 是 157×116（头盔画在 (2,15) 的
139×76 子区里）。它只被 `Soldier` 一个预制体使用。

这说明**钢盔的轮廓是游戏原生的**，帧尺寸 139×76、PPU 200 都不用改。
（但最终没有用它——`theme_cbi` 把 Soldier 定为日军士兵，共用会让日军戴美军盔，
见 §3.1。它的价值在于证明"这个帧装得下钢盔"。）

---

## 2. 为什么不能用最省事的办法

| 做法 | 为什么不行 |
|---|---|
| 直接把共用贴图改成钢盔 | Vinnie 也跟着变钢盔——但他的和日军的应该是**两种**钢盔（M1 vs 昭五式） |
| 用 UnityPy 新建 Texture2D / Sprite | 本作 Unity 4.3.4f1，`env.save()` 重写整个 SerializedFile 会**直接损坏** `resources.assets`（已复现） |
| 新建预制体变体 | 代码按名字 `Resources.Load` 预制体，改名字/新增变体都要动 Assembly-CSharp，代价远大于收益 |
| 放弃区分，全用同一种钢盔 | 主题就塌了：远征军和日军看起来一模一样 |

---

## 3. 最终方案：合流，不克隆

原本打算"新增 Texture2D + 改 PPtr"，但查证后发现有更省的做法：**游戏本来就有一张
几何完全等价的第二张 Hat sprite**，而且它已经在给四个日军角色用。

| | Sprite | 贴图 | 帧 | m_Offset | PPU | 网格 |
|---|---|---|---|---|---|---|
| 主角+6 反派共用 | `#229` @ sharedassets15 | `#71` 139×76 | 139×76 | (−3.9155, −8.9911) | 200 | 8 顶点 |
| 4 反派已用 | `#3633` @ resources | `#832` 139×76 | 139×76 | **同上** | **200** | 13 顶点 |

帧、偏移、PPU 三者完全一致 → **从 #229 改指 #3633 是零像素位移**。
两个网格都覆盖新美术 100% 的不透明像素（实测，见 §5）。

所以：

```
sharedassets15#71  ← 美制 M1        Vinnie / VinnieRagdoll / VinnieCutScenes（不动 PPtr）
resources#832      ← 昭五式铁帽     Gangster2/3/6、BonninoBoss（不动 PPtr）
6 个反派           m_Sprite #229 → #3633   （6 × 8 字节）
```

**总代价：2 次等长像素覆盖 + 6 次 8 字节 PPtr 改指，零新增对象。**
主角一次都不改指，风险最低。

### 3.1 为什么放弃了 A1（和 Soldier 共用 `resources#906`）

`theme_cbi.ROLE_OF["Soldier"] = 日军士兵`。把 `#906` 画成美制 M1 再让 Vinnie 指过去，
等于**给日军士兵发了一顶美军钢盔**——题材直接错。所以 `resources#906` 一个字节都没动
（`--verify` 里有专门一条断言它在原样）。

### 3.2 为什么不能新建对象

`env.save()` 在本作会损坏 `resources.assets`（TextAsset 重序列化长度错）。对象表、
所有 offset 与 size 必须逐字节不变，所以只能等长覆盖：

- 贴图像素块 = `w*h*4` 字节，位于 Texture2D 对象末尾，`A,R,G,B` 逐像素、行自下而上；
- Sprite PPtr = SpriteRenderer 里两个 int32 字段，`m_FileID` 由 5 变 0（同文件）。

### 3.3 美术：B2 程序化重彩（0 点数）

`restyle_ink.py`，**槽位 `hat` + 显式 role**，颜料从 `theme_cbi.ROLE_KIND` 取：

| 角色兵种 | hat 色带 | 结果 |
|---|---|---|
| 远征军 | 赭石 + 墨 | 卡其/橄榄褐，M1 的读感 |
| 日军士兵 | 墨 + 石绿 | 国防色偏橄榄，昭五式的读感 |

两次踩坑，记录在此：

1. **`slot='hat'` 不传 role** → 回退到 faction 默认"墨"，整盔发黑发闷。
2. **`slot='garment'`** → 石青+石绿，看着不错，但远征军色带要求 `石青 ≤ 0.06`，
   主角直接违规。

在程序化美术之上补两笔辨识度：昭五式加**菱形伪装网 + 朱红五星**，M1 加**下颚带**。
两者在游戏实际尺寸（约 40px）下仍一眼可分。

### 3.4 几何：零位移，无裁切

- 两个 sprite 的 `m_Offset` / `m_Rect` / `m_PixelsToUnits` 完全相同 → 改指后不移动。
- `#3633` 采样宽度 137.92 / 139 px，昭五式美术在第 136 列之后已全透明 → 不丢像素。
- 两个网格对新美术的不透明像素覆盖率均为 **100.00%**（0 被裁切像素）。

## 4. 已实施与验收

已按 A1′（合流）+ B2（程序化重彩）+ C2（先做 Hat）落地：

```
TEX  sharedassets15.assets#71  @+23228048  42256B   ← hat_m1.png
TEX  resources.assets#832      @+513234624 42256B   ← hat_syo5.png
PPtr SR#15797 Gangster1          @+1346382724  [5,229] -> [0,3633]
PPtr SR#15795 Frankie            @+1346382532  [5,229] -> [0,3633]
PPtr SR#15794 EvilFrankieOnFloor @+1346382436  [5,229] -> [0,3633]
PPtr SR#15311 Goon3              @+1346336068  [5,229] -> [0,3633]
PPtr SR#15754 Scientist          @+1346378596  [5,229] -> [0,3633]
PPtr SR#15808 Salvatore          @+1346383780  [5,229] -> [0,3633]
```

`split_hat.py --verify` 全绿：

- 6 个反派 → `(0, 3633)`；4 个原本就在 #3633 的保持不变；Vinnie ×3 仍是 `(5, 229)`
- 两张贴图的像素与源 PNG **逐通道零误差**
- `resources#906`（Soldier）**逐字节未变**

验收门：`acceptance.py Gangster1 --suffix redraw` **PASS 17/17**、
`acceptance.py Vinnie --suffix redraw|restyled` **PASS 17/17**。

回滚：`backup/pre_hat_split/` 存了写入前的 `resources.assets` 与
`sharedassets15.assets`。

## 5. 后续（等 ImageGen 恢复）

B1 生成的两张 139×76 概念图可以直接覆盖 `art/hat_split/hat_m1.png` /
`art/hat_split/hat_syo5.png`，重跑 `split_hat.py` 即可——落位点、尺寸、字节数完全相同，
**不需要再动任何 PPtr**。

## 6. 数据出处


- 角色 → Hat Sprite → 贴图 的完整映射：`art/hats/_map.json`（本文件生成，29 条）
- 9 个 Hat 渲染器 → 根预制体：`/tmp/sr_owner.py` 输出（Vinnie / VinnieRagdoll /
  VinnieCutScenes / Gangster1 / Frankie / EvilFrankieOnFloor / Goon3 / Scientist / Salvatore）
- 贴图与 Sprite 的字节级字段：`/tmp/probe2.py`、`/tmp/clone_probe.py`
