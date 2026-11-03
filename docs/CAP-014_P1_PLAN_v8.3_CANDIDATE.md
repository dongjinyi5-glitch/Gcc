# CAP-014 P1 防护方案 v8.3（候选稿）

> **CANDIDATE — N01_T5_ALLGONE_FIXES_COMPLETE — REVIEW_REQUIRED — NOT AUTHORIZED FOR EXECUTION**
>
> 本文档为纯设计文本。全部测试用例处于 `NOT EXECUTED` 状态。
> 本版**只处理三项**：**N-01**（自动 `CP-5` 的旧代保留与发布语义，新增 `A.5.11`）、**N-04**（T5 的起点只能是 `MANUAL_BLOCKED`）、**DD-1**（组合 #3a 纳入 ALL-GONE，新增 `EMPTY_STATE` 谓词）；
> **F-07～F-19（P1 × 6 + P2 × 7）、N-02、N-03 仍未处理**，且**未作出任何 BLK 决策**。
> 未经人工审查与书面授权，不得进入 P1 测试执行、功能实现或真实资产写入阶段。

| 项 | 值 |
|---|---|
| 文档版本 | **v8.3（候选稿）** |
| 直接上游 | v8.2（`docs\CAP-014_P1_PLAN_v8.2.md`，211,324 B，2,073 行，SHA-256 `7f1d20ddcff15adc81b342d11d0806dc34ba3c0cbdf9ccf68eeebca14572080b`，**未被修改**） |
| 间接上游 | v8.1（166,205 B / 1,808 行 / `b5cc4668…9ae50f`）→ v8（135,620 B / 1,607 行 / `c864625b…48659`），**均未被修改** |
| 静态审查依据 | `docs\CAP-014_P1_v8_STATIC_CLOSURE_REVIEW.md`（83,420 B，1,149 行，SHA-256 `315b74c176a8f49c5f16df688ea74b8e0715bb0e85e6b63042115254aeebdf97`）：19 条问题（P0 × 6 / P1 × 6 / P2 × 7） |
| 修订依据 | **本轮只处理三项**：**N-01**（自动 `CP-5` 仍用 `os.replace`，与红线 16 冲突 → 拆为 CP-5a/5b/5c + 新增 `A.5.11`）/ **N-04**（T5 被写成 `RECOVERY_REQUIRED` 的出口，结构上不可达 → 起点唯一化为 `MANUAL_BLOCKED`）/ **DD-1**（组合 #3a 的 ALL-GONE 适用性在 v8.2 中三处互斥 → 经人工裁定**从严**，新增 `EMPTY_STATE`）。**F-07～F-19 未处理；N-02 / N-03 已记录未修** |
| 文档性质 | PLAN-ONLY，静态文本 |
| 执行状态 | 全部用例 `NOT EXECUTED` |
| **P0 阻塞项** | **5 项（A.22：BLK-1…BLK-5），阻断真实写入，需人工决策；本轮未改变任何一项的决策状态** |

### 阶段状态（六个状态不可互相替代）

| 阶段 | 当前 | 说明 |
|---|---|---|
| ① 文档修订完成 | **是（v8.3 候选稿，仅 N-01 / N-04 / DD-1）** | 三项已写入本文档；**F-07～F-19 未处理**，**N-02 / N-03 未修** |
| ② 文档静态自检通过 | **是（仅就本轮 3 项而言）** | 见 A.18、B 统计与 D.3c 自检记录；**不覆盖 P1/P2 未修项** |
| ③ 人工审查通过 | **否** | 需人工逐条审查 N-01 / N-04 / DD-1、BLK-1…BLK-5，以及未处理的 13 条 P1/P2 |
| ④ 功能实现完成 | **否** | 全部机制未实现（C.2） |
| ⑤ 测试执行通过 | **否** | 全部用例 `NOT EXECUTED`（C.3） |
| ⑥ 生产写入获授权 | **否** | PWA-8 未满足（BLK 未决） |

> **① + ② 只说明"文档改完且自洽"，不说明任何保护机制有效，也不授权真实资产写入。**

---

# A. 完整方案

## A.1 边界与命名约定

### A.1.1 四级禁写边界

| 级别 | 对象 | 允许 | 禁止 |
|---|---|---|---|
| **L0-A** | `D:\BaiduNetdiskDownload\意大利黑1\Guns, Gore and Cannoli\ggc_Data\*.assets`（17 个） | 仅 `open(...,'rb')`、`os.stat` | 写 / 删 / 移 / 改名 / 覆盖 |
| **L0-B** | `D:\AI\Guns, Gore and Cannoli from WB\backup\**\*.assets`（14 个） | 同上 | 同上；测试快照不得写入此目录 |
| **L0-C** | `F:\GGC_snapshots\baseline_ledger.json` | 只读 | 覆盖 / 追加 / 改名 |
| **L0-D** | 3 个零字节 `roundtrip_*.assets` 验证文件（见 A.1.3） | 仅 `os.stat`、`open(...,'rb')` | 写 / 删 / 移 / 改名 / 覆盖；**不得作为基线、原始资产或测试目标** |
| **L1** | `%TEMP%\ggc_p1\**` | 唯一允许写入的根 | — |

**不重叠原则**：34 个已知 `.assets` 每个只归属一个级别（A.1.4）。

### A.1.2 命名约定

| 记号 | 含义 |
|---|---|
| `S<组><字母>` / `S<组>` | 测试用例 / 场景组 |
| `ST-<n>` | 被测操作步骤（A.8，12 步；v8 明确块写入模型与写游标） |
| `H<n>` | M9 屏障钩子位置（v7 扩为 6 个） |
| `RP-<n>` | 尾部修复步骤（A.6） |
| `CP-<n>` | 检查点更新步骤（A.5.5） |
| **`CP-R`** | **人工基线重建（A.5.10，仅由 T5 触发，v8 新增）** |
| **`MP-<n>`** | **人工处理阶段（A.7.9：MP-1 调查/恢复、MP-2 重置/签核，v8 新增）** |
| `V-<n>` / `V-T` | 启动扫描校验项（A.5.6；空态组合另见 A.5.9） |
| `T-<id>` | 测试目标类型 |
| `T1–T5` | 状态解除途径（v7 新增 T5 人工重置） |
| `PWA-<n>` / `STA-<n>` | 生产 / 测试准入条件 |
| `C<n>` / `M<n>` | 通用断言（v8 为 18 条，逐条定义见 A.19.1）/ 注入手段 |
| `BLK-<n>` | P0 阻塞项（A.22） |

### A.1.3 三个 `roundtrip_*.assets` 的精确路径

**来源**：`F:\GGC_snapshots\baseline_ledger.json`（CAP-014.4 产出，34 条记录）。以下路径逐字复制自台账 `normalized_absolute_path` 字段，未拼接、未推测。

| # | 精确路径 | 大小 | SHA-256（前 16 位） | entity_type |
|---|---|---|---|---|
| 1 | `D:\AI\Guns, Gore and Cannoli from WB\validation\roundtrip_sharedassets1.assets` | 0 字节 | `e3b0c44298fc1c14` | `DECOY_EMPTY` |
| 2 | `D:\AI\Guns, Gore and Cannoli from WB\validation\roundtrip_sharedassets10.assets` | 0 字节 | `e3b0c44298fc1c14` | `DECOY_EMPTY` |
| 3 | `D:\AI\Guns, Gore and Cannoli from WB\validation\roundtrip_sharedassets3.assets` | 0 字节 | `e3b0c44298fc1c14` | `DECOY_EMPTY` |

三条记录完整 SHA-256 均为 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`（空字节串的 SHA-256）。

**性质与禁令**：① 保留 `DECOY_EMPTY` 标记；② 不得视为有效基线、原始游戏资产、可写入测试目标或可回退来源；③ 按 basename 建索引时不得覆盖同名 live 条目；④ 任何测试不得使用、改写、修复或删除；⑤ 路径变化须重新以台账为准。

**路径确认状态**：3/3 `PATH_VERIFIED`（来源为 CAP-014.4 台账，非推测）。

### A.1.4 34 个 `.assets` 的完整分类（不重叠）

| 级别 | 数量 | 构成 |
|---|---|---|
| L0-A | 17 | `ggc_Data` 下 17 个（`resources.assets` + `sharedassets0`–`sharedassets15`） |
| L0-B | 14 | `backup\` 根 8 + `pre_hat_split\` 2 + `pre_hat_rollout\` 1 + `pre_scene_20261022_2327\` 1 + `pre_scene_20261027_1545\` 2 |
| **L0-D** | **3** | A.1.3 三个 `roundtrip_*.assets` |
| **合计** | **34** | 与台账 `files_total = 34` 一致 |

## A.2 术语与状态

### A.2.1 状态层

| 层 | 状态集 |
|---|---|
| 文件基线状态 | `VERIFIED_BASELINE` / `UNVERIFIED` / `KNOWN_OUTPUT` / `UNKNOWN` |
| 快照状态 | `SNAPSHOT_VALID` / `SNAPSHOT_ORPHAN` / `SNAPSHOT_NO_SIDECAR` / `SNAPSHOT_CORRUPT` / `SNAPSHOT_ABSENT` / **`SNAPSHOT_CONFLICT`（v8 新增：发布时同名已存在）** / **`SNAPSHOT_PUBLISH_UNSUPPORTED`（v8.1 新增，M4：发布机制不支持或不能安全执行，与"同名冲突"严格区分）** |
| 操作状态（派生） | `OP_COMMITTED` / `OP_ABORTED` / `OP_RECOVERED` / `OP_SUPERSEDED` / `OP_UNRESOLVED` / **`OP_MANUAL_RESET`（v7 新增）** |
| 记录持久性（派生） | `DURABLE` / `PROVISIONAL` |
| 检查点状态 | `VERIFIED` / **`VERIFIED_MANUAL`（v8 新增：经 CP-R 人工重建）** / `ABSENT_CLEAN` / `ABSENT_DIRTY` / `INCONSISTENT` |
| **WAL 身份状态（v7 新增）** | `IDENTITY_VERIFIED` / `IDENTITY_MISMATCH` / `IDENTITY_UNVERIFIABLE` / `IDENTITY_NOT_APPLICABLE` |
| **故障根因分类（v8.2 新增，R16）** | `FRC-IDENTITY_MISMATCH` / `FRC-IDENTITY_UNAVAILABLE` / `FRC-CHECKPOINT` / `FRC-FAILURELOG` / `FRC-STRUCTURAL` / `FRC-TARGET` / `FRC-UNKNOWN`（**派生值**，有序派生规则见 A.2.3；**不得人工指定**） |
| **故障日志状态（v7 新增）** | `FAIL_READABLE_EMPTY` / `FAIL_READABLE_WITH_RECORDS` / `FAIL_UNREADABLE` / `FAIL_CORRUPT` / `FAIL_ABSENT_CONSISTENT` / `FAIL_ABSENT_INCONSISTENT` |
| **运行状态（v7 三值）** | `READY` / `RECOVERY_REQUIRED` / **`MANUAL_BLOCKED`** |

**`RECOVERY_REQUIRED` vs `MANUAL_BLOCKED`**：前者存在自动出口（T1 / T4）或人工出口（**仅 T2**）。**（v8.3，N-04）`T5` 不是 `RECOVERY_REQUIRED` 的出口**——它的**唯一**起点是 `MANUAL_BLOCKED`（理由见 A.7.4"T5 的起点不可达"）。后者**没有任何自动出口**，且其人工出口**按故障类别分裂为三类（v8.1 / v8.2）**：

- **非身份类** `MANUAL_BLOCKED`（`FAULT_CLASS ∈ {FRC-CHECKPOINT, FRC-FAILURELOG, FRC-STRUCTURAL}`，且 `WAL_IDENTITY_STATUS` 为 `IDENTITY_VERIFIED` 或合法 `IDENTITY_NOT_APPLICABLE`）→ **只有** T5 三阶段人工出口（且须 A.7.3 T5 行四条硬前提全部成立）；
- **身份类** `MANUAL_BLOCKED`（`FAULT_CLASS ∈ {FRC-IDENTITY_MISMATCH, FRC-IDENTITY_UNAVAILABLE}`）→ **没有任何文档化出口**。`CP-R` 被 `CR-6` 两轴表禁止，T5 阶段 B 无法完成，因此 T5 对身份类故障**不可执行**（不是"执行后失败"，是"前提不成立"）。该状态只能保持，直到 BLK-1 决策。见 A.7.4、A.5.10 CR-6、A.15 第 10 项。
- **根因未定类** `MANUAL_BLOCKED`（`FAULT_CLASS == FRC-UNKNOWN`，v8.2 / R16）→ **同样没有文档化出口**：根因无法确认时，"该走哪条路"的判断本身不可靠，`CP-R` 一律禁止。

**（v8.2，R16）分类与身份状态是两个轴，不得互相替代**：`FAULT_CLASS` 回答"是哪一类故障把它卡住的"，`WAL_IDENTITY_STATUS` 回答"当前实测身份是什么"。二者**都**参与判定；`FAULT_CLASS` 由 A.2.3 的**有序派生规则**给出，**不允许人工挑选**，也不允许用"看起来像身份问题"替代派生。

**`VERIFIED` vs `VERIFIED_MANUAL`**：前者是机器校验通过的前缀；后者是**人工在两阶段（A.7.9）完成后由 `CP-R` 重建**的前缀，其检查点带 `manual_epoch` 印记。两者都允许 `WAL_STATE_COMPLETE == YES`，但 `wal_state_digest` 可区分，且 **T2 只接受 `VERIFIED`**。机器无法用 `VERIFIED_MANUAL` 证明历史真实性 → **BLK-5**。

**（v8.1，M1）`VERIFIED_MANUAL` 的授权边界**：`VERIFIED_MANUAL` **不是**"机器验证通过"，**也不是**写入许可。它只解除"检查点不可用"这一项，**必须**同时满足下列**四项否决条件全部不成立**才可能参与写入判定（见 A.7.8 真值表、A.10.1 PWA-6）：

| # | 否决条件 | 成立时的后果 |
|---|---|---|
| 1 | `manual_epoch == null` | 否决 |
| 2 | `BLK-5 != DECIDED_ACCEPT`（BLK-5 未决） | 否决 |
| 3 | 签核记录中**未**明确接受该 `manual_epoch` 下的写入 | 否决 |
| 4 | `OP_UNRESOLVED != ∅` | 否决 |

**任一项成立 → `VERIFIED_MANUAL` 一律 `WRITE_PERMITTED = NO`**。`VERIFIED_MANUAL` **永不单独**授予真实写入权限；把"集合内包含 `VERIFIED_MANUAL`"读成"可写"是错误解读（真值表见 A.7.8）。

### A.2.2 十九条术语红线

1. `TORN` 不是文件状态；部分写入表现为 `OP_UNRESOLVED` + 目标哈希 ∉ {B, A}。
2. `OP_SUPERSEDED` 不是 WAL 事件，是派生状态。
3. `REPAIR` 不是操作终态。
4. `FAILED` 不是操作终态，不关闭任何 op。
5. `PROVISIONAL` 不是 WAL 事件，也不是 `wal_failures` 的记录类型，是由持久证据派生的状态。
6. `.durable` 不是独立可信标记：必须能校验它描述的 WAL 前缀**存在且未被改动**。
7. `RECOVERY_VERIFIED` 与 `REDO_VERIFIED` 独立；`BYTES` 与 `OBJECT` 再分两维。
8. 并发保护不是完整覆盖；`W2-b` 是已证明的不可检出缺口（部分由 `V-T` 延迟检出，见 A.5.6）。
9. 可见 ≠ 已确认持久化：WAL 中存在某条记录，不等于该记录已通过检查点确认。
10. **（v7）文件身份不是绝对证明**：`st_ino` / 卷序列号 / 创建时间只能降低"被替换"的概率，不能形式化排除；单靠身份字段通过校验不构成安全结论。
11. **（v7）目标持久化先于 END**：`END` 只能在目标文件已持久化且回读验证通过之后写入；顺序颠倒即为缺陷。
12. **（v7）缺失的故障证据不能被"检查点已验证"替代**：`wal_failures` 不可用而 WAL 又不干净时，状态必须是 `UNKNOWN` / `MANUAL_BLOCKED`，不得推定为 `NO`。
13. **（v8）`MANUAL_BLOCKED` 不等于已恢复**：它只表示"自动路径全部关闭"，既不代表目标已回到基线，也不代表状态已被人工确认；T5 也**不修复任何数据**。
14. **（v8）快照与 sidecar 的发布必须"目标不存在才创建"**：`os.replace` 会替换同名目标，**禁止**用于快照发布；`SNAPSHOT_CONFLICT` 一律安全失败，不得覆盖。
15. **（v8）`END.target_sha256_after` 只有一个来源**：ST-10 / ST-11 已验证的预期哈希。**禁止**在 H6 之后重算目标哈希并回写该字段（否则 V-T 自我作废）。
16. **（v8.1，M3）检查点与快照的发布语义不同**：快照是**不可变证据**（一次写入、永久只读），发布必须"目标不存在才创建"（A.11.1）；检查点是**必须可更新的当代声明**，其更新必须"**先保留旧代证据、再发布新代**"（A.5.10 CR-e）。**禁止**直接覆盖旧检查点；也**禁止**把快照的"同名即中止"规则套用到检查点上。**（v8.3，N-01）本条同时约束自动 `CP-5` 与人工 `CP-R`**：自动路径旧代命名为 `pre_advance.<wal_size_at_marker>.<前缀哈希前 8 位>`，人工路径为 `pre_manual.<manual_epoch_id>`，两条路径**都不得**直接覆盖当代检查点（细则见 A.5.11）。
17. **（v8.2，R16）`FAULT_CLASS` 是派生值，不是判断**：只能按 A.2.3 的 F1–F9 有序规则得出；**禁止**人工指定、**禁止**只取"故障类别"或"身份状态"两轴之一做结论、**禁止**在 `mp1_evidence_ref` 中改写派生输入以改变分类。派生结果与 MP-1 记录不一致 → 强制降为 `FRC-UNKNOWN`。
18. **（v8.2，R18）截断必须在已验证句柄上执行**：`RP-4` 只允许 `os.ftruncate(H_wal.fileno(), ...)` / `SetEndOfFile(hFile)`；**禁止** `os.truncate(path, ...)`。截断**后**的身份复核（RP-4b）是**附加**检查，**不能**替代截断**前**的同句柄保证。
19. **（v8.2，R14 + R19）"仅 T5"不是授权**：表格中的 `T5*` 只表示"理论出口类别"；可执行性一律由 A.7.3 T5 行四条硬前提与 A.7.9 决定。`OP_UNRESOLVED != ∅` 或身份类故障时，`T5` **恒不可执行**，唯一允许的是保持 `MANUAL_BLOCKED`。

### A.2.3 故障根因分类 `FAULT_CLASS`（v8.2，R16）

**为什么需要它**：v8.1 的 `CR-6` 用"故障本身是否为身份类"这一**主观判据**分裂三类，导致 `IDENTITY_UNVERIFIABLE` **同时**落在 (a) 与 (c) 两个本应互斥的类别里（(a) 说"身份类一律禁止"，(c) 说"非身份类但身份不可得也禁止"）——同一实测值对应两个分类，判定不可复现。本节把分类改为**有序派生**，使每个 `(FAULT_CLASS, WAL_IDENTITY_STATUS)` 组合唯一。

**派生规则（严格短路，自上而下，第一条命中即为结果；顺序本身是规范的一部分）**：

| 序 | 命中条件（按顺序判定） | 派生结果 |
|---|---|---|
| **F1** | V-1b 失败：实测身份 ≠ 检查点声明身份 | `FRC-IDENTITY_MISMATCH` |
| **F2** | V-0 判定"WAL 不存在但检查点记录了非零 `wal_identity`" | `FRC-IDENTITY_MISMATCH` |
| **F3** | 句柄视图与路径视图矛盾（ID-5） | `FRC-IDENTITY_MISMATCH` |
| **F4** | 身份不可得（`st_ino == 0` 且无 `file_index`） | `FRC-IDENTITY_UNAVAILABLE` |
| **F5** | V-1 / V-2 / V-3 / V-4 / V-5 / V-6 任一失败，或检查点不可解析 | `FRC-CHECKPOINT` |
| **F6** | `FAILURE_LOG_STATUS ∈ {FAIL_UNREADABLE, FAIL_CORRUPT, FAIL_ABSENT_INCONSISTENT}` | `FRC-FAILURELOG` |
| **F7** | WAL 结构异常且不可按 A.6 修复（非末行不可解析 / seq 非单调 / 未知事件类型） | `FRC-STRUCTURAL` |
| **F8** | V-T 失败（目标当前哈希 ≠ 最后终态的 `target_sha256_after`） | `FRC-TARGET` |
| **F9** | 以上均不命中 | `FRC-UNKNOWN` |

**三条不变量（必须成立，否则视为文档冲突）**：

1. **`FRC-IDENTITY_*` ⟺ 身份状态为身份类**：`FRC-IDENTITY_MISMATCH` 必然伴随 `IDENTITY_MISMATCH`；`FRC-IDENTITY_UNAVAILABLE` 必然伴随 `IDENTITY_UNVERIFIABLE`。
2. **`FRC-CHECKPOINT` / `FRC-FAILURELOG` / `FRC-STRUCTURAL` / `FRC-TARGET` 出现时，`IDENTITY_UNVERIFIABLE` 必然已由 F4 拦下** → **不存在**"非身份类故障 + 身份不可得"这一交叉分类。v8.1 `CR-6(c)` 与 `CR-6(a)` 的重叠由此消除，`CR-6` 不再有 (c) 类。
3. **`FRC-UNKNOWN` 不等于"没有故障"**：它表示"派生输入不足或互相矛盾"，按 fail-closed 处理（禁止 `CP-R`、禁止任何自动路径）。

**派生输入（必须原样写入 `mp1_evidence_ref`）**：各 V-x 的结论、`WAL_IDENTITY_STATUS`、`FAILURE_LOG_STATUS`、V-T 结论、检查点解析结果。**禁止**只记录最终 `FAULT_CLASS` 而不记录输入——否则无法复核分类是否被改写。

**待决**：`FAULT_CLASS` 的派生在"输入本身互相矛盾"（例如 V-1b 报不一致而 `st_ino` 为 0）时如何取舍，本文档只规定"落到 `FRC-UNKNOWN`"，具体判据未定义（见 C.1 第 10 条）。

## A.3 持久化产物清单

| 产物 | 路径 | 性质 |
|---|---|---|
| 主 WAL | `wal\<target_key>.jsonl` | 追加式事件流，`buffering=0`，每行一次 write + fsync |
| 持久化检查点 | `wal\<target_key>.durable.json` | 描述 WAL 的一个可校验前缀（含身份与空态字段，A.5.2） |
| 失败日志 | `wal_failures\<target_key>.jsonl` | 追加式，记录写不进主 WAL 或 fsync 失败的事实 |
| 修复日志 | `wal_repairs\<target_key>.jsonl` | 追加式，`REPAIR_INTENT` / `REPAIR_DONE` |
| 尾部证据 | `wal_evidence\<target_key>.<ts>.tail.bin` | 被截断的原始字节，只增不改 |
| 签核 | `signoffs\<target_key>.<ts>.json` | T2 / T5 人工签核 |
| 快照 | `snap\<base>.<sha16>.assets` + `.json` | 内容 + sidecar |
| 锁 | `lock\<target_key>.lock` | 工具级锁文件 |
| 证据包 | `cases\<case_id>\evidence\` | 每用例归档 |

## A.4 WAL 事件与合法序列

### A.4.1 事件与必需字段（v7 新增第 7 类事件）

| 类别 | 事件 | 终态 | 关键字段 |
|---|---|---|---|
| 操作 | `BEGIN` | 开启 | `seq, op_id, op_kind, target_norm, target_identity{st_dev,st_ino}, target_sha256_before, size, snapshot_id, snapshot_sha256, tool, tool_sha256, args_digest, deps, pid, ts_wall, ts_mono`<br>**RECOVERY 额外**：`supersedes_recovery_op_id`、`expected_unresolved_set[]`、`expected_unresolved_set_digest`、`expected_unresolved_count` |
| 操作 | `END` | 是（WRITE） | `seq, op_id, op_kind, target_sha256_after, target_persisted:true, readback_verified:true, verify_summary, elapsed_ms`<br>**（v7）`target_persisted` 与 `readback_verified` 必须为 `true`，否则不得写 `END`**<br>**（v8）`target_hash_provenance{stage:"ST-11", precommit_recheck_verified:true, verified_sha256 == target_sha256_after, verified_before_seq}`：`target_sha256_after` 必须逐字等于 ST-11 的实测值，且该值必须在 H6 之前取得；**缺该字段或哈希与 ST-11 实测不符 → `END` 非法（C18）** |
| 异常 | `ABORTED` | 是（WRITE） | `seq, op_id, op_kind, reason, target_sha256_observed` |
| 异常 | `FAILED` | **否** | `seq, op_id(可空), stage, error_class, errno, target_sha256_observed, wal_durable, ts` |
| 恢复 | `RECOVERED` | 是（RECOVERY） | `seq, op_id, op_kind, snapshot_id_used, snapshot_sha256_used, snapshot_recomputed_sha256, pre_recovery_target_sha256, target_sha256_after, target_persisted, readback_verified, resolves_op_ids[], resolves_set_digest, resolves_count, recovery_verified:true, consistency_check:true` |
| 日志修复 | `REPAIR` | **否** | `seq, repaired_file, repair_of, repair_intent_id, discarded_bytes, discarded_lines, torn_tail_hex_prefix, evidence_path, reason, operator, ts` |
| **人工重置（v7 新增）** | **`MANUAL_RESET`** | 是（`op_kind=MANUAL`） | `seq, op_id, op_kind=MANUAL, override_reason, overridden_status{checkpoint_status, wal_identity_status, failure_log_status}, state_digest_at_override, target_sha256_observed, signoff_id, operator, ts`<br>**（v8）额外必填**：`unresolved_set_empty:true`、`mp1_evidence_ref`（MP-1 调查证据路径）、`target_sha256_confirmed_by_human`、`manual_epoch_id`、`checkpoint_rebuild_authorized:true` |

`REPAIR` 与 `MANUAL_RESET` 无 `op_id` 意义上的业务操作（`MANUAL_RESET` 自带独立 `op_id`）。检查点中 `last_durable_op_id` 对 `REPAIR` 记 `null`。

### A.4.2 合法序列

| 序列 | 结果 |
|---|---|
| `BEGIN(WRITE) → END` | `OP_COMMITTED` |
| `BEGIN(WRITE) → ABORTED` | `OP_ABORTED`（须复核 `observed == before`；不等则声明为假 → `OP_UNRESOLVED`） |
| `BEGIN(RECOVERY) → RECOVERED` | `OP_RECOVERED` |
| `BEGIN(RECOVERY) → FAILED` | **`OP_UNRESOLVED`**（`FAILED` 不关闭 op） |
| `BEGIN(RECOVERY) → ABORTED` | ❌ 非法 |
| `BEGIN(MANUAL) → MANUAL_RESET` | `OP_MANUAL_RESET`（**前提**：`OP_UNRESOLVED == ∅` **且** MP-1 调查证据存在 **且** MP-2 签核有效（A.7.9）；任一不满足即非法，**不得写 `MANUAL_RESET`**） |
| `MANUAL_RESET` 已持久 → `CP-R` | 允许（**顺序强制**：`MANUAL_RESET` 未持久时 `CP-R` 非法；见 A.5.10） |
| `BEGIN` 无自身终态但被已验证 `RECOVERED.resolves_op_ids` 覆盖 | `OP_SUPERSEDED` |
| `BEGIN` 无自身终态且未被覆盖 | `OP_UNRESOLVED` → `RECOVERY_REQUIRED` |
| 终态无 `BEGIN` / 同 `op_id` 两终态 / 未知 `op_id` | 隔离 → `RECOVERY_REQUIRED` |
| `REPAIR` / `FAILED` 单独出现 | 不改变任何 op 状态 |

### A.4.3 结构异常处理

| 异常 | 自动动作 | 禁止 | 结果 |
|---|---|---|---|
| 末尾残缺行 | 按 A.6 修复流程 | 解析为有效记录；不经 A.6 直接截断 | 见 A.6 |
| 中间行不可解析（非末行） | 隔离整文件 | 只丢该行继续 | `RECOVERY_REQUIRED` + 人工 |
| 重复（同 seq 同字节） | 折叠，扫描报告记 `DEDUP` | 视为两次操作 | 不变 |
| 重复（同 seq 异内容） | 隔离整文件 | 任选其一 | `RECOVERY_REQUIRED` |
| seq 非单调 | 隔离整文件 | 按时间重排 | `RECOVERY_REQUIRED` |
| 未知事件类型 | 隔离该行 | 当无害忽略 | 若因此无终态 → `RECOVERY_REQUIRED` |
| 主 WAL 写短计数 / 异常 / flush 失败 / fsync 失败 | 立即停止；检查点**不推进**；尽力向 `wal_failures` 写 `FAILED` | 重试追加；截断回滚；假定已在磁盘上 | 见 A.7.4 |
| `wal_failures` 亦不可写 | 标准错误输出 + 进程内标记 | 静默吞掉 | 见 A.7.4（v7 收紧） |

## A.5 检查点：与 WAL 内容及文件身份绑定

### A.5.1 `.durable` 的定位

`.durable` **不是**独立的可信标记，而是"对 WAL 某一前缀 + 某一文件身份的声明"。任何使用它的判定，必须先校验该声明所指的前缀确实存在、字节未变、且**文件身份未变**。

### A.5.2 检查点字段（v7 扩充）

```json
{
  "checkpoint_version": 3,
  "target_key": "<32 hex>",
  "manual_epoch": null,
  "manual_epoch_id": "<uuid> | null",
  "pre_rebuild_checkpoint_status": "VERIFIED|VERIFIED_MANUAL|ABSENT_CLEAN|ABSENT_DIRTY|INCONSISTENT|null",
  "pre_rebuild_checkpoint_sha256": "<64 hex> | null",
  "prefix_record_count": 0,
  "last_durable_record_seq": 0,
  "last_durable_record_kind": "BEGIN|END|ABORTED|RECOVERED|REPAIR|MANUAL_RESET|null",
  "last_durable_op_id": "<op_id> | null",
  "wal_size_at_marker": 0,
  "wal_prefix_sha256": "<64 hex>",
  "wal_identity": {
    "st_dev": 0,
    "st_ino": 0,
    "volume_serial_hex": "<8 hex> | null",
    "file_index_hex": "<16 hex> | null",
    "creation_time_ns": 0,
    "identity_source": "GetFileInformationByHandle|os.stat|unavailable"
  },
  "ts_wall": "ISO8601",
  "tool_sha256": "<64 hex>"
}
```

`prefix_record_count` 与 `wal_identity` 是 v7 新增的必需字段；缺失即视为 `INCONSISTENT`（旧格式不兼容，须人工迁移）。

**（v8.1，M3）旧代证据字段**：`manual_epoch_id` / `pre_rebuild_checkpoint_status` / `pre_rebuild_checkpoint_sha256` 三字段由 `CP-R` 写入（A.5.10 CR-e 情形 2），用于"旧内容可回读、证据可追溯"：
- `manual_epoch_id`：本次重建的唯一标识，**不得复用**（CR-f 与 S10e 断言 ⑤）；
- `pre_rebuild_checkpoint_status`：重建前检查点状态（通常为 `INCONSISTENT`）；
- `pre_rebuild_checkpoint_sha256`：被改名的旧代文件的**完整 SHA-256**，须与 `pre_manual.<manual_epoch_id>` 文件的实际哈希一致。

`manual_epoch == null` 时，后两字段必须同为 `null`；否则视为 `INCONSISTENT`。

**（v8.3，N-01）代际字段**：
- `checkpoint_generation`：整数，从 0 起，每次成功推进（含 `CP-R`）+1，单调递增；**不纳入** `wal_state_digest`（A.5.11.5）；
- `pre_advance_checkpoint_sha256`：自动推进时被改名保留的旧代文件的**完整 SHA-256**；首次创建（无旧代）时为 `null`；
- `manual_epoch` **随代携带**：旧代非 `null` 时新代必须写入**同一个** `manual_epoch` 对象（不是新生成），否则视为 `INCONSISTENT`。

**v8：`checkpoint_version` 升为 3，新增 `manual_epoch`**（正常为 `null`）：

```json
"manual_epoch": {
  "reset_op_id": "<op_id>",
  "signoff_id": "<uuid>",
  "mp1_evidence_ref": "wal_evidence\\<key>.<ts>.manual_investigation.json",
  "rebuilt_at_seq": 0,
  "rebuilt_at_wall": "ISO8601",
  "pre_rebuild_checkpoint_status": "INCONSISTENT",
  "target_sha256_confirmed_by_human": "<64 hex>"
}
```

`manual_epoch != null` ⇒ `CHECKPOINT_STATUS == VERIFIED_MANUAL`。**`VERIFIED_MANUAL` 不得被当作 `VERIFIED`**：T2 拒绝它（A.7.5 T2-2），`wal_state_digest` 必须携带该字段。

### A.5.3 `wal_prefix_sha256` 的计算范围与字节边界（含空前缀）

| 项 | 规定 |
|---|---|
| 起点 | 字节偏移 `0` |
| 终点 | 字节偏移 `wal_size_at_marker`（**不含**该字节） |
| 计算式 | `sha256( wal_bytes[0 : wal_size_at_marker] )`，小写十六进制 |
| 换行符 | 包含前缀内所有记录的结尾 `\n`；`wal_size_at_marker` 必须恰好落在某条记录换行符之后的偏移上 |
| 编码 | 原始字节，不做换行转换（WAL 以 `newline="\n"` 写入） |
| **空前缀** | `prefix_record_count == 0` 时，`wal_size_at_marker` 必须为 `0`，`wal_prefix_sha256` 必须为 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`（即 `sha256(b"")`）。**空前缀不虚构"最后一条记录"** |
| 前缀读取方式 | 必须经**已校验身份的同一文件句柄**读取（A.5.7），不得用另一路径重新打开后拼接结论 |

### A.5.4 一致性约束（v7：三向 → 四向）

| # | 约束 | 适用 |
|---|---|---|
| 1 | **序号一致**：前缀末条记录 `seq == last_durable_record_seq` | `prefix_record_count > 0` |
| 2 | **身份一致**：末条记录 `kind == last_durable_record_kind`；`op_id`（`REPAIR` 为 `null`）== `last_durable_op_id` | `prefix_record_count > 0` |
| 3 | **偏移一致**：末条记录 `\n` 的偏移 + 1 == `wal_size_at_marker` | `prefix_record_count > 0` |
| 4 | **空态一致**：`prefix_record_count == 0` ⇒ `last_durable_record_seq == 0` ∧ `last_durable_record_kind == null` ∧ `last_durable_op_id == null` ∧ `wal_size_at_marker == 0` ∧ `wal_prefix_sha256 == EMPTY_PREFIX` | `prefix_record_count == 0` |
| 5 | **计数一致**：前缀内实际记录条数 == `prefix_record_count` | 全部 |
| 6 | **身份一致**：`wal_identity` 与当前 WAL 句柄实测身份一致（A.5.7） | 全部 |

任一条不成立 → `CHECKPOINT_STATUS = INCONSISTENT`。

### A.5.5 检查点更新顺序（CP-1…CP-6，v7 加身份复核）

```
CP-1  向主 WAL 追加一条完整记录（单次 write，buffering=0，经已校验句柄 H_wal）
CP-2  fsync(H_wal)
CP-3  经 H_wal 读取 [0, size_after) 并计算 wal_prefix_sha256
CP-4  经 H_wal 取当前文件身份（fstat / GetFileInformationByHandle），与本次操作的
      BEGIN 记录中的 wal_identity_baseline 比对；不一致 → 立即中止，不发布检查点
CP-5a 写 <key>.durable.json.tmp.<pid>.<attempt> → fsync(tmp) → 经新句柄回读校验 tmp
      （长度 / 可解析 / 前缀哈希 / 身份 / generation 全部一致；失败即中止，当代检查点不动）
CP-5b 旧代保留：若 <key>.durable.json 存在 → 原子改名为
      <key>.durable.json.pre_advance.<旧代 wal_size_at_marker>.<旧代 wal_prefix_sha256 前 8 位>
      （**改名不是覆盖**：旧代内容完整保留、可回读；命名与保留规则见 A.5.11）
CP-5c 发布新代：以"目标不存在才创建"的原子语义发布（同 A.11.1 ⑤）
      失败 → 中止，按 A.5.11 情形 3 处理；**禁止**回退到 os.replace 或"先删后建"
CP-6  重新打开检查点并回读校验（含 CP-3 的哈希、CP-4 的身份）；失败即视为未推进
```

**CP-R 不属于自动推进**：人工基线重建（`CP-R`）定义见 **A.5.10**，只能由 T5 触发，且必须在 `MANUAL_RESET` 已持久之后执行。CP-1…CP-6 的自动路径**永远不得**调用 `CP-R`。

**CP-5 的适用前置（v8.3，N-01）**：① 旧代 `CHECKPOINT_STATUS ∈ {VERIFIED, VERIFIED_MANUAL}`（`ABSENT_CLEAN` 时无旧代，直接 CP-5a → CP-5c）；② 旧代为 `INCONSISTENT` / `ABSENT_DIRTY` 时**禁止** CP-5，只能走 `CP-R`（A.5.10）；③ 旧代 `manual_epoch != null` 时，新代**必须原样携带同一个 `manual_epoch`**、状态**仍为** `VERIFIED_MANUAL`——**禁止**经自动推进把人工代洗成 `VERIFIED`（A.5.10 硬规则 1、A.5.11.6 第 2 条）。

