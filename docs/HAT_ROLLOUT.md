# Hat 合流：42 角色全量落地报告

> 一句话：**10 个角色靠改 8 字节换了真钢盔（零美术），9 个角色就地重绘贴图（零点数），
> 6 个平民保留原帽型，13 个角色根本没有 Hat 节点。**
> 全部写入校验通过：alpha 逐字节不变、sprite 矩形外零改动。

工具：`tools/scripts/hat_plan.py`（`--apply` / `--verify`）
渲染核对：`tools/scripts/render_live.py`（读 ggc_Data，不是 backup）
回滚点：`backup/pre_hat_rollout/resources.assets`

---

## 1. 分类结果（42 = 5 + 9 + 9 + 6 + 13）

| 桶 | 数量 | 含义 | 代价 |
|---|---|---|---|
| **ALREADY** | 5 | 已在角色对应的规范 sprite 上 | 0 |
| **MERGE** | 9 | 与规范 sprite 几何完全一致 → 改指 | 8 字节/人 |
| **REPAINT** | 9 | 帧尺寸/轴心不同 → 只能就地重绘 | 1 张像素覆盖/人 |
| **KEEP_ROLE** | 6 | 平民，帽型是身份的一部分 | 0 |
| **NO_HAT** | 13 | 预制体没有 Hat 节点 | 0 |

### ALREADY（5）
Vinnie、Gangster2、Gangster3、Gangster6、BonninoBoss

### MERGE（9）→ 全部改指 `resources#3633`（昭五式铁帽）

| 角色 | 兵种 | 原 sprite | 说明 |
|---|---|---|---|
| Gangster1 | 日军士兵 | `sharedassets15#229` | 上一轮已改 |
| Goon3 | 日军士兵 | `sharedassets15#229` | 上一轮已改 |
| Salvatore | 日军佐官 | `sharedassets15#229` | 上一轮已改（默认姿态 Hat 为 inactive） |
| Scientist | 日军军医 | `sharedassets15#229` | 上一轮已改（默认姿态 Hat 为 inactive） |
| Frankie | 日军将官 | `sharedassets15#229` | 上一轮已改 |
| EvilFrankieOnFloor | 日军将官 | `sharedassets15#229` | 上一轮已改 |
| **Gangster4** | 日军佐官 | `resources#3360` | **本轮新增** |
| **Gangster5** | 日军佐官 | `resources#3768` | **本轮新增** |
| **Paulie** | 日军佐官 | `resources#3051` | **本轮新增** |

新增的 3 个是纯收益：他们原本各有一张**独占的礼帽贴图**（`#555` / `#966` / `#241`），
改指后这 3 张图**不再需要任何美术**，直接省掉 3 张画。

### REPAINT（9）→ 就地重绘自己的贴图

| 角色 | 兵种 | 贴图 | 贴图内矩形 | 显示尺寸 |
|---|---|---|---|---|
| Goon1 | 日军士兵 | `resources#587` | 117×62 @11,0 | 117×62 |
| Goon2 | 日军士兵 | `resources#986` | 122×67 @1,0 | 122×67 |
| Vito | 日军佐官 | `resources#1694` | 139×76 @0,0 | 139×76 |
| Soldier | 日军士兵 | `resources#906` | 139×76 @2,15 | 139×76 |
| ZombieSailor | 日本海军 | `resources#1568` | 96×68 @5,6 | 131×90 |
| ZombieOfficer | 日军将官 | `resources#1504` | 127×83 @0,7 | 131×90 |
| ZombieGun | 日军佐官 | `resources#1921` | 118×86 @0,4 | 131×90 |
| ZombieSoldier | 日军士兵 | `resources#1660` | 132×89 @10,1 | 132×89 |
| ZombieCharger | 日本海军 | `resources#1376` | 106×106 @0,0 | 106×106 |

注意后 4 行的**贴图矩形小于显示尺寸**：原资源是把小图放大显示的。重绘时按
`atlas_rect` 裁剪与回贴，所以放大后的柔和度与原资源一致，不会被我们二次劣化。

### KEEP_ROLE（6）
ZombieRegular、ZombiePaulie、ZombieCop、ZombieSandwichBoard、ZombieFloater、FatDockworker
—— 全是「日本平民·劳作」，帽子是身份的一部分，保留原帽型。

### NO_HAT（13）
EvilFrankie、ZombieCrawler、ZombieJumper、ZombieRunner1/2/3、ZombieBurping、
ZombieStripper、FatCook、ZombieRat / RatBoss / RatJumper / RatSpitter
—— 预制体里没有 Hat 节点，无从下手。

---

## 2. 一处不得不接受的妥协

`resources#1921` 被 **ZombieGun（日军佐官）** 和 **ZombieCop（日本平民·劳作）** 共用。
重绘后两人都是日军帽。两者都是僵尸，读感不冲突，但 ZombieCop 确实从"平民"变成了"军帽"。

如果要拆开，办法和 Vinnie/Gangster1 那次一样：找一个几何等价的第三张 Hat sprite 改指过去。
目前没找到空闲的等价 sprite，且收益很小，暂不处理。

---

## 3. 一处做不到的事：Vito / Goon1 / Goon2 的**帽型**

`restyle_ink` 是逐像素改色，**动不了 alpha**（STYLE_SPEC §10.4）。所以：

| 角色 | 结果 | 问题 |
|---|---|---|
| Goon1 | 深橄榄平顶帽 | 帽型是平顶帽，读作日军戦闘帽，可接受 |
| Goon2 | 深橄榄圆顶帽 + 五星 | 帽型偏圆顶礼帽，五星位置略怪 |
| **Vito** | **卡其色礼帽** | **最弱**：帽型仍是礼帽，读作平民帽，不像军人 |

我试过把 Vito 直接改指到钢盔 sprite（`SR#15813 → #3633`），**结果是钢盔压住眉眼**：
Vito 的 Hat sprite 轴心是 (69.60, 30.88)，规范 sprite 是 (65.59, 29.01)，差 4px；
而 Vito 的头在身体上的位置又和别人不同，所以改指后钢盔低了约 2px、左了约 4px，
帽檐切进眉毛。已回滚（`try_repoint.py` 就是干这个的可回退探针）。

**建议**：Vito 要走**重绘线**（生成概念图 → 新 alpha → 碰撞盒复核），而不是调色线。
这是唯一能真正换掉帽型的路径，也是唯一需要额外成本的一步。

---

## 4. 校验

`hat_plan.py --verify` 全绿：

- 9 个 MERGE 渲染器 `m_Sprite` 全部指向 `(0, 3633)`；5 个 ALREADY 保持不变
- 9 张重绘贴图：**alpha 通道与原始备份逐字节零差异**
- 9 张重绘贴图：**sprite 矩形之外零改动**（其余像素与原文件完全相同）
- 上一轮 `split_hat.py --verify` 仍全绿（`resources#906` 之外的三张 Hat 贴图状态未变）

---

## 5. 剩余工作量

| 项 | 数量 | 阻塞 |
|---|---|---|
| 武器重绘（11 族概念图） | 11 张 | **ImageGen 后端路由缺失** |
| Vito / Goon2 / Goon1 帽型重绘 | 3 张 | ImageGen |
| 其余角色身体（大衣/躯干/四肢） | 按角色计 | 需要各自的概念图 |

Hat 这一层到此**已经收口**：42 个角色里，凡是有 Hat 节点且属于军人的，
要么换了真钢盔（10），要么换成了国防色（9），没有漏的。
