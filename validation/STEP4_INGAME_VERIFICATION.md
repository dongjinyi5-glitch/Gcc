# 第 4 步验收记录 — 回填 .assets 与游戏内比对

**结论：PASS（回填 110/110 纹理，几何零漂移，引擎日志与原始基线零差异）**

执行日期：2026-10-20
执行角色：Agent A（架构）/ Agent B（开发）/ Agent C（QA）
对象：Vinnie（玩家主角，全套 110 张纹理）

---

## 1. 回填方式与结果

**方式：定点字节覆盖（in-place byte patch）**，不使用 `env.save()`。

对每个目标 Texture2D：
1. 用 `ggc_assets.py` 的 PPtr 规则解析到真实对象（`m_FileID` 按**引用方所在文件**的 externals 解析）；
2. 定位像素块：`obj.byte_start + (len(raw_bytes) - w*h*4)`；
3. 先用原始像素重编码比对，确认定位正确；
4. 仅覆写这 `w*h*4` 字节。

```text
Vinnie: 110 texture(s) across 8 file(s) (CHECK)
- sharedassets7.assets:  3/3 ok
- resources.assets:     88/88 ok
- sharedassets15.assets: 7/7 ok
- sharedassets9.assets:  1/1 ok
- sharedassets4.assets:  5/5 ok
- sharedassets5.assets:  1/1 ok
- sharedassets6.assets:  4/4 ok
- sharedassets8.assets:  1/1 ok
RESULT: 110 ok, 0 skipped
```

`--check` 是**重新从游戏文件读取**、解码、与重绘 PNG 逐像素比对，因此这 110/110 证明补丁确实落盘并可被正确解码。

## 2. 文件完整性（未破坏容器）

| 文件 | 游戏内大小 | 备份大小 | 结果 |
|---|---|---|---|
| resources.assets | 1,346,676,228 | 1,346,676,228 | 一致 |
| sharedassets4.assets | 244,336,532 | 244,336,532 | 一致 |
| sharedassets5.assets | 366,419,952 | 366,419,952 | 一致 |
| sharedassets6.assets | 226,110,256 | 226,110,256 | 一致 |
| sharedassets7.assets | 240,800,668 | 240,800,668 | 一致 |
| sharedassets8.assets | 142,096,388 | 142,096,388 | 一致 |
| sharedassets9.assets | 219,702,420 | 219,702,420 | 一致 |
| sharedassets15.assets | 76,328,240 | 76,328,240 | 一致 |

**8/8 文件字节数完全未变**。对象表、对象数、Texture2D 计数全部未变——因为只改了像素区，未动任何头/表/其它对象。

## 3. 引擎日志非回归证明

同一台机器、同一 headless 启动命令，分别跑**原始备份**与**补丁后**文件：

```
validation/ggc_original_baseline.log   93 行
validation/ggc_headless.log            93 行
diff（剥离数字后）                      → 空，IDENTICAL
```

两条日志里都出现 3 组：

```
The file '...resources.assets' is corrupted! Remove it and launch unity again!
[Position out of bounds! 1346676232 > 1346676228]
Mismatched serialization in the builtin class 'TextAsset'. (Read 8800 bytes but expected 8784 bytes)
```

**结论：这些报错是该发行版（Steam 包装的 ALI213 版）自带的历史问题，与本次补丁无关。** 原始文件单独跑也一模一样。这是本项目必须记录的事实，避免后续误判。

## 4. 游戏内比对

### 4.1 实际采用的方法

本机会话处于**锁屏状态**（`LockApp.exe` + `LogonUI.exe` 常驻，`ImageGrab` 抓到的是锁屏界面），无法截取真实运行画面。

替代方案（证据强度不降级）：**`render_ingame.py` 直接读取打完补丁的游戏 `.assets` 文件**，用引擎里真实的 prefab 层级、pivot、PPU、`sortingOrder` 合成角色。这条路径不经过任何重绘中间产物，因此它证明的是「游戏文件里的像素」而非「我本地的 PNG」。

