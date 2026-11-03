# 场景图层清单

> **一句话**：场景层共 **1450 张纹理 / 420.4 Mpx 有效绘制 / 15,751 个渲染实例**，分布在
> 12 个战役关卡 + 主菜单动态背景。按关卡分 **13 批**，另加 **FX 粒子层 8 张**、
> **UI 图集 11 张**。
>
> **推荐先做 L3（港口码头）**：第一关、167 张 / 42.1 Mpx，体量适中且命名规整，
> 适合当风格样板；玩家第一印象也在这里。

样图全部在 `docs/SCENE_LAYERS.html`（每关一张合成全景 + 一张逐图缩略表）。
本文件是数据与结论，HTML 是看图的地方。

---

## 1. 口径：怎么算出来的

场景美术不是独立文件，是关卡里的 **SpriteRenderer**。关卡文件本身**不存像素**，
它通过 externals 引用 `sharedassetsN`，所以解析必须用**引用方所在文件**的 externals：

```
levelN 的 SpriteRenderer
  → m_Sprite (PPtr, m_FileID 指向 levelN 的 externals)
  → Sprite (在 sharedassetsN 里)
  → m_RD.texture (PPtr，用 sharedassetsN 自己的 externals)
  → Texture2D
```

漏掉任何一层 externals 都会取错对象（这个坑在角色阶段已经踩过，见
`docs/REVERSE_ENGINEERING.md`）。

**两个面积口径**，不要混用：

| 口径 | 含义 | 用途 |
|---|---|---|
| `W×H` = 588.6 Mpx | 纹理尺寸总和 | 显存/打包 |
| `painted` = **420.4 Mpx** | alpha>8 的像素数 | **真实绘制量** |

1024×1024 的一张图可能是满幅背景（fill 1.00），也可能是透明底上的一个门把手
（fill 0.03）。用 `W×H` 估工作量会高估 40%。

**数据源**：`ggc_Data` 实时目录。场景层从未打过补丁（补丁只动过 11 张角色帽/身体图），
所以读出来就是原始美术。

复现：

```bash
python tools/scripts/scene_survey.py      # 每关有哪些对象类型
python tools/scripts/scene_textures.py    # 走 PPtr 建 art/scene_inventory.json
python tools/scripts/scene_stats.py       # 算 fill / painted，导出 CSV
python tools/scripts/scene_sheets.py      # 出逐图缩略表
python tools/scripts/scene_render.py --all# 出合成全景
python tools/scripts/build_scene_doc.py   # 出 docs/SCENE_LAYERS.html
```

---

## 2. 总量

| | 数值 |
|---|---|
| 场景纹理（去重） | **1450** |
| 有效绘制面积 | **420.4 Mpx** |
| 纹理尺寸合计 | 588.6 Mpx |
| 渲染实例 | **15,751** |
| 跨关卡共用 | **389**（27%） |
| 关卡批次 | 13（L0 + L3…L14） |
| FX 粒子贴图 | 8 张 / 810 个 ParticleSystemRenderer / 12 个材质 |
| UI 图集 | 11 张（NGUI，不走 SpriteRenderer） |

`level1` 是 NGUI 界面场景（1082 个 MonoBehaviour：UILabel/UISprite/UIButton，**0 个
SpriteRenderer**），`level2` 只有 5 个设置对象。所以关卡美术实际在 `level0` 与
`level3`–`level14`。

---

## 3. 六个关键发现

### 3.1 工作量是**平摊**的，没有"画 50 张就完事"的捷径

| 最大 N 张 | 占有效绘制面积 |
|---|---|
| top 10 | 3.7% |
| top 50 | 13.7% |
| top 100 | 26.2% |
| top 200 | 48.6% |
| top 400 | 76.9% |
| top 800 | 96.2% |

场景不是"几十张背景图 + 一堆可忽略小道具"。**800 张才到 96%**，说明这是
一张一张铺出来的美术量。任何"只重画关键几张"的方案，视觉上都会露馅。

### 3.2 80% 的绘制面积在 1024 级页面

| 尺寸 | 张数 | 占绘制面积 |
|---|---|---|
| ≥2048 | 2 | 1.4% |
| 1024–2047 | **531** | **79.8%** |
| 512–1023 | 347 | 14.9% |
| 256–511 | 298 | 3.2% |
| <256 | 272 | 0.7% |

场景基本是 **1024² 拼出来的**。这对生成端是好消息：尺寸统一，不用为每张图单独
定分辨率。

### 3.3 一图一精灵，**没有图集打包**

1450 张里：