**崩溃方向性**：检查点永远描述一个**仍然存在且身份未变**的前缀，因此任何时刻崩溃只会导致"更多记录被判 `PROVISIONAL`"（保守），**不会**导致"未持久化或来自另一文件的记录被判 `DURABLE`"（乐观）。

| 崩溃点 | 结果 |
|---|---|
| CP-1 前 | 无新记录；旧检查点仍 `VERIFIED` |
| CP-1 后、CP-2 前 | 新记录可见但未 fsync；检查点未推进 → 新记录 `PROVISIONAL` |
| CP-2 后、CP-5a 前 | 新记录实际已持久，但检查点未推进 → 仍判 `PROVISIONAL`（保守方向） |
| CP-4 检测到身份变化 | 中止，不发布检查点 → 见 A.5.7 |
| CP-5a 中（tmp 已写、未改名） | 当代检查点未动 → 仍为旧代状态，新记录 `PROVISIONAL`；残留 tmp **不被采用**（A.5.11.4） |
| **CP-5b 后、CP-5c 前（旧代已改名、新代未发布）** | 磁盘上只有 `pre_advance.*` 与 tmp、**没有当代检查点** → 判 **`ABSENT_DIRTY`** → `UNKNOWN` → `MANUAL_BLOCKED`；**禁止**把 `pre_advance.*` 改回当代名，**禁止**删除旧代（A.5.11.3） |
| CP-5c 后、CP-6 前 | 新检查点已生效；若回读失败则下次扫描发现不一致（旧代仍在 `pre_advance.*`，可回读对照） |

**关键语义（T4 的基础）**：一次成功的 `fsync` 会把该文件此前所有未确认的字节一并持久化。因此后续的检查点推进**合法地**把此前的 `PROVISIONAL` 记录转为 `DURABLE` —— 这不是掩盖，而是该 fsync 的真实效果。

### A.5.6 启动扫描的校验序列（V-0…V-6 + V-T）

| 项 | 校验 | 失败后果 |
|---|---|---|
| **V-0（v7 新增，v8 补充）** | WAL 文件存在性与可打开性；取当前文件身份。**（v8）WAL 不存在时不得声称"已验证该文件的句柄身份"**：此时 `WAL_IDENTITY_STATUS = IDENTITY_NOT_APPLICABLE`，且检查点必须满足空态六项（A.5.9） | 缺失且检查点描述非空前缀 → `INCONSISTENT`；**缺失但检查点记录了非零 `wal_identity` → `INCONSISTENT`（无法一致解释）**；存在但身份不可得 → `IDENTITY_UNVERIFIABLE` |
| V-1 | `size >= wal_size_at_marker` | `INCONSISTENT` |
| **V-1b（v7 新增）** | `wal_identity` 与当前实测身份一致 | `IDENTITY_MISMATCH` → `INCONSISTENT` |
| V-2 | `sha256(wal[0:wal_size_at_marker]) == wal_prefix_sha256` | `INCONSISTENT` |
| V-3 | 前缀可完全解析，`seq` 严格单调 | `INCONSISTENT` |
| V-4 | 前缀末条记录 `seq` / `kind` / `op_id` 与检查点字段一致（空前缀改走 A.5.4 第 4 条） | `INCONSISTENT` |
| V-5 | 前缀末条记录结束偏移 == `wal_size_at_marker`（空前缀要求 `wal_size_at_marker == 0`） | `INCONSISTENT` |
| V-6 | `prefix_record_count` 与实际条数一致 | `INCONSISTENT` |
| **V-T（v7 新增）** | **目标一致性**：若最后一条终态为 `END` 或 `RECOVERED`，则当前目标全文件 SHA-256 必须等于该记录的 `target_sha256_after` | 不等 → 判定"目标在最后一次提交后被改动" → `RECOVERY_REQUIRED` |

**V-T 的作用**：把"写 END 之后、下一次扫描之前"的外部写入从**永不检出**变为**延迟检出**。它不能替代写时检测，只是缩小不可检出窗口。

### A.5.7 WAL 文件身份连续性（P0-1）

#### A.5.7.1 设计层面要求（**未实现**）

| # | 要求 |
|---|---|
| **ID-1** | 单次操作内，WAL 的**追加、fsync、前缀哈希计算、身份读取**必须基于**同一个已打开的文件句柄** `H_wal`（以 `buffering=0` 打开）。禁止用"路径 A 打开算哈希 + 路径 B 打开做 stat"的方式拼接"已验证"结论 |
| **ID-2** | `BEGIN` 记录中必须写入 `wal_identity_baseline`（`{st_dev, st_ino, volume_serial, file_index, creation_time_ns}`），作为本次操作的身份基线 |
| **ID-3** | CP-4 必须在发布检查点之前，用 `H_wal` 实测身份并与 `wal_identity_baseline` 比对；不一致即中止 |
| **ID-4** | 检查点发布后（CP-6）必须用**新打开的句柄**再读一次检查点与 WAL 前缀，并与 `H_wal` 的哈希结论比对；两者不一致 → 判定视图矛盾 |
| **ID-5** | 任何"句柄视图"与"路径视图"的结论冲突（例如句柄读到旧内容、路径 stat 指向新文件）→ 立即中止，不得择一采信 |
| **ID-6** | 扫描期（V-0 / V-1b）必须同时记录"检查点声明的身份"与"当前实测身份"，并写入 `wal_state_digest` |

#### A.5.7.2 如何检测"被替换 / 重命名 / 重新创建 / 指向其他对象"

| 事件 | 可观察迹象 | 判定 |
|---|---|---|
| **内容相同、文件被替换** | 前缀哈希相同，但 `st_ino` / `file_index` / `creation_time_ns` 不同 | `IDENTITY_MISMATCH` → `INCONSISTENT` → `UNKNOWN` / `MANUAL_BLOCKED` |
| **重命名后新建同名文件** | 同上；另可观察到 `creation_time_ns` 晚于检查点 `ts_wall` | 同上 |
| **文件被删除后重建** | V-0 通过（存在），但身份全变 | 同上 |
| **指向其他对象（重解析点/硬链接）** | `st_dev` 变化，或 `st_nlink > 1`，或 realpath 解析目标变化 | 同上；硬链接额外按 S0e 拒绝 |
| **句柄与路径视图矛盾** | `H_wal` 读到的大小/哈希与按路径 stat/读取的结果不同 | `INCONSISTENT`，**且视为并发替换信号**，不得择一采信 |

#### A.5.7.3 `st_ino` 在 Windows / NTFS 上的适用限制（**不得当作绝对证明**）

| 限制 | 说明 |
|---|---|
| 来源不稳定 | Python 的 `os.stat().st_ino` 在 Windows 上由 `GetFileInformationByHandle` 的 64 位文件索引派生；在 FAT32、部分网络共享、部分虚拟文件系统上可能为 `0` 或不稳定 |
| 可能被复用 | 文件删除后索引号可能被新文件复用，因此"索引相同"不证明"同一文件" |
| 不覆盖内容 | 身份相同不代表内容未被改写（等长原地覆盖不改身份） |
| 无事务语义 | 身份读取与后续 I/O 之间没有原子性；理论上仍存在竞态窗口 |
| 卷序列号可伪造 | `volume_serial_hex` 可被工具修改，不能作为强证据 |

**结论**：`st_ino` + 卷序列号 + 文件索引 + 创建时间**四者叠加只降低概率，不构成形式化证明**。任何"因为 `st_ino` 相同所以文件未被替换"的推理都是错误的。

#### A.5.7.4 身份异常时的处理（**fail-closed**）

| 情形 | `FAULT_CLASS`（A.2.3） | `WAL_IDENTITY_STATUS` | `CHECKPOINT_STATUS` | `WAL_STATE_COMPLETE` | 运行状态 | 允许 |
|---|---|---|---|---|---|---|
| 身份一致 | 由 F5–F8 决定 | `IDENTITY_VERIFIED` | 由 V-1…V-6 决定 | 由记录与 op 状态决定 | — | 按 A.7 |
| 身份不一致（V-1b 失败） | `FRC-IDENTITY_MISMATCH`（F1） | `IDENTITY_MISMATCH` | `INCONSISTENT` | `UNKNOWN` | `MANUAL_BLOCKED` | **无出口**（`CR-6` 两轴表禁止 `CP-R`，T5 不可执行） |
| 身份不可得（`st_ino == 0` 且无 `file_index`） | `FRC-IDENTITY_UNAVAILABLE`（F4） | `IDENTITY_UNVERIFIABLE` | `INCONSISTENT` | `UNKNOWN` | `MANUAL_BLOCKED` | **无出口**（同上） |
| **WAL 与检查点均不存在** | 不适用（无故障，F1–F8 均不命中） | `IDENTITY_NOT_APPLICABLE` | `ABSENT_CLEAN` | `YES` **仅当** ALL-GONE ①–⑦ 全部成立；否则 `UNKNOWN` | ALL-GONE 成立 → `READY`；否则 `MANUAL_BLOCKED` | **仅当 ALL-GONE 成立**才允许正常写入；否则禁止（**v8.2：本行不得绕过 A.5.9 硬规则 4**） |
| **WAL 不存在 + 检查点存在且描述空前缀**（v8） | 不适用（同上） | `IDENTITY_NOT_APPLICABLE` | `VERIFIED`（空态） | `YES` **仅当** 空态六项 ∧ **ALL-GONE ①–⑦** 全部成立；否则 `UNKNOWN` | 同上 | **仅当上述全部成立**才允许；**另需**：`manual_epoch == null` ∧ 检查点 `wal_identity` 为 `null` 或 `identity_source == "unavailable"` |
| **WAL 不存在但检查点记录了非零身份**（v8） | `FRC-IDENTITY_MISMATCH`（F2） | `IDENTITY_MISMATCH`（无法一致解释） | `INCONSISTENT` | `UNKNOWN` | `MANUAL_BLOCKED` | **无出口**；禁止把"文件不存在"当作"身份已验证" |
| 句柄视图与路径视图矛盾 | `FRC-IDENTITY_MISMATCH`（F3） | `IDENTITY_MISMATCH` | `INCONSISTENT` | `UNKNOWN` | `MANUAL_BLOCKED` | **无出口** |

**命名澄清（v8.2，消除 v8.1 的表述冲突）**：`ABSENT_CLEAN` 是**检查点状态**的取值（A.2.1）；`EMPTY_CLEAN` / `EMPTY_UNCHECKPOINTED` 是 **A.5.9 的组合分类名**。两者不在同一层，**不得互换、也不得视为同义**。"WAL 与检查点均不存在"的准确写法是：**`CHECKPOINT_STATUS = ABSENT_CLEAN` 且组合分类 = `EMPTY_CLEAN`**。

**硬规则（v8.2 强化）**：

1. `IDENTITY_MISMATCH` / `IDENTITY_UNVERIFIABLE` 时**不得自动推进 durable checkpoint，不得允许新写入**。
2. **本表任何一行都不得绕过 ALL-GONE**——"WAL 与检查点均不存在"不是"干净"的证明，只是"没有可校验的当代状态"，必须由 A.5.9 的 ①–⑦ 旁证补齐（S14i）。**（v8.3）表外的组合 #3a（WAL 0 字节 + 空前缀检查点）同样适用 ALL-GONE**（`EMPTY_STATE == true`，S14j）。ALL-GONE 的定义**只在 A.5.9**，本表只引用、不重述。
3. 表中"允许"列**不是授权式**：实际可写性一律由 A.7.8 `WRITE_PERMITTED` 与 A.10.1 PWA 决定；本表只回答"运行状态落在哪"。
4. **身份类故障不得写成"仅 T5"**：`CR-6` 两轴表已禁止 `CP-R`，T5 阶段 B 无法完成（v8.2，R14）。

#### A.5.7.7 WAL 不存在时的身份适用边界（v8，R5）

| 情形 | 允许的断言 | 禁止的断言 |
|---|---|---|
| WAL 存在 | 可断言"该句柄所指文件身份 == 检查点声明身份"（`IDENTITY_VERIFIED`） | 断言"该身份在未来不会被替换" |
| WAL 不存在 + 检查点空前缀 + 检查点身份为空/`unavailable` | 可断言"当前不存在可校验的文件身份"（`IDENTITY_NOT_APPLICABLE`），并按空态六项判定 | **断言"已校验不存在文件的句柄身份"**；断言"该 target 从未被写过" |
| WAL 不存在 + 检查点记录非零身份 | 只能断言"检查点与文件系统状态无法一致解释" | 断言"文件被删除所以是干净的"；自动重建检查点 |
| WAL 0 字节 | 同"WAL 存在"（0 字节文件仍有身份） | 把 0 字节当成"文件不存在"而跳过身份校验 |

**结论**：`IDENTITY_NOT_APPLICABLE` **不是**"身份校验通过"，只是"无对象可校验"。它只在空前缀 + 检查点身份为空时成立；任何其它组合都必须落到 `IDENTITY_MISMATCH` / `IDENTITY_UNVERIFIABLE`。

#### A.5.7.5 设计 vs 实现的分离声明

> 以上 ID-1…ID-6、V-0 / V-1b、`wal_identity` 字段、身份比对逻辑**全部为设计层面要求，尚未实现，尚未测试**。本文档不得被理解为"身份连续性已经保证"。相关验证见 S11a–S11d，全部 `NOT EXECUTED`。

#### A.5.7.6 平台可行性 → P0 阻塞项

若在目标卷上无法获得**稳定、非零、可区分**的文件身份（`st_ino == 0` 或索引复用不可忽略），则本方案**不能提供 WAL 身份连续性保证**，该情形列为 **BLK-1（A.22）**，必须阻断真实写入，不得以文字描述视为已解决。

### A.5.8 纳入 `wal_state_digest` 与 T2

```json
{"wal_size": 0, "last_seq": 0,
 "checkpoint_status": "VERIFIED|VERIFIED_MANUAL|ABSENT_CLEAN|ABSENT_DIRTY|INCONSISTENT",
 "manual_epoch": null,
 "wal_identity_status": "IDENTITY_VERIFIED|IDENTITY_MISMATCH|IDENTITY_UNVERIFIABLE|IDENTITY_NOT_APPLICABLE",
 "failure_log_status": "FAIL_READABLE_EMPTY|FAIL_READABLE_WITH_RECORDS|FAIL_UNREADABLE|FAIL_CORRUPT|FAIL_ABSENT_CONSISTENT|FAIL_ABSENT_INCONSISTENT",
 "prefix_record_count": 0,
 "last_durable_record_seq": 0,
 "wal_prefix_sha256": "<64 hex> | null",
 "ops": [{"op_id": "...", "derived_state": "OP_..."}],
 "unresolved_set_digest": "<64 hex>"}
```

序列化：UTF-8 无 BOM，键名按字典序，无多余空白，SHA-256 小写十六进制。

T2 签核必须基于**已通过 V-0…V-6 校验且 `WAL_IDENTITY_STATUS == IDENTITY_VERIFIED`** 的状态；摘要含上述全部字段，因此检查点、身份或故障日志任一变化都会使签核自动失效。

**（v8）`manual_epoch` 必须进入摘要**：人工重建过的 target，其 `wal_state_digest` 与重建前不同，任何基于旧摘要的签核自动失效；T2 要求 `checkpoint_status == "VERIFIED"`，因此 `VERIFIED_MANUAL` 状态下 T2 必然不可用。

### A.5.9 空 WAL / 检查点的六种初始组合（P1-1）

**空前缀常量**：`EMPTY_PREFIX_SHA256 = e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`。

**"干净初始"判定条件（ALL-GONE，v8.1，M6 强化）**：以下**每一项**都必须被**显式检查并确认"不存在或为空"**；任一项"存在"、"无法读取"或"状态矛盾" → **不得判干净**。

| # | 检查对象 | 判"不干净"的条件 |
|---|---|---|
| ① | `wal_evidence\<key>.*` | 存在任意匹配文件（含 0 字节）；或目录不可读 |
| ② | `wal_repairs\<key>.jsonl` | 存在且非空；或存在但不可解析；或不可读 |
| ③ | `wal_failures\<key>.jsonl` | 存在且非空；或存在但不可解析；或不可读 |
| ④ | `lock\<key>.lock` | 存在（**含残留锁**）；或不可判定是否存在 |
| ⑤ | `snap\<key>\` 下的快照 | 存在该 target 的任意快照（内容文件与 sidecar 单独存在均计入） |
| ⑥ | **（v8.1 新增）恢复记录** | `wal_evidence\` 中存在任何 `RECOVERY` / `#r<n>` / `supersedes` 相关记录；或存在指向该 target 的未归档人工调查文件 |
| ⑦ | **（v8.1 新增）签核记录** | `signoffs\<key>.*` 存在任意签核文件（T2 或 T5），说明该 target 曾进入人工处置 |

**三项判定结果（缺一不可，全部满足才判干净）**：

1. **①–⑦ 全部检查完成**，且均"不存在或为空"；
2. **检查本身没有发生"无法读取"**——不可读 ≠ 不存在；不可读一律判**不干净**；
3. **检查过程中没有出现两份证据互相矛盾**（例如 `wal_repairs` 声称已修复而 `wal_failures` 无对应记录）。

**禁止**：把"目录不存在"当作"检查通过"；把"读取失败"当作"不存在"；只检查 ①–⑤ 而跳过 ⑥⑦；把"检查未做"当作"检查通过"。

**（v8.3，DD-1）空态分类谓词 `EMPTY_STATE`（唯一出处：本节）**：

