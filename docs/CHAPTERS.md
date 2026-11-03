# 章节 ↔ 场景 ↔ 关卡文件 权威对照

这份对照不是猜的，三条独立证据互相咬合：

1. **build settings 场景表**：`ggc_Data/mainData`（Unity 4 的场景清单载体，不是
   `globalgamemanagers`）里按顺序列着 16 个 `.unity`，去掉 Game / MainMenu / NGUI /
   EmptyLevel 四个非关卡场景，剩下 12 个正是 `level3`–`level14`。
2. **章节卡贴图**：`resources.assets` 里有 11 张 **800×500** 的 Texture2D，名字直接就是
   场景名（`HarbourPart1`、`BrokenBridge`、`SecretLab`…）；第 12 张 `Boat` 单独躺在
   `sharedassets2.assets` 里——只扫 `resources.assets` 会漏掉它，这是第一次只找到 11 张的原因。
3. **游戏内章节选择界面的照片**：给出中文章节名与卡面标题（「战争码头」「遥远的桥」…），
   顺序与上面 12 个一一对齐。

## 对照表

| # | 中文章节名 | 卡面标题 | 贴图名 | 关卡文件 | 场景 | 画面内容 |
|---|---|---|---|---|---|---|
| 1 | 轮船 | 到达即死亡 | `Boat` | level3 | boat | 船舱内部，黄绿墙板、舷窗、木桶 |
| 2 | 暴徒镇港口 | 战争码头 | `HarbourPart1` | level4 | harbour | 夜码头、栈桥棚屋、月亮、杂物 |
| 3 | 市郊 | 仓库暴乱 | `HarbourPart2` | level5 | harbourPart2 | 船坞、门吊、船体、仓库 |
| 4 | 暗黑小巷 | 一夜肢解 | `Alleys` | level6 | alleyStreets | 砖墙小巷、绿门、壁灯 |
| 5 | 博尼诺的脱衣舞夜总会 | 干净利索！ | `Stripclub` | level7 | stripclub | 红紫舞台、包厢、吧台 |
| 6 | 军团据点 | 乔尼，拿起你的枪！ | `Bridge` | level8 | bridge | 石阶、铁栏、探照灯、据点建筑 |
| 7 | 河流 | 遥远的桥 | `BrokenBridge` | level9 | brokenBridge | 夜河、断桥、月亮、汽车残骸 |
| 8 | 下水道 | 追逐白日梦 | `SewersPart1` | level10 | sewers | 砖砌暗渠、拱顶 |
| 9 | 存储器 | 大智若愚 | `SewersPart2` | level11 | sewersPart2 | 蓄水池、穹顶、水面 |
| 10 | 选择标签栏 | 月光屠杀 | `SecretLab` | level12 | secretLab | 铁网、探照灯、厂区外景 |
| 11 | 建筑工地 | 有很长的路要走 | `ConstructionSite` | level13 | constructionSite | 脚手架、跳板、未完工楼体 |
| 12 | 屋顶 | 圣诞老公公来了 | `Rooftops` | level14 | rooftops | 屋顶、民居、夜空 |

产物：`art/chapter_cards/*.png`（12 张 800×500 原图）、`_sheet.png`（带名字总表）、
`chapters.json`。生成脚本 `tools/scripts/chapter_cards.py`。

## 两个必须记下来的发现

### 1. 「选择标签栏」是本地化 bug

第 10 章的章节名显示为「选择标签栏」，而它的场景是 `secretLab`、卡面标题是「月光屠杀」。
这明显是**一句 UI 文案漏进了章节名表**——原文应该是「秘密实验室」之类。
不在我们的改造范围，但要知道：**改这一关的章节名会顺带修掉这个 bug**，是个白送的加分项。

### 2. 这 12 张卡是 UI 资源，也必须一起重画

它们躺在 `resources.assets` 里，由 NGUI 的章节选择界面引用，**不是关卡场景美术**。
所以只改关卡贴图的话，进游戏选章节时会看到「旧卡通画风的预览图 + 新国画风的实际关卡」，
接缝非常明显。

处理方式：这 12 张属于 UI 层，跟 UI 图集（`HudAtlasHD` / `MenuAtlasHD`）一起排期；
但它们画的就是关卡本身，**最好和对应关卡的 T1 地标一起重绘**，风格才连续。

## 对历史改编的影响（重要）

之前 `SCENE_PLAN.md` 里的历史标签是**按美术猜的**，现在有了权威场景名，可以校正：

| 关卡 | 之前写的 | 实际场景 | 校正后建议 |
|---|---|---|---|
| L3 | 仰光港 | **boat 船上** | 伊洛瓦底江运兵船 / 撤退渡江 |
| L4 | 腊戍转运站 | **harbour 港口** | 仰光港 1942.3（英军撤离前） |
| L5 | 曼德勒·伊洛瓦底江 | **harbourPart2 船坞仓库** | 仰光码头区后段 / 仁安羌油田物资转运 |
| L6 | 腾冲古城 | **alleyStreets 街巷** | 腾冲古城街巷（原判断成立） |
| L7 | 蓝姆伽军人俱乐部 | **stripclub 夜总会** | 曼德勒英军俱乐部（插叙，无战役名） |
| L8 | 同古城区 | **bridge 桥头据点** | 惠通桥东岸桥头堡 |
| L9 | 惠通桥 | **brokenBridge 断桥** | **惠通桥 1942.5.5 炸桥**（完全吻合，原判断正确） |
| L10 | 松山坑道 | **sewers 下水道** | 松山日军坑道工事 |
| L11 | 松山地下工事 | **sewersPart2 蓄水池** | 松山子高地坑道药室 / 蓄水池 |
| L12 | 蓄水池/指挥所 | **secretLab 厂区** | 日军地下指挥所 / 战俘营 |
| L13 | 雷多中印公路 | **constructionSite 工地** | 修筑中印公路 / 惠通桥抢修 |
| L14 | 密支那机场 | **rooftops 屋顶 + 齐柏林飞艇** | 密支那机场 / 飞虎队 P-40（飞艇需改轮廓） |

三条硬约束不变：L9 断桥是收益最高的一关；L14 的飞艇没有碰撞盒，改轮廓成本低但要重跑网格覆盖验证；
L7 没有对应战役，只能做插叙，不要硬套战役名。