- **1176 张（81%）** 的 sprite rect 就是整张纹理 → 可以直接 1:1 替换整张图
- **274 张（19%）** 有 padding（例：`Zeppelin` 1916×1293 显示在 2048×1356 上，
  `Harbour_024front` 1024×736 / 1024×1024）→ 按 rect 裁切后贴回，保住原图的放大柔边
- **1 张** 被两个 sprite 共用

**结论：不需要拆图集、不需要重建 atlas 页。** 替换单位就是"一张纹理"，和角色帽子
repaint 的做法完全一样。

### 3.4 389 张跨关卡共用

27% 的纹理被 2 个以上关卡用（`FireLoop0`、`stripclub_background_*`、
`OldBuildingInside*`、`buildingWall*` 等）。这些画一次多处收益，应优先。

### 3.5 命名有两套写法，而且**不能按名字认图**

同一族存在 `Harbour-Background_*`（43 张）与 `Harbour_Background_*`（27 张）两种
分隔符写法，编号段不重叠，是两批不同的图，但属于同一批重画任务。

更危险的是**27 组同名不同图**：

| 名字 | 实际是两张不同的图 |
|---|---|
| `garage01` | sharedassets7#108（level6） / `Garage01` sharedassets14#66（level13） |
| `platform` | sharedassets12#67（level11） / `Platform` sharedassets4#105（level3/4/5） / `Platform` sharedassets10#21（level9） |
| `kitchen_rack2` | sharedassets8#54 / `kitchen-rack2` sharedassets8#60（**同一文件里**） |

**纹理身份必须是 `(文件, path_id)`，不能是名字。** 本项目的清单、CSV、脚本全部按
`(file, path_id)` 索引；任何按名字批量覆盖的脚本都会写错图。

### 3.6 纯白蒙版：只买形状，不买颜色

`WindowBackdoor`、`WindowFrontdoor`、`WindShield`、`VinnieHealthExtendable` 等
是**纯白 + alpha 形状**，颜色来自 `SpriteRenderer.m_Color`（做窗口灯光、血条染色）。
这类纹理只需保住轮廓，不需要画颜色，也不该被当成"白色占位图"删掉。

> 这个坑在写合成器时先踩了一遍：忽略 `m_Color` 会把它们画成白色方块。
> `scene_render.py` 现在会乘上 `m_Color`。

---

## 4. 分层结构（sortingOrder）

整数排序层，负数在最里侧（远景/视差），0 附近是建筑与地面，正数是前景遮挡与
光照叠加。

| 批次 | 主题 | 纹理 | 有效绘制 | 实例 | sortingOrder | 层数 |
|---|---|---|---|---|---|---|
| L0 | 主菜单动态背景 | 2 | 2.6 M | 2 | 0…0 | 1 |
| L3 | 港口码头 | 167 | 42.1 M | 3,479 | −100…700 | 55 |
| L4 | 港区货场 | 230 | 49.1 M | 4,162 | −101…1100 | 64 |
| L5 | 港湾远景 | 242 | 45.6 M | 4,945 | −101…1115 | 60 |
| L6 | 老城街道 | 258 | 56.8 M | 4,189 | −101…1100 | 58 |
| L7 | 夜总会 | 198 | 42.2 M | 2,724 | −101…1115 | 52 |
| L8 | 城区街区 | 275 | 45.0 M | 6,886 | −100…1617 | 90 |
| L9 | 河畔大桥 | 117 | 14.9 M | 4,112 | −100…1617 | 59 |
| L10 | 竖井与下水道 | 143 | 46.5 M | 3,356 | −100…1115 | 66 |
| L11 | 地铁与水库 | 178 | 59.6 M | 4,275 | −100…1115 | 65 |
| L12 | 水库深处 | 114 | 17.6 M | 4,642 | −100…1115 | 81 |
| L13 | 车库与电梯 | 265 | 44.7 M | 6,310 | −101…1115 | 64 |
| L14 | 齐柏林飞艇 | 277 | 24.7 M | 6,679 | −100…1116 | 97 |
| FX | 粒子层 | 8 | — | 810 | — | — |
| UI | NGUI 图集 | 11 | — | — | — | — |

主题不是猜的，是从该关实际使用的纹理族读出来的（L3 = `Boat*` / `Crane*` / `Quay*`，
L7 = `stripclub*`，L14 = `Zeppelin` / `BelluccioWall*`）。

L8 和 L14 的层数最多（90 / 97），视差最细，重画时最容易出现"层间风格不连续"。

---

## 5. 技术路线：三档，按图层选