| 项 | 内容 |
|---|---|
| 定义 | `EMPTY_STATE == true` ⟺ 组合 ∈ {**#1, #2, #3a, #5a**}，即"不存在任何 WAL 记录，且当代检查点要么不存在、要么描述空前缀" |
| 含义 | `EMPTY_STATE == true` 时，**ALL-GONE ①–⑦ 全部成立**是"干净 / `WAL_STATE_COMPLETE == YES` / `READY` / 可写"的**必要条件** |
| 引用规则 | `A.7.1` / `A.7.8` / `A.10.1` / `A.5.7.4` **只允许引用本谓词**，不得各自枚举组合，**也不得只写 `ABSENT_CLEAN`**——v8.2 的写法把 #3a / #5a（检查点为 `VERIFIED`）漏在 ALL-GONE 之外，v8.3 修正 |

**为什么把 #3a 纳入（DD-1 的裁定理由）**：v8.2 在 `A.5.9` 硬规则 4（"WAL 不存在时"才要 ALL-GONE）与 R5 映射表（"#3a 一律适用"）之间**互相矛盾**，表行 #3a 又是无条件的。裁定采用**从严**一侧：0 字节 WAL 无法与"被截断到 0"区分（硬规则 2 自己给出的理由对 #3a 同样成立），因此旁证要求必须一致。代价为零——`A.5.9` #1 已声明空前缀检查点"从未落盘"，收紧 #3a **不阻断任何合法路径**。

**（v8.2）ALL-GONE 的唯一出处与五处统一**：`ALL-GONE` 的定义**只在本节**（①–⑦ + 三项判定结果）。`A.5.7.4`（状态行）、`A.7.1`（`YES` 行）、`A.7.8`（`WRITE_PERMITTED` 第 3b 行）、`A.10.1`（PWA-6）、`A.22`（规则段）**只允许引用本节**，不得各自重述、不得各自放宽、也不得出现"某一行状态表可以直接判干净"的写法。任一处出现独立定义即为缺陷。

| # | 组合 | 分类名 | 干净初始 | 允许创建/初始化检查点 | 人工 | 允许 `READY` | 允许目标写入 | "无末条记录"的处理 |
|---|---|---|---|---|---|---|---|---|
| **1** | WAL 不存在 + checkpoint 不存在 | `EMPTY_CLEAN` | **是，当且仅当 ALL-GONE 成立**（v8.1，M6） | **允许**（惰性：首次写 `BEGIN` 时按 CP-1…CP-6 创建，`prefix_record_count=0` 只是从未落盘的状态） | ALL-GONE 不成立 → **必须** | ALL-GONE 成立 → 允许；否则**禁止** | ALL-GONE 成立 → 允许（PWA 全通过时）；否则**禁止** | 不涉及末条记录；首次检查点在 `BEGIN` 落盘后创建，`prefix_record_count=1` |
| **2** | WAL 存在但 0 字节 + checkpoint 不存在 | `EMPTY_UNCHECKPOINTED` | **是**，**当且仅当 ALL-GONE 成立** | **允许**（同上） | ALL-GONE 不成立 → **必须** | ALL-GONE 成立 → 允许；否则禁止 | 同上 | 同 #1；0 字节与"不存在"在语义上等价 |
| **3a** | WAL 0 字节 + checkpoint 存在且描述**空前缀** | `VERIFIED`（空态） | **是，当且仅当 ALL-GONE 成立**（v8.3） | 已存在，不新建 | ALL-GONE 不成立 → **必须** | ALL-GONE 成立 → 允许；否则**禁止** | ALL-GONE 成立 → 允许（PWA 全通过时）；否则**禁止** | 走 A.5.4 第 4 条空态一致性（`prefix_record_count==0`、`size==0`、`sha==EMPTY_PREFIX`、`seq==0`、`kind==null`、`op_id==null`），**不比对末条记录** |
| **3b** | WAL 0 字节 + checkpoint 描述**非空前缀** | `INCONSISTENT` | 否 | **禁止** | **必须** | 禁止 | 禁止 | V-1 失败（`0 < wal_size_at_marker`） |
| **4** | WAL 有记录 + checkpoint 不存在 | `ABSENT_DIRTY` | 否 | **禁止**（不得凭空创建检查点） | **必须** | 禁止 | 禁止 | 无检查点可依，不涉及 |
| **5a** | WAL 不存在 + checkpoint 描述**空前缀** | `VERIFIED`（空态，WAL 视作空） | **是，当且仅当 ALL-GONE 成立**（v8.3） | 已存在 | ALL-GONE 不成立 → **必须** | ALL-GONE 成立 → 允许；否则**禁止** | ALL-GONE 成立 → 允许（PWA 全通过时）；否则**禁止** | 同 #3a |
| **5b** | WAL 不存在 + checkpoint 描述**非空前缀** | `INCONSISTENT` | 否 | **禁止** | **必须** | 禁止 | 禁止 | V-0 失败（文件缺失但声明非空前缀） |
| **6** | WAL 有记录 + checkpoint 存在，但 seq / 前缀哈希 / 计数 / **文件身份**任一不一致 | `INCONSISTENT` | 否 | **禁止** | **必须** | 禁止 | 禁止 | 见 V-1…V-6 / V-1b |

**与 v8-R5 六类区分的对应关系**（R5 要求逐类区分，不得合并）：

| R5 类别 | 本表行 |
|---|---|
| WAL 不存在且检查点不存在 | **#1** |
| WAL 为 0 字节且检查点不存在 | **#2** |
| WAL 为 0 字节且检查点描述空前缀 | **#3a** |
| WAL 不存在但检查点描述空前缀 | **#5a** |
| WAL 不存在或为空，但存在 `wal_evidence` / `wal_repairs` / `wal_failures` / 残留锁 / 快照 / 恢复记录 / 签核记录 | **ALL-GONE 不成立分支**（转 `MANUAL_BLOCKED`）；**#1 / #2 / #3a / #5a 一律适用**，判定规则统一见本节**硬规则 4**（不再在此处重复条件） |
| WAL 含记录但检查点不存在 | **#4** |

**身份列（v8）**：上表每一行的 `WAL_IDENTITY_STATUS` 如下 —— #1 / #2 / #5a → `IDENTITY_NOT_APPLICABLE`（**仅当**检查点身份为空或 `unavailable`；#2 无检查点，天然不适用）；#3a / #3b / #4 / #6 → WAL 文件存在，**必须**按 V-1b 实测比对（#4 无检查点可比，记 `IDENTITY_NOT_APPLICABLE` 但 `CHECKPOINT_STATUS = ABSENT_DIRTY` 已阻断）；#5b → `IDENTITY_MISMATCH`。**WAL 不存在但检查点记录非零身份**（表外情形）→ `IDENTITY_MISMATCH` → `INCONSISTENT` → `MANUAL_BLOCKED`。

**四条硬规则**：

1. **禁止虚构末条记录**：`prefix_record_count == 0` 时不得用"假想的一条记录"通过 V-4 / V-5，必须走空态一致性（A.5.4 第 4 条）。六项必须**共同**成立：`prefix_record_count == 0` ∧ `wal_size_at_marker == 0` ∧ `wal_prefix_sha256 == EMPTY_PREFIX` ∧ `last_durable_record_seq == 0` ∧ `last_durable_record_kind == null` ∧ `last_durable_op_id == null`。
2. 组合 #2 的"干净"判定**依赖 ALL-GONE**：0 字节 WAL 无法与"被截断到 0"区分，只能靠旁证；旁证不成立即转 `MANUAL_BLOCKED`。
3. 组合 #3b / #4 / #5b / #6 一律不得自动创建或重写检查点。
4. **（v8.1，M6）空态不等于"身份已验证"，也不等于"干净"**：`IDENTITY_NOT_APPLICABLE` 只表示"无对象可校验"（A.5.7.7）；任何"文件不存在所以干净"的推理都是错误的。
   - **#1 与 #2 必须同时满足 ALL-GONE**（①–⑦ 全部检查完成且均不存在/为空、无不可读、无矛盾）；
   - **#3a / #5a 必须同时满足空态六项，且同样必须满足 ALL-GONE ①–⑦**（**v8.3，DD-1 决策**：0 字节 WAL 与"WAL 不存在"在旁证要求上**等价**——两者都无法与"被截断到 0 / 被删除"区分，A.5.9 硬规则 2 已给出该理由）；
   - 任一不成立 → `WAL_STATE_COMPLETE == UNKNOWN` → `MANUAL_BLOCKED`；**禁止** `READY`，**禁止**目标写入，**禁止**自动创建检查点。

### A.5.10 人工基线重建 `CP-R`（v8 新增，R3；v8.1 修 CR-6 / CR-e，M2 / M3）

`CP-R` 是**唯一**能把 `INCONSISTENT` 检查点替换为可用检查点的路径，且**不是**"重写检查点消除不一致"，理由见下表。

**触发前提（全部满足，缺一不可）**：

| # | 前提 |
|---|---|
| CR-1 | `MANUAL_RESET` 记录**已持久**（`DURABLE`，且被上一代检查点或本次重建覆盖） |
| CR-2 | `MANUAL_RESET.unresolved_set_empty == true` 且当前扫描 `OP_UNRESOLVED == ∅` |
| CR-3 | MP-1 调查证据存在（`mp1_evidence_ref` 指向的文件可读且哈希记录一致） |
| CR-4 | MP-2 签核有效且 `state_digest_at_override` == 当前 `wal_state_digest` |
| CR-5 | 人工已独立确认目标当前哈希（`target_sha256_confirmed_by_human`），且该值 == 现场实测 |
| CR-6 | **身份前提按两轴判定（v8.2，R16 重写）**：轴 1 = `FAULT_CLASS`（A.2.3 派生），轴 2 = `WAL_IDENTITY_STATUS`（实测）。**两轴必须同时落在"CR-6 两轴表"的允许行内**；不在允许集合内 → `CP-R` 禁止，**无例外**，不得以人工签核、`VERIFIED_MANUAL` 或任何"已调查"结论绕过。表见下方 **CR-6 两轴表** |

**CR-6 两轴表（v8.2，R16）**：

| `FAULT_CLASS` | 允许的 `WAL_IDENTITY_STATUS` | `CP-R` | 理由 |
|---|---|---|---|
| `FRC-IDENTITY_MISMATCH` | （必然为 `IDENTITY_MISMATCH`，A.2.3 不变量 1） | **禁止，无例外** | 身份已被换过；"重建前缀"会以新文件为基准伪造连续性 |
| `FRC-IDENTITY_UNAVAILABLE` | （必然为 `IDENTITY_UNVERIFIABLE`，A.2.3 不变量 1） | **禁止，无例外** | `CR-c` 的身份复核无法完成；不得以"截断后 / 重建后再复核"替代 |
| `FRC-CHECKPOINT` / `FRC-FAILURELOG` / `FRC-STRUCTURAL` | `IDENTITY_VERIFIED`；或 `IDENTITY_NOT_APPLICABLE` 且满足 A.5.7.7 | **允许**（仍须 CR-1…CR-5） | 故障不在身份，且身份可复核 |
| `FRC-TARGET` | 任意 | **禁止** | 目标与最后终态不符；`CP-R` 只重建检查点、不修目标 → 阶段 C 的 V-T **必然**再次失败，重建只会产出一个立即失效的 `VERIFIED_MANUAL` |
| `FRC-UNKNOWN` | 任意 | **禁止** | 根因无法确认 → 无法证明"重建的是正确的前缀" |

**两轴表的三条推论**：① **不存在**"非身份类 + 身份不可得"的组合（A.2.3 不变量 2），v8.1 的 `CR-6(a)` / `CR-6(c)` 重叠消失；② `IDENTITY_UNVERIFIABLE` **只**对应 `FRC-IDENTITY_UNAVAILABLE` 一种分类；③ 表中**没有**任何"人工可覆盖"的行——`CP-R` 的允许集合完全由派生值决定，签核只能满足 CR-3 / CR-4，不能改变 `FAULT_CLASS`。

**执行顺序**：

```
CR-a  重新完整扫描 WAL（V-0…V-6 + V-T），记录重建前状态与 digest
CR-b  以当前 WAL 的实际字节重算前缀：size / sha256 / record_count / 末条记录
CR-c  复核 WAL 身份（CP-4 同等要求）
CR-d  写 <key>.durable.json.tmp.<pid>（checkpoint_version=3，manual_epoch 非空，
      pre_rebuild_checkpoint_status 记录重建前值）→ fsync
CR-e  检查点发布（**与 A.11.1 的快照发布语义不同，禁止混用**），三种情形：
      **情形 1 — 检查点不存在**：按"目标不存在才创建"发布（同 A.11.1 ⑤ 的原子语义）。
      **情形 2 — 检查点已存在**（INCONSISTENT 的当代必然已存在）：
        ① 复核旧文件：可解析、身份一致（CP-4 同等要求）、可计算完整 SHA-256；
        ② 把旧文件**原子改名**为 <key>.durable.json.pre_manual.<manual_epoch_id>
           （**改名不是覆盖**：旧内容完整保留、可回读、可作为证据）；
        ③ 用"目标不存在才创建"发布新文件（同情形 1）；
        ④ 回读校验（CR-f）。
      **情形 3 — 保留、校验或发布任一步骤失败**：
        中止；CHECKPOINT_STATUS 保持 INCONSISTENT；运行状态 MANUAL_BLOCKED；
        **禁止**继续发布、**禁止**回退到"直接覆盖旧文件"、**禁止**删除已改名的旧代。
      **中间状态定义（不得留空）**：若 ② 成功而 ③ 失败，磁盘上**只有**
        <key>.durable.json.pre_manual.<manual_epoch_id>，没有当代检查点 →
        该组合判 **ABSENT_DIRTY**（**不是** ABSENT_CLEAN、**不是** EMPTY_CLEAN）→
        WAL_STATE_COMPLETE = UNKNOWN → MANUAL_BLOCKED；证据完整保留；
        人工可按 CR-1 重新走一遍，但 **manual_epoch_id 不得复用**，须新生成。
      **禁止**：用 os.replace / MoveFileEx(REPLACE_EXISTING) 直接覆盖旧检查点
        （会销毁 pre_rebuild_checkpoint_status 的对照物）。
CR-f  回读校验：manual_epoch 可解析、前缀哈希/计数/身份/末条记录全部一致
CR-g  重新执行完整扫描；只有结果为 WAL_STATE_COMPLETE == YES 且 V-T 通过才允许 READY
```

**为什么这不是"重写检查点消除 INCONSISTENT"**：

| 区别点 | 被禁止的做法 | `CP-R` |
|---|---|---|
| 时机 | 发现不一致就重写 | 必须在 `MANUAL_RESET` 持久**之后** |
| 印记 | 无痕覆盖 | `manual_epoch` 永久写入检查点，且 `MANUAL_RESET` 永久留在 WAL |
| 结论 | 声称"历史已验证" | 只声称"从此刻起的前缀已由人工接受"，状态标 `VERIFIED_MANUAL` |
| 数据 | 可能顺手改目标 | **不修改目标、不修改 WAL 历史记录** |
| 可回退 | 覆盖后无法区分 | `pre_rebuild_checkpoint_status` 保留重建前状态 |

**硬规则（v8.1）**：

1. `CP-R` 未完成前，`CHECKPOINT_STATUS` 保持 `INCONSISTENT`；`CP-R` 完成后为 `VERIFIED_MANUAL`，**永不**变成 `VERIFIED`。
2. `VERIFIED_MANUAL` 下的写入属于**人工接受的风险**（BLK-5）。`VERIFIED_MANUAL` **不单独**授予写权限；四项否决条件见 A.2.1 / A.7.8。
3. **旧代证据不可销毁**：情形 2 的 ② 必须成功，否则中止。旧代文件的完整 SHA-256 必须记录在新检查点的 `pre_rebuild_checkpoint_sha256` 字段中，与 `pre_rebuild_checkpoint_status` 并列，供事后核对。
4. **`UNVERIFIABLE` 声明（M3 要求）**：CR-e 情形 2 的 ②（改名）与 ③（发布）是**两次独立的文件系统操作**，**其组合不具备原子性**。本文档**不声称**能保证"旧代已改名、新代未发布"这一中间态在**掉电**下的可见性——该组合的正确恢复依赖**目录项持久化**，而 Windows 无等价机制（BLK-4）。因此：
   - 该中间态的**进程崩溃**行为**可判定**（见情形 3，判 `ABSENT_DIRTY` → `MANUAL_BLOCKED`）；
   - 该中间态的**掉电**行为 **`UNVERIFIABLE`**，**不得声称已保证**（见 A.21、C.4 第 46 条）。

### A.5.11 检查点代际保留与自动推进的发布语义（v8.3，N-01）

**背景（N-01）**：v8.2 的 `CP-5` 写作 `tmp → fsync → os.replace`，与 `A.2.2` 红线 16"禁止直接覆盖旧检查点"**直接冲突**；而 `A.11.1` 适用范围表只给了 `CP-R` 的 `pre_manual.<manual_epoch_id>` 命名——`manual_epoch_id` **只在人工路径存在**。也就是说：自动路径的旧代命名、保留策略、崩溃分支在 v8.2 里**一个都没有定义**。本节补齐完整生命周期；只改函数名不解决语义。

#### A.5.11.1 两条路径的职责分工

| 维度 | 自动 `CP-5`（本节） | 人工 `CP-R`（A.5.10） |
|---|---|---|
| 起点状态 | `CHECKPOINT_STATUS ∈ {VERIFIED, VERIFIED_MANUAL, ABSENT_CLEAN}` | `CHECKPOINT_STATUS == INCONSISTENT`（`ABSENT_DIRTY` 只能经人工处置后重建） |
| 旧代内容 | **可由 WAL 确定性重建**（每个字段都是 WAL 前缀的函数） | **不可重建**（旧代与 WAL 矛盾，其内容就是"矛盾"本身唯一的记录） |
| 旧代命名 | `<key>.durable.json.pre_advance.<wal_size_at_marker>.<前缀哈希前 8 位>` | `<key>.durable.json.pre_manual.<manual_epoch_id>` |
| 触发者 | T1 / T2 / T4 成功后的推进，以及载荷写入后的正常推进 | **仅** T5 阶段 B，且 `MANUAL_RESET` 已持久 |
| 新代状态 | 与旧代同族：旧代 `VERIFIED` → 新代 `VERIFIED`；旧代 `VERIFIED_MANUAL` → 新代**仍为** `VERIFIED_MANUAL` | 恒为 `VERIFIED_MANUAL` |
| 印记 | 无新增；旧代的 `manual_epoch` **原样携带** | 写入新的 `manual_epoch`，`manual_epoch_id` **不得复用** |

**禁止**互换两条路径的旧代命名：`pre_advance.*` 不含 `manual_epoch_id`，`pre_manual.*` 不由自动路径生成。

#### A.5.11.2 三种发布情形

| 情形 | 判定 | 动作 |
|---|---|---|
| **1 当代检查点不存在**（`ABSENT_CLEAN`） | `<key>.durable.json` 不存在 | 直接 CP-5a → CP-5c，无旧代可保留；发布仍用"目标不存在才创建" |
| **2 当代检查点存在** | 可解析、身份一致（CP-4 同等要求）、完整 SHA-256 可算 | CP-5a → CP-5b（改名保留）→ CP-5c（不覆盖发布）；新代写入 `pre_advance_checkpoint_sha256` = 旧代完整哈希、`checkpoint_generation` = 旧代 + 1 |
| **3 任一步失败**（写 tmp / fsync / 回读 tmp / 改名 / 发布） | 任一步报错，或校验不一致 | **中止**；`CHECKPOINT_STATUS` 保持旧代状态（若旧代已改名 → 落到 A.5.5 崩溃矩阵的 `ABSENT_DIRTY` 行）；**禁止**继续发布、**禁止**回退 `os.replace` / "先删后建"、**禁止**删除已改名的旧代 |

#### A.5.11.3 中间状态（不得留空）

| 崩溃点 | 磁盘状态 | 判定 | 允许的恢复 |
|---|---|---|---|
| CP-5a 中 | 旧代完好 + 一个不完整 tmp | 旧代仍为当代 → 按旧代状态判定；tmp **不被采用** | 下次扫描忽略 tmp；新一次 CP-5 用**新的** `attempt` 后缀 |
| **CP-5b 后、CP-5c 前** | 只有 `pre_advance.*` 与 tmp、**没有当代检查点** | **`ABSENT_DIRTY`** → `UNKNOWN` → `MANUAL_BLOCKED` | 人工按 A.7.9 处置；**禁止**自动把 `pre_advance.*` 改回当代名（那等于用自动路径"修复"一个不可判定的中间态） |
| CP-5c 后、CP-6 前 | 新代已发布 + `pre_advance.*` 仍在 | 新代可读 → 继续 CP-6；回读失败 → 下次扫描发现不一致 | 旧代始终可回读，可作对照物 |

#### A.5.11.4 保留策略与残留

1. **不自动删除任何 `pre_advance.*`**：旧代是"这次推进前检查点长什么样"的唯一物证；删除须单独人工授权并记录到 `wal_evidence\`。
2. **孤儿 `pre_advance.*` 只作证据**：不参与 V-0…V-6 的当代判定，**不得**被当作当代检查点读入，**也不得**因为"存在旧代"而判 `INCONSISTENT`。
3. **残留 tmp 不阻塞推进**：tmp 名含 `<pid>.<attempt>`，崩溃残留既不被采用也不构成冲突；新一次 CP-5 换 `attempt` 即可，**不需要**先删除旧 tmp。
4. **旧代数量无上限**：每次成功推进产生一个 `pre_advance.*`。这是红线 16"绝对禁止覆盖"的直接代价，**不在本方案内解决**；容量治理须由人工在测试阶段评估（C.4 第 51 条）。

#### A.5.11.5 `generation` 语义

- `checkpoint_generation` 从 0 起，每次成功推进（含 `CP-R`）+1，单调递增、**不得回退**。
- `checkpoint_generation` **不纳入** `wal_state_digest`——否则每次推进都会使既有 T2 签核失效，形成"签核永远追不上推进"的死循环。
- `generation` **不参与** `WAL_STATE_COMPLETE` 判定；它只用于事后核对代际顺序（哪个 `pre_advance.*` 早于哪个当代检查点）。

#### A.5.11.6 硬规则

1. **自动路径与人工路径都不得直接覆盖当代检查点**——红线 16 对两者**同等生效**。
2. **`VERIFIED_MANUAL` 不得经自动推进洗成 `VERIFIED`**：旧代 `manual_epoch != null` → 新代必须原样携带同一 `manual_epoch`，状态保持 `VERIFIED_MANUAL`。否则 A.5.10 硬规则 1 会被 CP-5 悄悄绕过。
3. **`INCONSISTENT` / `ABSENT_DIRTY` 时禁止 CP-5**，只能走 `CP-R`。
4. **发布失败不得回退**到 `os.replace` / "先删后建" / "把 `pre_advance.*` 改名回当代"。
5. **掉电语义 `UNVERIFIABLE`**：CP-5b 与 CP-5c 是两次独立的文件系统操作，其组合不具备原子性；掉电后能否看到"旧代已改名、新代未发布"依赖**目录项持久化**，Windows 无等价机制（BLK-4）。本文档**不声称**能保证该中间态的掉电可见性（C.4 第 50 条）。
6. 本节是 `A.11.1` 适用范围表中"检查点"行的**唯一细则来源**；`A.5.5` 的 CP-5a/5b/5c 只写步骤，不重复条件。

---

## A.6 WAL 尾部残缺行修复流程

### A.6.1 适用范围与禁止范围

| | 内容 |
|---|---|
| **允许修复** | 主 WAL **末尾**存在无法解析为记录的字节，且该残行是**最后一行** |
| **禁止** | 因主 WAL 写入失败（短写 / 异常 / fsync 失败）而主动截断回滚——这些字节**可能是完整记录**，截断即销毁证据 |
| **禁止** | 非末行不可解析时自动修复 |
| **禁止** | 手工编辑 WAL；不经 A.6 直接 `truncate`；删除或重写历史以掩盖不确定状态 |
| **禁止（v7）** | 在 `WAL_IDENTITY_STATUS != IDENTITY_VERIFIED` 时执行任何修复步骤 |

### A.6.2 九步流程（v7：RP-4 后加身份复核；v8.2：RP-4 前加 RP-4a，RP-4 改为同句柄截断）

| 步 | 动作 | 持久化要求 |
|---|---|---|
| **RP-1 识别** | 经已校验句柄逐行解析，定位第一条失败行；断言它是最后一行；计算 `tail_offset`、`tail_len` | 只读 |
| **RP-2 保存证据** | 复制 `[tail_offset, EOF)` 到 `wal_evidence\<key>.<ts>.tail.bin`；flush + fsync；回读算 `tail_sha256`；记录 `tail_hex_prefix` | 证据文件必须 fsync 后才可继续 |
| **RP-3 写修复意图** | 向 `wal_repairs\<key>.jsonl` 追加 `REPAIR_INTENT{repair_intent_id, wal_size_before, tail_offset, tail_len, tail_sha256, evidence_path, wal_identity_before, tool_sha256, ts}`；fsync | 必须先于任何截断 |
| **RP-4a 截断前置（v8.2，R18）** | 三条**同时**成立才允许进入 RP-4：<br>① `H_wal` **仍处于打开状态**（自 RP-1 起未关闭、未重开，`buffering=0`）；<br>② 截断前 `os.fstat(H_wal)` 的**身份 == `wal_identity_before`** 且 **`st_size == wal_size_before`**；<br>③ 持有 `LockFileEx` + 工具锁，且**无第二个写者**（PWA-1 / PWA-4 成立）。<br>任一不成立 → **不截断**，`MANUAL_BLOCKED`，`REPAIR_INTENT` 与证据保留 | 只读 |
| **RP-4 截断** | **只允许对已验证句柄执行**：`os.ftruncate(H_wal.fileno(), tail_offset)`（POSIX）/ `SetEndOfFile(hFile)`（Windows）。**禁止** `os.truncate(path, tail_offset)`——路径截断与路径替换之间存在竞态，可能截断到另一个文件 | 截断本身不产生新的持久证据 |
| **RP-4b 句柄复核（v8.2 重写）** | 在**同一句柄**上 `os.fstat(H_wal)`：`st_size == tail_offset` 且身份未变；再关闭句柄、**按路径重开**复核身份仍 == `wal_identity_before`。任一不符 → `MANUAL_BLOCKED` | 只读 |

> **RP-4 的边界（v8.2，R18）**：RP-4b 是**附加**检查，**不能**替代 RP-4a 的事前保证；理由与平台不可用时的中止规则见 **A.6.5**。
| **RP-5 复核** | 重读主 WAL：大小 == `tail_offset`，全文件可解析，seq 单调 | 只读 |
| **RP-6a 追加 REPAIR** | 向主 WAL 追加 `REPAIR` 事件；fsync | 主 WAL fsync 成功 |
| **RP-6b 推进检查点** | 按 A.5.5 CP-3…CP-6 计算前缀哈希、复核身份并发布检查点；回读校验 `VERIFIED` 且覆盖到 `REPAIR` 结束偏移 | 检查点必须 `VERIFIED` |
| **RP-7 标记完成** | 向 `wal_repairs\<key>.jsonl` 追加 `REPAIR_DONE{repair_intent_id, confirmed_checkpoint_seq}`；fsync | 必须在 RP-6b 成功之后 |

### A.6.3 `REPAIR` 三种持久化状态的启动恢复规则

| 情况 | 识别条件 | 持久性 | `WAL_STATE_COMPLETE` | 允许 `REPAIR_DONE` | 允许再次修复 | 运行状态 | 人工 |
|---|---|---|---|---|---|---|---|
| **① 已确认持久化** | `REPAIR` 可解析且字段完整；`VERIFIED`；`last_durable_record_seq >= REPAIR.seq`；前缀哈希覆盖其结束偏移；身份一致 | `DURABLE` | 由其他条件决定 | **允许** | **禁止** | 视 op 状态 | 否 |
| **② 可见但未确认** | `REPAIR` 可解析完整；但 `VERIFIED` 不成立 / marker 未覆盖 / 前缀哈希未覆盖 / 身份未验证 | `PROVISIONAL` | `VERIFIED` 且身份一致 → `NO`；否则 → `UNKNOWN` | **禁止**（须先完成 RP-6b 并复核） | **禁止** | `NO` → `RECOVERY_REQUIRED`；`UNKNOWN` → `MANUAL_BLOCKED` | `UNKNOWN` 分支必须 |
| **③ 损坏或不可解析** | 行不可解析 / 字段缺失非法 / `seq` 非单调 / `repair_intent_id` 不匹配 / 完整性不可判定 | 按 `PROVISIONAL` 处理 | `UNKNOWN` | **禁止** | **禁止** | `MANUAL_BLOCKED` | **必须** |

**三条原则**：① 只有通过 WAL 与检查点**双向一致性 + 身份验证**的修复证据，才能按"已完成"继续；② 对 `PROVISIONAL` / 损坏 / 不确定的修复记录，不得自动认定修复已完成；③ 不得因为看到 `REPAIR` 就跳过恢复校验，不得通过截断、删记录、重写历史来掩盖不确定状态。

### A.6.4 每步崩溃后的重启判定

| 崩溃点 | 持久证据 | 重启判定 | 允许的下一步 | 禁止 |
|---|---|---|---|---|
| RP-1 / RP-2 之间 | 无 INTENT；主 WAL 原样 | 未开始 | 重做 RP-1…RP-2（证据按新时间戳新建） | 覆盖既有证据；直接截断 |
| RP-2 完成、RP-3 之前 | 有证据文件，无 INTENT | 未开始 | 从 RP-3 起（复用证据须校验 `tail_sha256`） | 无 INTENT 就截断 |
| RP-3 完成、RP-4 之前 | INTENT 存在、无 DONE；大小 == `wal_size_before`；tail 哈希匹配 | 已开始未截断 | 从 **RP-4a** 起（三条前置全部复检） | 重写 INTENT；删证据；**跳过 RP-4a 直接截断** |
| **RP-4a 前置不成立**（v8.2，R18） | INTENT 存在、无 DONE；句柄已关闭 / 身份或大小与基线不符 / 非独占写者 | **不允许截断** | 停止 → `MANUAL_BLOCKED`；保留 INTENT 与证据 | 任何截断；**按路径截断**；关闭并重开后再截断；删证据 |
| **RP-4b 检测到身份变化** | INTENT 存在、无 DONE；身份 ≠ `wal_identity_before` | **身份不可信** | 停止 → `MANUAL_BLOCKED` | 任何自动动作 |
| RP-4 进行中，大小 ∈ (`tail_offset`, `wal_size_before`) | INTENT 存在、无 DONE；大小非两端值 | **边界不可确定** | 停止 → `RECOVERY_REQUIRED` + 人工 | 再次截断；猜边界；删证据 |
| RP-4 完成、RP-6a 之前 | INTENT 存在、无 DONE；大小 == `tail_offset`；无 `REPAIR` | 已截断未记录 | 从 RP-6a 继续 | 重复截断 |
| RP-6a 完成、RP-6b 之前 | INTENT 存在、无 DONE；`REPAIR` 可见；检查点未覆盖 | 情况 ② | 先完成 RP-6b 并复核 | 写 `REPAIR_DONE`；再次截断 |
| RP-6b 完成、RP-7 之前 | INTENT 存在、无 DONE；`VERIFIED` 且覆盖 `REPAIR` | 情况 ① | 写 `REPAIR_DONE` | 再写一条 `REPAIR` |
| RP-7 之后 | INTENT + DONE；检查点覆盖 `REPAIR` | 完成 | 常规扫描 | — |
| 任何时刻大小 ∉ {`wal_size_before`, `tail_offset`} | — | **不可确定** | 停止 → `RECOVERY_REQUIRED` + 人工 | 任何自动动作 |
| `REPAIR_DONE` 存在但无匹配 `REPAIR` 或检查点未覆盖 | — | 不一致 | 停止 → 人工 | 自动补写 |

**总则**：任何一步无法确定 → 保持 `RECOVERY_REQUIRED` 或转 `MANUAL_BLOCKED`，证据全部保留，不得静默忽略。

### A.6.5 截断操作的身份安全（v8.2，R18）

**问题**：v8.1 的 RP-4 写作 `os.truncate(wal, tail_offset)`（"经同一路径"），身份复核放在 **RP-4b（截断之后）**。这在两个层面不成立：

1. **路径不是身份**：`os.truncate(path, ...)` 在内核里是"按路径解析 → 打开 → 设置长度"。解析与打开之间若发生重命名 / 替换，截断会落在**另一个文件**上；"同一路径"这个措辞无法排除该竞态。
2. **事后复核不能倒推事前安全**：RP-4b 只能发现"截断后路径上的文件已不是基线身份"，**不能证明被截断的就是 `wal_identity_before` 指的那个文件**。若目标与 WAL 一并被替换，截断可能已经破坏了别处数据，而 RP-4b 只报一句"身份不符"。

**规范（六条）**：

| # | 规则 |
|---|---|
| **TR-1** | 截断**必须**在 RP-1 打开并校验过的**同一句柄**上执行（`ftruncate` / `SetEndOfFile`）；**禁止**任何按路径的截断调用 |
| **TR-2** | 截断**前**必须完成 RP-4a 的三条前置校验（句柄连续 / 身份与大小一致 / 独占写者）；**不得**推迟到截断之后 |
| **TR-3** | 截断**后**的复核（RP-4b）是**附加**检查，用于发现"截断期间路径被换"，**不能**替代 TR-2 |
| **TR-4** | 若目标平台或当前实现**无法保证**"对同一已验证句柄执行截断"（只能按路径截断 / `ftruncate` 不可用 / `SetEndOfFile` 被拒绝）→ **中止自动修复**：不执行截断，`REPAIR_INTENT` 与证据保留，运行状态 `MANUAL_BLOCKED`，等待人工与 BLK-1 决策 |
| **TR-5** | 截断的**原子性**（掉电后大小是 `tail_offset` 还是 `wal_size_before`）**不由本方案保证**；两种结果分别落到 A.6.4 的"RP-4 完成"或"RP-4 进行中"行，后者 → `RECOVERY_REQUIRED` + 人工 |
| **TR-6** | **不得**用"截断后身份复核通过"作为"截断前操作对象正确"的证明（这正是 v8.1 的缺陷） |

**为什么 TR-4 是中止而不是降级**：降级到"按路径截断 + 事后复核"等于把唯一的身份保证换成一个**只能发现失败、不能阻止破坏**的检查。WAL 尾部修复本来就是"销毁字节"的操作，一旦对象错了不可撤销；因此宁可停在 `MANUAL_BLOCKED`。

**`UNVERIFIABLE` 声明**：`ftruncate` / `SetEndOfFile` 在目标卷上的可用性，以及掉电瞬间长度字段的可见性，**均未测**（C.3 第 32 条、C.4 第 48 条）。本节只规定"若不能保证就中止"，**不声称已经保证**。

## A.7 持久化判定与状态转移

### A.7.1 `WAL_STATE_COMPLETE` 三值（v7 扩充失败日志条件）

| 值 | 条件 |
|---|---|
| **`YES`** | `CHECKPOINT_STATUS ∈ {VERIFIED, VERIFIED_MANUAL, ABSENT_CLEAN}` **且**（若为 `VERIFIED_MANUAL` 则 `manual_epoch != null` 且 `OP_UNRESOLVED == ∅`）**且** `WAL_IDENTITY_STATUS ∈ {IDENTITY_VERIFIED, IDENTITY_NOT_APPLICABLE}` **且** `FAILURE_LOG_STATUS ∈ {FAIL_READABLE_EMPTY, FAIL_ABSENT_CONSISTENT}` **且** 所有记录 `DURABLE` **且** 无 `OP_UNRESOLVED` **且** 无结构异常 **且** V-T 通过 **且**（若 `EMPTY_STATE == true`（组合 #1 / #2 / #3a / #5a）则 **ALL-GONE ①–⑦ 全部成立**，A.5.9） |
| **`NO`** | 检查点与身份均可验证；但存在 `OP_UNRESOLVED` 或存在 `PROVISIONAL` 记录，**且** `FAILURE_LOG_STATUS ∈ {FAIL_READABLE_EMPTY, FAIL_READABLE_WITH_RECORDS, FAIL_ABSENT_CONSISTENT}` 且其中若为 `FAIL_READABLE_WITH_RECORDS`，每条记录均能对应到已识别的失败阶段。**（v8）`VERIFIED_MANUAL` 且存在 `OP_UNRESOLVED` 时不得判 `NO`** —— 人工印记下不得再走自动恢复 |
| **`UNKNOWN`** | `CHECKPOINT_STATUS ∈ {ABSENT_DIRTY, INCONSISTENT}`；或 `WAL_IDENTITY_STATUS ∈ {IDENTITY_MISMATCH, IDENTITY_UNVERIFIABLE}`；或 `FAILURE_LOG_STATUS ∈ {FAIL_UNREADABLE, FAIL_CORRUPT, FAIL_ABSENT_INCONSISTENT}`；或 V-T 失败；或存在无法判定的结构异常；**（v8）或 `CHECKPOINT_STATUS == VERIFIED_MANUAL` 且存在 `OP_UNRESOLVED`**（人工 epoch 下自动路径全部关闭） |

**关键区分**：`NO` = 已知不完整、可走受控自动路径；`UNKNOWN` = 状态不可判定、**只能人工**。

**（v8.2，R13）判定优先级——三值不是并列可选项，必须按序短路**：

```
判 1  若命中 UNKNOWN 的任一条件            → UNKNOWN（立即返回，不再检查 NO / YES）
判 2  否则若命中 NO 的任一条件             → NO
判 3  否则若命中 YES 的全部条件            → YES
判 4  否则（三组条件均不满足）             → UNKNOWN（兜底，fail-closed）
```

**为什么必须这样**：`UNKNOWN` 的条件（检查点不可用 / 身份异常 / 故障日志不可用 / V-T 失败）与 `NO` 的条件（存在 `OP_UNRESOLVED` 或 `PROVISIONAL`）**可以同时成立**。例如"检查点 `INCONSISTENT` + 故障日志 `FAIL_READABLE_WITH_RECORDS` + 存在未解决 op"：单看 `NO` 的条件全部命中，单看 `UNKNOWN` 的条件也命中。若允许"先命中先返回"，结果取决于条件的书写顺序——这是不可复现的判定。

**禁止**：① 让宽泛的 `NO` 条件覆盖更严格的 `UNKNOWN` 条件；② 把 `UNKNOWN` 与 `NO` 视为"同级二选一"；③ 在 `NO` 分支里"顺带处理"身份异常；④ 用"`YES` 的条件都成立"反推"因此不是 `UNKNOWN`"（`YES` 的判定必须在 `UNKNOWN` 之后）。

**（v8.2，R13 + R17）`UNKNOWN` 是 `T2` 的全局否决条件**：`WAL_STATE_COMPLETE == UNKNOWN` 时 `T2` 一律不成立——**不是**"因为 T2-2 / T2-6 恰好失败"，而是**显式**规定为全局否决（见 A.7.5）。文字（A.7.3 的 T2 行）、表格（A.7.4）、真值表（A.7.5）三处必须一致。

### A.7.2 故障日志状态判定（P0-2）

| 状态 | 判定条件 | 对自动路径的影响 |
|---|---|---|
| `FAIL_READABLE_EMPTY` | 文件不存在且 **WAL 侧独立证明无失败**（全部记录 `DURABLE`、无 `OP_UNRESOLVED`、无结构异常）；或文件存在且为空 | 不阻断 |
| `FAIL_ABSENT_CONSISTENT` | 文件不存在，WAL 不干净，但**每一个** `PROVISIONAL` / 未解决 op 都能由 `wal_repairs` 或快照侧独立解释 | 允许 `NO`，允许 T1 / T4 |
| `FAIL_READABLE_WITH_RECORDS` | 文件存在且有记录；每条记录均可解析、可归属到具体 `stage`，且与 WAL 侧观测一致 | 允许 `NO`，允许 T1 / T4（**这是唯一"运行期写失败但可继续"的情形**） |
| `FAIL_ABSENT_INCONSISTENT` | 文件不存在，但 WAL 不干净且**存在无法由其他证据解释**的 `PROVISIONAL` / 未解决 op | `UNKNOWN` → `MANUAL_BLOCKED` |
| `FAIL_UNREADABLE` | 文件存在但无法打开（权限 / 占用 / I/O 错误） | `UNKNOWN` → `MANUAL_BLOCKED` |
| `FAIL_CORRUPT` | 文件存在但格式损坏（不可解析行、字段非法、seq 非单调） | `UNKNOWN` → `MANUAL_BLOCKED` |

**四条硬规则（P0-2）**：

1. **运行期写日志失败、但重新读取已有日志成功** → 依 `FAIL_READABLE_WITH_RECORDS` 处理，允许进入 T1 / T4；但**不得仅凭检查点 `VERIFIED` 就假定所有状态安全** —— 必须逐条核对失败记录与 WAL 观测一致。
2. **启动或恢复阶段日志缺失 / 不可读 / 损坏 / 真实性不可确认** → `UNKNOWN` 或 `MANUAL_BLOCKED`，**禁止 T1、T2、T4**。
3. **故障日志与检查点均不可持久化** → `MANUAL_BLOCKED`，不得继续尝试真实目标写入。
4. **不得用"检查点已验证"替代缺失的故障证据**：WAL 干净时缺失日志可由 WAL 侧独立证明（`FAIL_READABLE_EMPTY`）；WAL 不干净时缺失日志**必须**由其他证据补齐（`FAIL_ABSENT_CONSISTENT`），否则一律 `FAIL_ABSENT_INCONSISTENT`。

### A.7.3 五条解除路径（v7：新增 T5）

| 路径 | 性质 | 适用前提 | 动作 |
|---|---|---|---|
| **T1** | 自动 | `WAL_STATE_COMPLETE == NO`；检查点 `VERIFIED`；身份 `IDENTITY_VERIFIED`；`FAILURE_LOG_STATUS ∈ {FAIL_READABLE_EMPTY, FAIL_READABLE_WITH_RECORDS, FAIL_ABSENT_CONSISTENT}`；**存在** `OP_UNRESOLVED`；快照 `SNAPSHOT_VALID` | 一次完整 `RECOVERY` 操作，`resolves_op_ids` 覆盖全部未解决 op；**完成后必须按 A.7.10 的 PR-1…PR-5 复核**（重扫故障日志、重算 `WRITE_PERMITTED`） |
| **T2** | **必须人工签核** | A.7.5 的 7 条全部成立 **且 `WAL_STATE_COMPLETE != UNKNOWN`**（v8.2，R17：`UNKNOWN` 是 T2 的**全局否决**条件，不得靠"逐条恰好失败"间接排除） | 修复 + 签核；**完成后必须按 A.7.10 复核** |
| **T3** | 无需转换 | 本就 `READY` | — |
| **T4** | 自动 | `WAL_STATE_COMPLETE == NO`；检查点 `VERIFIED`（**不含 `VERIFIED_MANUAL`**）；身份 `IDENTITY_VERIFIED`；故障日志同上三值之一；**无** `OP_UNRESOLVED`；无结构异常；唯一缺陷是存在 `PROVISIONAL` 记录 | 检查点重同步：`fsync(H_wal)` → 重算前缀哈希 → 复核身份（CP-4）→ 按 CP-5/CP-6 发布 → 复核 `VERIFIED`。**不写任何 WAL 记录，不改动目标内容，不得调用 `CP-R`**；**完成后必须按 A.7.10 复核**（尤其 PR-1 的故障日志重扫） |
| **T5** | **仅人工**（v7 新增，v8 改两阶段，v8.1 限定范围，**v8.2 统一前置**） | **起点状态（v8.3，N-04）**：`RUN_STATE == MANUAL_BLOCKED`；从 `RECOVERY_REQUIRED` / `READY` / 其他任何状态调用 T5 **一律非法**（A.7.4"T5 的起点不可达"）。<br>**硬前提（四条缺一不可，v8.2 / R14 + R19）**：① `OP_UNRESOLVED == ∅`；② MP-1 调查证据存在且哈希一致；③ MP-2 签核有效且 `state_digest_at_override` == 当前 `wal_state_digest`；④ **`FAULT_CLASS ∈ {FRC-CHECKPOINT, FRC-FAILURELOG, FRC-STRUCTURAL}` 且 `WAL_IDENTITY_STATUS == IDENTITY_VERIFIED`**（A.5.10 CR-6 两轴表）。<br>**任一不成立 → T5 不可执行**（不是"执行后失败"，是"前提不成立"）→ 保持 `MANUAL_BLOCKED` | **阶段 A**：写 `BEGIN(MANUAL) → MANUAL_RESET`（含 `unresolved_set_empty:true`、`mp1_evidence_ref`、`target_sha256_confirmed_by_human`、`manual_epoch_id`），fsync；**不推进检查点**。<br>**阶段 B**：满足 A.5.10 CR-1…CR-6 后执行 `CP-R`，检查点变 `VERIFIED_MANUAL`。<br>**阶段 C**：重新完整扫描 + V-T；仅当 `WAL_STATE_COMPLETE == YES` 且目标哈希 == 人工确认值 → `READY`，否则**保持 `MANUAL_BLOCKED`**。<br>**全程不修改目标、不伪造 `END`/`RECOVERED`/`ABORTED`** |

**T4 的合法性依据**：A.5.5 已确立"一次成功 `fsync` 会把此前所有未确认字节一并持久化"。T4 只把这一事实记录进检查点。它**不能**用于 `UNKNOWN`。

**（v8.2，R14）`T5*` 记号——全文档统一读法**：`T5*` 一律表示"`T5`，且上述四条硬前提**全部成立**"。前提不成立时，`T5*` 的**实际结果**是"保持 `MANUAL_BLOCKED`，无可执行出口"。**禁止**把表格里出现 `T5*` 读成"因此可以执行 T5"；**也禁止**在表格中单独写 `T5` 而省略前置条件（v8.1 的 6 处"仅 T5"已全部改写）。

**T5 的边界（v8 重写）**：

- T5 **不是**"把 `UNKNOWN` 变成已验证"，而是"人工确认后带印记地接受现状"。`MANUAL_RESET` 永久保留，`wal_state_digest` 带上人工印记。
- T5 **不修复数据**：不重写目标、不伪造 `END` / `RECOVERED` / `ABORTED`、不通过重写检查点"消除" `INCONSISTENT`（`CP-R` 不是消除，见 A.5.10 对照表）。
- T5 **不得**用于跳过 T1：存在 `OP_UNRESOLVED` 时 T5 非法，唯一出口是保持 `MANUAL_BLOCKED`（A.7.9）。
- **签核 ≠ 恢复**：签核只授权"记录人工决定"，不授权"把状态改成 `READY`"。进入 `READY` 必须由阶段 C 的**重新扫描**决定；目标状态无法证明时，即使签核有效也**必须**保持 `MANUAL_BLOCKED`。

### A.7.4 状态转移闭包表（P0-2 第 4 条：证明不存在 UNKNOWN → READY 的自动路径）

| 起点 | 出口 | 是否自动 | 条件 |
|---|---|---|---|
| `READY` | `READY` | — | 正常 |
| `READY` | `RECOVERY_REQUIRED` | 自动 | 出现 `OP_UNRESOLVED` / `PROVISIONAL` / V-T 失败 |
| `READY` | `MANUAL_BLOCKED` | 自动 | 身份 / 检查点 / 故障日志进入不可判定 |
| `RECOVERY_REQUIRED` | `READY` | 自动 | **T1** 或 **T4** 成功（A.7.3 前提全满足） |
| `RECOVERY_REQUIRED` | `READY` | **人工** | **T2** 签核（`WAL_STATE_COMPLETE != UNKNOWN`）。**（v8.3，N-04）不含 `T5`**——见下方"T5 的起点不可达" |
| `RECOVERY_REQUIRED` | `MANUAL_BLOCKED` | 自动 | 身份 / 故障日志 / 检查点恶化 |
| **`MANUAL_BLOCKED`** | **`READY`** | **仅人工 T5（三阶段全部完成）** | `OP_UNRESOLVED == ∅` + MP-1 证据 + MP-2 签核 + `MANUAL_RESET` 持久 + `CP-R` 成功（`VERIFIED_MANUAL`）+ **重新扫描 `YES` 且 V-T 通过**；**无任何自动出口** |
| **`MANUAL_BLOCKED`** | **`MANUAL_BLOCKED`（保持）** | **唯一安全出口（未解决集合非空时）** | `OP_UNRESOLVED != ∅` → 禁止 T1/T2/T4/T5；人工只能做 MP-1 调查与有授权的外部恢复，然后重新验证 |
| **`MANUAL_BLOCKED`（身份类，v8.1 / M2；v8.2 按 `FAULT_CLASS` 重述）** | **无任何出口** | **禁止** | `FAULT_CLASS ∈ {FRC-IDENTITY_MISMATCH, FRC-IDENTITY_UNAVAILABLE}` → `CR-6` 两轴表禁止 `CP-R` → T5 阶段 B 无法完成；**不得**表述为"可经 T5 或 `CP-R` 恢复"；只能保持，待 BLK-1 决策 |
| **`MANUAL_BLOCKED`（根因未定类，v8.2 / R16）** | **无任何出口** | **禁止** | `FAULT_CLASS == FRC-UNKNOWN` → 无法确定该走哪条路径，`CP-R` 一律禁止（A.5.10 CR-6 两轴表）；只能保持，补足派生输入后重新扫描 |
| `MANUAL_BLOCKED` | `RECOVERY_REQUIRED` | **不允许** | 不得降级；只能经 T5 出（**仅非身份类**） |
| 任意 | `UNKNOWN`（子状态） | — | `WAL_STATE_COMPLETE` 是派生值，不是运行状态 |

**结论（v8.1）**：`WAL_STATE_COMPLETE == UNKNOWN` 的三个来源（检查点 / 身份 / 故障日志）全部映射到 `MANUAL_BLOCKED`，而 `MANUAL_BLOCKED` **没有自动出口**。因此**不存在从未知状态自动回到 `READY` 的路径**。

**（v8.3，N-04）T5 的起点不可达——为什么本表不再把 T5 列为 `RECOVERY_REQUIRED` 的出口**：

`RECOVERY_REQUIRED` 只有三个入口（本表首行：`OP_UNRESOLVED` / `PROVISIONAL` / V-T 失败）。逐个代入 A.7.3 T5 行的四条硬前提，**无一成立**：

| `RECOVERY_REQUIRED` 的入口 | 撞哪条硬前提 |
|---|---|
| 存在 `OP_UNRESOLVED` | ① `OP_UNRESOLVED == ∅` 不成立（A.7.9.2 MP2-1、S15a） |
| 仅有 `PROVISIONAL`、无未解决 op | 按 A.2.3 F1–F8 均不命中 → F9 = `FRC-UNKNOWN` → ④ 不成立；且这本是 **T4** 的自动领域 |
| V-T 失败 | A.7.1 已把"V-T 失败"列为 `UNKNOWN` 条件，**本不应**进 `RECOVERY_REQUIRED`（该路由冲突另记 **N-02**，本轮范围外未修） |

因此 **T5 的起点只能是 `MANUAL_BLOCKED`**。把 T5 写成 `RECOVERY_REQUIRED` 的出口，会产生一条"表格允许、结构上不可达"的**伪转换**——它不增加任何能力，只会让读者以为存在第二条人工出口。

**（v8.1，M2）人工出口的准确表述**：`MANUAL_BLOCKED` 的人工出口**不是一条**，而是**按故障类别分裂**：

- **非身份类**（`FRC-CHECKPOINT` / `FRC-FAILURELOG` / `FRC-STRUCTURAL` 且身份已验证）→ T5 三阶段（`MANUAL_RESET` → `CP-R` → 重扫）是唯一出口，**且须四条硬前提全部成立**；
- **身份类**（`FRC-IDENTITY_MISMATCH` / `FRC-IDENTITY_UNAVAILABLE`）→ **没有文档化出口**；
- **根因未定类**（`FRC-UNKNOWN`）→ **没有文档化出口**（v8.2，R16）；
- 三类共同的禁止：**不得**把 `T2` / `T4` 当作"另一条出口"（两者都要求 `WAL_STATE_COMPLETE != UNKNOWN` 且 `IDENTITY_VERIFIED`）。

**禁止**把身份类 `MANUAL_BLOCKED` 描述为"可通过人工签核恢复"；也**禁止**通过人工签核或 `VERIFIED_MANUAL` 把身份不匹配转换为写入许可。

**v8 补充两点**：① `MANUAL_BLOCKED → READY` 的唯一人工路径必须**穿过**"`MANUAL_RESET` 持久 + `CP-R` + 重新扫描通过"三道门，缺一即停在 `MANUAL_BLOCKED`；② `VERIFIED_MANUAL` 状态下若又出现 `OP_UNRESOLVED`，**不得**判 `NO` 走 T1（A.7.1），只能回到 `MANUAL_BLOCKED`。

### A.7.5 T2 的 7 条（v7 强化 T2-2 / T2-6）

| # | 条件 |
|---|---|
| **T2-1** | 唯一结构缺陷是末尾不可解析残行，且已按 A.6 完成修复（`REPAIR` 含 `repair_intent_id` 与 `evidence_path`） |
| **T2-2** | 修复后文件完全可解析、seq 严格单调、无重复 `op_id`、无未知事件类型；**且 `CHECKPOINT_STATUS == VERIFIED`（v8：`VERIFIED_MANUAL` 不算，人工重建过的前缀不得走 T2）覆盖到修复后末尾（V-0…V-6 全通过）；且 `WAL_IDENTITY_STATUS == IDENTITY_VERIFIED`** |
| **T2-3** | **不存在任何 `OP_UNRESOLVED`**。不放宽 |
| **T2-4** | 三集合语义校验成立（A.9），且 `actual_unresolved_set_after == ∅`；**不得把恢复前集合与恢复后空集直接比较** |
| **T2-5** | 目标全文件 SHA-256 == B，B 为现场重算的快照内容哈希 |
| **T2-6** | `FAILURE_LOG_STATUS ∈ {FAIL_READABLE_EMPTY, FAIL_ABSENT_CONSISTENT}`（v7：`FAIL_READABLE_WITH_RECORDS` 也可，但每条记录须已闭合；`FAIL_UNREADABLE` / `FAIL_CORRUPT` / `FAIL_ABSENT_INCONSISTENT` 一律不成立） |
| **T2-7** | 存在有效签核，且其 `wal_state_digest_at_signoff` == **当前** `wal_state_digest`（含 `checkpoint_status` / `wal_identity_status` / `failure_log_status`） |

**（v8.2，R17）T2 的全局否决条件**：`WAL_STATE_COMPLETE == UNKNOWN` 时 **T2 一律不成立**。这一条是**独立的前置否决**，不是"由 T2-2 / T2-6 推导出来的副作用"——因为逐条推导依赖"`UNKNOWN` 的每个来源都恰好使某一条失败"，一旦新增 `UNKNOWN` 来源（v8 就新增了 `VERIFIED_MANUAL + OP_UNRESOLVED`），逐条推导可能悄悄失效，而全局否决不会。

**三处一致性要求**：① **文字**——本节与 A.7.3 的 T2 行都必须写明该否决；② **表格**——A.7.4 的 T2 出口行必须带 `!= UNKNOWN` 条件；③ **真值表**——A.7.1 的判定优先级必须把 `UNKNOWN` 排在 `NO` 之前。任一处缺失即为缺陷。

**推论**：`UNKNOWN` 时 T2-2 与 T2-6 亦必然不成立，因此 **T2 永不适用于 `UNKNOWN`**（全局否决是充分条件，逐条推导只是它的一个特例）。

### A.7.6 S7b / S7e / S7f / S7g / S7h / S7i / S7j 的分支处理

**统一规则（v8.2，R14 + R19）——"仅 T5"不是授权**：

1. 下表的"允许路径"列只表示**理论出口类别**，**不构成任何路径的可执行授权**。
2. 任何路径的可执行性一律由 **A.7.3 的"适用前提"** 与 **A.7.9 的硬前提**共同决定；表格单元格**不得**被读成"因此可以执行 T5"。
3. **`T5*` 记号**：表示"`T5`，且 A.7.3 T5 行的四条硬前提（`OP_UNRESOLVED == ∅` / MP-1 证据 / MP-2 签核 / 非身份类 `FAULT_CLASS` + `IDENTITY_VERIFIED`）**全部成立**"。前提不成立时，`T5*` 的**实际结果**是"**保持 `MANUAL_BLOCKED`，无可执行出口**"。
4. 因此本表所有 `T5*` 单元格都必须按"**条件成立才可执行，否则保持阻塞**"阅读；v8.1 写作"仅 T5"而不标前置条件的 6 处已全部改写。
5. **`OP_UNRESOLVED != ∅` 时 `T5` 恒不可执行**——即使故障类型、检查点状态、签核都齐备。此时唯一允许的是保持 `MANUAL_BLOCKED` + MP-1 调查（A.7.9.3）。
6. **身份类故障（`FRC-IDENTITY_*`）时 `T5` 恒不可执行**，且**不得**用 `T5*` 书写（会暗示存在条件成立的可能）——必须写"无出口"。
7. **（v8.3，N-04）起点状态也是前提**：`T5*` 的读法包含"`RUN_STATE == MANUAL_BLOCKED`"。在 `RECOVERY_REQUIRED` 下即使四条硬前提看似成立，`T5*` 仍不可执行——因为 `RECOVERY_REQUIRED` 的每个入口都会破坏其中至少一条（A.7.4）。

| 用例 | 故障 | 分支 | 检查点 | 身份 | 故障日志 | `WAL_STATE_COMPLETE` | 允许路径（**受前置条件约束**） |
|---|---|---|---|---|---|---|---|
| **S7b** | `BEGIN` 持久化失败 | b1 完整可见 + 已覆盖 | `VERIFIED` | `VERIFIED` | 任一可判定值 | `NO` | T1 |
| | | b2 完整可见 + 未覆盖 | `VERIFIED` | `VERIFIED` | 同上 | `NO` | T1 |
| | | b3 不完整（残行） | `VERIFIED` | `VERIFIED` | 同上 | `NO` | 先按 A.6 修复 → b1/b2 或 T2 |
| | | b4 检查点 `INCONSISTENT` | `INCONSISTENT` | `IDENTITY_VERIFIED` | — | `UNKNOWN` | **`T5*`**（`OP_UNRESOLVED == ∅` 才可执行；否则保持 `MANUAL_BLOCKED`） |
| **S7e** | `fsync` 失败 **且** `wal_failures` 不可写 | e1 有未解决 op | `VERIFIED` | `VERIFIED` | `FAIL_ABSENT_INCONSISTENT` | `UNKNOWN` | **`T5*`；本行通常不成立**——有未解决 op → 硬前提 ① 失败 → **实际无出口**，保持 `MANUAL_BLOCKED`（S7i） |
| | | e2 无未解决 op | `VERIFIED` | `VERIFIED` | `FAIL_ABSENT_INCONSISTENT` | `UNKNOWN` | **`T5*`**（`OP_UNRESOLVED == ∅` 时可执行） |
| | | e3 检查点也损坏 | `INCONSISTENT` | `IDENTITY_VERIFIED` | — | `UNKNOWN` | **`T5*`**（`OP_UNRESOLVED == ∅` 时可执行） |
| **S7f** | `.durable` 缺失 / 损坏 / 回退 | f1 缺失 + WAL 有记录 | `ABSENT_DIRTY` | `IDENTITY_VERIFIED` | — | `UNKNOWN` | **`T5*`**（须 `OP_UNRESOLVED == ∅`；`ABSENT_DIRTY` + 未解决 op → 无出口） |
| | | f2 损坏或不可解析 | `INCONSISTENT` | `IDENTITY_VERIFIED` | — | `UNKNOWN` | **`T5*`**（同上） |
| | | f3 回退（合法更早前缀） | `VERIFIED` | `VERIFIED` | 任一可判定值 | `NO` | T1 / T4 |
| **S7g** | `PROVISIONAL` 且无未解决 op | — | `VERIFIED` | `VERIFIED` | 任一可判定值 | `NO` | T4 |
| **S7h（v7 新增）** | `fsync` 失败 **但** `wal_failures` 可写且含对应 `FAILED` | h1 有未解决 op | `VERIFIED` | `VERIFIED` | `FAIL_READABLE_WITH_RECORDS` | `NO` | T1 |
| | | h2 无未解决 op | `VERIFIED` | `VERIFIED` | `FAIL_READABLE_WITH_RECORDS` | `NO` | T4 |
| **S7i（v8.2，R14）** | 交叉校验：任一 `T5*` 分支 + `OP_UNRESOLVED != ∅` | — | 视分支 | `IDENTITY_VERIFIED` | 视分支 | `UNKNOWN` | **无出口**：硬前提 ① 失败 → 只能保持 `MANUAL_BLOCKED` + MP-1；**不得**因表格写 `T5*` 就执行 `MANUAL_RESET` |
| **S7j（v8.2，R15）** | `T4` 成功后重扫 `wal_failures` 发现新增不可解析行 | — | `VERIFIED`（T4 后） | `IDENTITY_VERIFIED` | `FAIL_CORRUPT`（重扫后） | `UNKNOWN`（重扫后） | **无出口**：`T4` 的"成功"不能覆盖重扫结论 → 立即转 `MANUAL_BLOCKED`，`WRITE_PERMITTED = NO` |

> **（v8.2）身份列补全**：v8.1 中 b4 / e3 / f1 / f2 四行的"身份"列为"—"，导致无法判断 `T5*` 的前提 ④；v8.2 补为 `IDENTITY_VERIFIED`（这四类故障的根因均非身份，按 A.2.3 的 F5/F6 派生）。若实测为身份类，则按 A.2.3 的 F1–F4 改判为 `FRC-IDENTITY_*` → **无出口**，不再适用 `T5*`。
>
> **v6 → v7 的收紧**：v6 把 S7e 判为 `NO`（可走 T1/T4）。v7 依 P0-2 第 6 条"不得用检查点已验证替代缺失的故障证据"改为 `UNKNOWN` → **`T5*`**（v8.2 标前置条件）；同时新增 S7h 承载"失败日志可写"的合法自动路径。二者共同覆盖"故障日志可用 / 不可用"两侧。

### A.7.7 持久化失败情形总表

| 情形 | 主 WAL | 检查点 | 身份 | 故障日志 | 记录判定 | `WAL_STATE_COMPLETE` | 放行 |
|---|---|---|---|---|---|---|---|
| fsync 失败 + 日志可写 + 有对应记录 | 可见 | 未推进但 `VERIFIED` | `VERIFIED` | `FAIL_READABLE_WITH_RECORDS` | `PROVISIONAL` | `NO` | 否（须先 T1/T4） |
| fsync 失败 + 日志不可写 | 可见 | 未推进但 `VERIFIED` | `VERIFIED` | `FAIL_ABSENT_INCONSISTENT` | `PROVISIONAL` | `UNKNOWN` | **否；`T5*`** |
| 日志与检查点均不可持久化 | 可见 | 不可用 | 可能 `VERIFIED` | `FAIL_UNREADABLE` | `PROVISIONAL` | `UNKNOWN` | **否；`T5*`** |
| 日志损坏 | 可见 | 视情况 | 视情况 | `FAIL_CORRUPT` | 视情况 | `UNKNOWN` | **否；`T5*`** |
| 检查点 `INCONSISTENT`（非身份类） | 可见 | 不可用 | `IDENTITY_VERIFIED` | 视情况 | `PROVISIONAL` | `UNKNOWN` | **否；`T5*`** |
| 身份不一致 / 身份不可得 | 可见 | 不可用 | `IDENTITY_MISMATCH` / `IDENTITY_UNVERIFIABLE` | 视情况 | `PROVISIONAL` | `UNKNOWN` | **否；无出口**（`CR-6` 两轴表禁止 `CP-R`） |
| 正常完成 | 可见 | 已推进 `VERIFIED` | `VERIFIED` | `FAIL_READABLE_EMPTY` | `DURABLE` | 由 op 状态决定 | 视 op 状态 |

> **（v8.2，R14）"放行"列的读法**：`否；`T5*`` 表示"载荷写入不放行；`T5` 只在四条硬前提全部成立时可执行，否则**无出口**"。本列**不是**路径授权，见 A.7.6 统一规则。

### A.7.8 `WRITE_PERMITTED`

```
WRITE_PERMITTED = YES 仅当：
  WAL_STATE_COMPLETE == YES
  AND CHECKPOINT_STATUS ∈ {VERIFIED, VERIFIED_MANUAL, ABSENT_CLEAN}
  AND (  EMPTY_STATE == false
      OR ALL-GONE ①–⑦ 全部成立（A.5.9） )      ← v8.3：空态分类 #1/#2/#3a/#5a 一律不得绕过 ALL-GONE
  AND (  CHECKPOINT_STATUS != VERIFIED_MANUAL
      OR (   manual_epoch != null
         AND BLK-5 == DECIDED_ACCEPT
         AND 签核记录中已明确接受该 manual_epoch 下的写入
         AND OP_UNRESOLVED == ∅ ) )
  AND WAL_IDENTITY_STATUS ∈ {IDENTITY_VERIFIED, IDENTITY_NOT_APPLICABLE}
  AND FAILURE_LOG_STATUS ∈ {FAIL_READABLE_EMPTY, FAIL_ABSENT_CONSISTENT}
  AND V-T 通过
  AND 快照 == SNAPSHOT_VALID（不含 SNAPSHOT_CONFLICT）
  AND 锁已获取（LockFileEx + 工具锁）
  AND 无待人工签核项
  AND 游戏进程未运行
  AND PWA 准入通过（A.10.1）
```

**（v8.1，M1）`CHECKPOINT_STATUS` 真值表**（按 `AND` / `∨` 的短路语义逐行验证）：

| `CHECKPOINT_STATUS` | 第 2 行集合判定 | 第 3 行括号判定 | 第 3b 行 ALL-GONE 判定 | 合取结果 | `WRITE_PERMITTED` |
|---|---|---|---|---|---|
| `VERIFIED` | 真 | 真（`!= VERIFIED_MANUAL` 成立） | 真（`!= ABSENT_CLEAN` 成立） | 真 | 由其余条件决定 |
| `EMPTY_STATE`（#1 / #2 / #3a / #5a）+ ALL-GONE ①–⑦ 成立 | 真 | 真 | 真 | 真 | 由其余条件决定 |
| **`EMPTY_STATE` + ALL-GONE 不成立**（v8.3） | 真 | 真 | **假** | **假** | **NO** |
| `VERIFIED_MANUAL` + `manual_epoch != null` + BLK-5 = `DECIDED_ACCEPT` + 签核接受 + `OP_UNRESOLVED == ∅` | 真 | 真 | 真 | 真 | 由其余条件决定 |
| `VERIFIED_MANUAL` + 上述四项**任一不成立** | 真 | **假** | 真 | **假** | **NO** |
| `ABSENT_DIRTY` / `INCONSISTENT` | **假** | 真 | 真 | **假** | **NO** |

**关键结论（M1 的核心要求）**：

1. **BLK-5 未决时 `VERIFIED_MANUAL` 恒为 `NO`**：`BLK-5 != DECIDED_ACCEPT` 使第 3 行括号恒假 → 合取假 → `WRITE_PERMITTED = NO`，与 A.22"任一 BLK 未决禁止真实写入"一致。
2. **`VERIFIED_MANUAL` 永不单独授予写权限**：它只解除"检查点不可用"这一项；四项否决条件（`manual_epoch` / BLK-5 / 签核接受 / `OP_UNRESOLVED == ∅`）**必须全部通过**。
3. **第 2 行的集合扩展不是授权式**：它只为让第 3 行的否决条件**有机会被求值**。若第 3 行不成立，结果与"不在集合内"完全相同（均为 `NO`）。
4. **不得只替换集合文本而忽略括号与否定条件**：若把第 3 行删掉或写成"`VERIFIED_MANUAL` 允许"，则 `VERIFIED_MANUAL` 会绕过 BLK-5 直接放行——这是被明确禁止的误读。
5. **（v8.2 / v8.3）空态不再是无条件放行**：第 3b 行把 ALL-GONE 变成合取项，且 v8.3 把适用范围从 `ABSENT_CLEAN` 扩到整个 `EMPTY_STATE`（#1 / #2 / **#3a** / #5a）。只要 `wal_evidence` 等旁证存在，`WRITE_PERMITTED = NO`（与 A.5.9 硬规则 4、A.7.1 `YES` 行、A.10.1 PWA-6 同构）。
6. **（v8.2）本式只判"载荷写入"**：恢复性目标写入（T1 / T2）与状态写入（检查点 / WAL / 签核 / 快照）**不**用本式，见 A.7.10。

**不得假设 `write()` 或 `fsync()` 失败意味着数据一定在盘上，或一定不在盘上**；失败只能推出"持久性未知"。

### A.7.9 人工处理两阶段与"未解决集合非空"的唯一出口（v8，R3）

**原则**：`MANUAL_BLOCKED` 既不是"自动恢复成功"，也不等于"目标文件已回到基线"。人工处理必须分成两个**不可合并**的阶段。

**（v8.3，N-04）起点唯一**：T5 的起点**只能**是 `MANUAL_BLOCKED`。`RECOVERY_REQUIRED` 的人工出口只有 **T2**（A.7.4）；把 T5 当作"另一条出口"会产生不可达的伪转换。

#### A.7.9.1 MP-1 人工调查 / 恢复阶段

| # | 要求 |
|---|---|
| MP1-1 | 只读调查：导出 `wal_state_digest`、WAL 全文、检查点、身份字段、故障日志、目标全文件哈希、快照清单 |
| MP1-2 | 允许的操作**仅限**：① 只读比对；② 在**有独立证据**（如快照哈希 + 现场重算一致）支持时执行**有授权的恢复**（`BEGIN(RECOVERY)` 走 T1 规则）；③ 复制证据到 `wal_evidence\` |
| MP1-3 | **禁止**：手工编辑 WAL / 检查点 / 故障日志；直接改写目标；删除证据；"看一眼就算恢复" |
| MP1-4 | 无法证明时**保持阻塞**，不得升级为"已恢复" |
| MP1-5 | 产出 `mp1_evidence_ref`（调查记录 JSON：时间、操作者、观察到的事实、做过/没做过什么、结论与不确定性） |

#### A.7.9.2 MP-2 人工重置 / 签核阶段

| # | 要求 |
|---|---|
| MP2-1 | 前提：`OP_UNRESOLVED == ∅`（硬性）；否则 **T5 非法**，不得写任何 `MANUAL_RESET` |
| MP2-2 | 前提：MP1-5 的证据存在且可读 |
| MP2-3 | 签核内容见 A.14.4，必须含 `unresolved_set_empty:true`、`target_sha256_confirmed_by_human`、`manual_epoch_id` |
| MP2-4 | 执行顺序强制：`MANUAL_RESET`（持久）→ `CP-R`（A.5.10）→ 重新扫描 → 才可能 `READY` |
| MP2-5 | **禁止**伪造 `END` / `RECOVERED` / `ABORTED`；**禁止**重写目标；**禁止**在 `MANUAL_RESET` 未持久时执行 `CP-R` |

#### A.7.9.3 未解决集合非空时的唯一安全出口

| 状态 | 允许 | 禁止 |
|---|---|---|
| `MANUAL_BLOCKED` 且 `OP_UNRESOLVED != ∅` | 保持 `MANUAL_BLOCKED`；执行 MP-1；在独立证据支持时执行有授权的 `RECOVERY`（T1 规则）并重新验证 | T1 自动路径、T2、T4、**T5**、任何目标写入、任何"人工已查看所以放行"的推断 |
| `MANUAL_BLOCKED` 且 `OP_UNRESOLVED == ∅`（**非身份类**） | MP-2 → `MANUAL_RESET` → `CP-R` → 重新扫描 | 跳过任一阶段；仅凭签核改 `READY` |
| **`MANUAL_BLOCKED`（身份类：`IDENTITY_MISMATCH` / `IDENTITY_UNVERIFIABLE`）** | **只能保持**；可执行 MP-1 只读调查与有独立证据支持的 `RECOVERY`（T1 规则）并重新验证；**待 BLK-1 决策** | **T5**（阶段 B 无法完成）；**`CP-R`**；任何"人工已签核所以放行"的推断；宣称"已恢复"或"可恢复" |
| 重新扫描后目标哈希 ≠ 人工确认值 | 保持 `MANUAL_BLOCKED`，回到 MP-1 | 把签核当作"目标已确认" |

**硬规则（v8.1）**：① `unresolved_set_empty == true` 是 T5 的硬性前提，任何情况下不得放宽；② "人工已查看"**不等于**"已恢复"；③ 无法通过自动机制闭合的场景**保留人工阻塞并列为待决**，不得擅自放宽安全条件（见 C.1 / C.5）；④ **（M2；v8.2 按 `FAULT_CLASS` 重述）身份类与 `FRC-UNKNOWN` 下 T5 不可执行**——`CR-6` 两轴表禁止 `CP-R`，阶段 B 无法完成，因此"签核齐全"不能使这两类 `MANUAL_BLOCKED` 前进任何一步；⑤ **（M1）`VERIFIED_MANUAL` 不单独授予写权限**，四项否决条件见 A.7.8。

### A.7.10 写入路径准入统一表（v8.2，R15 + R17）

**问题**：v8.1 把 `WRITE_PERMITTED`（A.7.8）与 PWA（A.10.1）都写成"全条件"，但其中 `WAL_STATE_COMPLETE == YES` 是**载荷写入**的前提；而 `T1` / `T2` / `T4` 的前提恰恰是 `WAL_STATE_COMPLETE == NO`。若要求恢复路径也满足 `WRITE_PERMITTED` / PWA-6，则**恢复永远无法开始**——这是循环依赖，v8.1 未拆开。

**三类写入必须分开判定**：

| 类别 | 写什么 | 准入谓词 | 说明 |
|---|---|---|---|
| **载荷写入** | 目标 `.assets` 的 ST-12 数据块 | **`WRITE_PERMITTED == YES`（A.7.8）+ PWA 全 PASS（A.10.1）** | 唯一需要 `WAL_STATE_COMPLETE == YES` 的写入 |
| **恢复性目标写入** | 目标（`RECOVERY` 回滚 / T2 修复） | **`RECOVERY_PERMITTED`（本节定义）**；**不**要求 `WRITE_PERMITTED == YES` | 用 `WRITE_PERMITTED` 判它会造成循环依赖 |
| **状态写入** | WAL 记录、检查点、签核、快照、证据文件 | **不需要** `WRITE_PERMITTED`，**不需要** PWA-6；只要求锁、路径安全、A.11.1 / **A.5.11** / CR-e 的发布语义 | 状态写入本身是为了让状态可判定，不能反过来要求状态已可判定 |

**`RECOVERY_PERMITTED`（v8.2 新增）**：

```
RECOVERY_PERMITTED = YES 仅当：
  路径前提全满足（T1：A.7.3 T1 行全部；T2：A.7.5 七条 且 WAL_STATE_COMPLETE != UNKNOWN）
  AND 快照 == SNAPSHOT_VALID
  AND 锁已获取（LockFileEx + 工具锁）
  AND 游戏进程未运行
  AND PWA-1 / PWA-2 / PWA-4 / PWA-5 / PWA-7 / PWA-8 全部 PASS
  AND PWA-3 已有具名风险接受（否则 UNVERIFIABLE → 阻断）
  AND resolves_op_ids 覆盖 expected_unresolved_set（A.9 三集合语义）
```

**PWA-6 的适用范围（v8.2 明确）**：PWA-6 内含 `WAL_STATE_COMPLETE == YES`，**只适用于载荷写入**；**禁止**把 PWA-6 用于 T1 / T2 / T4 / T5 / `CP-R` / `RP-*`，否则形成循环依赖。恢复路径改用 `RECOVERY_PERMITTED`（T1 / T2）或"仅状态写入"（T4 / T5 / `CP-R` / `RP-*`）。

**恢复后的强制复核（v8.2，R15）**：`T1` / `T2` / `T4` **成功之后**，必须按下列顺序复核，**不得**因"路径已成功"直接放行后续载荷写入：

| 步 | 动作 | 不通过的后果 |
|---|---|---|
| **PR-1** | **重新扫描 `wal_failures`** 并按 A.7.2 六值**重新判定** `FAILURE_LOG_STATUS`；**禁止**沿用恢复前的值 | 重扫结果 ∈ {`FAIL_UNREADABLE`, `FAIL_CORRUPT`, `FAIL_ABSENT_INCONSISTENT`} → `WAL_STATE_COMPLETE = UNKNOWN` → **`MANUAL_BLOCKED`** |
| **PR-2** | 重新执行 V-0…V-6 + V-T，重算 `wal_state_digest` | 任一失败 → 按 A.7.1 重新定值 |
| **PR-3** | 按 A.7.8 **重算** `WRITE_PERMITTED`，按 A.10.1 **重算** PWA | `WRITE_PERMITTED = NO` → 本次载荷写入**终止**；不得以"T1/T4 已成功"为由放行 |
| **PR-4** | 若 PR-1 / PR-2 使 `WAL_STATE_COMPLETE` 变为 `UNKNOWN` | **立即**转 `MANUAL_BLOCKED`，禁止继续任何写入 |
| **PR-5** | 若重分类使 `FAULT_CLASS` 变为身份类 | 转 `MANUAL_BLOCKED`，**无出口**（A.7.4） |

**三条硬规则**：① **`T1` / `T4` 成功只把运行状态从 `RECOVERY_REQUIRED` 推到 `READY`，不等于 `WRITE_PERMITTED == YES`**；② **`T4` 只写检查点，不是"修复"，不得因它成功就跳过 PR-1 的故障日志重扫**（S7j 就是这一条的用例）；③ **`PR-1` 的重扫结果优先于任何缓存值**——包括本次进程内先前判定的 `FAILURE_LOG_STATUS`。

### A.7.11 状态机一致性检查表（v8.2，汇总）

**用途**：把散落在 A.2.1 / A.5.7.4 / A.5.9 / A.7.1 / A.7.4 / A.7.6 / A.7.9.3 / A.10.1 的规则汇总成"一张表能查完"的形态，供人工复核逐行对照。本表**不引入任何新规则**；与上述小节冲突时，一律以各小节为准。

| 运行状态 | 进入条件（全部满足） | 允许操作 | 禁止操作 | 退出条件 |
|---|---|---|---|---|
| `READY` | `WAL_STATE_COMPLETE == YES`；快照 `SNAPSHOT_VALID`；无 `OP_UNRESOLVED`；V-T 通过 | 载荷写入（须 `WRITE_PERMITTED == YES` 且 PWA 全 PASS）；常规扫描 | 在 `WRITE_PERMITTED == NO` 时写入；跳过 A.7.10 的复核 | 出现未解决 op / 结构异常 → `RECOVERY_REQUIRED`；身份、检查点或故障日志不可判定 → `MANUAL_BLOCKED` |
| `RECOVERY_REQUIRED` | 存在 `OP_UNRESOLVED` / `PROVISIONAL`；检查点与身份仍可验证 | T1（自动）/ T2（人工签核）/ T4（仅 `VERIFIED` 检查点）；恢复性目标写入须 `RECOVERY_PERMITTED == YES` | 载荷写入；**T5**（T5 的唯一起点是 `MANUAL_BLOCKED`，v8.3 / N-04）；跳过 A.7.10 的复核 | T1 / T2 / T4 成功**且** PR-1…PR-5 全过 → `READY`；状态恶化 → `MANUAL_BLOCKED` |
| `MANUAL_BLOCKED`（非身份类） | `FAULT_CLASS ∈ {FRC-CHECKPOINT, FRC-FAILURELOG, FRC-STRUCTURAL}` 且身份已验证 | MP-1 只读调查；有独立证据时执行有授权的 `RECOVERY`；MP-2 → `MANUAL_RESET` → `CP-R` → 重扫 | 任何载荷写入；T1 自动路径；T2；T4；未解决集合非空时进入 T5 | 三阶段全过且重扫 `YES` → `READY`；否则保持 |
| `MANUAL_BLOCKED`（身份类） | `FAULT_CLASS ∈ {FRC-IDENTITY_MISMATCH, FRC-IDENTITY_UNAVAILABLE}` | 只能保持；MP-1 只读调查 | `CP-R`；T5；T1 / T2 / T4；任何写入；宣称"已恢复" | **无出口**（待 BLK-1 决策） |
| `MANUAL_BLOCKED`（根因未定类） | `FAULT_CLASS == FRC-UNKNOWN` | 只能保持；补足派生输入后重新扫描 | `CP-R`；T5；任何写入 | **无出口**；重新扫描后若派生成功，按新分类落入上两行 |

**三值的判定与使用**：`WAL_STATE_COMPLETE` 按 A.7.1 的优先级（`UNKNOWN` → `NO` → `YES` → 兜底 `UNKNOWN`）定值；它**不是**运行状态，只是 `READY` 的必要条件之一。`WRITE_PERMITTED` 与 `RECOVERY_PERMITTED` 是**准入谓词**，同样不是状态。

**两条一致性断言**：① 上表五行中**只有第一行**允许载荷写入；② 后三行的"退出条件"列中，**没有任何一行**以"签核"或"检查点重建"单独作为出口。

## A.8 操作时序与屏障钩子（P0-3：12 步）

### A.8.1 十二个步骤

```
ST-1   词法检查            纯字符串，零文件系统访问，零副作用
ST-2   实体解析            realpath + commonpath + 捕获 (st_dev, st_ino, st_size, st_mtime_ns)
ST-3   安全打开 + 身份确认   open 后立即 fstat 比对
ST-4   取锁                LockFileEx 全文件范围独占 + 工具级锁文件
ST-5   创建并校验快照      A.11.1 八步
ST-6   写 BEGIN            write + fsync + 检查点推进（CP-1…CP-6）
ST-7   复检                紧贴写入，中间无其他 I/O
ST-8   写入                等长原地覆盖，1 MiB 固定块、升序、每块一次 write（写游标模型见 A.8.1.1）
ST-9   目标持久化          flush + os.fsync(目标句柄) / FlushFileBuffers
ST-10  回读验证            长度 + 全文件 SHA-256 == A + 对象级回读
ST-11  提交前复检          紧贴 END，再次全文件 SHA-256（捕捉 ST-10 之后的变化）
ST-12  写 END + fsync + 检查点推进
```

### A.8.1.1 块写入模型与写游标（v8，R1）

**这是 S5b 全部时序断言的唯一依据。** 任何与本节不符的偏移/`k` 值都不得使用。

| 项 | 规定 |
|---|---|
| 块大小 | `BLK = 1 MiB = 1,048,576` 字节 |
| 块数 | `N = ceil(size / BLK)`；`T-64M` 的 `size = 67,108,864` ⇒ `N = 64` |
| 顺序 | **严格升序**，块 `i` 覆盖 `[i·BLK, (i+1)·BLK)`；单遍，**每块只写一次** |
| 钩子 `H3(k)` 的位置 | 第 `k-1` 块（0 基）写完并返回**之后**、第 `k` 块开始**之前**触发；`1 ≤ k ≤ N-1` |
| **已完成前缀** | `[0, k·BLK)` —— 字节已由我方写入，**后续块不会再触碰** |
| **未写区** | `[k·BLK, size)` —— 尚未写入，**后续块会覆盖** |
| **写游标位置** | `cur = k·BLK`（下一块的首字节） |

**由模型直接推出的两条判据**（S5b 必须遵守）：

1. 外部写入偏移 `off` **落在未写区**（`off >= k·BLK`）→ 我方后续块会把该区间**整体覆盖** → 最终目标哈希 **`== A`** → **写时不可检出**。
2. 外部写入偏移 `off` **落在已完成前缀**（`off + len <= k·BLK`）→ 后续块不再触碰该区间 → 最终目标哈希 **`!= A`** → **必须检出**（ST-10 / ST-11 的全文件哈希）。

**术语约定**：本文档中"**写游标之后**"= 未写区（判据 1）；"**写游标之前**"= 已完成前缀（判据 2）。v7 的 S5b 两个用例把这两个方向标注反了，v8 已按本节重排（见 A.17-S5 与 A.18）。

**不可达组合声明**：在"升序 + 单遍 + 每块一次"模型下，**不存在**"位于已完成前缀、且随后仍会被载荷覆盖"的位置 —— 已完成前缀不会再被写。v7/R1 任务描述中的这一子目标标注为 **`MODEL_UNREACHABLE`**，不得伪造；若未来改为多遍写入或非升序，需新增钩子 `H3'`（第二遍开始处）与独立用例。

### A.8.2 目标持久化与 END 的顺序（P0-3 核心）

| 规则 | 内容 |
|---|---|
| **ORD-1** | `ST-9` 必须对**目标文件句柄**执行 `flush` + `os.fsync(fd)`（Windows 上 `os.fsync` 走 `_commit` → `FlushFileBuffers`）。仅有 `flush()` 不算持久化 |
| **ORD-2** | `ST-10` 必须重新读取目标（经同一句柄或重新打开后经 ST-3 身份确认），验证：文件长度 == 预期、全文件 SHA-256 == A、对象级可解析（`T-REAL`） |
| **ORD-3** | `ST-12` 写 `END` 的**前提**是 `ST-9` 与 `ST-10` 均成功；`END.target_persisted` 与 `END.readback_verified` 必须为 `true` |
| **ORD-4** | `ST-11` 是"提交前最后一道门"：再次计算全文件哈希，若 ≠ A 则**不写 `END`**，写 `FAILED{stage:precommit_recheck}` |
| **ORD-5a** | `ST-9` / `ST-10` / `ST-11` 失败（此时 **`END` 尚未开始写入**，可证明不存在 `END`）→ op 保持 `OP_UNRESOLVED`，写 `FAILED{stage:...}`，**禁止**写 `END`，按 T1 恢复 |
| **ORD-5b（v8）** | `ST-12` 中 `write(END)` 或 `fsync(WAL)` 失败 → **既不能证明 `END` 已完整持久化，也不能证明它不存在** → **禁止自动重写 `END`**，op 保持 `OP_UNRESOLVED`，写 `FAILED{stage:end_write\|end_fsync}`，进入 `RECOVERY_REQUIRED` 并**重新扫描 WAL**，按 A.6 / A.7 判定后再决定路径 |
| **ORD-6（v8 限定）** | 仅适用于"**`END` 已验证持久、检查点未推进**"这一分支（阶段 3）：`END` 为 `PROVISIONAL`、op 已 `OP_COMMITTED`、`WAL_STATE_COMPLETE == NO` → **T4**；**不得**视为失败、**不得**重写 `END`、**不得**回滚目标 |
| **ORD-7（v8）** | `FAILED` **永不关闭**写入 op；`END` 的四种阶段（见下表）必须分别判定，**禁止**把 `ST-12` 的任何故障笼统归为同一结果 |

**`END` 四阶段判定表（v8，R2）**：

| 阶段 | 判定依据 | `END` 记录 | op 状态 | 允许的下一步 | 禁止 |
|---|---|---|---|---|---|
| **① END 尚未开始写入** | ST-9 / ST-10 / ST-11 失败；WAL 中无本 op 的 `END` | 无 | `OP_UNRESOLVED` | 记录失败证据；T1 恢复或人工阻塞 | 写 `END`；假定"没写就等于没发生"后直接放行 |
| **② END 写入或 fsync 失败，持久性未知** | `write`/`fsync` 报错，但无法判定磁盘上 `END` 的完整性 | **不可判定**（可能完整、可能残行、可能不存在） | `OP_UNRESOLVED` | `RECOVERY_REQUIRED`；重新扫描 WAL；残行按 A.6 修复后再判定 | **自动重写 `END`**；宣告成功；直接 T1 而不重扫 |
| **③ END 已验证持久、检查点未推进** | `END` 可解析、字段完整（含 `target_hash_provenance`）、前缀哈希覆盖其结束偏移、身份一致；但 `last_durable_record_seq < END.seq` | `PROVISIONAL` | `OP_COMMITTED` | 满足 T4 全部条件 → **T4**（只重同步检查点） | 重写 `END`；视为失败；改动目标 |
| **④ END 与检查点均已验证** | 阶段 ③ 条件 + 检查点覆盖到 `END.seq` | `DURABLE` | `OP_COMMITTED` | 正常完成 | 追加任何"补偿"记录；改写 `END` |

**Windows / NTFS 持久化机制与保证边界**：

| 机制 | 保证 | 不保证 |
|---|---|---|
| `os.fsync(fd)`（→ `FlushFileBuffers`） | 该文件已写入的数据被提交到卷 | 目录项持久化；硬件写缓存（除非 `FILE_FLAG_NO_BUFFERING` / 关闭写缓存）；掉电后的最终状态 |
| `file.flush()` | 用户态缓冲交给 OS | 任何持久性 |
| `os.replace` | 同卷原子替换目录项 | 目录项本身是否已落盘 |
| 进程正常退出 | 无 | **不等同于**断电持久性验证 |

**声明**：本文档**不声称**已验证 Windows/NTFS 的全部持久化语义，**不声称**普通进程退出测试等同于断电测试。

### A.8.3 六个屏障钩子（M9，v7 扩为 6 个）

| 钩子 | 精确位置 | 用于 |
|---|---|---|
| **H1** | `ST-7` 内部，**在计算目标 SHA-256 之前** | S5a |
| **H2** | `ST-7` 返回成功之后、`ST-8` 首次 `write()` 之前 | S5d、S5e |
| **H3** | `ST-8` 内部，**块边界 k 处**（第 `k-1` 块完成后、第 `k` 块开始前；已完成前缀 `[0, k·1 MiB)`，见 A.8.1.1） | S5b-1（`k=32`）、S5b-2（`k=48`） |
| **H4** | `ST-8` 全部块完成之后、`ST-9` 目标持久化之前 | S5c |
| **H5（v7）** | `ST-10` 回读验证成功之后、`ST-11` 提交前复检之前 | S5f |
| **H6（v7）** | `ST-11` 成功之后、`ST-12` 写 `END` 之前 | S5g |

### A.8.4 屏障释放顺序

```
① 我方线程到达钩子 Hx，写 "at-hook" 标记，阻塞
② fixture 收到 "at-hook" 信号
③ fixture 启动 helper：open(target,'r+b') → seek(off) → write(buf) → flush → fsync → close → exit
④ helper 回传 "write-done" 信号（含偏移、长度、字节摘要）
⑤ fixture 回读该区间确认写入已落地
⑥ fixture 释放屏障
⑦ 我方线程继续
```

③ 的 `close` 与 ④ 的完成信号都必须发生在 ⑥ 之前。否则用例判 `UNCOVERED`。

### A.8.5 无钩子时

对应用例标记 **`UNCOVERED`**，不得用 sleep / 大致同时 / 概率并发代替。报告须写明缺失的是哪个钩子。

## A.9 三集合语义

| 名称 | 时点 | 内容 |
|---|---|---|
| `expected_unresolved_set` | 写 `BEGIN(RECOVERY)` 时 | 该 target 当前全部 `OP_UNRESOLVED` 的 `op_id` |
| `resolves_op_ids` | 写 `RECOVERED` 时 | 本次恢复声称解决的 `op_id` |
| `actual_unresolved_set_after` | 应用该 `RECOVERED` 后重新扫描 | 剩余 `OP_UNRESOLVED` |

**唯一正确校验链**：

```
① resolves_op_ids == expected_unresolved_set        （逐项 + digest + count）
② actual_unresolved_set_after == ∅
③ 把 expected_unresolved_set 与 actual_unresolved_set_after 直接比较是【错误】的
```

`unresolved_set_digest`：`op_id` 小写十六进制；按 UTF-8 字节序升序；以 `"\n"` 连接，末尾不加换行；UTF-8 无 BOM；SHA-256 小写十六进制；空集 = `e3b0c442…b855`；必须同时记录 `count` 与完整 `op_id` 列表。

## A.10 准入：PWA 与 STA

### A.10.1 生产写入准入（PWA）

| # | 条件 | 判定 |
|---|---|---|
| PWA-1 | `LockFileEx` 全文件范围独占，持有 ST-4→ST-12 | PASS / FAIL |
| PWA-2 | 游戏进程未运行 | PASS / FAIL |
| **PWA-3** | 无其他进程持有该文件的内存映射 | **UNVERIFIABLE** |
| PWA-4 | 单写者策略（进程级工具锁） | PASS / FAIL |
| PWA-5 | 快照 == `SNAPSHOT_VALID` | PASS / FAIL |
| PWA-6 | `WAL_STATE_COMPLETE == YES` ∧ `CHECKPOINT_STATUS ∈ {VERIFIED, VERIFIED_MANUAL, ABSENT_CLEAN}` ∧ (`CHECKPOINT_STATUS != VERIFIED_MANUAL` ∨ (`manual_epoch != null` ∧ `BLK-5 == DECIDED_ACCEPT` ∧ 签核记录中已明确接受该 `manual_epoch` ∧ `OP_UNRESOLVED == ∅`)) ∧ `WAL_IDENTITY_STATUS ∈ {IDENTITY_VERIFIED, IDENTITY_NOT_APPLICABLE}` ∧ (`EMPTY_STATE == false` ∨ **ALL-GONE ①–⑦ 全部成立**) ∧ `FAILURE_LOG_STATUS ∈ {FAIL_READABLE_EMPTY, FAIL_ABSENT_CONSISTENT}`（**v8.1，M1**：与 A.7.8 的 `WRITE_PERMITTED` **逐字同构**，真值表见 A.7.8；`VERIFIED_MANUAL` 的四项否决条件任一成立 → 本项 `FAIL`。**v8.2**：增 `ALL-GONE` 合取项；**v8.3**：合取项适用范围由 `ABSENT_CLEAN` 扩到 `EMPTY_STATE`，与 A.7.8 第 3b 行同构） | PASS / FAIL / UNKNOWN |
| PWA-7 | 用户对该文件、该次写入的书面授权 | PASS / FAIL |
| **PWA-8（v8.1，M5）** | **无 `BLK-1…BLK-5` 未决阻塞项（A.22）**；**任一 BLK 未决 → 本项 `FAIL`**。前四项已决**不能**推出 BLK-5 可放行，反之亦然（数量以 A.22 为唯一来源） | PASS / FAIL |

**规则**：① PWA-1/2/4/5/6/7/8 必须全部 `PASS`，任一 `FAIL`/`UNKNOWN` → 阻止真实写入；② PWA-3 恒为 `UNVERIFIABLE`，真实写入必须另有用户具名风险接受并写入台账 `risk_acceptance`；③ PWA 全满足也不代表并发保护完整（`W2-b` 部分不可检出，仅 V-T 延迟检出）；④ **（v8.2，R15）PWA-6 只适用于载荷写入**：它内含 `WAL_STATE_COMPLETE == YES`，而 T1 / T2 / T4 的前提恰为 `NO`；把 PWA-6 用于恢复路径会形成循环依赖。恢复性目标写入改用 `RECOVERY_PERMITTED`（A.7.10），状态写入不适用 PWA-6。⑤ **（v8.1，M5）PWA-8 的判定以 A.22 的 BLK 数量为唯一来源**——A.22 列几项，PWA-8 就检几项，两者不得出现数量差异。当前为 **5 项（BLK-1…BLK-5）**。

### A.10.2 隔离测试准入（STA）

| # | 条件 | 证明方式 |
|---|---|---|
| STA-1 | 目标路径经 ST-1/ST-2/ST-3 通过，落在 `TEST_ONLY_ROOT` 内 | 运行时断言 |
| STA-2 | 目标是 `seeds\` 的副本，种子来源与哈希已记录 | 前置校验 5 项 |
| STA-3 | 用例清单中不存在任何解析到 L0-A/L0-B/L0-C/L0-D 的路径 | manifest 静态检查 |
| STA-4 | 用例结束时 34 个真实 `.assets` 完整 SHA-256 == `baseline_ledger.json` | 事后比对 |
| STA-5 | 测试构建钩子已启用；生产构建中钩子不存在 | 构建标志断言 |
| STA-6 | 全局 `open()` 审计钩子：凡 mode 含 `w`/`+`/`x` 的路径必须落在 L1 内 | 进程级审计钩子 |

**STA 允许**：M1–M11 全部注入、WAL 破坏、检查点破坏、身份替换、故障日志破坏、锁破坏、快照破坏、尾部截断（仅在用例目录内）。
**STA 禁止**：任何 L0 路径的写模式打开；把测试快照写进项目 `backup\`；把钩子留在生产构建中；使用或改写 L0-D 的三个 `roundtrip_*.assets`。

### A.10.3 STA 与 PWA 的关系

> **STA 通过 ≠ PWA 满足。** 合成夹具全部通过不能推出真实文件写入安全、内存映射写者不存在、游戏进程无干扰、WAL 身份连续性成立、并发保护完整。PWA 只能在 P4 前由人工逐项确认；PWA-3 永远只能"风险接受"。

## A.11 快照规范

### A.11.1 发布九步（v8：由 8 步扩为 9 步，R4）

**核心约束（v8，R4）**：**同名永不覆盖**。`os.replace` 会无条件替换已存在的目标，**因此禁止用于快照与 sidecar 的发布**。发布必须使用"**目标不存在才创建**"的原子语义。

```
① 写内容到 <snap>\<base>.<sha16>.assets.tmp.<pid>.<rand>
② flush + fsync tmp
③ 回读 tmp 全文件 SHA-256 == B          ← 不通过则中止，tmp 保留
④ 预检最终名称是否已存在（早失败，非保证；TOCTOU 由 ⑤ 兜底）
     已存在 → 中止，SNAPSHOT_CONFLICT，保留 tmp 与既有文件
⑤ 原子"不存在才创建"发布（**禁止在最终名上直接写入内容**）：
     前提：①②③ 已完成——tmp 内容已写完、已 flush+fsync、已回读校验全文件 SHA-256 == B。
     Windows：MoveFileExW(tmp, final, 0)        ← **不带** MOVEFILE_REPLACE_EXISTING
              目标已存在 → 返回 FALSE / ERROR_ALREADY_EXISTS（不覆盖）
     通用：  os.link(tmp, final) → 成功后 unlink(tmp)
              目标已存在 → FileExistsError
     同卷要求：tmp 与 final 必须位于同一卷（本方案中同目录，天然满足）。
     失败分类（**必须区分，不得混报**）：
       - FileExistsError / ERROR_ALREADY_EXISTS
         → SNAPSHOT_CONFLICT（目标确实存在）
       - OSError(EXDEV) / EPERM / ERROR_NOT_SUPPORTED / 卷不支持硬链接
         → SNAPSHOT_PUBLISH_UNSUPPORTED（发布机制不支持或不能安全执行）
         → **安全失败**：本次写入终止，tmp 保留，既有文件不变，该用例记 UNCOVERED
       - 其余错误 → 同上，按 SNAPSHOT_PUBLISH_UNSUPPORTED 处理
         （**不得猜测目标是否存在**，不得凭空生成冲突方）
     **禁止**：把 EXDEV / 不支持硬链接 / 权限问题误报为 SNAPSHOT_CONFLICT；
     **禁止**通过"回退到 os.replace"或"先删后建"等不安全方式继续发布。
⑥ 回读最终内容文件 SHA-256 == B
⑦ 写 sidecar 到 sidecar.tmp.<pid>，flush + fsync
⑧ 以与 ⑤ 相同的"不覆盖"语义发布 sidecar（已存在 → SNAPSHOT_CONFLICT）
⑨ 回读 sidecar + 内容，三方交叉校验
```

**禁止清单（v8）**：

| 禁止 | 原因 |
|---|---|
| `os.replace` / `MoveFileEx(MOVEFILE_REPLACE_EXISTING)` 发布快照或 sidecar | 会覆盖同名既有文件，销毁唯一证据 |
| **（v8.1，M4）用 `CreateFileW(final, ..., CREATE_NEW, ...)` 打开最终名后向其写入内容** | 名字先占用、内容后写；崩溃后留下"看似已发布但内容不完整"的文件，且因同名永不覆盖而**永久不可恢复**；同时绕过 ①②③ 的写-持久化-全哈希保证 |
| **（v8.1，M4）把 `EXDEV` / 不支持硬链接 / 权限拒绝当作 `SNAPSHOT_CONFLICT`** | 会生成错误的冲突报告（声称存在同名文件而实际不存在），把"平台限制"伪装成"人为冲突" |
| **（v8.1，M4）发布失败后回退到 `os.replace` 或"先删后建"继续发布** | 等于放弃"不覆盖"保证，直接销毁唯一证据 |
| 先删除同名文件再发布 | 删除不可逆，且并发窗口内可能删掉他人刚发布的文件 |
| 仅凭文件名含 `<sha16>` 就认定内容可信 | 前缀是**声明**，不是校验；必须回读并重算完整 SHA-256 |
| 冲突时自动重命名旧文件"让位" | 属于未经授权的移动/改名 |

**冲突处理**：`SNAPSHOT_CONFLICT` → 本次写入终止（不写 `BEGIN`）；保留 tmp、保留既有文件；生成冲突报告（两侧完整 SHA-256、大小、mtime、sidecar 内容）；**不自动覆盖、不自动删除、不自动改名**；由人工按 A.11.3 判定。

**适用范围（v8.1，M3）——快照与检查点的更新语义不同，禁止混用**：

| 对象 | 性质 | 发布语义 | 依据 |
|---|---|---|---|
| 快照内容文件 / sidecar | **不可变证据**（一次写入、永久只读） | **"目标不存在才创建"**；同名已存在 → `SNAPSHOT_CONFLICT` → 中止 | 本节 ①–⑨ |
| 检查点 `<key>.durable.json`（**自动**推进，`CP-5`） | **必须可更新的当代声明**（旧代可由 WAL 重建） | **"先保留旧代证据、再发布新代"**；旧代原子改名为 `pre_advance.<wal_size_at_marker>.<前缀哈希前 8 位>`，**改名不是覆盖** | **A.5.11** |
| 检查点 `<key>.durable.json`（**人工**重建，`CP-R`） | **必须可更新的当代声明**（旧代不可重建） | **"先保留旧代证据、再发布新代"**；旧代原子改名为 `pre_manual.<manual_epoch_id>`，**改名不是覆盖** | **A.5.10 CR-e** |

**禁止**把本节的"同名即中止"套用到检查点上（那会使 `CP-R` 永远无法完成）；也**禁止**把 CR-e 的"改名保留"套用到快照上（快照没有"旧代"概念，改名会破坏证据命名）。

### A.11.2 可用性

`SNAPSHOT_VALID` ✅；`SNAPSHOT_NO_SIDECAR` ❌ 默认不可用（丢失操作归属，须人工确认）；`SNAPSHOT_ORPHAN` / `SNAPSHOT_CORRUPT` / `SNAPSHOT_ABSENT` / **`SNAPSHOT_CONFLICT`** / **`SNAPSHOT_PUBLISH_UNSUPPORTED`（v8.1，M4）** ❌。

**`SNAPSHOT_CONFLICT` vs `SNAPSHOT_PUBLISH_UNSUPPORTED`（v8.1，M4）——两者必须区分，不得合并**：

| 状态 | 含义 | 判定依据 | 处置 |
|---|---|---|---|
| `SNAPSHOT_CONFLICT` | **目标确实已存在** | `FileExistsError` / `ERROR_ALREADY_EXISTS` | 保留双方；生成冲突报告；按 **A.11.3** 人工判定 |
| `SNAPSHOT_PUBLISH_UNSUPPORTED` | **发布机制本身不可用** | `EXDEV` / 不支持硬链接 / `EPERM` / `ERROR_NOT_SUPPORTED` | **不存在冲突方**；**不得**生成冲突报告；本次写入终止；该用例记 `UNCOVERED` |

**禁止**把 `SNAPSHOT_PUBLISH_UNSUPPORTED` 描述为"同名冲突"，也**禁止**要求人工"比对两侧文件"（此时没有第二侧）。

硬规则：存在 ≠ 可用；不自动删除孤立/损坏/冲突快照；**同名永不覆盖（由 A.11.1 ⑤/⑧ 的原子"不存在才创建"保证，不靠预检）**。

### A.11.3 同名冲突的人工判定（v8）

| 情形 | 允许 | 禁止 |
|---|---|---|
| 内容文件同名且**完整 SHA-256 相同** | 视为同一内容；本次发布中止，复用既有文件前须人工确认 sidecar 归属 | 自动复用；自动删除 tmp 之外的任何文件 |
| 内容文件同名但哈希**不同** | 保留两者；人工比对大小/mtime/sidecar；判定是否为哈希前缀碰撞或外部替换 | 覆盖；删除任一方；按 mtime 择新 |
| sidecar 已存在 | 人工核对 `snapshot_sha256` 与内容是否匹配 | 覆盖 sidecar；无 sidecar 就恢复 |
| 证据不完整（tmp 残留、sidecar 缺失） | 安全失败，保持不可用状态 | 猜测补齐 |

## A.12 恢复关联与恢复失败

### A.12.1 三条硬约束

- **A-1**：`resolves_op_ids` 恰好等于 `expected_unresolved_set`（逐项 + digest + count）。
- **A-2**：不得包含任何已终结 `op_id`（否则一致性失败 → 隔离 + `RECOVERY_REQUIRED` + 人工）。
- **A-3**：不得遗漏（遗漏者仍 `OP_UNRESOLVED`）。

不伪造 `END`/`ABORTED`；原始 `BEGIN(WRITE)` 原样保留，派生为 `OP_SUPERSEDED`。

### A.12.2 恢复自身崩溃

| 崩溃点 | 证据 | 处理 |
|---|---|---|
| 写入前 | `#r1` 存在、目标 ∉ {B} | `OP_UNRESOLVED` → 保持；允许 `#r2` |
| 写到一半 | `#r1` 无终态、目标 ∉ {B} | 同上；不判进度，一律重做 |
| 写完但 `RECOVERED` 未持久化 | `#r1` 无终态、目标 == B | **T2 不适用**（T2-3）；必须 `#r2` 重做并落盘 `RECOVERED` |
| **恢复的 ST-9 / ST-10 失败** | `#r1` 无终态；目标持久性未知或哈希 ≠ B | 保持；`FAILED{stage:recovery_persist\|recovery_verify}`；重做 `#r2` |
| 快照失效 | `#r1` 无终态、快照校验失败 | 保持；`CURRENT_STATE`；人工 |
| 一致性检查失败 | 存在未被覆盖的未解决 op | 保持；人工 |
| 检查点 `INCONSISTENT` / 身份不一致 | — | **`MANUAL_BLOCKED`；禁止自动恢复** |

### A.12.3 重试规则

| 规则 | 内容 |
|---|---|
| R-1 | 允许多个 `BEGIN(RECOVERY)` 并存，必须形成链：`#r2.supersedes_recovery_op_id = #r1` |
| R-2 | 一次 `RECOVERED` 可解决多个 op（含链上所有未解决 RECOVERY op 与未解决 WRITE op） |
| R-3 | `RECOVERY_REQUIRED` 下恢复是唯一允许的内容写操作（T4 只改检查点；T5 只写 `MANUAL_RESET`，不改目标）；WRITE 一律禁止 |
| R-4 | 恢复必须幂等：从同一 `SNAPSHOT_VALID` 覆盖到 B 可重复执行 |
| R-5 | 每次恢复尝试必须有独立 `BEGIN(RECOVERY)`。**成功** → `RECOVERED`（终态）；**失败** → `FAILED`（**非终态**）且 op **保持 `OP_UNRESOLVED`**。禁止写 `ABORTED`、禁止伪造 `RECOVERED` |
| R-6 | 不得进入 `READY`：`RECOVERY_VERIFIED` 未通过 / `consistency_check` false / 三集合关系不满足 / 检查点非 `VERIFIED` / 身份未 `IDENTITY_VERIFIED` |

## A.13 恢复验证与重做验证

| 判定 | 对象 | 内容 |
|---|---|---|
| `RECOVERY_VERIFIED_BYTES` | 恢复后字节 | 快照身份现场重算通过；全文件 SHA-256 == B；`RECOVERED` 字段与实测一致；三集合关系正确；检查点 `VERIFIED`；身份 `IDENTITY_VERIFIED`；`target_persisted` 与 `readback_verified` 均为 true |
| `RECOVERY_VERIFIED_OBJECT` | 可解析性 | 读取器可枚举对象；`inventory_digest` == 对照运行记录（同读取器版本） |
| `REDO_VERIFIED` | 独立副本 | 重做后全文件 SHA-256 == A；四项一致性前提满足 |

| 情形 | BYTES | OBJECT | 用例判定 |
|---|---|---|---|
| 字节一致 + 对象一致 | PASS | PASS | 通过 |
| 字节一致 + 对象不可解析 | PASS | FAIL | 失败 |
| 字节一致 + 读取器不可用 | PASS | **UNVERIFIED** | 部分通过，不计入通过 |
| 字节不一致 | FAIL | 不评估 | 失败 |
| 合成目标 | PASS/FAIL | **N/A** | 不得记 PASS 或 UNVERIFIED |

`OBJECT = UNVERIFIED` 证据要求：读取器名称与版本、Python 版本、异常类型与原文、区分"夹具/依赖限制"vs"数据问题"、声明结论仅限字节层。

`REDO_VERIFIED` 前提：`RECOVERY_VERIFIED_BYTES == PASS`；独立副本；载荷哈希、`args_digest`、`tool_sha256`、`deps` 四项一致。任一不满足 → 标"未验证"。

## A.14 实现定义

### A.14.1 `inventory_digest`

| 项 | 规定 |
|---|---|
| 来源 | 读取器枚举的 `(path_id: int, class_name: str)` |
| 排序 | `path_id` 升序；相同则按 `class_name` UTF-8 字节序 |
| 每项编码 | `f"{path_id}\t{class_name}"` |
| 连接 | `"\n"` 连接，末尾不加换行；UTF-8 无 BOM |
| 摘要 | SHA-256 小写十六进制 |
| 记录字段 | `{algorithm, count, path_id_min, path_id_max, digest, reader_name, reader_version}` |
| 可比性 | 仅同一读取器版本内可比；版本不同标 `INCOMPARABLE` |
| 空集 | `sha256(b"")` = `e3b0c442…b855`，`count == 0` |

### A.14.2 `tool_sha256` 与 `deps`

| 项 | `tool_sha256` | `deps` |
|---|---|---|
| 来源 | 执行写入的脚本字节；多文件按 `relpath` 排序后聚合再算 SHA-256 | `importlib.metadata.version()` / `__version__`：python / unitypy / pillow / numpy |
| 记录时点 | 进程启动时计算，写入 `BEGIN.tool_sha256` | 同上 |
| 验证 | 重做前重算并与对照运行比对，不等即 `REDO_VERIFIED` 不可执行 | 同上 |
| **当前状态** | **机制尚未实现** | 同上 |
| 后果 | 涉及重做的用例只能标 **"未验证"** | 同上 |

**受影响用例（8 条）**：S2、S3a、S3b、S3c、S7c-1、S7c-2、S7d、S8g。

### A.14.3 T2 签核记录

**位置**：`%TEMP%\ggc_p1\signoffs\<target_key>.<ts>.json`（生产为 `F:\GGC_snapshots\signoffs\`）。

```json
{
  "signoff_id": "uuid",
  "target_norm": "...", "target_key": "...", "wal_file": "...",
  "repair_intent_id": "...", "evidence_path": "...",
  "repaired_bytes": 0, "repaired_lines": 0, "torn_tail_hex_prefix": "...",
  "recomputed_snapshot_sha256": "...", "observed_target_sha256": "...",
  "checkpoint_status": "VERIFIED",
  "wal_identity_status": "IDENTITY_VERIFIED",
  "failure_log_status": "FAIL_READABLE_EMPTY",
  "prefix_record_count": 0,
  "last_durable_record_seq": 0,
  "wal_prefix_sha256": "...",
  "t2_conditions": {"T2-1": true, "T2-2": true, "T2-3": true,
                    "T2-4": true, "T2-5": true, "T2-6": true},
  "wal_state_digest_at_signoff": "...",
  "operator": "...", "ts_wall": "...", "tool_sha256": "...",
  "statement": "本次解除依赖已丢弃的日志字节，我接受该判断不可由机器复核。"
}
```

`t2_conditions` 只列 T2-1…T2-6；T2-7 由"文件存在 + `wal_state_digest_at_signoff` 与当前一致"满足。

**缺失与不一致处理**：签核不存在 / 任一条件 false / `statement` 缺失或措辞不符 / 摘要 ≠ 当前 / `signoff_id` 复用 / `observed_target_sha256` ≠ 当前 / `checkpoint_status` ≠ `VERIFIED` / `wal_identity_status` ≠ `IDENTITY_VERIFIED` → **T2 不适用**，保持原状态，不自动重试。

### A.14.4 T5 签核记录（v7 新增）

**位置**：`signoffs\<target_key>.<ts>.manual.json`。

```json
{
  "signoff_id": "uuid",
  "scope": "MANUAL_RESET",
  "target_norm": "...", "target_key": "...", "wal_file": "...",
  "override_reason": "IDENTITY_MISMATCH | FAIL_CORRUPT | CHECKPOINT_INCONSISTENT | ...",
  "overridden_status": {"checkpoint_status": "...", "wal_identity_status": "...",
                        "failure_log_status": "...", "fault_class": "FRC-..."},
  "state_digest_at_override": "...",
  "observed_target_sha256": "...",
  "unresolved_set_empty": true,
  "mp1_evidence_ref": "wal_evidence\\<key>.<ts>.manual_investigation.json",
  "mp1_evidence_sha256": "...",
  "target_sha256_confirmed_by_human": "...",
  "manual_epoch_id": "uuid",
  "checkpoint_rebuild_authorized": true,
  "operator": "...", "ts_wall": "...", "tool_sha256": "...",
  "statement": "我已知悉该 target 的持久化状态不可由机器判定；本次重置仅重建状态记录，不修复任何数据，且不会使该 target 恢复为已验证状态。"
}
```

**前提（v8 强化）**：① `unresolved_set_empty == true`（存在未解决 op 时 T5 非法，唯一出口是保持 `MANUAL_BLOCKED`，A.7.9.3）；② `mp1_evidence_ref` 指向的文件存在且哈希匹配（MP-1 已完成）；③ `target_sha256_confirmed_by_human` 与现场实测一致；④ `checkpoint_rebuild_authorized == true` 且 `manual_epoch_id` 唯一；⑤ **（v8.2，R16）`fault_class ∈ {FRC-CHECKPOINT, FRC-FAILURELOG, FRC-STRUCTURAL}` 且 `wal_identity_status == IDENTITY_VERIFIED`**（A.5.10 CR-6 两轴表）——身份类或 `FRC-UNKNOWN` 的签核**一律无效**，不得作为 `CP-R` 的授权。

**缺失处理**：签核不存在 / `unresolved_set_empty` 为 false / **缺 `mp1_evidence_ref` 或其哈希不符** / `target_sha256_confirmed_by_human` ≠ 实测 / `state_digest_at_override` ≠ 当前 / `signoff_id` 复用 / `manual_epoch_id` 复用 / **（v8.2）`fault_class` 缺失或属身份类或为 `FRC-UNKNOWN`** → **T5 不可执行**，状态保持 `MANUAL_BLOCKED`。

**执行后状态（v8）**：签核有效**只**授权写 `MANUAL_RESET` 与执行 `CP-R`；**不**授权进入 `READY`。`READY` 只能由阶段 C 的重新扫描给出（A.7.3 T5 行）。

## A.15 故障路径交叉核对表

**通用前提**：不得假设 `write()` 或 `fsync()` 失败意味着数据一定在盘上或一定不在盘上；失败只能推出"持久性未知"。

| # | 故障点 | 可能持久化的证据 | 重启扫描结果 | 允许的下一步 | 禁止的动作 | 预期运行状态 |
|---|---|---|---|---|---|---|
| 1 | 快照发布中途失败 | 半截 `.tmp`；内容已发布无 sidecar；三方不一致 | 无条目 / `SNAPSHOT_NO_SIDECAR` / `SNAPSHOT_CORRUPT` | 保留证据；本次写入终止；释放锁 | 删除 tmp/内容；用无 sidecar 快照恢复；重写 sidecar 覆盖 | `READY`（无 `BEGIN`，目标未触碰） |
| 2 | WAL 尾部修复中途失败 | `REPAIR_INTENT` / `REPAIR_DONE`；`wal_evidence`；`REPAIR` 记录；检查点 | 见 A.6.4 | 按 A.6.4 对应行继续 | 再次截断；猜边界；删证据；无 INTENT 就截断；未确认持久化就写 `REPAIR_DONE` | 完成或可继续 → 继续扫描；否则 `RECOVERY_REQUIRED` / `MANUAL_BLOCKED` |
| 3 | WAL 持久化失败（日志可写） | 主 WAL 可见记录；检查点未推进；`wal_failures` 有 `FAILED` | `PROVISIONAL`；`FAIL_READABLE_WITH_RECORDS`；`NO` | 有未解决 op → **T1**；无 → **T4** | 一律导向 T2；假定已落盘；截断回滚 | `RECOVERY_REQUIRED` |
| 4 | **WAL 持久化失败（日志不可写）** | 主 WAL 可见；检查点未推进；`wal_failures` 缺失/不可读 | `PROVISIONAL`；`FAIL_ABSENT_INCONSISTENT` / `FAIL_UNREADABLE`；`UNKNOWN` | **`T5*`（两阶段，A.7.9）**；`OP_UNRESOLVED != ∅` 时**无出口**，只能保持 `MANUAL_BLOCKED` | T1；T2；T4；任何写入；用"检查点已验证"替代故障证据 | **`MANUAL_BLOCKED`** |
| 5 | WRITE 中途崩溃 | `BEGIN(WRITE)` 无终态；目标部分内容 | `OP_UNRESOLVED`；目标哈希 ∉ {B, A} | T1 | 继续写；跳过该 target；用大小判成功 | `RECOVERY_REQUIRED` |
| 6 | RECOVERY 中途崩溃 | `BEGIN(RECOVERY)` 无终态；目标部分恢复 | `OP_UNRESOLVED`（可能多条链） | `#r2`（`supersedes=#r1`），幂等重做 | 判断恢复到哪一步；伪造 `RECOVERED`；写 `ABORTED` | `RECOVERY_REQUIRED` |
| 7 | 连续多次 RECOVERY 失败后重启 | 多个 `BEGIN(RECOVERY)` 无终态；多个 `FAILED` | 未解决集合 = 全部未终结 op | `#rn` 覆盖**全部**未解决 op；或人工 | 只解决最后一个；遗漏链上 op；把 `FAILED` 当终态 | `RECOVERY_REQUIRED`，直至 `#rn` 成功 |
| 8 | 快照与 WAL 状态不一致 | `BEGIN.snapshot_sha256` 与现存快照不符；`SNAPSHOT_ORPHAN` | 快照不可用 | 生成 `CURRENT_STATE`（标注非 B）；人工报告 | 用不符快照恢复；删孤立快照；把 `CURRENT_STATE` 当 B | `RECOVERY_REQUIRED` + 人工 |
| 9 | 检查点与 WAL 不一致 | V-1…V-6 失败；WAL 短于 marker；末条不符；前缀哈希不符 | `INCONSISTENT` → `UNKNOWN` | **`T5*`（两阶段）**；`CP-R` 只能在 `MANUAL_RESET` 持久后执行；`OP_UNRESOLVED != ∅` 或 `FAULT_CLASS` 不在允许集合 → **无出口** | **无 `MANUAL_RESET` 就重写检查点**；T1；T2；T4；任何写入 | **`MANUAL_BLOCKED`** |
| **10（v7，v8.1 修正）** | **WAL 文件身份变化** | 前缀哈希相同但 `st_ino` / `file_index` / `creation_time` 不同；或句柄视图与路径视图矛盾 | `IDENTITY_MISMATCH` / `IDENTITY_UNVERIFIABLE` → `INCONSISTENT` → `UNKNOWN` | **无文档化出口**（v8.2 按 `FAULT_CLASS` 重述）：`FAULT_CLASS ∈ {FRC-IDENTITY_MISMATCH, FRC-IDENTITY_UNAVAILABLE}` → `CR-6` 两轴表禁止 `CP-R` → T5 阶段 B 无法完成，T5 **不可执行**；只能保持 `MANUAL_BLOCKED`，待 BLK-1 决策 | 自动推进检查点；T1；T2；T4；**T5**；任何写入；择一采信冲突视图；**宣称"可通过人工签核恢复"** | **`MANUAL_BLOCKED`（无出口）** |
| **11（v7）** | **故障日志不可用** | `wal_failures` 缺失/不可读/损坏；WAL 有无法解释的 `PROVISIONAL` | `FAIL_UNREADABLE` / `FAIL_CORRUPT` / `FAIL_ABSENT_INCONSISTENT` → `UNKNOWN` | **`T5*`（两阶段）** | T1；T2；T4；用检查点 `VERIFIED` 替代缺失证据 | **`MANUAL_BLOCKED`** |
| **12（v7）** | **目标持久化 / 回读 / 提交前复检失败**（阶段 ①：`END` 未开始） | `BEGIN` 无终态；目标内容可能是 A 但持久性未知；**可证明无 `END`** | `OP_UNRESOLVED` | T1 | 写 `END`；宣告成功；跳过 ST-9/10/11 | `RECOVERY_REQUIRED` |
| **13（v8）** | **`END` 写入或 `fsync` 失败（阶段 ②：持久性未知）** | `BEGIN` 无终态；`FAILED{stage:end_write\|end_fsync}`；磁盘上 `END` 可能完整/残行/不存在 | `OP_UNRESOLVED`；`END` 完整性不可判定 | `RECOVERY_REQUIRED` + **重新扫描**；残行按 A.6 修复后再判定 | **自动重写 `END`**；直接 T1 而不重扫；宣告成功 | `RECOVERY_REQUIRED` |
| **14（v8）** | **快照发布同名冲突** | 半截 tmp；既有同名内容文件与 sidecar 完好 | `SNAPSHOT_CONFLICT` | 本次写入终止；保留全部文件；人工按 A.11.3 判定 | 覆盖；删除；自动改名；用冲突快照恢复 | `READY`（无 `BEGIN`，目标未触碰） |

**表的使用规则**：本表是设计判定表，不是执行记录。每一条的实际结果须由对应用例产出；未产出即"未验证"。

**（v8.2）三点补充**：① 表中 `T5*` 一律按 A.7.6 的统一规则读——**四条硬前提全部成立才可执行**，否则保持 `MANUAL_BLOCKED`；**（v8.3，N-04）本表所有 `T5*` 行的"预期运行状态"均为 `MANUAL_BLOCKED`，与"T5 的唯一起点是 `MANUAL_BLOCKED`"一致**；② `FAULT_CLASS == FRC-UNKNOWN` 的处置与第 10 行**同构**（无出口、保持阻塞、补足派生输入后重新扫描）；③ 本表"允许的下一步"列**不是**授权，实际准入见 A.7.10。

## A.16 夹具与注入

### A.16.1 目标集

| ID | 来源 | 大小 | 载荷范围 |
|---|---|---|---|
| `T-1K` | 合成（固定种子） | 1 KB | 全文件 |
| `T-1M` | 合成 | 1 MiB | 全文件 |
| `T-1M-P` | 合成 | 1 MiB | `[256 KiB, 768 KiB)` |
| `T-64M` | 合成 | 64 MiB | 全文件 |
| `T-REAL` | 只读复制 `sharedassets3.assets`（L0-A，只读） | 4,104 B | 全文件 |

种子存 `seeds\`（只读）；所有副本从种子复制，绝不从已写入过的文件复制。**不使用 L0-D 的三个 `roundtrip_*.assets` 作为任何测试目标或种子。**

### A.16.2 注入手段（v7 新增 M11）

| 手段 | 能证明 | 不能证明 |
|---|---|---|
| M1 步骤级抛异常 | 应用层该步错误处理 | 任何 OS 持久化行为 |
| M2 短写 | 应用层对未写满的检测 | 真实磁盘满的 errno 语义 |
| M3 合成 errno 28 | 错误分类与分支 | 真实 ENOSPC 返回点 |
| M4 `os._exit(9)` | 进程终止后的可观察状态 | 掉电持久性 |
| M5 缓冲未刷新 | — | `buffering=0`，不适用 |
| M6 持久化替身 | 逻辑层对"完整 END 不存在"的判定 | 真实掉电后磁盘状态 |
| M7 真实掉电/强制关机 | — | **未覆盖** |
| M8 状态直接构造 | 系统对指定状态的判定逻辑 | 该状态如何自然产生 |
| M9 屏障注入 | 在 H1–H6 精确定点让外部进程写入 | 不能证明系统能检测该写入 |
| M10 检查点篡改 | 系统对 `INCONSISTENT` 的判定与阻断 | 真实外部篡改的动机与范围 |
| **M11 文件身份替换 / 故障日志破坏** | 系统对 `IDENTITY_*` 与 `FAIL_*` 的判定与阻断 | 真实攻击者能力；身份字段本身不可伪造 |

`injection_kind`：`FAULT_INJECTED`（M1–M4、M6、M9）/ `STATE_CONSTRUCTED`（M8、M10、M11）。

## A.17 场景 S0–S15（106 条）

> **v8 变更**：新增 S15（人工两阶段，5 条）；S1 +3（S1f/S1g/S1h 同名冲突）；S13 +3（S13d/S13e/S13f 覆盖 `END` 四阶段）；S14 +2（S14g/S14h 覆盖组合 #5a 与身份矛盾）。合计 **89** 条。
>
> **v8.1 变更（仅 P0 修复）**：S1 **+2**（**S1i** 目标已存在 → `SNAPSHOT_CONFLICT`；**S1j** `os.link` 返回 `EXDEV` → `SNAPSHOT_PUBLISH_UNSUPPORTED`，M4）；S10 **+1**（**S10e** 检查点已存在时执行 `CP-R`，M3）；S14 **+1**（**S14i** WAL 与检查点均不存在但 `wal_evidence` 存在 → 不得判干净，M6）；S15 **+1**（**S15f** 身份不匹配且完整签核 → 拒绝 `CP-R`，M2）。合计 **94** 条。

### S0 路径安全与保护分类（6 条）

S0a 词法｜S0b 重解析点内外｜S0c 句柄身份替换 + `st_ino==0`｜S0d 零副作用｜S0e 硬链接 `st_nlink>1`｜S0f 静态保护分类断言（仅读清单与台账，不访问任何 `.assets`，断言 34 个文件各归一个级别、3 个 `roundtrip` 归 L0-D / `DECOY_EMPTY`、无用例清单解析到 L0-A/B/C/D）。

**S0 不覆盖 W2**；W2 由 S5d/S5e 覆盖。

### S1 快照创建失败与发布冲突（**10 条**，v8 扩 3 条；v8.1 扩 2 条）

S1a tmp 写 ENOSPC｜S1b fsync 失败或回读 ≠ B｜S1c **原子"不存在才创建"发布失败**（`os.link` / `CREATE_NEW` 报错，非 `os.replace`）｜S1d 内容已发布但 sidecar 失败｜S1e 三方交叉校验不一致。

**S1f–S1h（v8，R4：同名永不覆盖）**：

| 用例 | 构造 | 期望 |
|---|---|---|
| **S1f** | 最终快照名 `<base>.<sha16>.assets` **已存在**（分支 f1：既有内容哈希相同；f2：哈希不同） | 发布中止 → `SNAPSHOT_CONFLICT`；**不得覆盖**；**不得删除既有文件**；**不得自动改名让位**；无 `BEGIN`；`READY`；目标未被触碰；生成冲突报告（两侧完整 SHA-256 / 大小 / mtime / sidecar） |
| **S1g** | 内容文件可发布，但 sidecar `<base>.<sha16>.json` **已存在** | 同上 → `SNAPSHOT_CONFLICT`；**不得覆盖 sidecar**；内容文件保留但整体不可用（无匹配 sidecar 不算 `SNAPSHOT_VALID`） |
| **S1h** | **并发发布竞争**：两个进程同时发布同一最终名（钩子：预检后、原子创建前） | **恰好一个成功**；失败方必须得到 `FileExistsError` / `ERROR_FILE_EXISTS` → `SNAPSHOT_CONFLICT`；**失败方不得删除或覆盖成功方文件**；最终目录中该名字只有一份，且其哈希 == 成功方内容 |

**S1i–S1j（v8.1，M4：区分"目标已存在"与"发布机制不支持"）**：

| 用例 | 构造 | 期望 |
|---|---|---|
| **S1i** | 最终快照名 `<base>.<sha16>.assets` **已存在**（内容任意，含 0 字节）；发布走 `MoveFileExW(tmp, final, 0)` → 返回 `FALSE` / `ERROR_ALREADY_EXISTS` | `SNAPSHOT_CONFLICT`；断言：① 既有文件**逐字节不变**（完整 SHA-256 与构造前相同）；② tmp 保留；③ **不得**生成 `SNAPSHOT_PUBLISH_UNSUPPORTED`；④ 无 `BEGIN`；`READY`；`WRITE_PERMITTED == NO` |
| **S1j** | `os.link(tmp, final)` 被桩替换为返回 `OSError(EXDEV)`（模拟跨卷）；目标名**不存在** | `SNAPSHOT_PUBLISH_UNSUPPORTED`；断言：① **不得**判 `SNAPSHOT_CONFLICT`；② **不得**生成"同名冲突报告"（不存在冲突方）；③ tmp 保留；④ **不得**回退到 `os.replace` 或"先删后建"；⑤ 无 `BEGIN`；`READY`；该用例记 `UNCOVERED` |

**全部 S1**：无 `BEGIN`；`READY`；目标 == B；残留物保留并标注。**任何覆盖行为 → 判失败**（即使最终哈希正确）。

### S2 写入中途崩溃（1 条）

| 项 | 内容 |
|---|---|
| 前状态 | `T-64M`；`SNAPSHOT_VALID`；`BEGIN(WRITE)` 已 fsync + 检查点已推进；`LockFileEx` 已持有；目标 == B |
| 钩子 | **H3**，`k = 19`（第 19 块写完、第 20 块未开始） |
| 偏移 | `inject_offset = 19 × 1 MiB = 19,922,944` |
| 注入 | `os._exit(9)` |
| 证据（4 条） | ① `target[0:19,922,944] == payload[0:19,922,944]` ② `target[19,922,944:] == B[19,922,944:]` ③ 大小 == B 的大小 ④ 全文件哈希 ∉ {B, A} |
| 状态 | `OP_UNRESOLVED` → `RECOVERY_REQUIRED` |
| 后续 | T1 恢复；独立副本 `REDO_VERIFIED`（**当前标"未验证"**） |

### S3 END 不存在（3 条）

S3a M8（BEGIN 无 END、目标 == A）｜S3b M8（末尾残行，须先按 A.6 修复；修复后若无未解决 op 且检查点 `VERIFIED` 且身份 `IDENTITY_VERIFIED` → 评估 T2；否则走 T1）｜S3c M6（sink 模拟 END 未持久化）。

核心：不得因"目标 == A"推断已完成。

### S4 快照缺失/损坏（4 条）

S4a 删内容｜S4b 篡改内容｜S4c sidecar 缺失/篡改｜S4d 快照与目标双双被改。

全部：保持 `RECOVERY_REQUIRED`；生成 `CURRENT_STATE`（标注非 B）；人工报告。

### S5 外部并发（**8 条**，v8 按 A.8.1.1 重排 S5b-1 / S5b-2）

| 用例 | 钩子 | 外部写入 | 相对写游标（A.8.1.1） | 最终哈希 | 期望 |
|---|---|---|---|---|---|
| S5a | H1 | `T-1M`：`[1024, 5120)` | 尚未开始写 | ≠ B | 复检失败 → **不得写 `ABORTED`**，写 `FAILED{stage:recheck}` → `OP_UNRESOLVED` → `RECOVERY_REQUIRED` |
| **S5b-1** | **H3（k=32）** | `T-64M`：`[40 MiB+1024, +4096)` = `[41,944,064, 41,948,160)` | **写游标之后**（游标 `cur = 32 MiB = 33,554,432`；`off > cur` → 未写区） | **== A**（块 40 会整体覆盖该区间） | **写时不可检出**；**必须声明为未检出**；若实现声称"已检出"→ 判失败；若实现另有逐块回读机制则须在报告中单列，不得计入本用例的检出 |
| **S5b-2** | **H3（k=48）** | `T-64M`：`[40 MiB+1024, +4096)` = `[41,944,064, 41,948,160)` | **写游标之前**（游标 `cur = 48 MiB = 50,331,648`；`off+4096 <= cur` → 已完成前缀；块 48–63 不再触碰该区） | **≠ A** | **必须检出**（ST-10 / ST-11 全文件哈希）；声称"不可检出"→ 判失败 |
| S5c | H4 | `T-1M`：`[1024, 5120)` | 全部写完、未持久化 | ≠ A | **必须检出**（ST-9 之后的 ST-10 回读会看到外部字节） |
| S5d | H2 | `T-1M-P`：`[0, 1024)` | **载荷范围之外** | **≠ A** | **必须检出** |
| S5e | H2 | `T-1M-P`：`[512 KiB, 512 KiB+1024)` | **载荷范围之内**，被覆盖 | **== A** | **写时不可检出**；须声明 |
| **S5f** | **H5** | `T-1M`：`[1024, 5120)` | 已回读通过、未写 END | ≠ A | **必须检出**：ST-11 提交前复检发现 ≠ A → `FAILED{stage:precommit_recheck}` → `OP_UNRESOLVED` → `RECOVERY_REQUIRED`；**禁止写 `END`** |
| **S5g** | **H6** | `T-1M`：`[1024, 5120)` | 提交前复检通过、END 未写 | **写时 == A，之后 ≠ A** | **写时不可检出**；但**下次扫描的 V-T 必须检出**（目标 ≠ `END.target_sha256_after`）→ `RECOVERY_REQUIRED`；若实现未做 V-T → 判失败 |

**S5b-1 / S5b-2 前置断言（v8 强化）**：外部字节固定 `0xAB × 4096`；夹具必须断言 ① `payload[off:off+4096] != 0xAB×4096`；② `B[off:off+4096] != 0xAB×4096`；③ **helper 回读 `target[off:off+4096] == 0xAB×4096`**（证明外部写入确实落地，而不是被 helper 自己吞掉）；④ 释放屏障后我方线程确实继续写完剩余块（日志记录最后一块的完成时刻）。

**S5b-1 / S5b-2 方向重排说明（v8）**：v7 把 `k=32` 与 `4 MiB` 标为"写游标之后"、把 `k=32` 与 `40 MiB` 标为"写游标之前"，与 A.8.1.1 的模型**方向相反**（`k=32` 时已完成前缀只到 32 MiB）。v8 按模型重排：`k=32` + `40 MiB` = 未写区（不可检出），`k=48` + `40 MiB` = 已完成前缀（必须检出）。**结论互换，不是新增覆盖**。

**S5 统一规则**：检出 → 进入/保持 `RECOVERY_REQUIRED`，禁止自动回滚/重试/解除/跳目标；哈希、mtime、锁状态、屏障日志仅为辅助证据；`∈{B,A}` 不能证明未被外部修改；**不得声称哈希可以发现所有第三方写入**（**S5b-1**、S5e 为写时反例；S5g 依赖 V-T 延迟检出）；无对应钩子 → `UNCOVERED`。

**统计口径（v8）**：**不得把不可检测场景算作成功检出**。S5 的 8 条中，**必须检出 = 5 条**（S5a、S5b-2、S5c、S5d、S5f），**写时不可检出 = 3 条**（S5b-1、S5e、S5g）。不可检出项必须显式声明，且 S5g 只在 V-T 生效时才算"延迟检出"。

### S6 锁（5 条）

S6a pid 存活｜S6b pid 已死残留｜S6c 锁损坏｜S6d 锁目录缺失｜S6e 锁被占用（含 `LockFileEx` 获取失败）。

WAL 无变化；`READY`。禁止自动删锁、降级无锁、时间阈值判死、损坏锁视为无锁、先 `BEGIN` 后取锁。

### S7 磁盘/持久化失败（**11 条**，v7 加 S7h；v8.2 加 S7i / S7j）

| 用例 | 类别 | 期望 |
|---|---|---|
| S7a | 类1 快照创建失败 | 无 `BEGIN`；`READY`；不需人工 |
| S7b | 类2 `BEGIN` 持久化失败 | 按 A.7.6 四分支（b1–b4）；**目标 == B 不单独放行** |
| S7c-1 | 类3 写入 ENOSPC | `BEGIN` 无终态 → T1 |
| S7c-2 | 类3 **短写**（大小不变） | `BEGIN` 无终态 → T1；唯一拦截手段是写后全文件 SHA-256 |
| S7d | 类3 END 失败 | `BEGIN` 无终态 → T1 |
| S7e | fsync 失败 **且** `wal_failures` 不可写 | `FAIL_ABSENT_INCONSISTENT` → `UNKNOWN` → **`MANUAL_BLOCKED`；`T5*`**（v7 收紧；v8.2 标前置条件：`OP_UNRESOLVED == ∅` 才可执行，e1 分支实际无出口） |
| S7f | `.durable` 缺失/损坏/回退 | f1/f2 → `UNKNOWN` → **`T5*`**（须 `OP_UNRESOLVED == ∅`）；f3 → `NO` → T1/T4 |
| S7g | `PROVISIONAL` 且无未解决 op | `NO` → **T4** → `YES` → `READY`；断言 T4 不写 WAL 记录、不改目标 |
| **S7h** | fsync 失败 **但** `wal_failures` 可写且含对应 `FAILED` | `FAIL_READABLE_WITH_RECORDS` → `NO`；h1 有未解决 op → T1；h2 无 → T4 |
| **S7i（v8.2，R14）** | 任一 `T5*` 分支 + `OP_UNRESOLVED != ∅` | `UNKNOWN` → **`MANUAL_BLOCKED`，无出口**；断言：① 不写 `MANUAL_RESET`；② 不执行 `CP-R`；③ 不出现 `BEGIN(MANUAL)`；④ 表格中的 `T5*` **未被**当作授权 |
| **S7j（v8.2，R15）** | `T4` 成功 → 重扫 `wal_failures` 发现新增不可解析行 | `T4` 成功只把运行状态推到 `READY`；PR-1 重扫得 `FAIL_CORRUPT` → `UNKNOWN` → **`MANUAL_BLOCKED`**；断言：① 不得沿用 `T4` 之前的 `FAILURE_LOG_STATUS`；② `WRITE_PERMITTED == NO`；③ 不得因"`T4` 已成功"继续载荷写入 |

**三类故障不混同**：类1（快照失败）/ 类2（`BEGIN` 失败）/ 类3（目标已写）。

### S8 恢复关联与恢复崩溃（7 条）

S8a M4 恢复中途崩溃｜S8b M8 目标 == B、`RECOVERED` 缺失（**T2 不适用**，走 `#r2` + `resolves=[#1,#r1]`）｜S8c 恢复期间快照失效｜S8d 恢复后一致性检查失败｜S8e `resolves` 遗漏 → 仍保持｜S8f `resolves` 含已终结 op → 一致性失败 + 人工｜S8g 恢复链成功 → `READY`，历史完整、无伪造记录。

### S9 WAL 尾部修复（**9 条**，v7 加 S9g；v8.2 加 S9h / S9i）

| 用例 | 崩溃点 | 持久证据 | 期望 |
|---|---|---|---|
| S9a | RP-3 之前 | 可能有证据文件，无 INTENT | 未开始；允许重做；主 WAL 原样；证据不覆盖；`RECOVERY_REQUIRED` |
| S9b | RP-3 之后、RP-4 之前 | INTENT 无 DONE；大小 == `wal_size_before`；tail 哈希匹配 | 从 RP-4 继续 |
| S9c | RP-4 之后、RP-6a 之前 | INTENT 无 DONE；大小 == `tail_offset`；无 `REPAIR` | 从 RP-6a 继续；不得重复截断 |
| S9d | 截断到中间值 | 大小非两端值 | **边界不可确定** → `RECOVERY_REQUIRED` + 人工 |
| S9e | RP-6a 之后、RP-6b 之前 | `REPAIR` 可见；检查点未覆盖 | `PROVISIONAL`；**禁止 `REPAIR_DONE`**；`VERIFIED` → 先完成 RP-6b；否则 `MANUAL_BLOCKED` |
| S9f | `REPAIR` 损坏或字段不一致 | 行不可解析 / 字段缺失 / seq 非单调 / `repair_intent_id` 不匹配 | 隔离；`UNKNOWN`；禁止 `REPAIR_DONE`；禁止再次修复；**`MANUAL_BLOCKED`** |
| **S9g（v7）** | **RP-4b 检测到 WAL 身份变化** | INTENT 无 DONE；身份 ≠ `wal_identity_before` | **`MANUAL_BLOCKED`**；禁止任何后续修复步骤；证据保留 |

| **S9h（v8.2，R18）** | 平台 / 实现不支持同句柄截断（只能按路径截断，或 `ftruncate` 不可用） | INTENT 存在、无 DONE；主 WAL 原样 | **不截断**；`MANUAL_BLOCKED`；断言：① WAL 大小仍 == `wal_size_before`；② **未调用** `os.truncate(path, ...)`；③ INTENT 与证据保留；④ 不得"降级为路径截断 + 事后复核" |
| **S9i（v8.2，R18）** | RP-4a 前置不成立：句柄已关闭 / `fstat` 大小 ≠ `wal_size_before` / 非独占写者 | INTENT 存在、无 DONE | **不截断**；`MANUAL_BLOCKED`；断言：① 未发生任何截断调用；② 不得关闭后重开句柄再截断；③ 证据保留 |

> S9 条数：v7 由 6 条扩为 **7 条**（新增 S9g）；v8.2 再扩为 **9 条**（新增 S9h / S9i）。上表 9 行。

### S10 检查点一致性（**11 条**，v8.1 加 S10e；v8.2 加 S10f / S10g / S10h；v8.3 加 S10i / S10j / S10k）

| 用例 | 注入 | 构造状态 | 期望 |
|---|---|---|---|
| S10a | M10 篡改 `wal_prefix_sha256` | 字段自洽但前缀哈希不符 | V-2 失败 → `INCONSISTENT` → `UNKNOWN` → **`T5*`**（`FRC-CHECKPOINT`；须 `OP_UNRESOLVED == ∅`） |
| S10b | M10 截断 WAL 短于 marker | WAL 被外部截断 | V-1 失败 → `INCONSISTENT` → `UNKNOWN` → **`T5*`**（同上） |
| S10c | M10 删除 WAL 保留检查点 / 反向 | 二者之一缺失 | `INCONSISTENT` / `ABSENT_DIRTY` → `UNKNOWN` → **`T5*`**（同上；`ABSENT_DIRTY` + 未解决 op → 无出口） |
| S10d | M4 在 CP-5 期间崩溃（tmp 已写、replace 未完成） | 旧检查点仍有效 | `VERIFIED` → 新记录 `PROVISIONAL` → `NO` → T1/T4；**不得因 tmp 存在而采信 tmp** |
| **S10e（v8.1，M3）** | M8：检查点已存在且为 `INCONSISTENT`；完整 MP-1 证据 + MP-2 签核 + `MANUAL_RESET` 已持久 → 执行 `CP-R` | 走 CR-e **情形 2** | `CHECKPOINT_STATUS == VERIFIED_MANUAL`；`manual_epoch != null`；断言：① 旧检查点被改名为 `<key>.durable.json.pre_manual.<manual_epoch_id>`，**内容可回读且完整 SHA-256 与改名前的记录一致**；② 新检查点 `pre_rebuild_checkpoint_status == "INCONSISTENT"`、`pre_rebuild_checkpoint_sha256` 与 ① 一致；③ **未使用** `os.replace` / `MoveFileEx(REPLACE_EXISTING)`；④ 目录中旧代文件**仍存在**（未被删除、未被覆盖）；⑤ 再执行一次 `CP-R` 必须使用**新的** `manual_epoch_id`（禁止复用） |

| **S10f（v8.2，R16）** | M11：构造 `st_ino == 0` 且无 `file_index`（`IDENTITY_UNVERIFIABLE`），其余 CR-1…CR-5 全部满足 | `FAULT_CLASS == FRC-IDENTITY_UNAVAILABLE`（F4） | `CP-R` **必须被拒绝**；断言：① 不写 `.durable.json.tmp`；② `CHECKPOINT_STATUS` 保持 `INCONSISTENT`；③ 不生成 `VERIFIED_MANUAL`；④ 不得因"签核齐全"而执行 |
| **S10g（v8.2，R16）** | 构造派生输入互相矛盾（V-1b 报不一致而 `st_ino == 0`） | `FAULT_CLASS == FRC-UNKNOWN`（A.2.3 第 3 条 + 矛盾降级） | `CP-R` **必须被拒绝**；`MANUAL_BLOCKED` 且**无出口**；断言：① 不得人工指定 `FAULT_CLASS`；② 不得"择一采信"任一派生输入；③ 不写任何检查点 |
| **S10h（v8.2，R13）** | 构造"`CHECKPOINT_STATUS == INCONSISTENT` + `FAIL_READABLE_WITH_RECORDS` + 存在未解决 op" | `UNKNOWN` 与 `NO` 的条件**同时**成立 | **必须判 `UNKNOWN`**（判 1 先于 判 2）；断言：① 不得判 `NO`；② 不得走 T1/T4；③ `WRITE_PERMITTED == NO` |
| **S10i（v8.3，N-01）** | M4：正常推进时在 **CP-5b 完成、CP-5c 之前**崩溃（旧代已改名为 `pre_advance.*`，新代未发布） | 磁盘上只有 `pre_advance.*` 与 tmp | **`ABSENT_DIRTY`** → `UNKNOWN` → `MANUAL_BLOCKED`；断言：① **不得**自动把 `pre_advance.*` 改回当代名；② **不得**删除或覆盖旧代；③ 不得发布新代；④ 旧代完整 SHA-256 可回读并与崩溃前记录一致；⑤ tmp 不被采用 |
| **S10j（v8.3，N-01）** | 正常载荷写入后的一次完整推进（CP-5a → 5b → 5c → CP-6） | 旧代 `VERIFIED`、无人工印记 | 推进成功；断言：① 旧代以 `pre_advance.<旧 wal_size_at_marker>.<前缀哈希前 8 位>` 存在且**完整哈希 == 新代 `pre_advance_checkpoint_sha256`**；② **未使用** `os.replace` / `MoveFileEx(REPLACE_EXISTING)`；③ `checkpoint_generation` == 旧代 + 1；④ 旧代**仍存在**（未删除）；⑤ 新代发布用的是"目标不存在才创建"语义 |
| **S10k（v8.3，N-01）** | 旧代 `VERIFIED_MANUAL`（`manual_epoch != null`）之上执行一次自动推进 | 人工代 + 自动推进 | 断言：① 新代 `CHECKPOINT_STATUS` **仍为 `VERIFIED_MANUAL`**；② `manual_epoch` **原样携带**（`reset_op_id` / `signoff_id` / `manual_epoch_id` 三者与旧代完全相同）；③ **不得**出现 `CHECKPOINT_STATUS == VERIFIED`；④ T2 仍然拒绝该新代（T2-2 只接受 `VERIFIED`）；⑤ `checkpoint_generation` == 旧代 + 1 |

**S10 核心断言**：任何 `INCONSISTENT` 情形下不得判任何记录为 `DURABLE`，`WAL_STATE_COMPLETE` 必须 `UNKNOWN`，`WRITE_PERMITTED = NO`；**（v8.2）且 `CP-R` 只在 `FAULT_CLASS` 属非身份类且身份已验证时允许**；**（v8.3，N-01）自动推进必须保留旧代且不得覆盖当代检查点；`VERIFIED_MANUAL` 经自动推进不得升格为 `VERIFIED`（S10i / S10j / S10k）**。

### S11 WAL 文件身份（**4 条**，v7 新增）

| 用例 | 注入 | 构造状态 | 期望 |
|---|---|---|---|
| **S11a** | M11：把 WAL 替换为**内容完全相同**的新文件（复制后 `os.replace`） | 前缀哈希仍相等，但 `st_ino` / `file_index` / `creation_time_ns` 改变 | V-1b 失败 → `IDENTITY_MISMATCH` → `INCONSISTENT` → `UNKNOWN` → **`MANUAL_BLOCKED`，无出口**（`FRC-IDENTITY_MISMATCH`，`CR-6` 两轴表禁止 `CP-R`）；**禁止**因"哈希相同"判 `VERIFIED`；**禁止**写成"仅 T5" |
| **S11b** | M11：重命名 WAL 后新建同名空文件 | V-0 通过（存在），身份全变，`creation_time_ns` 晚于检查点 `ts_wall` | 同上；且不得把新文件当作"空态" |
| **S11c** | M11：构造 `st_ino == 0` 且无 `file_index` 的卷/桩 | 身份不可得 | `IDENTITY_UNVERIFIABLE` → `INCONSISTENT` → `UNKNOWN` → **`MANUAL_BLOCKED`，无出口**（`FRC-IDENTITY_UNAVAILABLE`）；不得"降级为只比哈希"；**禁止**写成"仅 T5" |
| **S11d** | M11：CP-2 与 CP-3 之间替换 WAL（句柄仍指旧文件，路径指新文件） | 句柄视图与路径视图矛盾 | `IDENTITY_MISMATCH` → `INCONSISTENT` → `UNKNOWN` → **`MANUAL_BLOCKED`，无出口**（`FRC-IDENTITY_MISMATCH`，F3）；**不得择一采信** |

**S11 核心断言**：任何 `IDENTITY_MISMATCH` / `IDENTITY_UNVERIFIABLE` 情形下，**不得自动推进 durable checkpoint，不得允许新写入**。

### S12 故障日志可用性（**4 条**，v7 新增）

| 用例 | 注入 | 构造状态 | 期望 |
|---|---|---|---|
| **S12a** | M11：`wal_failures` 存在但含不可解析行 | `FAIL_CORRUPT` | `UNKNOWN` → **`MANUAL_BLOCKED`；`T5*`**（须 `OP_UNRESOLVED == ∅`）；禁止 T1/T2/T4 |
| **S12b** | M11：`wal_failures` 被独占打开 / 权限拒绝 | `FAIL_UNREADABLE` | 同上 |
| **S12c** | WAL 干净（全 `DURABLE`、无未解决 op、无结构异常）+ `wal_failures` 缺失 | `FAIL_READABLE_EMPTY`（由 WAL 侧独立证明） | **允许** `YES` → `READY` → 允许写入；断言：不得因为"日志缺失"而误判 `UNKNOWN` |
| **S12d** | WAL 含 `PROVISIONAL` 记录（来自上一次运行）+ `wal_failures` 缺失 | `FAIL_ABSENT_INCONSISTENT` | `UNKNOWN` → **`MANUAL_BLOCKED`；`T5*`**；断言：**不得**因检查点 `VERIFIED` 就判 `NO` |

### S13 `END` 四阶段（**6 条**，v8 由 3 条扩为 6 条）

覆盖 A.8.2 的 `END` 四阶段判定表，**每个阶段至少一条用例**。

| 用例 | 阶段 | 注入 | 构造状态 | 期望 |
|---|---|---|---|---|
| **S13a** | ① `END` 未开始 | M1：ST-9 `os.fsync(目标句柄)` 抛异常 | 目标内容可能已写，持久性未知；**可证明无 `END`** | `FAILED{stage:target_fsync}` → `OP_UNRESOLVED` → `RECOVERY_REQUIRED` → T1；**禁止写 `END`**；断言 `END` 不存在 |
| **S13b** | ① `END` 未开始 | M1：ST-10 回读哈希 ≠ A（注入短写或内容偏移） | 目标内容与预期不符；无 `END` | `FAILED{stage:target_verify}` → `OP_UNRESOLVED` → T1；**禁止写 `END`** |
| **S13c** | ③ `END` 已持久、检查点未推进 | M4：ST-12 写 `END` 并 fsync 成功后、CP 推进前崩溃 | `END` 可解析且字段完整；检查点未覆盖 | `END` 为 `PROVISIONAL`；op `OP_COMMITTED`；`WAL_STATE_COMPLETE == NO` → **T4**；**禁止**视为失败并重写 `END`；T4 后 `END` 转 `DURABLE`，目标哈希不变 |
| **S13d（v8）** | ② `END` 持久性未知 | M1 / M2：ST-12 `write(END)` 短写或抛异常 | 磁盘上 `END` 可能完整 / 残行 / 不存在，**均不可判定** | `FAILED{stage:end_write}` → `OP_UNRESOLVED` → **`RECOVERY_REQUIRED` + 重新扫描**；残行按 A.6 修复后再判定；**禁止自动重写 `END`**；断言：WAL 中**至多一条** `END`（`op_id` 唯一），且不得出现第二条 |
| **S13e（v8）** | ② `END` 持久性未知 | M1：ST-12 `write(END)` 成功但 `fsync(WAL)` 失败 | `END` 可见；持久性未知 | `FAILED{stage:end_fsync}` → `OP_UNRESOLVED` → **`RECOVERY_REQUIRED` + 重新扫描**；**禁止**立即 T4、**禁止**重写 `END`；重扫后若 `END` 完整且检查点未覆盖 → 归入阶段 ③ → 允许 T4；若 `END` 残行 → A.6 |
| **S13f（v8）** | ④ 均已验证 | 无故障（正常路径） | `END` 与检查点均覆盖 | `END` 为 `DURABLE`；op `OP_COMMITTED`；`WAL_STATE_COMPLETE == YES` → `READY`；断言：**不追加任何补偿记录**、**不改写 `END`**、`target_hash_provenance` 与 ST-11 实测逐字一致 |

**S13 核心断言**：① `END.target_persisted` 与 `readback_verified` 必须为 `true`，构造出 `false` 的 `END` → 判失败；② **四个阶段必须可区分**：把阶段 ② 判成阶段 ①（"可证明无 `END`"）或直接判成阶段 ③（`PROVISIONAL` → T4）→ 判失败；③ 阶段 ② 中**任何自动重写 `END`** → 判失败；④ `FAILED` 不得使 op 离开 `OP_UNRESOLVED`（R2 第 3 条）。

### S14 空 WAL / 检查点初始组合（**10 条**，v8 扩 2 条；v8.1 扩 1 条；v8.3 扩 1 条）

| 用例 | 构造 | 分类 | 期望 |
|---|---|---|---|
| **S14a** | WAL 不存在 + 检查点不存在 | `EMPTY_CLEAN` | `READY`；允许写入；首次 `BEGIN` 时惰性创建检查点（`prefix_record_count=1`） |
| **S14b** | WAL 0 字节 + 检查点不存在 + ALL-GONE 成立 | `EMPTY_UNCHECKPOINTED` | `READY`；允许写入；不得因"0 字节"判 `ABSENT_DIRTY` |
| **S14c** | WAL 0 字节 + 检查点不存在 + 存在 `wal_evidence` / `wal_repairs` / 残留锁之一 | ALL-GONE 不成立 | `UNKNOWN` → **`MANUAL_BLOCKED`**；**不得**判干净 |
| **S14d** | WAL 0 字节 + 检查点描述**空前缀** + **ALL-GONE ①–⑦ 成立** | `VERIFIED`（空态）+ `EMPTY_STATE` | `READY`；走 A.5.4 第 4 条空态一致性；**不得**要求"末条记录"；**（v8.3）必须已确认 ALL-GONE 成立**——只满足空态六项**不足** |
| **S14e** | WAL 0 字节 + 检查点描述**非空前缀** | `INCONSISTENT` | `UNKNOWN` → **`MANUAL_BLOCKED`**；V-1 失败 |
| **S14f** | WAL 不存在 + 检查点描述非空前缀 | `INCONSISTENT` | `UNKNOWN` → **`MANUAL_BLOCKED`**；V-0 失败 |
| **S14g（v8）** | WAL 不存在 + 检查点描述**空前缀** + `wal_identity` 为 `null` 或 `identity_source == "unavailable"` | `VERIFIED`（空态）+ `IDENTITY_NOT_APPLICABLE` | `READY`；允许写入；走空态六项；**断言：不得声称"已验证不存在文件的句柄身份"**，证据包必须记录"无对象可校验"而非"身份校验通过" |
| **S14h（v8）** | WAL 不存在 + 检查点描述**空前缀**，但 `wal_identity` 记录了非零 `st_ino` / `file_index` | `INCONSISTENT`（检查点与文件系统无法一致解释） | `UNKNOWN` → **`MANUAL_BLOCKED`**；**禁止**自动重建检查点；**禁止**把"文件不存在"当作"干净" |
| **S14i（v8.1，M6）** | WAL 不存在 + 检查点不存在 + **`wal_evidence\<key>.*` 存在**（ALL-GONE ①不成立） | `EMPTY_CLEAN` **不成立**（ALL-GONE 未满足） | `UNKNOWN` → **`MANUAL_BLOCKED`**；断言：① **不得**判 `EMPTY_CLEAN` / 干净；② `WAL_STATE_COMPLETE == UNKNOWN`；③ **不得** `READY`；④ **不得**目标写入；⑤ **不得**自动创建检查点；⑥ 证据文件保留、不删除 |
| **S14j（v8.3，DD-1）** | WAL 0 字节 + 检查点描述**空前缀** + **`wal_evidence\<key>.*` 存在**（ALL-GONE ① 不成立） | `VERIFIED`（空态）+ `EMPTY_STATE`，但 ALL-GONE 不成立 | `UNKNOWN` → **`MANUAL_BLOCKED`**；断言：① **不得**判干净；② `WAL_STATE_COMPLETE == UNKNOWN`；③ **不得** `READY`；④ **不得**目标写入；⑤ **不得**自动创建或推进检查点；⑥ 证据文件保留、不删除 |

**S14 核心断言**：`prefix_record_count == 0` 时**禁止虚构末条记录**；空态一致性必须由 `prefix_record_count` / `wal_size_at_marker` / `wal_prefix_sha256 == EMPTY_PREFIX` / `seq == 0` / `kind == null` / `op_id == null` 六项共同成立。

**S14 覆盖说明（v8.3 更新）**：S14a–S14j 覆盖组合 **#1（干净与不干净两侧）/ #2（干净与不干净两侧）/ #3a（干净与不干净两侧）/ #3b / #5a（两条）/ #5b**；组合 **#4**（WAL 有记录 + 无检查点）由 **S10c** 覆盖；组合 **#6** 由 **S10a / S10b / S10c** 覆盖。**#1 的"ALL-GONE 不成立"一侧由 S14i 覆盖**（v8.1，M6 补齐）；**#3a 的"ALL-GONE 不成立"一侧由 S14j 覆盖**（v8.3，DD-1）。

**v8 关闭的缺口**：v7 中"组合 #5a 无独立用例"的缺口已由 **S14g**（身份为空 → `IDENTITY_NOT_APPLICABLE` → 可用）与 **S14h**（身份非空 → 无法解释 → 阻塞）关闭，**不再计为已知测试缺口**。剩余**不覆盖**项：组合 #5a 下 `manual_epoch != null` 的变体（即人工重建后 WAL 又丢失）——列为 `UNCOVERED`，需要"人工重建 + WAL 删除"的组合构造，当前未设计。

### S15 人工两阶段与 T5（**7 条**，v8 新增 R3；v8.1 加 S15f；v8.3 加 S15g）

覆盖 A.7.9：`MANUAL_BLOCKED` 的两个阶段与"未解决集合非空"的唯一出口。

| 用例 | 构造 | 期望 |
|---|---|---|
| **S15a** | `MANUAL_BLOCKED` + `OP_UNRESOLVED != ∅` + 一份看似完整的 T5 签核 | **T5 必须被拒绝**（`unresolved_set_empty == false` 或前提不满足）；**不得写 `MANUAL_RESET`**；保持 `MANUAL_BLOCKED`；断言：不出现 `BEGIN(MANUAL)` |
| **S15b** | `MANUAL_BLOCKED` + `OP_UNRESOLVED == ∅` + 签核齐全但**缺 `mp1_evidence_ref`**（或哈希不符） | **T5 必须被拒绝**；保持 `MANUAL_BLOCKED`；断言：不得因为"签核存在"就放行（MP-1 不可省略） |
| **S15c** | 完整 MP-1 证据 + MP-2 签核 + `MANUAL_RESET` 已持久 + `CP-R` 成功 + 重新扫描通过 | `CHECKPOINT_STATUS == VERIFIED_MANUAL`；`manual_epoch != null`；`WAL_STATE_COMPLETE == YES` → **`READY`**；断言：① 目标全文件哈希 == `target_sha256_confirmed_by_human`；② **目标字节未被改动**；③ 未伪造 `END` / `RECOVERED` / `ABORTED`；④ `MANUAL_RESET` 与 `manual_epoch` 永久可见；⑤ **不得**出现 `CHECKPOINT_STATUS == VERIFIED`（必须是 `VERIFIED_MANUAL`） |
| **S15d** | 同 S15c，但重新扫描时目标哈希 **≠** 人工确认值（构造：MP-2 之后目标被外部改动） | **保持 `MANUAL_BLOCKED`**；**禁止**仅凭签核进入 `READY`；断言：`CP-R` 的结果不得覆盖该矛盾；需回到 MP-1 |
| **S15e** | `CP-R` 在 `MANUAL_RESET` **未持久**时被调用（顺序违规） | 实现**必须拒绝**（CR-1 不满足）；`CHECKPOINT_STATUS` 保持 `INCONSISTENT`；断言：不得生成 `manual_epoch`，不得产生 `VERIFIED_MANUAL` |
| **S15f（v8.1，M2）** | `MANUAL_BLOCKED` + `IDENTITY_MISMATCH`（或 `IDENTITY_UNVERIFIABLE`）+ `OP_UNRESOLVED == ∅` + MP-1 证据齐全 + MP-2 签核齐全 + `MANUAL_RESET` 已持久 → 尝试执行 `CP-R` | **`CP-R` 必须被拒绝**（`CR-6` 两轴表：`FAULT_CLASS == FRC-IDENTITY_MISMATCH`，不在允许集合）；`CHECKPOINT_STATUS` 保持 `INCONSISTENT`；运行状态保持 `MANUAL_BLOCKED`；断言：① 不得生成 `manual_epoch`；② 不得产生 `VERIFIED_MANUAL`；③ **不得**进入 `READY`；④ 不得修改目标字节；⑤ **不得**以"签核完整"为由豁免 `CR-6` 两轴表；⑥ 报告必须写明"该状态无文档化出口，待 BLK-1 决策"，**不得**表述为"已恢复"或"可经 T5 恢复" |
| **S15g（v8.3，N-04）** | `RECOVERY_REQUIRED`（仅有 `PROVISIONAL`、`OP_UNRESOLVED == ∅`）+ MP-1 证据齐全 + MP-2 签核齐全 + `MANUAL_RESET` 已持久 → 尝试执行 `T5` | 起点状态非法 | **`T5` 必须被拒绝**（`RUN_STATE != MANUAL_BLOCKED`）；运行状态保持 `RECOVERY_REQUIRED`；断言：① **不得**写 `BEGIN(MANUAL)` / `MANUAL_RESET`；② **不得**执行 `CP-R`；③ 不得生成 `manual_epoch` 或 `VERIFIED_MANUAL`；④ 不得进入 `READY`；⑤ 报告须写明"T5 的起点不成立"，**不得**表述为"T5 执行后失败" |

**S15 核心断言**：① `unresolved_set_empty == true` 是 T5 的硬前提；② `MANUAL_BLOCKED` 只能经"三阶段全通过"离开，**签核本身不是出口**；③ `VERIFIED_MANUAL` 不得被当成 `VERIFIED`（T2 拒绝、`wal_state_digest` 可区分）；④ T5 全程**不改动目标字节**；⑤ **（v8.1，M2；v8.2 按 `FAULT_CLASS` 重述）身份类与 `FRC-UNKNOWN` 的 `MANUAL_BLOCKED` 不存在任何出口**——`CP-R` 被 `CR-6` 两轴表禁止，T5 阶段 B 无法完成；⑥ **（v8.1，M1）`VERIFIED_MANUAL` 不单独授予写权限**，四项否决条件任一成立即 `WRITE_PERMITTED = NO`；⑦ **（v8.3，N-04）T5 只在 `MANUAL_BLOCKED` 下可执行**——`RECOVERY_REQUIRED` 下出现任何一次 `T5` 尝试即判失败（S15g）。

## A.18 一致性自审（v8）

| 检查 | 结论 |
|---|---|
| `.durable` 定义 vs A.5.6 | 检查点不独立可信，必须通过 V-0…V-6 + V-T；身份不通过时不得判 `DURABLE` |
| **身份 vs 检查点** | `wal_identity` 写入检查点；V-1b 校验；CP-4 发布前复核；冲突视图不择一采信 |
| **身份 vs T1/T2/T4** | 三条自动路径均要求 `IDENTITY_VERIFIED`；不一致时唯一出口是 T5 |
| **故障日志 vs `WAL_STATE_COMPLETE`** | `YES` 要求 `FAIL_READABLE_EMPTY` / `FAIL_ABSENT_CONSISTENT`；`FAIL_*` 三值一律 `UNKNOWN` |
| **故障日志 vs T1/T2/T4** | 不可读/损坏/不一致时三条自动路径全部关闭；T2-6 显式排除 |
| **（v8.1，M1）`VERIFIED_MANUAL` vs `WRITE_PERMITTED`** | 集合扩展仅为让否决条件可求值；四项否决（`manual_epoch` / BLK-5 / 签核接受 / `OP_UNRESOLVED == ∅`）任一成立 → `NO`；真值表见 A.7.8；与 `A.7.1` `YES` 行、`A.10.1` PWA-6 逐字同构 |
| **（v8.1，M2；v8.2 按 `FAULT_CLASS` 重述）身份类 `MANUAL_BLOCKED`** | `A.2.1` / `A.7.3` T5 行 / `A.7.4` / `A.7.9.3` / `A.5.10 CR-6` 两轴表 / `A.15 #10` / `S15f` **七处一致**：**无文档化出口**，不得表述为"可经 T5 恢复" |
| **（v8.1，M3）检查点 vs 快照发布语义** | `A.2.2` 红线 16 / `A.5.10 CR-e` / `A.11.1` 适用范围表 **三处一致**：快照"不存在才创建"，检查点"先保留旧代再发布" |
| **（v8.1，M4）`SNAPSHOT_CONFLICT` vs `SNAPSHOT_PUBLISH_UNSUPPORTED`** | `A.2.1` / `A.11.1` ⑤ / `A.11.2` / `S1i` / `S1j` **五处一致**：前者"目标确实存在"，后者"机制不支持"，不得混报 |
| **（v8.1，M5）BLK 数量** | `A.22`（5 项）= `PWA-8`（5 项）= `A.19.2` 第 10 条（5 项）= 头部阶段表（5 项）= `E` 第 2 条（5 项） |
| **（v8.1，M6）组合 #1 与 ALL-GONE** | `A.5.9` #1 行 / 硬规则 4 / 映射表 / `S14i` **四处一致**：#1 **必须**满足 ALL-GONE 才可判干净 |
| **UNKNOWN → READY 闭包** | A.7.4 已逐条列出；`MANUAL_BLOCKED` 无自动出口 → 无自动回环；**v8**：唯一人工出口须穿过 `MANUAL_RESET` → `CP-R` → 重新扫描三道门 |
| **目标持久化 vs END** | ORD-1…ORD-4 + **ORD-5a / ORD-5b / ORD-6 / ORD-7**（v8 拆分为四阶段）；`END.target_persisted` / `readback_verified` 必须为 true；阶段 ① 禁写 `END`，阶段 ② 禁重写 `END` |
| **`END` 四阶段互斥** | A.8.2 判定表 + S13a–S13f 一一对应；阶段 ② 不得判成 ① 或 ③ |
| **`END` 哈希来源** | `target_hash_provenance` 必须等于 ST-11 实测；H6 之后不得重算回写（C18、红线 15） |
| **`FAILED` 语义** | `FAILED` 永不关闭 op（红线 4、ORD-7）；S13d/S13e 中 op 保持 `OP_UNRESOLVED` |
| **快照同名不覆盖** | A.11.1 ⑤/⑧ 使用原子"不存在才创建"；`os.replace` 已禁用；S1f–S1h 断言"任何覆盖即失败" |
| **`MANUAL_BLOCKED` 语义** | A.7.9 两阶段；`unresolved_set_empty == true` 为 T5 硬前提；签核 ≠ 恢复；S15a–S15e |
| **`VERIFIED` vs `VERIFIED_MANUAL`** | T2-2 只接受 `VERIFIED`；T4 只接受 `VERIFIED`；`YES` 接受两者但 `VERIFIED_MANUAL` 需 `manual_epoch != null` |
| **`CP-R` 与"重写检查点消除 INCONSISTENT"** | A.5.10 对照表：时机 / 印记 / 结论 / 数据 / 可回退 五点区分；CR-1…CR-6 强制 |
| **WAL 不存在时的身份** | A.5.7.7；`IDENTITY_NOT_APPLICABLE` ≠ 身份校验通过；S14g / S14h 两侧 |
| **写游标语义** | A.8.1.1 唯一依据；S5b-1（未写区 → 不可检出）与 S5b-2（已完成前缀 → 必须检出）方向正确 |
| **空态 vs 检查点校验** | `prefix_record_count == 0` 走 A.5.4 第 4 条，禁止虚构末条记录 |
| 空态 vs 干净判定 | 组合 #1 / #2 / **#3a** / #5a（即 `EMPTY_STATE`）**全部**依赖 ALL-GONE **七项**旁证（A.5.9，v8.3 统一） |
| RP-4b vs A.6.3 | 身份变化 → `MANUAL_BLOCKED`，与情况②③一致 |
| S7e vs S7h | 日志不可写 → `UNKNOWN`（**`T5*`**，`OP_UNRESOLVED == ∅` 才可执行）；日志可写 → `NO`（T1/T4）；两侧互补不重叠 |
| 用例数 | 矩阵、通过标准、统计三处均为 **106**（v8.3 重算；v8.2 的 101 / 266 / 2084 属上一版口径） |
| 断言数 | 通用 18 条（A.19.1 逐条定义）；106 × 18 + 280 = **2188** |
| 统计口径 | 不可检出场景**不计入成功检出**；S5 必须检出 5 条 / 不可检出 3 条 |
| **（v8.2，R13）三值判定优先级** | A.7.1 判 1 `UNKNOWN` → 判 2 `NO` → 判 3 `YES` → 判 4 兜底；A.7.1 文字 / A.7.4 表格 / A.7.5 真值表三处一致；S10h 验证"同时成立时判 `UNKNOWN`" |
| **（v8.2，R15）恢复后复核** | A.7.10 的 PR-1…PR-5；T1 / T2 / T4 三行均指向 A.7.10；S7j 验证"`T4` 成功不等于可写" |
| **（v8.2，R16）`FAULT_CLASS` 两轴** | A.2.3 派生（F1–F9）/ A.5.10 CR-6 两轴表 / A.7.4 三类出口 / A.14.4 签核字段 / A.15 #10 **五处一致**；`IDENTITY_UNVERIFIABLE` 只对应 `FRC-IDENTITY_UNAVAILABLE` |
| **（v8.2，R18）截断句柄安全** | A.2.2 红线 18 / A.6.2 的 RP-4a / A.6.5 的 TR-1…TR-6 / A.6.4 两行 / S9h / S9i **六处一致**：截断前保证 ≠ 截断后复核 |
| **（v8.2，R14 + R19）`T5*` 记号** | A.7.3 T5 行四条硬前提 / A.7.6 六条统一规则 / A.7.7 拆行 / A.15 #4 #9 #11 / A.17 的 S7e / S7f / S11a / S11c / S11d / S7i **十处一致**：`OP_UNRESOLVED != ∅` 时 `T5` 恒不可执行 |
| **（v8.2，R17）`UNKNOWN` 全局否决** | A.7.1 / A.7.3 T2 行 / A.7.4 / A.7.5 **四处一致**：`UNKNOWN` 时 T2 一律不成立 |

## A.19 通过标准

### A.19.1 通用断言 C1–C18（v8：**首次逐条定义**）

> v7 声明"17 条通用断言"却未在文档任何位置列出定义，属可核查性缺陷；v8 补齐并新增 C18。无 `END` 的用例对 C18 记 `N/A`（与 A.13 的 `OBJECT = N/A` 同口径），`N/A` 不计为通过也不计为失败。

| # | 断言 | 适用 |
|---|---|---|
| **C1** | 前置 5 项证据完整（前状态、快照状态、检查点内容、身份字段、故障日志状态） | 全部 |
| **C2** | 执行前后 WAL 全文快照 + 逐行可解析性结论 | 全部 |
| **C3** | 目标全文件 SHA-256（前/后）+ 文件大小未变（等长覆盖） | 全部 |
| **C4** | 锁状态记录：获取 / 持有 / 释放；无自动删锁 | 全部 |
| **C5** | 注入点日志 + `injection_kind`（`FAULT_INJECTED` / `STATE_CONSTRUCTED`） | 有注入的用例 |
| **C6** | 实际运行状态 == 预期运行状态；无"静默通过"（未命中预期分支必须显式记 `FAIL`） | 全部 |
| **C7** | A.20 禁止假通过项逐条核对，命中任一 → `FAIL` | 全部 |
| **C8** | 无越界写入：STA-6 审计钩子报告中所有写模式打开均落在 L1 内 | 全部 |
| **C9** | 证据包目录完整（`cases\<case_id>\evidence\`） | 全部 |
| **C10** | 恢复类用例：`BYTES` / `OBJECT` / `REDO_VERIFIED` 分别记录，未验证不得记通过 | 恢复类 |
| **C11** | 无自动降级：`RECOVERY_REQUIRED` / `MANUAL_BLOCKED` 未被自动改为 `READY` | 全部 |
| **C12** | 结束时目标哈希 ∈ 断言允许集合，且与用例预期一致 | 全部 |
| **C13** | 34 个 L0 文件（含 3 个 L0-D）完整 SHA-256 == `baseline_ledger.json`，无新增/删除/改名 | 全部 |
| **C14** | 可重放：同一构造脚本二次运行得到同一预期状态（差异须解释） | 全部 |
| **C15** | WAL 身份验证记录：`wal_identity` 四字段 + `WAL_IDENTITY_STATUS` 判定值 + 判定依据 | 全部 |
| **C16** | 故障日志状态记录：`FAILURE_LOG_STATUS` 六值之一 + 判定依据 | 全部 |
| **C17** | ST-9 → ST-10 → ST-11 → ST-12 时序记录（含 `fsync` 调用点与返回） | 有写入的用例 |
| **C18（v8）** | `END.target_hash_provenance` 与 ST-11 实测逐字一致，且该值取得时刻早于 H6；**若 `END` 哈希等于 H6 之后重算的结果 → `FAIL`** | 有 `END` 的用例；无 `END` 记 `N/A` |

### A.19.2 通过标准

1. **106/106 用例**产出预期状态，零静默通过。
2. 每用例证据包：C1–C18 全部可核对项、执行前后 WAL 快照与原文、**检查点内容 + 身份字段 + 校验结果**、**故障日志状态**、目标前后完整 SHA-256、mtime（仅辅助）、锁状态、屏障日志、目录树、注入点日志、`injection_kind`、所用钩子编号、ST-9/10/11/12 的时序记录、**`target_hash_provenance`**。
3. 恢复类用例：`BYTES`/`OBJECT`/`REDO_VERIFIED` 分别记录；`UNVERIFIED` 或未验证 → 判"部分通过"，不计入通过。
4. `RECOVERY_REQUIRED` 用例中无一次被自动降级为 `READY`；`MANUAL_BLOCKED` 用例中无一次走 T1/T2/T4；**T5 用例（S15）中无一次在 `OP_UNRESOLVED != ∅` 或 MP-1 缺失时执行**；**（v8.2，R14）任何标注 `T5*` 的分支（S7b-b4 / S7e-e2 / S7e-e3 / S7f-f1 / S7f-f2 / S10a–S10c / S12a / S12d）中，无一次在四条硬前提未全部成立时执行 `T5`**（S7i）。**（v8.3，N-04）`T5` 只在 `MANUAL_BLOCKED` 下被调用——`RECOVERY_REQUIRED` 下出现任何一次 `T5` 尝试即判失败（S15g）**。
5. S0a–S0f 通过：拒绝逻辑零副作用；真实资产（含 L0-D 三个文件）未被写入入口接触。
6. 结束后 `snap\` 条目数 == 预期；除 S6d 的目录重建外无锁被自动删除；`wal_evidence\` 无删除；**无任何快照或 sidecar 被覆盖（S1f–S1i 全通过）**；**`SNAPSHOT_CONFLICT` 与 `SNAPSHOT_PUBLISH_UNSUPPORTED` 未发生任何一次混报（S1j）**。
7. 真实目录 34 个 `.assets` 完整 SHA-256 == `baseline_ledger.json`。
8. `END` 四阶段（S13a–S13f）全部可区分，且阶段 ② 无一次自动重写 `END`。
9. S5 的 8 条中，**必须检出的 5 条全部检出**；**不可检出的 3 条（S5b-1 / S5e / S5g）在报告中显式声明为不可检出**，不得计入检出数。
10. 报告明确声明：结果仅覆盖 L1；**STA 通过 ≠ PWA 满足**；**W2-b / S5b-1 / S5e 写时不可检出，S5g 仅靠 V-T 延迟检出**；不构成对现有脚本的保护证明；**A.22 五项阻塞项（BLK-1…BLK-5）未解决前不得真实写入**；**（v8.1，M5）PWA-8 必须逐项检查 5 项，任一未决即 `FAIL`**。
11. **（v8.1）** ① `VERIFIED_MANUAL` 下 `WRITE_PERMITTED == YES` 的记录必须同时具备 `manual_epoch != null`、BLK-5 = `DECIDED_ACCEPT`、签核接受、`OP_UNRESOLVED == ∅` **四项**；缺一而报 `YES` → 判失败（M1）。② 身份类 `MANUAL_BLOCKED` 的记录中，**不得出现任何一次** `CP-R` 成功、`VERIFIED_MANUAL` 生成或 `READY` 进入（S15f，M2）。③ `CP-R` 的成功记录中，旧代检查点必须仍存在且可回读（S10e，M3）。
12. **（v8.2）** ① `UNKNOWN` 与 `NO` 条件同时成立的记录中，**无一条**被判 `NO`（S10h）；② 身份类 / `FRC-UNKNOWN` 的 `CP-R` 请求**无一次**被接受（S10f / S10g）；③ 平台不支持同句柄截断时**无一次**发生截断调用（S9h / S9i）；④ `T1` / `T2` / `T4` 之后**每一条**记录都有 PR-1…PR-5 的重扫证据（S7j）；⑤ 任一 `T5*` 分支的记录中，**无一次**在 `OP_UNRESOLVED != ∅` 时写 `MANUAL_RESET`（S7i）。

## A.20 禁止的假通过

| 模式 | 原因 |
|---|---|
| 用大小判断写入成功 | 等长覆盖下恒真（S7c-2） |
| 用 mtime 判断是否被改 | 可保留/回填 |
| "目标看起来完整所以已完成" | S3a/S8b |
| 目标哈希 == B 即放行 | 仅 T2-5 一条 |
| 哈希 == A 即证明无并发写入 | **S5b-1** / S5e 反例（v8：写游标语义重排后，不可检出的是 S5b-1 而非 S5b-2） |
| 哈希可以发现所有第三方写入 | 同上 |
| 仅比较 `seq <= last_durable_seq` 而不校验前缀 | WAL 被截断/替换时误判 `DURABLE` |
| **仅比较前缀哈希而不校验文件身份** | P0-1：同内容替换可绕过（S11a） |
| **用路径重新打开算哈希、与另一路径 stat 拼接"已验证"** | ID-1 / ID-5 禁止 |
| **把 `st_ino` 当作文件未被替换的证明** | A.5.7.3 |
| **重写检查点来消解 `INCONSISTENT`** | 掩盖外部干扰 |
| **把 WAL 持久化失败一律导向 T2** | 已删除该泛化 |
| **把日志不可写判成 `NO` 并走 T1/T4** | P0-2：缺失的故障证据不得被检查点替代（S7e / S12d） |
| **因"日志文件不存在"就判 `UNKNOWN`** | WAL 干净时属 `FAIL_READABLE_EMPTY`（S12c） |
| **看到 `REPAIR` 就写 `REPAIR_DONE`** | 可见 ≠ 已确认持久化 |
| **先写 `END` 再持久化目标 / 只 `flush` 不 `fsync` 就写 `END`** | P0-3 ORD-1…ORD-3（S13a） |
| **把 `flush()` 当持久化** | 仅交给 OS |
| **空 WAL 虚构一条"最后记录"通过 V-4/V-5** | P1-1 |
| **把 0 字节 WAL 直接判 `ABSENT_DIRTY`** | 组合 #2 应判 `EMPTY_UNCHECKPOINTED`（S14b） |
| **（v8）用 `os.replace` 发布快照或 sidecar** | 会覆盖同名既有文件（A.11.1、S1f/S1g） |
| **（v8）快照同名冲突时自动改名/删除/覆盖** | 销毁唯一证据；冲突只能人工判定（A.11.3） |
| **（v8）仅凭文件名含 `<sha16>` 就认定快照可信** | 前缀是声明不是校验 |
| **（v8）把 S5b-1 的"未检出"记成"已检出"** | 未写区被载荷覆盖，写时不可能检出（A.8.1.1） |
| **（v8）把 `END` 阶段 ②（持久性未知）判成阶段 ① 或 ③** | 违反 A.8.2 判定表；S13d/S13e |
| **（v8）`END` 写入/fsync 失败后自动重写 `END`** | ORD-5b |
| **（v8）在 `MANUAL_RESET` 未持久时执行 `CP-R`** | 顺序强制（A.5.10 CR-1、S15e） |
| **（v8）仅凭 T5 签核把状态改成 `READY`** | 签核 ≠ 恢复；须重新扫描（A.7.9、S15d） |
| **（v8）用 `VERIFIED_MANUAL` 冒充 `VERIFIED` 走 T2** | T2-2 只接受 `VERIFIED` |
| **（v8）在 H6 之后重算目标哈希并回写 `END.target_sha256_after`** | 使 V-T 自我作废（红线 15、C18） |
| **（v8）把 `IDENTITY_NOT_APPLICABLE` 说成"身份校验通过"** | 无对象可校验 ≠ 通过（A.5.7.7、S14g） |
| **（v8.1，M1）把 `VERIFIED_MANUAL` 放进允许集合就宣称"可写"** | 集合扩展只为让否决条件可求值；四项否决任一成立即 `NO`（A.7.8 真值表） |
| **（v8.1，M2）把身份类 `MANUAL_BLOCKED` 说成"可经 T5 / `CP-R` 恢复"** | `CR-6` 两轴表禁止 `CP-R`，T5 阶段 B 不可完成；该状态无文档化出口（S15f） |
| **（v8.1，M3）用 `os.replace` 直接覆盖旧检查点** | 销毁 `pre_rebuild_checkpoint_status` 的对照物（A.5.10 CR-e 情形 2） |
| **（v8.1，M4）把 `EXDEV` / 不支持硬链接 / `EPERM` 报成 `SNAPSHOT_CONFLICT`** | 会生成不存在的"冲突方"报告，把平台限制伪装成人为冲突（S1j） |
| **（v8.1，M4）在最终名上直接写入完整快照** | 崩溃后留下"看似已发布但内容不完整"的文件，且永久不可恢复（A.11.1 ⑤） |
| **（v8.1，M6）WAL 与检查点均不存在就直接判 `EMPTY_CLEAN`** | 必须 ALL-GONE ①–⑦ 全部通过（A.5.9 #1、S14i） |
| **（v8.2，R14）把表格里的 `T5*` 读成"因此可以执行 T5"** | `T5*` 只表示理论出口；四条硬前提不成立时无出口（A.7.6 统一规则、S7i） |
| **（v8.2，R14）`OP_UNRESOLVED != ∅` 时仍写 `MANUAL_RESET`** | T5 硬前提 ① 失败，T5 非法（A.7.3、A.7.9.2 MP2-1、S7i） |
| **（v8.2，R16）用"故障看起来是身份类 / 不是身份类"代替 `FAULT_CLASS` 派生** | 分类必须按 A.2.3 的 F1–F9 有序派生；人工指定即无效（红线 17、S10g） |
| **（v8.2，R16）把 `IDENTITY_UNVERIFIABLE` 同时算作"身份类"与"非身份类但身份不可得"** | 两轴表中它只对应 `FRC-IDENTITY_UNAVAILABLE`（A.2.3 不变量 1/2、S10f） |
| **（v8.2，R18）用 `os.truncate(path, ...)` 截断 WAL** | 路径截断与替换存在竞态，可能截断到另一个文件（A.6.5 TR-1、S9h） |
| **（v8.2，R18）以"截断后身份复核通过"证明"截断前操作对象正确"** | 事后复核不能倒推事前安全（A.6.5 TR-6） |
| **（v8.2，R13）`UNKNOWN` 与 `NO` 条件同时成立时判 `NO`** | 宽泛条件不得覆盖更严格的异常条件（A.7.1 判定优先级、S10h） |
| **（v8.2，R15）`T4` / `T1` 成功后直接放行载荷写入** | 必须经 PR-1…PR-5 重扫与重算（A.7.10、S7j） |
| **（v8.2，R15）沿用恢复前的 `FAILURE_LOG_STATUS`** | 恢复后必须重新扫描并重新判定（PR-1） |
| **（v8.2，R17）用"T2-2 / T2-6 恰好失败"代替 `UNKNOWN` 的全局否决** | 全局否决是独立前置条件，不依赖逐条推导（A.7.5） |
| 把 `expected` 与 `actual_after` 直接比较 | 三集合语义错误 |
| 用 `FAILED` 关闭恢复 op | R-5 |
| 声称 `realpath`/`fstat`/`TestPath` 提供完整并发保护 | A.9 |
| 快照存在即可回滚 | 未校验/无 sidecar 均不可用 |
| `fsync` 失败即断言磁盘有/无数据 | A.7.8 |
| 用内存标记代替持久证据 | A.5 |
| 因写入失败而截断回滚 | A.6.1 |
| 无钩子仍宣称 S5 已覆盖 | A.8.5 |
| 用 STA 结果推断 PWA 满足 | A.10.3 |
| 用 L0-D 文件做测试 | A.1.3 |
| `os._exit` 结果表述为断电持久性 | M4 边界 |
| M8/M10/M11 表述为真实故障 | `injection_kind` |

## A.21 未覆盖范围

真实 OS 级 ENOSPC；掉电/强制关机/真实 fsync 语义；跨卷快照；大文件 244 MB/1.3 GB；游戏进程持有句柄；多工具并发；硬链接"打开瞬间"窗口；**W2-b / S5b-1 / S5e 写时不可检出**；对象级校验仅 `T-REAL`；**PWA-3（内存映射写者）**；Windows 目录 fsync 无直接等价（CP-5 后目录项持久化）；**文件身份字段的可伪造性**；现有脚本的保护状态；**`VERIFIED_MANUAL` 下的历史真实性不可由机器验证（BLK-5）**；**组合 #5a 且 `manual_epoch != null` 的变体（S14 覆盖说明中列为 `UNCOVERED`）**。

**（v8.1 新增）检查点更新的原子性与掉电可见性 `UNVERIFIABLE`**：`A.5.10 CR-e` 情形 2 的"旧代改名"与"新代发布"是**两次独立文件系统操作**，**组合不具备原子性**。其**进程崩溃**行为可判定（判 `ABSENT_DIRTY` → `MANUAL_BLOCKED`），但**掉电**下"改名已持久而新代未持久"或"改名未持久而新代已持久"的可见性**无法由本方案保证**（依赖目录项持久化，Windows 无等价机制 → BLK-4）。该项**声明为未覆盖**，**不得声称已保证**（见 C.4 第 46 条）。

**（v8.2 新增）`FAULT_CLASS` 派生的输入完备性未覆盖**：A.2.3 只规定"输入互相矛盾 → `FRC-UNKNOWN`"，但"何种程度的矛盾算矛盾"（例如 V-1b 报不一致而 `st_ino` 为 0、`FAILURE_LOG_STATUS` 与 WAL 侧观测部分吻合）没有可判定的阈值；该判据**待决**（C.1 第 10 条），不得据本文档声称分类总是可复现。

**（v8.2 新增）同句柄截断的平台可用性未覆盖**：`ftruncate` / `SetEndOfFile` 在目标卷上是否可用、失败时的 errno 集合、以及截断在掉电瞬间的长度可见性，**均未测**（C.3 第 32 条、C.4 第 48 条）。A.6.5 只规定"不能保证即中止"，**不构成已保证**。

**（v8.3 新增）自动检查点推进的掉电中间态与容量治理未覆盖**：`A.5.11` 的 CP-5b / CP-5c 组合不具备原子性，进程崩溃可判定（S10i），但掉电下"旧代已改名、新代未发布"的可见性**无法保证**（BLK-4 / C.4 第 50 条）；旧代文件的**容量治理**未设计（C.4 第 51 条），本方案只规定"不自动删除"。

**模型内不可达组合（v8 显式声明）**：在 A.8.1.1 的"升序 + 单遍 + 每块一次"写入模型下，**不存在**"位于已完成前缀、且随后仍会被载荷覆盖"的位置 → v7/R1 描述的这一子目标标记 **`MODEL_UNREACHABLE`**，**不伪造、不计入覆盖**。若要覆盖该组合，需要：① 非升序或多遍写入模型；② 新增钩子 `H3'`（第二遍开始处）与独立用例；③ 重新计算 S5 统计。当前均未设计。

## A.22 P0 阻塞项（阻断真实写入，需人工决策）

| ID | 阻塞项 | 性质 | 不解决的后果 |
|---|---|---|---|
| **BLK-1** | **WAL 文件身份连续性无法在目标卷上可靠保证**（`st_ino == 0` / 索引复用 / 无 `file_index`） | 平台能力未验证 | 无法区分"同一文件"与"同内容替换"；S11a/S11b/S11c 无法通过；`WRITE_PERMITTED` 恒为 NO |
| **BLK-2** | **目标持久化与 WAL END 的持久化顺序无法被形式化证明**（Windows/NTFS `FlushFileBuffers` 语义边界、硬件写缓存） | 语义边界未验证 | 断电场景下可能"END 已持久但目标未持久"；只能声明为未覆盖 |
| **BLK-3** | **故障日志与检查点可能同时不可持久化** | 设计缺口 | 该时刻的失败无法被任何持久证据记录；只能 fail-closed 到 `MANUAL_BLOCKED` |
| **BLK-4** | **CP-5 之后的目录项持久化无 Windows 等价机制** | 平台缺口 | 检查点文件可能在掉电后"消失"而内容文件仍在，导致 `INCONSISTENT` |
| **BLK-5（v8）** | **`VERIFIED_MANUAL` 的语义无法由机器等同 `VERIFIED`**：经 `CP-R` 重建的前缀是"人工接受"而非"机器校验"，其历史真实性不可验证 | 语义缺口 | 允许在 `VERIFIED_MANUAL` 下写入等于接受一段不可验证的历史；是否允许须人工决策（`WRITE_PERMITTED` 中已设为条件项） |

**规则**：`BLK-1…BLK-5` 任一未决（`PWA-8 = FAIL`）时，**禁止真实目标写入**。**（v8.2）** 另注：`ALL-GONE`（A.5.9）不是 BLK，但它是"空态（`EMPTY_STATE`：#1 / #2 / #3a / #5a）可判干净"的**必要条件**——不成立时 `WAL_STATE_COMPLETE` 必须为 `UNKNOWN`，与 BLK 是否未决无关。两者**不得互相替代**：ALL-GONE 成立不能解除任何 BLK，BLK 全部已决也不能使 ALL-GONE 可跳过。合成夹具（STA）仍可在 L1 内运行，但其结果**不能**用于推断真实写入安全。

**（v8.1，M5）数量唯一来源**：BLK 项数以本表为**唯一来源**（当前 **5 项**）。`A.10.1` PWA-8、`A.19.2` 第 10 条、头部阶段表、`E` 第 2 条必须与本表数量**逐项一致**；任一处出现 `BLK-1…BLK-4` 即为缺陷。**BLK-1…BLK-4 已决不能推出 BLK-5 可放行。**

**v8 说明**：BLK-1、BLK-2、BLK-3、BLK-4 四项的结论**未因文档修订而改变**；BLK-5 是本轮 R3 引入 `CP-R` 后**新增**的阻塞项，不得因"设计已闭环"而视为已解决；**（v8.1，M5）BLK-5 未决时同样禁止真实写入，不得因前四项已决而放行。**

---

# B. 测试统计

| 口径 | v7 | v8 | v8.1 | v8.2 | **v8.3** | 变化原因 |
|---|---|---|---|---|---|---|
| 场景组数 | 15 | 16 | 16 | 16 | **16** | 无变化（未新增组） |
| 子场景数 | 76 | 89 | 94 | 101 | **106** | v8.3 **+5**：S10 +3（S10i / S10j / S10k）、S14 +1（S14j）、S15 +1（S15g） |
| 独立执行用例数 | 76 | 89 | 94 | 101 | **106** | 与子场景 1:1 |
| 通用断言/用例 | 17 | 18 | 18 | 18 | **18** | 无变化（C1–C18） |
| 通用断言小计 | 1292 | 1602 | 1692 | 1818 | **1908** | 106 × 18 |
| 专项断言小计 | 201 | 235 | 247 | 266 | **280** | 见下明细（+14：S10 +9、S14 +2、S15 +3） |
| **总断言数** | 1493 | 1837 | 1939 | 2084 | **2188** | 1908 + 280 |

**专项断言明细（v8.2）**：

| 组 | 用例数 | 每条 | 小计 |
|---|---|---|---|
| S0 | 6 | 3 | 18 |
| S1 | 10 | 2 | 20 |
| S2 | 1 | 4 | 4 |
| S3 | 3 | 2 | 6 |
| S4 | 4 | 3 | 12 |
| S5 | 8 | 3 | 24 |
| S6 | 5 | 2 | 10 |
| **S7（v8.2 +2）** | **11** | 2 | **22** |
| S8 | 7 | 3 | 21 |
| **S9（v8.2 +2）** | **9** | 3 | **27** |
| **S10（v8.2 +3；v8.3 +3）** | **11** | 3 | **33** |
| S11 | 4 | 3 | 12 |
| S12 | 4 | 3 | 12 |
| S13 | 6 | 3 | 18 |
| **S14（v8.3 +1）** | **10** | 2 | **20** |
| **S15（v8.3 +1）** | **7** | 3 | **21** |
| **合计** | **106** | — | **280** |

- 合计：**106 × 18 + 280 = 1908 + 280 = 2188**。
- 逐行自洽：每组 `用例数 × 每条` == 该组小计（18 + 20 + 4 + 6 + 12 + 24 + 10 + 22 + 21 + 27 + **33** + 12 + 12 + 18 + **20** + **21** = **280**）。
- **对照运行不计入**：5 次（T-1K / T-1M / T-1M-P / T-64M / T-REAL）× 3 条断言 = 15，作为夹具前置条件单独统计。
- 若实现偏离 `buffering=0`，须补 S3d → **107 用例 / 2208 断言**（107 × 18 + 282）。
- **v8.3 新增 5 条的性质**：全部为**状态构造型**（`STATE_CONSTRUCTED`），**不依赖** BLK-1 的判定结果即可执行；但其结论**不构成对 BLK-1…BLK-5 任何一项的解决**。

**派生上界（v8.3 重算；口径问题仍未修，见下）**：

- 若 M9 钩子缺失：S5a / S5b-1 / S5b-2 / S5c / S5d / S5e / S5f / S5g 共 **8** 条记 `UNCOVERED` → **实际可执行用例 = 98**（106 − 8）。
- 若 `tool_sha256` / `deps` 机制未建立：S2 / S3a / S3b / S3c / S7c-1 / S7c-2 / S7d / S8g 共 **8** 条只能"部分通过" → **可完全通过用例上界 = 98**（106 − 8）。
- 若 BLK-1 未决：S11a–S11d 共 **4** 条无法通过 → 链式结果 **94**（98 − 4）。
- 若 BLK-5 未决：S15c（T5 后进入 `READY`）无法判定通过 → 链式结果 **93**（94 − 1）。
- **（v8.3 注，口径仍未修）** 上述 `98 / 94 / 93` 是**条件链**，不是并列单项：两个 `98` 来自**互不相交**的影响集合（M9 的 8 条 vs `tool_sha256` 的 8 条，交叠 = 0），且一个是"可执行"、一个是"可完全通过"，是两个不同度量；**单独** BLK-1 未决的真实上界为 **102**（106 − 4），**单独** BLK-5 未决为 **105**（106 − 1）；四条件同时成立的真实**联合上界为 85**（106 − 21，并集 = 8 + 8 + 4 + 1）。
  该项属静态审查报告的 **F-09（P1）**，**本轮未修**，仅把数字同步到 v8.3 基线；**不得把两个单项上界当成联合上界**，也不得把 `98` 当作"最坏情况"（它只是某一条件成立时的值）。
- **不可检出不计入成功检出**：S5 的 8 条中，必须检出 **5** 条（S5a / S5b-2 / S5c / S5d / S5f），写时不可检出 **3** 条（S5b-1 / S5e / S5g）。任何把不可检出计为检出的统计口径均判无效。

---

# C. 未解决 / 未验证事项（四分类）

### C.1 已知设计缺口（不可通过实现消除）

| # | 缺口 |
|---|---|
| 1 | W2-b / **S5b-1** / S5e：外部写落在未写区或被载荷完整覆盖时**写时不可检出**（S5g 类可经 V-T 延迟检出，S5e 类仍可能永不检出） |
| 2 | PWA-3：无法断言"无其他进程持有内存映射" |
| 3 | 故障日志与检查点可能同时不可持久化（BLK-3） |
| 4 | 硬链接"打开瞬间创建"的极窄窗口 |
| 5 | CP-5 之后目录项持久化无 Windows 等价机制（BLK-4） |
| 6 | **文件身份字段可被伪造 / 索引可被复用**，身份校验只能降低概率 |
| 7 | **（v8）`VERIFIED_MANUAL` 的历史真实性不可由机器验证**（BLK-5）：`CP-R` 只能记录"人工接受"，无法把人工判断变成机器校验 |
| 8 | **（v8）写入模型内不存在"位于已完成前缀、且随后仍会被载荷覆盖"的位置**（A.8.1.1，`MODEL_UNREACHABLE`）：该组合无法构造，只能声明不可达 |
| 10 | **（v8.2，R16）`FAULT_CLASS` 的派生在输入互相矛盾时无可判定阈值**：A.2.3 只规定"矛盾 → `FRC-UNKNOWN`"，但"何种程度算矛盾"（V-1b 与 `st_ino == 0` 并存、故障日志与 WAL 侧部分吻合等）**待决**。该缺口**不可通过实现消除**（是判据本身的定义问题），只能由人工决策给出阈值 |
| 9 | **（v8.1，M2；v8.2 按 `FAULT_CLASS` 重述）身份类 `MANUAL_BLOCKED` 无文档化出口**：`CR-6` 两轴表禁止 `CP-R`，T5 阶段 B 不可完成 → 该状态只能保持，直到 BLK-1 决策。这不是"可通过实现消除"的缺口，而是**设计上刻意 fail-closed** 的结果；但必须明确列为已知缺口，**不得表述为"可恢复"** |

### C.2 尚未实现

| # | 事项 |
|---|---|
| 9 | `tool_sha256` / `deps` 记录机制 |
| 10 | 检查点机制（CP-1…CP-6、V-0…V-6、V-T；含 `checkpoint_version=3` 与 `manual_epoch`） |
| 11 | **`wal_identity` 采集与比对（ID-1…ID-6）** |
| 12 | **`FAILURE_LOG_STATUS` 六值判定逻辑** |
| 13 | **T5 / `MANUAL_RESET` 与签核流程**（含 MP-1 / MP-2 两阶段） |
| 14 | **（v8）`CP-R` 人工基线重建（A.5.10，CR-1…CR-6）与 `VERIFIED_MANUAL` 判定** |
| 15 | **ST-9 目标持久化 / ST-10 回读 / ST-11 提交前复检** |
| 16 | `wal_repairs\` / `wal_evidence\` 与 RP-1…RP-7（含 RP-4b） |
| 17 | T4 检查点重同步 |
| 18 | M9 钩子 H1–H6；M10 检查点篡改；M11 身份替换 / 故障日志破坏注入器 |
| 19 | `signoffs\` 目录（T2 与 T5 两种签核） |
| 20 | 全局 `open()` 审计钩子（STA-6） |
| 21 | `inventory_digest` / `unresolved_set_digest` / `wal_state_digest` 计算代码（v8：digest 须含 `manual_epoch`） |
| 22 | L0-D 边界在工具层的强制 |
| 23 | **（v8）`SNAPSHOT_CONFLICT` 判定、原子"不存在才创建"发布、A.11.3 冲突报告生成** |
| 24 | **（v8）`END.target_hash_provenance` 的记录与校验（C18）** |
| 24b | **（v8.1，M3）`CR-e` 三情形实现**：旧代原子改名、`pre_rebuild_checkpoint_sha256` 记录、情形 3 中间态（`ABSENT_DIRTY`）判定 |
| 24c | **（v8.1，M4）`SNAPSHOT_PUBLISH_UNSUPPORTED` 判定与错误分类**：`EXDEV` / `EPERM` / `ERROR_NOT_SUPPORTED` 与 `ERROR_ALREADY_EXISTS` 的区分；`MoveFileExW(tmp, final, 0)` 分支 |
| 24d | **（v8.2，R16）`FAULT_CLASS` 派生实现（A.2.3 的 F1–F9）**，含"输入矛盾 → `FRC-UNKNOWN`"的判定与 `mp1_evidence_ref` 的输入留存 |
| 24e | **（v8.2，R18）`RP-4a` 三条前置与同句柄截断实现**（`ftruncate` / `SetEndOfFile`），含"平台不支持 → 中止"的分支 |
| 24f | **（v8.2，R15）`RECOVERY_PERMITTED` 与 `PR-1…PR-5` 复核实现**（重扫故障日志、重算 `WRITE_PERMITTED`） |

### C.3 尚未测试

| # | 事项 |
|---|---|
| 25 | 全部 **106** 条用例、**2188** 条断言（全部 `NOT EXECUTED`） |
| 26 | **`st_ino` / `file_index` 在 `%TEMP%` 卷上的稳定性与复用行为（BLK-1 的判定前提）** |
| 27 | **`os.fsync(目标句柄)` 在 NTFS 上的实际保证边界（BLK-2）** |
| 28 | junction / 符号链接创建权限 |
| 29 | `LockFileEx` 对内存映射写是否有效 |
| 30 | 实现是否按 1 MiB 升序分块（影响 S2 / S5b 偏移与写游标） |
| 31 | 读取器版本与 `sharedassets3.assets` 兼容性 |
| 32 | **同句柄截断**（`ftruncate` / `SetEndOfFile`）在 NTFS 上的可用性与原子性（影响 S9d / S9h，v8.2 改写） |
| 33 | 临时目录剩余空间（估算 < 1.4 GB） |
| 34 | 恢复链 ≥3 层的行为 |
| 35 | 检查点与身份采集在高频写入下的额外开销 |
| 36 | **（v8）`os.link` / `CREATE_NEW` 在 NTFS 上的并发语义与错误码（S1f–S1h 的判定前提）** |
| 37 | **（v8）`VERIFIED_MANUAL` 下 T2 / T4 的实际拒绝路径（BLK-5）** |
| 38 | **（v8）组合 #5a 且 `manual_epoch != null` 的变体**（S14 覆盖说明中标 `UNCOVERED`） |
| 38b | **（v8.2，R18）`ftruncate` / `SetEndOfFile` 在目标卷上的可用性与失败 errno 集合**（S9h 的判定前提） |
| 38c | **（v8.2，R16）`FAULT_CLASS` 派生在真实故障样本上的一致性**：同一状态多次派生是否稳定、MP-1 记录与派生结果是否总能对齐（S10f / S10g 的判定前提） |
| 38d | **（v8.2，R15）`PR-1` 重扫在真实 `wal_failures` 增量写入下的可观测性**（S7j 的判定前提） |

### C.4 理论残余风险

| # | 事项 |
|---|---|
| 39 | 各 digest 的 SHA-256 碰撞（用 count + 完整列表 + 长度缓解，不声称绝对） |
| 40 | 生产构建中钩子残留（靠 STA-5 缓解，非形式化证明） |
| 41 | 真实掉电 / 强制关机 / 真实 ENOSPC 语义完全未覆盖 |
| 42 | 身份字段四元组（`st_dev` + `st_ino` + `volume_serial` + `creation_time`）叠加仍非形式化证明 |
| 43 | V-T 只能在**下一次扫描**发现"END 之后"的改动；两次扫描之间的窗口不可检出 |
| 44 | **（v8）快照发布"预检"与"原子创建"之间的 TOCTOU 窗口**：预检只用于早失败，真正保证来自原子创建；若实现退回"预检 + `os.replace`"，窗口重新出现 |
| 45 | **（v8）`CP-R` 之后历史不可回溯**：`manual_epoch` 只记录"重建时的事实"，无法还原重建前的 WAL 语义 |
| 46 | **（v8.1，M3）检查点更新的两步操作不具原子性**：`CR-e` 情形 2 的"旧代改名 + 新代发布"是两次独立文件系统操作；进程崩溃行为可判定（判 `ABSENT_DIRTY`），但**掉电**下两种中间态的可见性**无法保证**（依赖目录项持久化，BLK-4）→ **`UNVERIFIABLE`** |
| 48 | **（v8.2，R18）同句柄截断的掉电可见性**：`ftruncate` / `SetEndOfFile` 设置长度后、元数据落盘前掉电，长度可能是 `tail_offset` 也可能是 `wal_size_before`；A.6.4 已按两种结果分流（后者 → `RECOVERY_REQUIRED`），但**本方案不保证**任一结果必然出现 → `UNVERIFIABLE` |
| 49 | **（v8.2，R16）`FAULT_CLASS` 的稳定性**：派生依赖多个 V-x 结论的**同一时刻快照**；若扫描期间状态发生变化，派生结果可能对应一个从未同时存在的组合。A.2.3 未规定"派生必须基于单次扫描的原子快照"，该风险**待决**（C.1 第 10 条） |
| 47 | **（v8.1，M4）`SNAPSHOT_PUBLISH_UNSUPPORTED` 在目标卷上的实际触发条件未测**：`EXDEV` / 硬链接不支持 / `EPERM` 的具体 errno 与卷类型相关，静态文本无法判定（与 C.3 第 36 条同源） |
| 50 | **（v8.3，N-01）自动 `CP-5` 的两步发布不具原子性**：CP-5b（旧代改名）与 CP-5c（新代发布）是两次独立文件系统操作；进程崩溃行为可判定（`ABSENT_DIRTY` → `MANUAL_BLOCKED`，S10i），但**掉电**下中间态的可见性**无法保证**（依赖目录项持久化，BLK-4）→ **`UNVERIFIABLE`** |
| 51 | **（v8.3，N-01）检查点旧代数量无上限**：每次成功推进产生一个 `pre_advance.*`；本方案规定"不自动删除"（A.5.11.4），**容量治理未设计**，须由人工在测试阶段评估 |

### C.5 路径确认状态

| 文件 | 状态 | 依据 |
|---|---|---|
| `validation\roundtrip_sharedassets1.assets` | `PATH_VERIFIED` | CAP-014.4 台账 |
| `validation\roundtrip_sharedassets10.assets` | `PATH_VERIFIED` | CAP-014.4 台账 |
| `validation\roundtrip_sharedassets3.assets` | `PATH_VERIFIED` | CAP-014.4 台账 |

**无 `PATH_UNVERIFIED` 项。**

---

# D. 本轮修改项与执行边界

### D.1 本轮修改项

| 编号 | 修改 | 涉及章节 |
|---|---|---|
| **R1** | **写游标语义**：新增 A.8.1.1（块写入模型、`H3(k)` 位置、已完成前缀 `[0,k·1MiB)`、两条判据）；S5b-1 改为 `k=32` + `40 MiB`（未写区 → **不可检出**）、S5b-2 改为 `k=48` + `40 MiB`（已完成前缀 → **必须检出**）；补充"外部写入确实落地"的前置断言；显式声明 `MODEL_UNREACHABLE`；统一"不可检出不计入检出"的统计口径 | A.1.2 / A.2.2 / A.8.1 / **A.8.1.1** / A.8.3 / A.15 / A.17-S5 / A.18 / A.19 / A.20 / A.21 / B / C.1 / C.3 |
| **R2** | **`END` 四阶段**：ORD-5 拆为 ORD-5a（阶段①，可证明无 `END`）/ ORD-5b（阶段②，持久性未知，禁重写）+ ORD-6 限定阶段③ + 新增 ORD-7；A.8.2 增"`END` 四阶段判定表"；新增 S13d/S13e/S13f；A.15 新增第 13 行；强化 S13 核心断言（阶段不可混判） | A.4.1 / A.4.2 / A.7.1 / **A.8.2** / A.12.2 / A.15 / A.17-S13 / A.18 / A.19 / A.20 / B |
| **R3** | **T5 / `MANUAL_BLOCKED` / 未解决操作闭环**：新增 A.7.9（MP-1 调查、MP-2 签核、未解决集合非空时的唯一出口）；T5 改三阶段（`MANUAL_RESET` → `CP-R` → 重新扫描）；新增 A.5.10 `CP-R` 与 `VERIFIED_MANUAL` 检查点状态；A.7.4 闭包表补两行；T2-2 / T4 明确拒绝 `VERIFIED_MANUAL`；A.14.4 签核补 5 个字段；新增 S15a–S15e；新增 **BLK-5** | A.1.2 / A.2.1 / A.2.2 / A.4.1 / A.4.2 / **A.5.10** / A.7.1 / A.7.3 / A.7.4 / A.7.5 / A.7.8 / **A.7.9** / A.14.4 / A.15 / A.17-S15 / A.18 / A.19 / A.20 / A.21 / A.22 / C.1 |
| **R4** | **快照发布不覆盖**：A.11.1 由 `os.replace` 改为原子"目标不存在才创建"（`os.link` / `CREATE_NEW`）九步；新增 `SNAPSHOT_CONFLICT` 状态与禁止清单；新增 A.11.3 同名冲突人工判定；新增 S1f/S1g/S1h；A.15 新增第 14 行 | A.2.1 / A.2.2 / **A.11.1** / A.11.2 / **A.11.3** / A.15 / A.17-S1 / A.18 / A.19 / A.20 / A.22 / C.2 / C.3 / C.4 |
| **R5** | **WAL 缺失 / 空检查点 / 身份关系**：新增 A.5.7.7（WAL 不存在时的身份适用边界）；V-0 补充"WAL 不存在不得声称已验证句柄身份"与"检查点记录非零身份 → `INCONSISTENT`"；A.5.7.4 增两行；A.5.9 增 R5 六类映射、身份列与第 4 条硬规则；新增 S14g/S14h，**关闭 v7 的"组合 #5a 无用例"缺口** | A.2.1 / **A.5.6** / A.5.7.4 / **A.5.7.7** / **A.5.9** / A.17-S14 / A.18 / A.19 / A.20 / C.3 |
| **R6** | **S5g 的 V-T 哈希来源绑定**：`END` 增 `target_hash_provenance{stage, precommit_recheck_verified, verified_sha256, verified_before_seq}`；新增通用断言 **C18**（哈希必须来自 ST-11，H6 之后重算即判失败）；A.2.2 增红线 15；A.21 声明 V-T 仅延迟检测 | A.2.2 / A.4.1 / A.5.6 / A.8.2 / A.17-S5 / A.17-S13 / A.18 / **A.19.1** / A.20 / A.21 / C.2 |
| **自检修正（v8 内部）** | ① **补齐 C1–C18 的逐条定义**（v7 声明 17 条却无任何定义，属可核查性缺陷）；② **通用断言 17 → 18**，全套统计重算（76/17/201/1493 → **89/18/235/1837**，派生上界 68/68/64 → **81/81/77/76**）；③ 修正 4 处 `S5b-2` → `S5b-1` 的"不可检出"指代（A.19.2 第 10 条 / A.20 / A.21 / C.1 第 1 条）；④ S9 标题声明数与实列数已一致（7 条）；⑤ 消除 `S5b` 裸引用歧义（S5 组标题与两处小标题改为 `S5b-1 / S5b-2`） | A.2.2 / A.17 / A.18 / **A.19** / A.20 / A.21 / B / C |

### D.1b 本阶段修改项（v8 → v8.1，仅 P0）

| 编号 | 修复内容 | 对应问题 | 涉及章节 |
|---|---|---|---|
| **M1** | `VERIFIED_MANUAL` 的授权边界：`A.7.8` / `PWA-6` 的集合扩为 `{VERIFIED, VERIFIED_MANUAL, ABSENT_CLEAN}`，并给出**四项否决条件**（`manual_epoch` / BLK-5 = `DECIDED_ACCEPT` / 签核接受 / `OP_UNRESOLVED == ∅`）+ **真值表**（5 行，逐行验证 `VERIFIED_MANUAL` 的合取结果）；`A.2.1` 增"授权边界"段 | **F-01** | A.2.1 / **A.7.8** / **A.10.1 PWA-6** / A.7.9 / A.18 / A.19.2 / A.20 / A.17-S15 |
| **M2** | `CR-6` 拆 **(a)(b)(c)**；`A.7.4` 增"身份类 `MANUAL_BLOCKED` 无出口"行；`A.2.1` / `A.7.3` T5 行 / `A.7.9.3` / `A.15 #10` / `S15f` 同步；明确**不得**以签核或 `VERIFIED_MANUAL` 把身份不匹配转为写入许可 | **F-02** | **A.2.1** / **A.5.10 CR-6** / **A.7.3** / **A.7.4** / **A.7.9.3** / **A.15 #10** / A.17-S15 / A.18 / A.19.2 / A.20 / C.1 |
| **M3** | `CR-e` 改**三情形**（不存在→创建 / 已存在→旧代改名保留后发布 / 失败→中止）；定义**中间态**（`ABSENT_DIRTY`）；`A.2.2` 增红线 16；`A.11.1` 增"适用范围"表（快照 vs 检查点）；新增 `pre_rebuild_checkpoint_sha256`；**`UNVERIFIABLE` 声明** | **F-03** | **A.2.2** / **A.5.10 CR-e** / **A.11.1** / A.17-S10 / A.18 / A.19.2 / A.20 / A.21 / C.2 / C.4 |
| **M4** | `A.11.1` ⑤ 改 `MoveFileExW(tmp, final, 0)`；**禁止** `CreateFileW(CREATE_NEW)` 直接写最终名；新增 **`SNAPSHOT_PUBLISH_UNSUPPORTED`** 状态并区分 `EXDEV`/`EPERM`/`ERROR_NOT_SUPPORTED` 与 `ERROR_ALREADY_EXISTS`；`A.11.2` 增区分表；新增 `S1i` / `S1j` | **F-04** | **A.2.1** / **A.11.1** / **A.11.2** / A.17-S1 / A.18 / A.19.2 / A.20 / C.2 / C.4 |
| **M5** | `PWA-8` 由 `BLK-1…BLK-4` 改为 **`BLK-1…BLK-5`**；任一未决即 `FAIL`；`A.10.1` 规则④、`A.22` 数量唯一来源段、`A.19.2` 第 10 条、`E` 第 2 条同步 | **F-05** | **A.10.1 PWA-8** / **A.22** / A.19.2 / A.18 / **E** |
| **M6** | `A.5.9` #1 的"干净初始"改"**当且仅当 ALL-GONE 成立**"；ALL-GONE 由 5 项扩为 **7 项**（增恢复记录、签核记录）并增"不可读/矛盾"判定与"三项判定结果"；硬规则 4 的枚举补 **#1**；映射表备注改为引用硬规则 4；新增 **`S14i`** | **F-06** | **A.5.9** / A.17-S14 / A.18 / A.19.2 / A.20 / C.1 |

> **（v8.2 注）** 上表 **M2** 行的"`CR-6` 拆 (a)(b)(c)"是 **v8.1 的历史记录**，其结论已被 v8.2 的 **CR-6 两轴表**（A.5.10）取代——(a)/(c) 两类的重叠已消除，`CR-6` 不再有 (c) 类。阅读 M2 时以 A.5.10 的现行文本为准。

**本阶段明确未处理**（留待后续）：

- **P1 × 6**：F-07（`A.5.7.7` 范围过窄）/ F-08（空态命名未定义）/ F-09（派生上界口径混用）/ F-10（S1 的 `READY` 语义）/ F-11（首次写入顺序与身份起点）/ F-12（C18 与证据包矛盾）。
- **P2 × 7**：F-13（`A.11.1 八步` 陈旧引用）/ F-14（`A.4.3` 指向 `A.7.4`）/ F-15（`A.5.7` 子节乱序）/ F-16（`E` 漏 BLK-3/BLK-4）/ F-17（同卷要求与不支持分支）/ F-18（`S1c` 无期望与断言）/ F-19（`S13e` 缺 2 个重扫分支）。
- 因此 **`S14j` 未新增**（对应 F-11 / M11，留待后续 P1 阶段）。

### D.1c 本阶段修改项（v8.1 → v8.2，7 项核心逻辑）

| 编号 | 修复内容 | 对应要求 | 涉及章节 |
|---|---|---|---|
| **R16** | 新增 **A.2.3 `FAULT_CLASS` 有序派生（F1–F9 + 三条不变量）**；`CR-6` 由"三类主观分裂"改为**两轴表**（`FAULT_CLASS` × `WAL_IDENTITY_STATUS`）；**删除 (c) 类**，消除 `IDENTITY_UNVERIFIABLE` 在 (a)/(c) 的重叠；`A.2.1` / `A.5.7.4` / `A.7.3` / `A.7.4` / `A.7.9.3` / `A.14.4` / `A.15 #10` / `A.18` 同步；新增 S10f / S10g | **R16** | A.2.1 / **A.2.2 红线 17** / **A.2.3** / A.5.7.4 / **A.5.10 CR-6** / A.7.3 / A.7.4 / A.7.9.3 / A.14.4 / A.15 / A.17-S10 / A.18 / A.19.2 / A.20 / A.21 / C.1 / C.3 / C.4 |
| **R18** | `RP-4` 由 `os.truncate(path, ...)` 改为**同句柄** `ftruncate` / `SetEndOfFile`；新增 **RP-4a** 三条前置（句柄连续 / `fstat` 身份与大小 / 独占写者）；RP-4b 降为**附加**复核；新增 **A.6.5**（TR-1…TR-6，含"平台不支持即中止"与"禁止以事后复核替代事前保证"）；`A.6.4` 增两行；新增 S9h / S9i | **R18** | **A.2.2 红线 18** / **A.6.2** / **A.6.4** / **A.6.5** / A.17-S9 / A.18 / A.19.2 / A.20 / A.21 / C.3 / C.4 |
| **R14 + R19** | 引入 **`T5*` 记号**并在 A.7.6 给出六条统一规则；A.7.3 T5 行改**四条硬前提**；A.7.6 的 **6 处"仅 T5"** 全部改写并补身份列；A.7.7 拆分"检查点 `INCONSISTENT`"与"身份不一致"两行；A.15 #4/#9/#11 改 `T5*`、#10 改按 `FAULT_CLASS`；A.17 的 S7e / S7f / S11a / S11c / S11d 同步；新增 S7i | **R14 / R19** | **A.2.2 红线 19** / A.7.3 / **A.7.6** / A.7.7 / A.7.9.3 / A.15 / A.17-S7 / A.17-S11 / A.18 / A.19.2 / A.20 |
| **R13** | A.7.1 增**判定优先级**（判 1 `UNKNOWN` → 判 2 `NO` → 判 3 `YES` → 判 4 兜底 `UNKNOWN`）与四条禁止；明确"宽泛 `NO` 不得覆盖更严 `UNKNOWN`"；新增 S10h | **R13** | **A.7.1** / A.17-S10 / A.18 / A.19.2 / A.20 |
| **R15** | 新增 **A.7.10**（三类写入分离 + `RECOVERY_PERMITTED` + **PR-1…PR-5** 恢复后强制复核）；A.7.3 T1/T2/T4 三行加"完成后必须按 A.7.10 复核"；明确 **PWA-6 只适用载荷写入**（解除"恢复需先满足 `WAL_STATE_COMPLETE == YES`"的循环依赖）；新增 S7j | **R15** | **A.7.3** / **A.7.10** / A.10.1 / A.17-S7 / A.18 / A.19.2 / C.2 |
| **R17** | `UNKNOWN` 明确为 **T2 的全局否决条件**（不依赖逐条推导）；A.7.3 T2 行 / A.7.4 出口行 / A.7.5 三处一致；A.7.8 与 PWA-6 增 **`ALL-GONE` 合取项（第 3b 行）**，真值表由 5 行扩为 6 行 | **R17** | A.7.3 / **A.7.4** / **A.7.5** / **A.7.8** / A.10.1 / A.18 |
| **ALL-GONE 统一** | `A.5.7.4` 表重写（增 `FAULT_CLASS` 列、"WAL 与检查点均不存在"行加 ALL-GONE、"仅 T5"改"无出口"、增命名澄清与四条硬规则）；`A.5.9` 增"唯一出处与五处统一"；A.7.1 `YES` 行加 ALL-GONE；A.22 增"ALL-GONE ≠ BLK"说明 | 第 5 项 / F-06 残留 | **A.5.7.4** / **A.5.9** / **A.7.1** / A.7.8 / A.10.1 / **A.22** / A.18 |
| **统计重算** | 用例 94 → **101**、专项 247 → **266**、通用 1692 → **1818**、总计 1939 → **2084**；`buffering=0` 变体 95/1959 → **102/2104**；派生上界链更新为 93 / 89 / 88，联合 **80**（**F-09 口径仍未修**）；修正 A.18 两处 v8 口径残留（89 / 235 / 1837） | 本轮新增 7 条 | A.17 / **A.18** / A.19.2 / **B** / C.3 / E |

**本阶段仍未处理**（沿用 v8.1 的清单，未新增、未删除）：

- **P1 × 6**：F-07（`A.5.7.7` 范围过窄）/ F-08（空态命名未定义 —— **v8.2 已补命名澄清段，但 `A.2.1` 的枚举本身未改，故仍按未闭合计**）/ F-09（派生上界口径混用）/ F-10（S1 的 `READY` 语义）/ F-11（首次写入顺序与身份起点）/ F-12（C18 与证据包矛盾）。
- **P2 × 7**：F-13（`A.11.1 八步` 陈旧引用）/ F-14（`A.4.3` 指向 `A.7.4`）/ F-15（`A.5.7` 子节乱序 —— **v8.2 在 A.5.7.4 与 A.5.7.7 之间新增内容，乱序依旧**）/ F-16（`E` 漏 BLK-3/BLK-4）/ F-17（同卷要求与不支持分支）/ F-18（`S1c` 无期望与断言）/ F-19（`S13e` 缺 2 个重扫分支）。
- **本轮新发现但未修（记入待决，不冒充已修）**：`N-01` —— `A.5.5` 的 **CP-5 仍用 `os.replace`** 发布检查点，与 `A.2.2` 红线 16"禁止直接覆盖旧检查点"、`A.11.1` 适用范围表"检查点 = 先保留旧代再发布"**互相矛盾**。CR-e 只约束了人工路径（`CP-R`），自动路径（CP-1…CP-6）未同步。该矛盾**属文档冲突**，本轮范围未含 `A.5.5`，故**未改**，列为待决。

### D.1d 本阶段修改项（v8.2 → v8.3 候选稿，仅 N-01 / N-04 / DD-1）

**范围声明**：本轮**只**处理三项——**N-01**（自动 `CP-5`）、**N-04**（T5 起点）、**DD-1**（组合 #3a 的 ALL-GONE）。**F-07～F-19 未处理**；**N-02（V-T 路由）/ N-03（F9 与 T4 的冲突）已记录、未修**；**BLK-1…BLK-5 一项未动**。

| # | 原章节 / 原规则 | 修改后 | 原因 | 交叉引用 | 测试影响 | 未验证 |
|---|---|---|---|---|---|---|
| **N-01-a** | `A.5.5` CP-5 = `tmp → fsync → os.replace → durable.json` | 拆为 **CP-5a**（写 tmp + fsync + 回读 tmp）/ **CP-5b**（旧代原子改名为 `pre_advance.*`）/ **CP-5c**（"不存在才创建"发布） | 红线 16 绝对禁止覆盖当代检查点，原 CP-5 直接违反 | `A.2.2` 红线 16 / `A.11.1` / `A.5.11` | S10j | 掉电中间态 `UNVERIFIABLE` |
| **N-01-b** | `A.5.5` 无 CP-5 适用前置 | 新增三条前置：旧代 ∈ {`VERIFIED`, `VERIFIED_MANUAL`, `ABSENT_CLEAN`}；`INCONSISTENT` / `ABSENT_DIRTY` 禁走 CP-5；`manual_epoch` 随代携带 | 否则 `VERIFIED_MANUAL` 会被自动推进**洗成** `VERIFIED`（A.5.10 硬规则 1 被绕过） | `A.5.10` 硬规则 1 / `A.5.11.6` | S10k | — |
| **N-01-c** | `A.5.5` 崩溃矩阵两行（"CP-5 中" / "CP-5 后"） | 换成三行：CP-5a 中 / **CP-5b 后 CP-5c 前 → `ABSENT_DIRTY`** / CP-5c 后 | 两步操作必须各有崩溃分支，中间态不得留空 | `A.5.11.3` | S10i | 同上 |
| **N-01-d** | 无 `A.5.11` | **新增 `A.5.11`**（职责分工 / 三种情形 / 中间状态 / 保留策略 / `generation` / 六条硬规则） | `A.11.1` 的 `pre_manual.<manual_epoch_id>` 只适用于人工路径，自动路径在 v8.2 中**没有任何**命名与保留规则 | `A.5.5` / `A.5.10` / `A.11.1` / `A.7.10` | S10i–S10k | 容量治理未解决（C.4 第 51 条） |
| **N-01-e** | `A.2.2` 红线 16 | 追加"同时约束自动 `CP-5` 与人工 `CP-R`"，并给出两条路径的旧代命名 | 原文只说"禁止覆盖"，未说明自动路径怎么做 | `A.5.11` | — | — |
| **N-01-f** | `A.11.1` 适用范围表"检查点"单行 | 拆成"自动 `CP-5`（依据 A.5.11）"与"人工 `CP-R`（依据 A.5.10 CR-e）"两行 | 单行把两条语义不同的路径混为一谈 | `A.5.11` / `A.5.10` | — | — |
| **N-01-g** | `A.5.2` 字段表 | 增 `checkpoint_generation` / `pre_advance_checkpoint_sha256`，并规定 `manual_epoch` 随代携带 | 旧代可追溯需要哈希；代际顺序需要单调计数 | `A.5.11.5` | S10j | — |
| **N-01-h** | `A.7.10` 状态写入行 | 发布语义引用增 `A.5.11` | 自动推进属状态写入，须指向细则 | — | — | — |
| **N-04-a** | `A.7.4` `RECOVERY_REQUIRED → READY` 人工出口 = "T2 / T5" | 改为"**仅 T2**"，并新增"T5 的起点不可达"三行推导表 | `RECOVERY_REQUIRED` 的三个入口各自撞掉 T5 的一条硬前提，T5 从该状态**结构上不可达** | `A.7.3` / `A.7.6` / `A.7.9` | S15g | — |
| **N-04-b** | `A.2.1` "人工出口（T2 / T5）" | 改为"**仅 T2**"；并修正"分裂为两类"→"**三类**"（v8.2 已加第三类，文字未同步） | 与 N-04-a 同一结论 | 同上 | — | — |
| **N-04-c** | `A.7.3` T5 行 | 增"**起点状态 = `MANUAL_BLOCKED`**"（置于四条硬前提之前） | 起点是前提，不是结果 | `A.7.4` | S15g | — |
| **N-04-d** | `A.7.6` 六条统一规则 | 增第 7 条：`T5*` 的读法含"起点为 `MANUAL_BLOCKED`" | 表格里的 `T5*` 不能脱离起点读 | — | — | — |
| **N-04-e** | `A.7.9` 原则段 | 增"起点唯一"一段 | 与 `A.7.4` 对齐 | — | — | — |
| **N-04-f** | `A.7.11` `RECOVERY_REQUIRED` 禁止列 = "未解决集合非空时的 T5" | 改为"**T5**（起点只能是 `MANUAL_BLOCKED`）" | 原写法暗示"未解决集合为空时可以从 `RECOVERY_REQUIRED` 走 T5" | — | — | — |
| **N-04-g** | `A.15` 补充段 | 增一句：所有 `T5*` 行的"预期运行状态"均为 `MANUAL_BLOCKED` | 表格与状态机对齐 | — | — | — |
| **N-04-h** | `A.19.2` 第 4 条 | 增"`T5` 只在 `MANUAL_BLOCKED` 下被调用" | 通过标准须可判定 | — | S15g | — |
| **DD-1-a** | `A.5.9` 硬规则 4 第二项："#3a / #5a 必须同时满足空态六项，且 **WAL 不存在时**同样必须满足 ALL-GONE" | 改为"#3a / #5a **同样必须满足 ALL-GONE ①–⑦**" | v8.2 在硬规则 4 与 R5 映射表之间自相矛盾；**DD-1 经人工裁定从严**（0 字节与"不存在"在旁证要求上等价） | `A.5.9` 硬规则 2 / R5 映射表 | S14d / S14j | — |
| **DD-1-b** | `A.5.9` 表行 #3a / #5a：干净 = "是"、`READY` = "允许"、写入 = "允许"（**无条件**） | 三列全部改为"**当且仅当 ALL-GONE 成立**" | 表行不得绕过定义（A.5.9 自述的"唯一出处"规则） | 同上 | S14d / S14j | — |
| **DD-1-c** | 无 `EMPTY_STATE` 谓词 | 新增 `EMPTY_STATE`（组合 ∈ {#1, #2, #3a, #5a}），并规定 `A.7.1` / `A.7.8` / `A.10.1` / `A.5.7.4` **只允许引用它** | v8.2 的合取项只写 `ABSENT_CLEAN`，**把 #3a / #5a 漏在 ALL-GONE 之外** | `A.7.1` / `A.7.8` / `A.10.1` / `A.5.7.4` | — | — |
| **DD-1-d** | `A.7.1` `YES` 行的 ALL-GONE 条件只挂 `ABSENT_CLEAN` | 改为挂 `EMPTY_STATE == true` | 同上——这是 v8.2 的**实质漏检**，不只是措辞 | — | — | — |
| **DD-1-e** | `A.7.8` 第 3b 行 / 真值表 / 结论 5；`A.10.1` PWA-6 | 四处同步改为 `EMPTY_STATE == false` | 四处必须逐字同构（M1 的既有要求） | — | — | — |
| **DD-1-f** | `A.5.7.4` 硬规则 2 | 增"表外的 #3a 同样适用 ALL-GONE" | 该表无 #3a 行，容易漏 | — | S14j | — |
| **DD-1-g** | `A.22` 规则段 / `A.18` 空态行 | 把"空态"改为 `EMPTY_STATE` 并列出四个组合 | 与谓词对齐 | — | — | — |

### D.2 执行边界声明

- 本轮**仅完成文档修订**（v8.1 → v8.2，且**只处理 R13–R19 + ALL-GONE 统一**），输出即本文件。
- **未执行任何 P1 测试**：S0a–S15g 共 **106** 条全部 `NOT EXECUTED`。
- **未编写或实现任何功能代码**：WAL、`.durable`、身份采集、`LockFileEx`、恢复、快照、签核、T5、`CP-R` 均未实现。
- **未修改任何项目源代码、配置文件、Git 状态或其他文件**；**v7 / v8 / v8.1 与静态审查报告均未被覆盖、删除或改名**。
- **未对任何真实 `.assets` 执行写入、删除、移动、重命名或覆盖**（含 17 个 L0-A、14 个 L0-B、3 个 L0-D）。
- **未写入或修改任何备份、快照、WAL、检查点或验证数据。**
- **未使用 `--apply`，未运行任何资产写回入口。**
- **未创建测试资产、临时资产或测试输出。**
- **未修改 baseline ledger。**
- **未执行任何 Git 写操作**（add / commit / reset / clean / checkout / switch / stash）。
- **未调用 Hermes**，未安装或更新依赖。
- 本轮只读动作：确认项目根、检查 v8.2 是否存在（`V82_ABSENT_OK`）、计算 v8 / v8.1 的 SHA-256、完整读取 v8.1 全文（1,808 行）与静态审查报告；**v8 与 v8.1 均未被覆盖、删除或改名**（两者 SHA-256 在写入前后一致）。

**静态文档检查不等于测试通过。**

### D.3 静态自检记录（v8.2，历史；v8.3 见 D.3c）

> 下表结果由独立只读脚本对 v8.2 全文**重新计算**得出（不采信文档自报值），未修改任何文件。

| # | 检查项 | 方法 | 结果 |
|---|---|---|---|
| 1 | 小节定义与交叉引用 | 抽取全部 `A.x[.y[.z]]` 引用与 `^#{2,4}` 定义比对 | 定义 **91** / 引用 **91** / 悬空 **0** → PASS |
| 2 | 用例 ID 与分组声明 | 逐组比对"标题声明数"与"实际 ID 集合"（S2 为单条无后缀用例，按 +1 计） | **16 组全部一致**，合计 **101** → PASS |
| 3 | 断言算术 | `Σ(用例数 × 每条)` 与 `101 × 18 + 266` 双向核对 | 专项 **266** / 通用 **1818** / 总计 **2084** → PASS |
| 4 | R13–R19 + ALL-GONE 落位 | 检索新增小节与修订标记 | **8/8** 落位 → PASS |
| 5 | `T5*` 全文一致 | 检索 `T5*`（55 处）与"仅 T5"（11 处） | 55 处均为"条件式出口"；10 处"仅 T5"**全部**为禁止/历史说明，**无一处**作为路径授权 → PASS |
| 6 | `CR-6` 旧分类残留 | 检索 `CR-6(a)` / `CR-6(c)` | 各 3 处，**全部**为"v8.1 的 (a)/(c) 重叠已消失"的历史说明或自检描述 → PASS |
| 7 | 截断语义唯一 | 检索 `os.truncate`（8 处） | 8 处**全部**为禁止 / 缺陷描述 / 历史记录，**无一处**作为可执行步骤 → PASS |
| 8 | `FAULT_CLASS` 五处一致 | `A.2.3`（23 处引用）/ `CR-6` 两轴表（9 处）/ `A.7.4` / `A.14.4`（`fault_class` 4 处）/ `A.15 #10` | 五处齐备且结论一致 → PASS |
| 9 | 判定优先级三处一致 | `A.7.1` 文字 / `A.7.4` 表格 / `A.7.5` 真值表 | 三处齐备，`UNKNOWN` 均排在 `NO` 之前 → PASS |
| 10 | `UNKNOWN` 全局否决 | `A.7.3` T2 行 / `A.7.4` 出口行 / `A.7.5` | 三处均写明 `!= UNKNOWN` → PASS |
| 11 | ALL-GONE 唯一出处 | `A.5.9` 定义（全文 56 处引用）+ 其余五处仅引用 | 定义仅 **1** 处；`A.5.7.4` / `A.7.1` / `A.7.8` / `A.10.1` / `A.22` 均为引用 → PASS |
| 12 | 恢复后复核 | `A.7.10`（18 处引用）/ `PR-1`（17 处）/ T1·T2·T4 三行 | 三行均指向 A.7.10 → PASS |
| 13 | 全部用例未执行 | 检索 `NOT EXECUTED`（9 处，覆盖头部 / 阶段表 / B / C.3 / D.2 / E） | 全部保留，**无一处**声称已执行 → PASS |
| 14 | `WRITE_PERMITTED` 保持 `NO` | 检索 `= YES`（1 处）/ `= NO`（8 处） | `YES` 仅出现在条件式定义中；结论仍为 `NO` → PASS |
| 15 | BLK 数量一致 | `PWA-8` / `A.22` / `A.19.2` 第 10 条 / 头部阶段表 / `E` | 全部为 **5 项（BLK-1…BLK-5）** → PASS |
| 16 | 上游未被修改 | 写入前后 `sha256sum` 比对 | v8 `c864625b…48659`（135,620 B）/ v8.1 `b5cc4668…9ae50f`（166,205 B）均未变 → PASS |
| 17 | 统计口径残留 | 检索 `五项旁证`（0）/ `94 条`（0）/ `89 条`·`1837`·`1939`（5） | 前两项已清零；后 4 处**全部**在"v8 / v8.1 历史对照列"或自检描述中 → PASS |

**FAIL 项：0。**

#### D.3b 自检覆盖不到的项与仍待决项

| # | 项 | 状态 |
|---|---|---|
| 1 | Windows 文件系统持久化语义（`FlushFileBuffers` 边界、目录项持久化） | **未验证**（BLK-2 / BLK-4） |
| 2 | 文件身份连续性（`st_ino` 稳定性、索引复用） | **未验证**（BLK-1） |
| 3 | 断电恢复行为（`CR-e` 两步操作、同句柄截断的长度可见性） | **`UNVERIFIABLE`**（C.4 第 46 / 48 条） |
| 4 | `ftruncate` / `SetEndOfFile` 在目标卷上的可用性 | **未测**（C.3 第 32 / 38b 条） |
| 5 | `FAULT_CLASS` 派生在真实故障样本上的一致性 | **未测**（C.3 第 38c 条；判据阈值属 C.1 第 10 条待决） |
| 6 | 106 条用例、2188 条断言 | **全部 `NOT EXECUTED`** |
| 7 | **`N-01`**：`A.5.5` 的 CP-5 仍用 `os.replace`，与红线 16 / `A.11.1` 适用范围表冲突 | **已修**（v8.3：CP-5a/5b/5c + A.5.11，见 D.1d） |
| 10 | **`N-02`**：`A.7.1` 把 V-T 失败判 `UNKNOWN`，而 `A.7.4` 首行与 S5g 期望它进 `RECOVERY_REQUIRED` | **未修**（v8.3 新发现，范围外） |
| 11 | **`N-03`**：`A.2.3` 的 F9 = `FRC-UNKNOWN` 会命中"纯 `PROVISIONAL`"状态，与"`FRC-UNKNOWN` 禁止一切自动路径"合起来会封死 T4 | **未修**（v8.3 新发现，范围外） |
| 12 | **`N-04`**：T5 被写成 `RECOVERY_REQUIRED` 的出口，结构上不可达 | **已修**（v8.3：起点唯一化为 `MANUAL_BLOCKED`，见 D.1d） |
| 8 | F-07～F-19（P1 × 6 + P2 × 7） | **未处理** |
| 9 | BLK-1…BLK-5 | **全部未决**；本轮**未作任何决策**，也未把任何一项标为已解决 |

**结论**：静态自检只能证明"文档内部一致"，**不能**证明"实现正确"或"运行安全"。上表 1–12 项均**不因** D.3 / D.3c 的 PASS 而改变。

#### D.3c v8.3 候选稿静态自检记录（实测，53 项全 PASS，0 FAIL）

**执行方式**：独立 Python 静态脚本，**只读文本**，不执行任何项目代码、不访问真实资源。计数**从正文用例 ID 与 B 表逐行数据重新计算**，不采信文档自报总数。

| 组 | 检查内容 | 结果 |
|---|---|---|
| **A 计数（6）** | ① 16 组"标题声明数"vs"实际 ID 集合"；② 用例总数 = 106；③ 每组 `用例数 × 每条 == 小计`；④ 专项 = 280；⑤ `106 × 18 + 280 = 2188`；⑥ B 表 106 / 280 / 1908 / 2188 四数齐备 | **6/6 PASS**（16 组全部一致；`S3d` 为 B 表声明的条件性补充用例，已显式排除） |
| **B 交叉引用（1）** | 全文 `A.x[.y[.z]]` 定义 vs 引用 | **PASS**：定义 **98** / 引用 **76** / **悬空 0** |
| **C ALL-GONE / DD-1（11）** | `EMPTY_STATE` 谓词已定义；硬规则 4 已去"WAL 不存在时"限定；#3a 表行收紧；#5a 表行收紧；`A.7.1 YES` 挂 `EMPTY_STATE`；`A.7.8` 第 3b 行改 `EMPTY_STATE`；`PWA-6` 改 `EMPTY_STATE`；旧 `ABSENT_CLEAN` 合取项**清零**；`A.5.7.4` 硬规则 2 提到 #3a；`S14j` 入正文；`S14d` 加 ALL-GONE 前置 | **11/11 PASS** |
| **D CP-5 / N-01（10）** | CP-5 拆三段；CP-5 不再以 `os.replace` 为步骤；`A.5.11` 存在；`A.5.11.6` 六条硬规则；红线 16 覆盖自动路径；`A.11.1` 表拆两行；代际字段已加；S10i / S10j / S10k 入正文；"CP-5b 后 CP-5c 前"判 `ABSENT_DIRTY`；`VERIFIED_MANUAL` 不升格规则存在 | **10/10 PASS** |
| **E T5 / N-04（10）** | `A.7.4` 出口行去 T5；`A.2.1` 去 T5 出口；`A.2.1` 三类修正；`A.7.3` 增起点状态；`A.7.6` 第 7 条；`A.7.9` 起点唯一；`A.7.11` 禁止列已改；`S15g` 入正文；"T5 的起点不可达"推导表存在；旧写法 `T2 / T5` **清零** | **10/10 PASS** |
| **F 执行边界（6）** | `NOT EXECUTED` 保留（9 处）；无"已执行 / 已通过"声称；`WRITE_PERMITTED` 结论仍 `NO`；PWA-8 仍 5 项；A.22 仍 5 项；BLK-5 未被标为已决 | **6/6 PASS** |
| **G 版本与范围（9）** | 最终横幅含 `CANDIDATE`；D.1d 变更清单存在；E 节未虚报；旧版数字仅出现在历史对照列（无"现行"表述）；106 条现行表述存在；`S3d` 明确为条件性补充；F-07～F-19 未标已修；`N-02` / `N-03` 已登记未修 | **9/9 PASS** |

**FAIL 项：0。**

**本脚本的局限（不得据此推断已安全）**：

1. 只能判断**文本一致性**；无法验证 Windows 持久化语义、`st_ino` 连续性、断电可见性、`ftruncate` / `SetEndOfFile` 在目标卷的可用性（BLK-1 / BLK-2 / BLK-4）。
2. "CP-5b 后、CP-5c 前"的崩溃分支只在**文本层面**自洽，**未经真实文件系统验证**（C.4 第 50 条，`UNVERIFIABLE`）。
3. 无法评估 `A.5.11.4`"旧代不自动删除"在长期运行下的**容量影响**（C.4 第 51 条）。
4. **无法验证任何用例的实际结果**——106 条全部 `NOT EXECUTED`。
5. 检查脚本自身的匹配规则若写错，会同时漏检与误报（本轮已两次修正：`S5b` 子项重复计数、`S3d` 条件性用例被计入基线）；**脚本通过 ≠ 文档无缺陷**。

---

# E. 最终状态

```
CANDIDATE — N01_T5_ALLGONE_FIXES_COMPLETE — REVIEW_REQUIRED — NOT AUTHORIZED FOR EXECUTION
```

**后续审查要求**：

1. 人工逐条审查 **N-01 / N-04 / DD-1 三项**是否闭合，特别是 **`A.5.11` 全文（N-01）**、**`A.7.4`"T5 的起点不可达"（N-04）**、**`A.5.9` 的 `EMPTY_STATE` 谓词与 `A.7.1` / `A.7.8` / `A.10.1` 三处合取项（DD-1）**。
2. 对 **BLK-1（文件身份）**、**BLK-2（持久化顺序）**、**BLK-3（日志与检查点同时不可持久化）**、**BLK-4（目录项持久化）**、**BLK-5（`VERIFIED_MANUAL` 语义）** 逐项作出决策：接受为"未覆盖"、另行设计，或放弃该保护路径。**本轮未解决任何一项 BLK**，也未把任何一项标为已解决。
3. **106 条用例、2188 条断言仍全部 `NOT EXECUTED`**；未实现项 **21 类**（C.2）、未测试项 **17 项**（C.3）、残余风险 **13 项**（C.4 第 39–51 条），均需保持标注。**另有 2 项本轮新发现、范围外未修的文档冲突（`N-02` V-T 路由 / `N-03` F9 与 T4），见 D.3b。**
4. v8.3 审查通过前，不得进入 P1 测试执行、功能实现、基线认定或真实资产写入阶段；**F-07～F-19（P1 × 6 + P2 × 7）未处理**，**`N-02` / `N-03` 未修**，均不得视为已闭合。
5. **本文件是"3 项文档修复完成 + 静态自检通过"的候选稿（阶段 ① + ②，且仅就这 3 项而言），不是安全功能验收，也不授权真实资产写入**（阶段 ③–⑥ 均为"否"，见头部阶段状态表）。

---

```
CORE_LOGIC_FIXES_COMPLETE — REVIEW_REQUIRED — NOT AUTHORIZED FOR EXECUTION
```