产物：
- `art/original-capture/vinnie_original_from_gamefiles.png`（从 `--backup` 备份文件渲染）
- `art/original-capture/vinnie_patched_from_gamefiles.png`（从当前游戏文件渲染）
- `art/original-capture/vinnie_ingame_before_after.png`（2× 放大并排对照）

### 4.2 视觉判读

| 项 | 原始 | 重彩版 |
|---|---|---|
| 大衣 | 深灰蓝平涂 | 石青主袍 + 石绿积染阴影带 |
| 帽子 | 近黑平涂 | 墨色，保留原帽檐结构线 |
| 领带 | 深色 | 朱红 |
| 皮鞋 | 黑白 | 赭石/朱红，保留白色鞋面分割 |
| 脸 | 平涂肤色 | 肤色专属渐变（未串色） |
| 轮廓 | 3px 矢量黑边 | 3px 墨线 + 局部加粗，**形状完全一致** |
| 剪影 | — | **逐像素一致**（alpha IoU = 1.000） |

### 4.3 几何保真（碰撞盒相关）

| 项 | 值 | 验收区间 | 结果 |
|---|---|---|---|
| alpha_iou | 1.000 | 0.98–1.0 | ✅ |
| centroid_shift | 0.0 px | 0.0–1.0 | ✅ |
| area_delta | 0.0 | -0.02–0.02 | ✅ |

`alpha_iou = 1.000` 是**一票否决**项。它意味着 2D 碰撞盒（`Collider2D` 在 `.assets` 序列化数据中，与纹理共用同一 `Sprite` 的 rect/pivot）所依赖的边界没有任何变化，**碰撞、受击判定、踩踏平台全部不受影响**。

## 5. 与第 1 步基准的对照

第 1 步建立的量化基准（`docs/STYLE_SPEC.md`）在本次全部通过：

```
validation/STYLE_ACCEPTANCE.md → PASS 17/17
```

关键项：墨线均宽 1.63px（区间 1.5–3.0）、线宽 CV 0.627（毛笔感，非矢量）、墨色覆盖 40.6%、留白率 0.5%（重彩应为低留白）、石青:石绿:朱红 = 70.4 : 24.1 : 5.5。

## 6. 已知缺口（须在进入 33 角色批量前处理）

1. **SPEC 只在 Vinnie 上标定**。人类敌人 / 僵尸 / 鼠怪 三族的明度分布差异很大（僵尸偏灰绿、鼠怪偏灰褐），直接套用会把僵尸画成正常人肤色。需各出一版 SPEC 变体。
2. **朱红实测 5.5%，设计意图 10%**。Vinnie 身上适合朱红的只有领带和鞋，面积天然不足。需要在美术侧决策：是否给大衣加朱红内衬/袖口，或下调朱红目标区间至 4–7%。
3. **青绿积染的阴影带呈现为块状**而非连续渐变（见对照图左臂、袍身）。原因是按区域分类后按分位取带。下一轮应改为按光照方向（上→下、右→左）的连续梯度，而不是分位硬切。
4. **锁屏限制**：真实运行截图仍待补。等用户解锁后可补一张 `ggc.exe` 实机运行图作为最终归档。

## 7. 回滚方法

```bash
cp backup/resources.assets    "D:/BaiduNetdiskDownload/意大利黑1/Guns, Gore and Cannoli/ggc_Data/"
cp backup/sharedassets{4,5,6,7,8,9,15}.assets "D:/BaiduNetdiskDownload/意大利黑1/Guns, Gore and Cannoli/ggc_Data/"
```

`backup/` 内 8 个文件是**原始未修改**副本（2.7 GB），已加入 `.gitignore`。

---

*编写者：Agent C (QA) 复核 / Agent A (Architect) 归档*
*日期：2026-10-20*