### A 档 — 重绘（ImageGen / 手绘）

适用：视差背景层、建筑主体、大面积连续画面。这批决定观感，必须真画。

- 成本：5–10 credits/张
- 输入用 `scene_sheets` 里的对应格子做参考图
- **Alpha 原样保留**（碰撞体、精灵网格都是按原轮廓做的）

### B 档 — 程序化重彩（需要新写 `restyle_scene`）

适用：大量中景建筑、墙、地面、管道。

**但现成的 `restyle_ink` 不能直接用。** 实测（`art/scene_sheets/probe_restyle.png`）：
`restyle_ink` 的默认槽位是 garment（石青+石绿），套到 `Riverside_01` 上，
砖墙变成蓝绿马赛克——它的槽位语义（skin / garment / hat / weapon）是为角色设计的，
场景没有"衣服"这个概念。

场景版需要另一套规则：**按明度分层**决定墨与赭石，只在暗部上石青，叠纸纹，
而不是按语义槽位。这是一个独立开发项，不是调参。

### C 档 — 只调色（FX）

8 张粒子贴图，810 个粒子渲染器、12 个材质。改材质调色 / Shader 着色即可，
不要重画——粒子是发光叠加，画进去的颜色会被 ADD 混合吃掉。

---

## 6. 推荐执行顺序

| 顺序 | 批次 | 理由 |
|---|---|---|
| 1 | **L3 港口码头**（167 张 / 42.1 M） | 第一关；命名最规整（Boat/Crane/Quay）；体量适中，适合当风格样板 |
| 2 | L4 + L5（472 张 / 94.7 M） | 港口续篇，与 L3 共用族，风格可复用 |
| 3 | L6 + L8（533 张 / 101.8 M） | 街道是出现最久的场景，也是玩家印象最深的一段 |
| 4 | L10 + L11 + L12（435 张 / 123.7 M） | 地下段，共用 `Shafts*` / `Subway*` / `WaterReservoir*` 族 |
| 5 | L7 + L13 + L14（740 张 / 111.6 M） | 夜总会、车库电梯、飞艇，各自独立 |
| 6 | UI（11 张） | 独立小批次，收益/成本比最高，可随时插队 |
| 7 | FX（8 张） | 只调色，半天 |

先 L3 的理由：**风格样板要在体量可控的关卡上定下来**。1450 张里任何一张画错风格，
返工成本都是乘以张数的。

---

## 7. 未覆盖 / 待确认

- **UI 图集没有逐格拆解**：`HudAtlasHD`（2048×1024）、`MenuAtlasHD`、`HudAtlasSD`
  是 NGUI 图集页，83 个 UISprite / 21 个 UI2DSprite / 16 个 UITexture 引用其中的矩形。
  重画需要按 atlas 内的 sprite rect 切分，工作量不在"11 张"这个数字里。
- **光照/雾效不是纹理**：`Rain`、`Fog`、`Lightning`、`OldFog` 是粒子系统 + Shader，
  改观感要动 Shader/材质，不在本清单。
- **角色与武器不在本清单**：见 `docs/CHARACTER_ROSTER.html` 与
  `docs/HAT_ROLLOUT.md`（42 个角色已全部合流完成）。
- **水面/玻璃的滚动 UV**：部分图层靠材质 UV 动画，重画时要保证接缝可平铺。

---

## 8. 交付物

| 文件 | 内容 |
|---|---|
| `docs/SCENE_LAYERS.html` | 可视化目录：13 关合成全景 + 逐图缩略表 + 分层表 |
| `art/scene_inventory.json` | 1450 行结构化清单（名称/文件/path_id/尺寸/fill/painted/实例/关卡/order/GO 名） |
| `art/scene_inventory.csv` | 同上的表格版，可直接 Excel 筛选 |
| `art/scene_batches.json` | 批次定义 |
| `art/scene_sheets/level*.png` | 13 张逐图缩略表（2012px 宽，格内含名称与尺寸） |
| `art/scene_sheets/scene_level*.png` | 13 张合成全景，另附 `_rows` 折行版 |
| `art/scene_sheets/top_backdrops.png` | 面积最大 48 张，定风格基调用 |
| `art/scene_sheets/fx.png` / `ui.png` | 粒子层 / UI 图集 |
| `art/scene_sheets/probe_restyle.png` | 程序化重彩在场景上的失败证据 |
| `tools/scripts/scene_{survey,textures,stats,sheets,render}.py` | 全流程可复现 |
| `tools/scripts/build_scene_doc.py` | 生成本目录 HTML |
