# CAP-014 P1 防护方案 v6

> **REVIEW_REQUIRED — NOT AUTHORIZED FOR EXECUTION**
>
> 本文档为纯设计文本。全部测试用例处于 `NOT EXECUTED` 状态。
> 未经人工审查与书面授权，不得进入 P1 测试执行、功能实现或真实资产写入阶段。

| 项 | 值 |
|---|---|
| 文档版本 | **v6** |
| 上游版本 | v5（仅以会话文本形式存在，项目内无对应文件） |
| 修订依据 | 上一轮审查的 4 项 P0（P0-1 检查点绑定 / P0-2 T2 误入 / P0-3 RP-6 冲突 / P0-4 roundtrip 边界） |
| 文档性质 | PLAN-ONLY，静态文本 |
| 执行状态 | 全部用例 `NOT EXECUTED` |

---

# A. 完整方案

## A.1 边界与命名约定

### A.1.1 四级禁写边界（P0-4 修订：新增 L0-D）

| 级别 | 对象 | 允许 | 禁止 |
|---|---|---|---|
| **L0-A** | `D:\BaiduNetdiskDownload\意大利黑1\Guns, Gore and Cannoli\ggc_Data\*.assets`（17 个） | 仅 `open(...,'rb')`、`os.stat` | 写 / 删 / 移 / 改名 / 覆盖 |
| **L0-B** | `D:\AI\Guns, Gore and Cannoli from WB\backup\**\*.assets`（14 个） | 同上 | 同上；测试快照不得写入此目录 |
| **L0-C** | `F:\GGC_snapshots\baseline_ledger.json` | 只读 | 覆盖 / 追加 / 改名 |
| **L0-D** | 3 个零字节 `roundtrip_*.assets` 验证文件（见 A.1.3） | 仅 `os.stat`、`open(...,'rb')` | 写 / 删 / 移 / 改名 / 覆盖；**不得作为基线、原始资产或测试目标** |
| **L1** | `%TEMP%\ggc_p1\**` | 唯一允许写入的根 | — |

**不重叠原则**：34 个已知 `.assets` 每个只归属一个级别，分类见 A.1.4。

### A.1.2 命名约定

| 记号 | 含义 |
|---|---|
| `S<组><字母>` / `S<组>` | 测试用例 / 场景组 |
| `ST-<n>` | 被测操作步骤（A.8） |
| `H<n>` | M9 屏障钩子位置 |
| `RP-<n>` | 尾部修复步骤（A.6） |
| `CP-<n>` | 检查点更新步骤（A.5.3） |
| `T-<id>` | 测试目标类型 |
| `T1/T2/T3/T4` | 状态解除途径 |
| `PWA-<n>` / `STA-<n>` | 生产 / 测试准入条件 |
| `C<n>` / `M<n>` | 通用断言 / 注入手段 |

### A.1.3 三个 `roundtrip_*.assets` 的精确路径（P0-4）

**来源**：`F:\GGC_snapshots\baseline_ledger.json`（CAP-014.4 产出，34 条记录）。以下路径逐字复制自台账 `normalized_absolute_path` 字段，未拼接、未推测。

| # | 精确路径 | 大小 | SHA-256（前 16 位） | entity_type |
|---|---|---|---|---|
| 1 | `D:\AI\Guns, Gore and Cannoli from WB\validation\roundtrip_sharedassets1.assets` | 0 字节 | `e3b0c44298fc1c14` | `DECOY_EMPTY` |
| 2 | `D:\AI\Guns, Gore and Cannoli from WB\validation\roundtrip_sharedassets10.assets` | 0 字节 | `e3b0c44298fc1c14` | `DECOY_EMPTY` |
| 3 | `D:\AI\Guns, Gore and Cannoli from WB\validation\roundtrip_sharedassets3.assets` | 0 字节 | `e3b0c44298fc1c14` | `DECOY_EMPTY` |

三条记录的完整 SHA-256 均为 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`（空字节串的 SHA-256）。

**性质与禁令**：

1. 三者是往返测试残留的**零字节验证文件**，保留 `DECOY_EMPTY` 标记。
2. **不得**视为有效基线、原始游戏资产、可写入的测试目标或可回退来源。
3. 按 basename 建立索引时**不得**让其覆盖同名 live 条目（`sharedassets1` / `sharedassets3` / `sharedassets10`）。
4. 任何测试**不得**使用、改写、修复或删除这三个文件；测试一律使用 L1 内合成数据。
5. 路径若未来变化，须重新以台账为准；本文档不自行访问或修改这些文件。

**路径确认状态**：3/3 `PATH_VERIFIED`（来源为 CAP-014.4 台账，非推测）。

### A.1.4 34 个 `.assets` 的完整分类（不重叠）

| 级别 | 数量 | 构成 |
|---|---|---|
| L0-A | 17 | `ggc_Data` 下 17 个（`resources.assets` + `sharedassets0`–`sharedassets15`） |
| L0-B | 14 | `backup\` 根 8 个 + `pre_hat_split\` 2 个 + `pre_hat_rollout\` 1 个 + `pre_scene_20261022_2327\` 1 个 + `pre_scene_20261027_1545\` 2 个 |
| **L0-D** | **3** | A.1.3 三个 `roundtrip_*.assets` |
| **合计** | **34** | 与台账 `files_total = 34` 一致 |

## A.2 术语与状态（四层）

| 层 | 状态集 |
|---|---|
| 文件基线状态 | `VERIFIED_BASELINE` / `UNVERIFIED` / `KNOWN_OUTPUT` / `UNKNOWN` |
| 快照状态 | `SNAPSHOT_VALID` / `SNAPSHOT_ORPHAN` / `SNAPSHOT_NO_SIDECAR` / `SNAPSHOT_CORRUPT` / `SNAPSHOT_ABSENT` |
| 操作状态（扫描期派生） | `OP_COMMITTED` / `OP_ABORTED` / `OP_RECOVERED` / `OP_SUPERSEDED` / `OP_UNRESOLVED` |
| 记录持久性（扫描期派生） | `DURABLE` / `PROVISIONAL` |
| **检查点状态**（P0-1 新增） | `VERIFIED` / `ABSENT_CLEAN` / `ABSENT_DIRTY` / `INCONSISTENT` |
| 运行状态 | `READY` / `RECOVERY_REQUIRED` |

### A.2.1 九条术语红线

1. `TORN` 不是文件状态；部分写入表现为 `OP_UNRESOLVED` + 目标哈希 ∉ {B, A}。
2. `OP_SUPERSEDED` 不是 WAL 事件，是派生状态。
3. `REPAIR` 不是操作终态。
4. `FAILED` 不是操作终态，不关闭任何 op。
5. `PROVISIONAL` 不是 WAL 事件，也不是 `wal_failures` 的记录类型，是由持久证据派生的状态（A.5）。
6. **`.durable` 不是独立的可信标记**（P0-1）：它必须能被校验为"描述了 WAL 的一个真实存在的前缀"；无法校验时不得据其判定任何记录为 `DURABLE`。
7. `RECOVERY_VERIFIED` 与 `REDO_VERIFIED` 独立；`BYTES` 与 `OBJECT` 再分两维。
8. **并发保护不是完整覆盖**；`W2-b` 是已证明的不可检出缺口。
9. **可见 ≠ 已确认持久化**（P0-3）：WAL 中存在某条记录，不等于该记录已通过检查点确认。

## A.3 持久化产物清单

| 产物 | 路径 | 性质 |
|---|---|---|
| 主 WAL | `wal\<target_key>.jsonl` | 追加式事件流，`buffering=0`，每行一次 write + fsync |
| **持久化检查点** | `wal\<target_key>.durable.json` | 描述 WAL 的一个可校验前缀（A.5） |
| 失败日志 | `wal_failures\<target_key>.jsonl` | 追加式，记录写不进主 WAL 或 fsync 失败的事实 |
| 修复日志 | `wal_repairs\<target_key>.jsonl` | 追加式，`REPAIR_INTENT` / `REPAIR_DONE` |
| 尾部证据 | `wal_evidence\<target_key>.<ts>.tail.bin` | 被截断的原始字节，只增不改 |
| 签核 | `signoffs\<target_key>.<ts>.json` | T2 人工签核 |
| 快照 | `snap\<base>.<sha16>.assets` + `.json` | 内容 + sidecar |
| 锁 | `lock\<target_key>.lock` | 工具级锁文件 |
| 证据包 | `cases\<case_id>\evidence\` | 每用例归档 |

## A.4 WAL 事件与合法序列

### A.4.1 事件与必需字段

| 类别 | 事件 | 终态 | 关键字段 |
|---|---|---|---|
| 操作 | `BEGIN` | 开启 | `seq, op_id, op_kind, target_norm, target_identity{st_dev,st_ino}, target_sha256_before, size, snapshot_id, snapshot_sha256, tool, tool_sha256, args_digest, deps, pid, ts_wall, ts_mono`<br>**RECOVERY 额外**：`supersedes_recovery_op_id`、`expected_unresolved_set[]`、`expected_unresolved_set_digest`、`expected_unresolved_count` |
| 操作 | `END` | 是（WRITE） | `seq, op_id, op_kind, target_sha256_after, verify_summary, elapsed_ms` |
| 异常 | `ABORTED` | 是（WRITE） | `seq, op_id, op_kind, reason, target_sha256_observed` |
| 异常 | **`FAILED`** | **否** | `seq, op_id(可空), stage, error_class, errno, target_sha256_observed, wal_durable, ts` |
| 恢复 | `RECOVERED` | 是（RECOVERY） | `seq, op_id, op_kind, snapshot_id_used, snapshot_sha256_used, snapshot_recomputed_sha256, pre_recovery_target_sha256, target_sha256_after, resolves_op_ids[], resolves_set_digest, resolves_count, recovery_verified:true, consistency_check:true` |
| 日志修复 | `REPAIR` | **否** | `seq, repaired_file, repair_of, repair_intent_id, discarded_bytes, discarded_lines, torn_tail_hex_prefix, evidence_path, reason, operator, ts` |

`REPAIR` 无 `op_id`。检查点中对应的 `last_durable_op_id` 记为 `null`。

### A.4.2 合法序列

| 序列 | 结果 |
|---|---|
| `BEGIN(WRITE) → END` | `OP_COMMITTED` |
| `BEGIN(WRITE) → ABORTED` | `OP_ABORTED`（须复核 `observed == before`；不等则声明为假 → `OP_UNRESOLVED`） |
| `BEGIN(RECOVERY) → RECOVERED` | `OP_RECOVERED` |
| `BEGIN(RECOVERY) → FAILED` | **`OP_UNRESOLVED`**（`FAILED` 不关闭 op） |
| `BEGIN(RECOVERY) → ABORTED` | ❌ 非法 |
| `BEGIN` 无自身终态但被已验证 `RECOVERED.resolves_op_ids` 覆盖 | `OP_SUPERSEDED` |
| `BEGIN` 无自身终态且未被覆盖 | `OP_UNRESOLVED` → `RECOVERY_REQUIRED` |
| 终态无 `BEGIN` / 同 `op_id` 两终态 / 未知 `op_id` | 隔离 → `RECOVERY_REQUIRED` |
| `REPAIR` / `FAILED` 单独出现 | 不改变任何 op 状态 |

### A.4.3 结构异常处理

| 异常 | 自动动作 | 禁止 | 结果 |
|---|---|---|---|
| 末尾残缺行 | 按 **A.6 修复流程** | 解析为有效记录；不经 A.6 直接截断 | 见 A.6 |
| 中间行不可解析（非末行） | 隔离整文件 | 只丢该行继续 | `RECOVERY_REQUIRED` + 人工 |
| 重复（同 seq 同字节） | 折叠，扫描报告记 `DEDUP` | 视为两次操作 | 不变 |
| 重复（同 seq 异内容） | 隔离整文件 | 任选其一 | `RECOVERY_REQUIRED` |
| seq 非单调 | 隔离整文件 | 按时间重排 | `RECOVERY_REQUIRED` |
| 未知事件类型 | 隔离该行 | 当无害忽略 | 若因此无终态 → `RECOVERY_REQUIRED` |
| 主 WAL 写短计数 / 异常 / flush 失败 / **fsync 失败** | 立即停止；检查点**不推进**；尽力向 `wal_failures` 写 `FAILED` | 重试追加；**截断回滚**；假定已在磁盘上 | `RECOVERY_REQUIRED`（A.7） |
| `wal_failures` 亦不可写 | 标准错误输出 + 进程内标记 | 静默吞掉 | `RECOVERY_REQUIRED`（检查点未推进即足以 fail-closed） |

## A.5 检查点：与 WAL 内容绑定（P0-1）

### A.5.1 `.durable` 的定位

`.durable` **不是**独立的可信标记，而是"对 WAL 某一前缀的声明"。任何使用它的判定，必须先校验该声明所指的前缀确实存在且未被改动。

### A.5.2 检查点字段（必需）

```json
{
  "checkpoint_version": 1,
  "target_key": "<32 hex>",
  "last_durable_record_seq": 0,
  "last_durable_record_kind": "BEGIN|END|ABORTED|RECOVERED|REPAIR",
  "last_durable_op_id": "<op_id> | null",
  "wal_size_at_marker": 0,
  "wal_prefix_sha256": "<64 hex>",
  "ts_wall": "ISO8601",
  "tool_sha256": "<64 hex>"
}
```

### A.5.3 `wal_prefix_sha256` 的计算范围与字节边界

| 项 | 规定 |
|---|---|
| **起点** | 字节偏移 `0` |
| **终点** | 字节偏移 `wal_size_at_marker`（**不含**该字节） |
| **计算式** | `sha256( wal_bytes[0 : wal_size_at_marker] )`，小写十六进制 |
| **换行符** | **包含**前缀内所有记录的结尾 `\n`。因每条记录以 `\n` 结束，`wal_size_at_marker` 必须恰好落在某条记录换行符之后的偏移上 |
| **编码** | 原始字节，不做任何换行转换（WAL 以 `newline="\n"` 写入） |

### A.5.4 三向一致性约束

检查点声明必须同时满足以下三条，缺一即为不一致：

1. **序号一致**：解析 `wal[0:wal_size_at_marker]` 得到的最后一条记录，其 `seq == last_durable_record_seq`。
2. **身份一致**：该记录的 `kind == last_durable_record_kind`；其 `op_id`（若为 `REPAIR` 则为 `null`）== `last_durable_op_id`。
3. **偏移一致**：该记录的最后一个字节（即其 `\n`）的偏移 + 1 == `wal_size_at_marker`。

### A.5.5 检查点更新顺序（CP-1…CP-5）

```
CP-1  向主 WAL 追加一条完整记录（单次 write，buffering=0）
CP-2  fsync 主 WAL
CP-3  计算 sha256(wal_bytes[0 : size_after])，size_after 为 CP-1 之后的文件大小
CP-4  写 <key>.durable.json.tmp.<pid> → fsync → os.replace 到 <key>.durable.json
CP-5  重新读取检查点并校验（回读校验，失败即视为未推进）
```

**崩溃方向性**：检查点永远描述一个**仍然存在的前缀**，因此任何时刻崩溃只会导致"更多记录被判 `PROVISIONAL`"（保守），**不会**导致"未持久化的记录被判 `DURABLE`"（乐观）。

| 崩溃点 | 结果 |
|---|---|
| CP-1 前 | 无新记录；旧检查点仍 `VERIFIED` |
| CP-1 后、CP-2 前 | 新记录可见但未 fsync；检查点未推进 → 新记录 `PROVISIONAL` |
| CP-2 后、CP-4 前 | 新记录实际已持久，但检查点未推进 → 仍判 `PROVISIONAL`（保守方向，安全） |
| CP-4 中（tmp 已写、replace 未完成） | 旧 `.durable.json` 未被替换 → 仍 `VERIFIED`，新记录 `PROVISIONAL` |
| CP-4 后、CP-5 前 | 新检查点已生效；若回读失败则下次扫描发现不一致 |

**关键语义（T4 的基础）**：一次成功的 `fsync` 会把该文件此前所有未确认的字节一并持久化。因此后续的检查点推进**合法地**把此前的 `PROVISIONAL` 记录转为 `DURABLE` —— 这不是掩盖，而是该 fsync 的真实效果。

### A.5.6 启动扫描的五步校验

| 步 | 校验 |
|---|---|
| V-1 | 主 WAL 存在，且 `size >= wal_size_at_marker` |
| V-2 | `sha256(wal[0:wal_size_at_marker]) == wal_prefix_sha256` |
| V-3 | 该前缀可完全解析，`seq` 严格单调 |
| V-4 | 前缀末条记录 `seq` / `kind` / `op_id` 与检查点字段一致 |
| V-5 | 前缀末条记录的结束偏移 == `wal_size_at_marker` |

### A.5.7 `CHECKPOINT_STATUS` 四值与判定

| 状态 | 条件 | 记录持久性判定 | `WAL_STATE_COMPLETE` |
|---|---|---|---|
| `VERIFIED` | V-1…V-5 全部通过 | `seq <= last_durable_record_seq` → `DURABLE`；`seq >` → `PROVISIONAL` | 由 op 状态与是否存在 `PROVISIONAL` 决定（YES / NO） |
| `ABSENT_CLEAN` | 主 WAL 不存在且检查点不存在 | 无记录 | `YES`（空态） |
| `ABSENT_DIRTY` | 主 WAL 存在且有记录，检查点不存在 | **全部 `PROVISIONAL`** | **`UNKNOWN`** |
| `INCONSISTENT` | 检查点存在但 V-1…V-5 任一失败；或检查点不可解析；或主 WAL 短于 `wal_size_at_marker` | **全部 `PROVISIONAL`** | **`UNKNOWN`** |

**硬规则**：

- `ABSENT_DIRTY` / `INCONSISTENT` → 不得把任何记录判为 `DURABLE`；状态转 `RECOVERY_REQUIRED`；`WAL_STATE_COMPLETE = UNKNOWN`；**禁止继续写入、禁止自动重做、禁止自动修复**；必须人工检查并明确授权。
- `INCONSISTENT` 意味着 WAL 可能被外部截断或替换 —— 视为外部干扰信号，不得用"重写检查点"来消解。

### A.5.8 纳入 `wal_state_digest` 与 T2

`wal_state_digest` 的规范化对象（P0-1 扩充）新增三个字段：

```json
{"wal_size": 0, "last_seq": 0,
 "checkpoint_status": "VERIFIED|ABSENT_CLEAN|ABSENT_DIRTY|INCONSISTENT",
 "last_durable_record_seq": 0,
 "wal_prefix_sha256": "<64 hex> | null",
 "ops": [{"op_id": "...", "derived_state": "OP_..."}],
 "unresolved_set_digest": "<64 hex>"}
```

序列化：UTF-8 无 BOM，键名按字典序，无多余空白，SHA-256 小写十六进制。

T2 签核必须基于**已通过 V-1…V-5 校验**的检查点状态；签核中记录的 `wal_state_digest_at_signoff` 已包含 `checkpoint_status`，因此检查点任何变化都会使签核自动失效。

## A.6 WAL 尾部残缺行修复流程

### A.6.1 适用范围与禁止范围

| | 内容 |
|---|---|
| **允许修复** | 主 WAL **末尾**存在无法解析为记录的字节，且该残行是**最后一行** |
| **禁止** | 因主 WAL 写入失败（短写 / 异常 / `fsync` 失败）而主动截断回滚到"写之前的大小"——这些字节**可能是完整记录**，截断即销毁证据；A.5 的检查点机制已足以 fail-closed |
| **禁止** | 非末行不可解析时自动修复 |
| **禁止** | 手工编辑 WAL；不经 A.6 直接 `truncate`；删除或重写历史记录以掩盖不确定状态 |

### A.6.2 八步流程（RP-6 已拆分，P0-3）

| 步 | 动作 | 持久化要求 |
|---|---|---|
| **RP-1 识别** | 逐行解析，定位第一条失败行；断言它是最后一行。计算 `tail_offset`、`tail_len` | 只读 |
| **RP-2 保存证据** | 复制 `[tail_offset, EOF)` 到 `wal_evidence\<key>.<ts>.tail.bin`；flush + fsync；回读算 `tail_sha256`；记录 `tail_hex_prefix`（前 32 字节） | 证据文件必须 fsync 后才可继续 |
| **RP-3 写修复意图** | 向 `wal_repairs\<key>.jsonl` 追加 `REPAIR_INTENT{repair_intent_id, wal_size_before, tail_offset, tail_len, tail_sha256, evidence_path, tool_sha256, ts}`；fsync | **必须先于任何截断** |
| **RP-4 截断** | `os.truncate(wal, tail_offset)` | — |
| **RP-5 复核** | 重读主 WAL：大小 == `tail_offset`，全文件可解析，seq 单调 | 只读 |
| **RP-6a 追加 REPAIR** | 向主 WAL 追加 `REPAIR` 事件（含 `repair_intent_id`、`evidence_path`、`discarded_bytes`、`discarded_lines`、`torn_tail_hex_prefix`）；fsync | 主 WAL fsync 成功 |
| **RP-6b 推进检查点** | 按 **A.5.5 CP-3…CP-5** 计算前缀哈希并发布检查点；回读校验 `CHECKPOINT_STATUS == VERIFIED` 且覆盖到 `REPAIR` 记录的结束偏移 | 检查点必须 `VERIFIED` |
| **RP-7 标记完成** | 向 `wal_repairs\<key>.jsonl` 追加 `REPAIR_DONE{repair_intent_id, confirmed_checkpoint_seq}`；fsync | **必须在 RP-6b 成功之后** |

### A.6.3 `REPAIR` 三种持久化状态的启动恢复规则（P0-3）

| 情况 | 识别条件 | 持久性判定 | `WAL_STATE_COMPLETE` | 允许 `REPAIR_DONE` | 允许再次修复 | `RECOVERY_REQUIRED` | 人工 |
|---|---|---|---|---|---|---|---|
| **① 已确认持久化** | `REPAIR` 行可解析且字段完整；`CHECKPOINT_STATUS == VERIFIED`；`last_durable_record_seq >= REPAIR.seq`；`wal_prefix_sha256` 覆盖到 `REPAIR` 结束偏移；V-4/V-5 显示末条即该 `REPAIR` | `DURABLE` | 由其他条件决定（YES / NO） | **允许**（可写 `REPAIR_DONE`） | **禁止** | 视 op 状态 | 否 |
| **② 可见但未确认** | `REPAIR` 行可解析且字段完整；但 `CHECKPOINT_STATUS != VERIFIED`，或 `last_durable_record_seq < REPAIR.seq`，或前缀哈希未覆盖到其结束偏移 | `PROVISIONAL` | `VERIFIED` 时 → `NO`；`ABSENT_DIRTY`/`INCONSISTENT` 时 → `UNKNOWN` | **禁止**（必须先完成 RP-6b 并复核） | **禁止**（不得再次截断） | 若为 `NO` → 允许先做 RP-6b；若为 `UNKNOWN` → **是** | `UNKNOWN` 分支必须 |
| **③ 损坏或不可解析** | `REPAIR` 行不可解析、字段缺失/非法、`seq` 非单调、`repair_intent_id` 与 `REPAIR_INTENT` 不匹配、或无法确定是否完整写入 | 不可判定 → 按 `PROVISIONAL` 处理 | **`UNKNOWN`** | **禁止** | **禁止** | **是（保持）** | **必须** |

**三条原则**：

1. 只有通过 WAL 与检查点**双向一致性验证**的修复证据，才能按"已完成"继续（写 `REPAIR_DONE`）。
2. 对 `PROVISIONAL`、损坏或不确定的修复记录，**不得**自动认定修复已完成。
3. **不得因为看到 `REPAIR` 就跳过恢复校验**；**不得**通过自动截断、删除记录或重写历史来掩盖不确定状态。

### A.6.4 每步崩溃后的重启判定

| 崩溃点 | 持久证据 | 重启判定 | 允许的下一步 | 禁止 |
|---|---|---|---|---|
| RP-1 / RP-2 之间 | 无 INTENT；主 WAL 原样 | 未开始 | 从头重做 RP-1…RP-2（证据文件按新时间戳新建，不覆盖旧的） | 覆盖既有证据；直接截断 |
| RP-2 完成、RP-3 之前 | 有证据文件，无 INTENT | 未开始 | 从 RP-3 起（复用证据须校验 `tail_sha256`） | 无 INTENT 就截断 |
| RP-3 完成、RP-4 之前 | INTENT 存在、无 DONE；大小 == `wal_size_before`；tail 哈希匹配 | 已开始未截断 | 从 RP-4 继续 | 重写 INTENT；删证据 |
| RP-4 进行中，大小 ∈ (`tail_offset`, `wal_size_before`) | INTENT 存在、无 DONE；大小非两端值 | **边界不可确定** | 停止 → `RECOVERY_REQUIRED` + 人工 | 再次截断；猜边界；删证据 |
| RP-4 完成、RP-6a 之前 | INTENT 存在、无 DONE；大小 == `tail_offset`；无 `REPAIR` | 已截断未记录 | 从 RP-6a 继续 | 重复截断 |
| **RP-6a 完成、RP-6b 之前** | INTENT 存在、无 DONE；`REPAIR` 可见；检查点未覆盖 | **情况 ②** | 先完成 RP-6b 并复核；`VERIFIED` 后写 `REPAIR_DONE` | **写 `REPAIR_DONE`**；再次截断 |
| RP-6b 完成、RP-7 之前 | INTENT 存在、无 DONE；检查点 `VERIFIED` 且覆盖 `REPAIR` | **情况 ①** | 写 `REPAIR_DONE` | 再写一条 `REPAIR` |
| RP-7 之后 | INTENT + DONE；检查点覆盖 `REPAIR` | 完成 | 常规扫描 | — |
| 任何时刻大小 ∉ {`wal_size_before`, `tail_offset`} | — | **不可确定** | 停止 → `RECOVERY_REQUIRED` + 人工 | 任何自动动作 |
| `REPAIR_DONE` 存在但主 WAL 无匹配 `REPAIR`，或检查点未覆盖 | — | 不一致 | 停止 → 人工 | 自动补写 |

**总则**：任何一步无法确定 → 保持 `RECOVERY_REQUIRED`，证据全部保留，不得静默忽略。

## A.7 持久化判定与状态转移（P0-2）

### A.7.1 `WAL_STATE_COMPLETE` 三值（重新定义）

| 值 | 条件 |
|---|---|
| **`YES`** | 检查点 `VERIFIED` 或 `ABSENT_CLEAN`；所有记录 `DURABLE`；无 `OP_UNRESOLVED`；无结构异常 |
| **`NO`** | 检查点 `VERIFIED`；但存在 `OP_UNRESOLVED`，或存在 `PROVISIONAL` 记录 —— 状态**可判定**，只是不完整 |
| **`UNKNOWN`** | 检查点 `ABSENT_DIRTY` 或 `INCONSISTENT`；或 `wal_failures` 不可读；或存在无法判定的结构异常 |

**关键区分**：`NO` 是"已知不完整，可走受控路径"；`UNKNOWN` 是"状态不可判定，只能人工"。

### A.7.2 四条解除路径（P0-2：新增 T4）

| 路径 | 性质 | 适用前提 | 动作 |
|---|---|---|---|
| **T1** | 自动 | `WAL_STATE_COMPLETE == NO`；检查点 `VERIFIED`；**存在** `OP_UNRESOLVED`；快照 `SNAPSHOT_VALID` | 一次完整 `RECOVERY` 操作，`resolves_op_ids` 覆盖全部未解决 op，通过 `RECOVERY_VERIFIED` |
| **T2** | **必须人工签核** | A.7.3 的 7 条全部成立 | 修复 + 签核 |
| **T3** | 无需转换 | 本就 `READY` | — |
| **T4** | 自动 | `WAL_STATE_COMPLETE == NO`；检查点 `VERIFIED`；**无** `OP_UNRESOLVED`；无结构异常；唯一缺陷是存在 `PROVISIONAL` 记录 | **检查点重同步**：`fsync(主 WAL)` → 重算 `sha256(wal[0:size])` → 校验末条记录 → 按 CP-4/CP-5 发布检查点 → 复核 `VERIFIED`。**不写任何 WAL 记录，不改动目标内容** |

**T4 的合法性依据**：A.5.5 已确立"一次成功 `fsync` 会把此前所有未确认字节一并持久化"。T4 只是把这一事实记录进检查点，不改变任何内容，也不掩盖任何不确定状态。它**不能**用于 `UNKNOWN`（检查点本身不可信时，重同步等于伪造可信度）。

### A.7.3 `UNKNOWN` 的处理（P0-2 硬规则）

`WAL_STATE_COMPLETE == UNKNOWN` 时：

- **禁止**继续写入；
- **禁止**自动重做；
- **禁止**自动解除故障状态（包括 T1、T4）；
- **禁止**重写检查点来"修复"一致性；
- **必须**保持 `RECOVERY_REQUIRED`，等待人工检查与明确授权。

### A.7.4 T2 的 7 条（P0-1 / P0-2 强化）

| # | 条件 |
|---|---|
| **T2-1** | 唯一结构缺陷是末尾不可解析残行，且已按 A.6 完成修复（`REPAIR` 含 `repair_intent_id` 与 `evidence_path`） |
| **T2-2** | 修复后文件完全可解析、seq 严格单调、无重复 `op_id`、无未知事件类型，**且 `CHECKPOINT_STATUS == VERIFIED` 且检查点覆盖到修复后的末尾（V-1…V-5 全部通过）** |
| **T2-3** | **不存在任何 `OP_UNRESOLVED`**（WRITE 与 RECOVERY 均算）。**不放宽** |
| **T2-4** | 三集合语义校验全部成立（A.9），且当前 `actual_unresolved_set_after == ∅`；**不得把恢复前集合与恢复后空集直接比较** |
| **T2-5** | 目标全文件 SHA-256 == B，B 为**现场重算**的快照内容哈希 |
| **T2-6** | `wal_failures` 可读、可判定为空，无未解释记录 |
| **T2-7** | 存在有效签核，且其 `wal_state_digest_at_signoff` == **当前** `wal_state_digest`（含 `checkpoint_status`） |

**推论（P0-2 核心）**：`WAL_STATE_COMPLETE == UNKNOWN` 时 T2-2 必然不成立，因此 **T2 永不适用于 `UNKNOWN`**。

### A.7.5 S7b / S7e / S7f / S7g 的分支处理（P0-2）

| 用例 | 故障（沿用 v5 定义） | 分支 | 检查点状态 | `WAL_STATE_COMPLETE` | 允许路径 | 禁止 |
|---|---|---|---|---|---|---|
| **S7b** | 类2：`BEGIN` 持久化失败 | b1：`BEGIN` 完整可见 + 检查点已覆盖 | `VERIFIED` | `NO` | T1 | T2、T4 |
| | | b2：`BEGIN` 完整可见 + 检查点未覆盖 | `VERIFIED` | `NO` | T1（恢复过程的 fsync 会把该 `BEGIN` 一并持久化） | T2、T4 |
| | | b3：`BEGIN` 不完整（残行） | `VERIFIED` | `NO` | 先按 A.6 修复 → 再按 b1/b2 或 T2 | 跳过修复 |
| | | b4：检查点 `INCONSISTENT` | `INCONSISTENT` | `UNKNOWN` | **仅人工** | T1、T2、T4、任何写入 |
| **S7e** | 类2：`fsync` 失败且 `wal_failures` 不可写 | e1：有未解决 op | `VERIFIED` | `NO` | T1 | T2、T4 |
| | | e2：无未解决 op | `VERIFIED` | `NO` | T4 | T2、T1（无可解决对象） |
| | | e3：检查点也损坏 | `INCONSISTENT` | `UNKNOWN` | **仅人工** | 全部自动路径 |
| **S7f** | `.durable` 缺失 / 损坏 / 回退 | f1：缺失且主 WAL 有记录 | `ABSENT_DIRTY` | `UNKNOWN` | **仅人工** | 全部自动路径 |
| | | f2：损坏或不可解析 | `INCONSISTENT` | `UNKNOWN` | **仅人工** | 全部自动路径 |
| | | f3：回退（marker 指向更早的合法前缀） | `VERIFIED` | `NO` | 视有无未解决 op → T1 / T4 | T2 |
| **S7g** | 存在 `PROVISIONAL` 记录且无未解决 op | — | `VERIFIED` | `NO` | T4 | T1、T2 |

> **v5 → v6 的精化说明**：v5 将 S7e 一律归为 `UNKNOWN`。v6 修正为"检查点 `VERIFIED` 时可判定为 `NO`"。理由：`UNKNOWN` 的语义是"状态不可判定"，而检查点通过 V-1…V-5 时，每条记录的持久性是**可判定**的（`seq` 与 marker 比较即得）。故障触发条件（`fsync` 失败 + `wal_failures` 不可写）未改变，改变的只是状态推导的精度。

### A.7.6 三种持久化失败情形

| 情形 | 主 WAL 有记录 | 检查点 | `wal_failures` | 记录判定 | `WAL_STATE_COMPLETE` | 放行 |
|---|---|---|---|---|---|---|
| `fsync` 失败，失败日志可写 | 可见 | 未推进但 `VERIFIED` | 有 `FAILED{wal_fsync}` | `PROVISIONAL` | `NO` | 否（须先 T1/T4） |
| `fsync` 失败，失败日志**不可写** | 可见 | 未推进但 `VERIFIED` | 无 | `PROVISIONAL`（依据来自 marker 未推进） | `NO` | 否（须先 T1/T4） |
| 上述之后进程崩溃 | 可见 | 未推进但 `VERIFIED` | 视情况 | 同上 | `NO` | 否 |
| 检查点 `ABSENT_DIRTY` / `INCONSISTENT` | 可见 | 不可用 | 视情况 | `PROVISIONAL` | `UNKNOWN` | **否，且仅人工** |
| 正常完成 | 可见 | 已推进 `VERIFIED` | 空 | `DURABLE` | 由 op 状态决定 | 视 op 状态 |

### A.7.7 `WRITE_PERMITTED`

```
WRITE_PERMITTED = YES 仅当：
  WAL_STATE_COMPLETE == YES
  AND CHECKPOINT_STATUS ∈ {VERIFIED, ABSENT_CLEAN}
  AND 快照 == SNAPSHOT_VALID
  AND 锁已获取（LockFileEx + 工具锁）
  AND 无待人工签核项
  AND 游戏进程未运行
  AND PWA 准入通过（A.10.1）
```

**不得假设 `write()` 或 `fsync()` 失败意味着数据一定在盘上，或一定不在盘上**；失败只能推出"持久性未知"。

## A.8 操作时序与屏障钩子

### A.8.1 九个步骤

```
ST-1  词法检查          纯字符串，零文件系统访问，零副作用
ST-2  实体解析          realpath + commonpath + 捕获 (st_dev, st_ino, st_size, st_mtime_ns)
ST-3  安全打开 + 身份确认
ST-4  取锁              LockFileEx 全文件范围独占 + 工具级锁文件
ST-5  创建并校验快照    A.11.1 八步
ST-6  写 BEGIN          write + fsync + 检查点推进（CP-3…CP-5）
ST-7  复检              紧贴写入，中间无其他 I/O
ST-8  写入              等长原地覆盖，1 MiB 固定块、升序、每块一次 write
ST-9  校验 + END        全文件 SHA-256 + 对象级回读 → END(write + fsync) + 检查点推进
```

### A.8.2 四个屏障钩子（M9）

钩子仅在测试构建启用；生产构建中钩子必须不存在（或为带断言的 no-op）。

| 钩子 | 精确位置 | 用于 |
|---|---|---|
| **H1** | `ST-7` 内部，**在计算目标 SHA-256 之前** | S5a |
| **H2** | `ST-7` **返回成功之后**、`ST-8` **首次 `write()` 之前** | S5d、S5e |
| **H3** | `ST-8` 内部，**块边界 k 处** | S5b-1、S5b-2 |
| **H4** | `ST-8` **全部块完成之后**、`ST-9` **开始之前** | S5c |

### A.8.3 屏障释放顺序

```
① 我方线程到达钩子 Hx，写 "at-hook" 标记，阻塞
② fixture 收到 "at-hook" 信号
③ fixture 启动 helper：open(target,'r+b') → seek(off) → write(buf) → flush → fsync → close → exit
④ helper 回传 "write-done" 信号（含偏移、长度、字节摘要）
⑤ fixture 回读该区间确认写入已落地
⑥ fixture 释放屏障
⑦ 我方线程继续
```

③ 的 `close` 与 ④ 的完成信号都必须发生在 ⑥ 之前。否则用例判"未覆盖"。

### A.8.4 无钩子时

对应用例标记 **`UNCOVERED`**，不得用 sleep / 大致同时 / 概率并发代替。报告中须写明缺失的是哪个钩子。

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
| PWA-1 | `LockFileEx` 全文件范围独占，持有 ST-4→ST-9 | PASS / FAIL |
| PWA-2 | 游戏进程未运行 | PASS / FAIL |
| **PWA-3** | 无其他进程持有该文件的内存映射 | **UNVERIFIABLE** |
| PWA-4 | 单写者策略（进程级工具锁） | PASS / FAIL |
| PWA-5 | 快照 == `SNAPSHOT_VALID` | PASS / FAIL |
| PWA-6 | `WAL_STATE_COMPLETE == YES` 且 `CHECKPOINT_STATUS ∈ {VERIFIED, ABSENT_CLEAN}` | PASS / FAIL / UNKNOWN |
| PWA-7 | 用户对该文件、该次写入的书面授权 | PASS / FAIL |

**规则**：

1. PWA-1/2/4/5/6/7 必须全部 `PASS`；任一 `FAIL` 或 `UNKNOWN` → **阻止真实写入**。
2. **PWA-3 恒为 `UNVERIFIABLE`**。真实写入必须额外具备用户**具名风险接受**，并写入台账 `risk_acceptance` 字段。未取得 → **阻止真实写入**。
3. **PWA 全部满足也不代表并发保护完整**：`W2-b` 仍不可检出。

### A.10.2 隔离测试准入（STA）

| # | 条件 | 证明方式 |
|---|---|---|
| STA-1 | 目标路径经 ST-1/ST-2/ST-3 通过，落在 `TEST_ONLY_ROOT` 内 | 运行时断言 |
| STA-2 | 目标是 `seeds\` 的副本，种子来源与哈希已记录 | 前置校验 5 项 |
| STA-3 | 用例清单中不存在任何解析到 L0-A/L0-B/L0-C/**L0-D** 的路径 | 用例 manifest 静态检查 |
| STA-4 | 用例结束时 34 个真实 `.assets` 完整 SHA-256 == `baseline_ledger.json` | 事后比对 |
| STA-5 | 测试构建钩子已启用；生产构建中钩子不存在 | 构建标志断言 |
| STA-6 | 全局 `open()` 审计钩子：凡 mode 含 `w`/`+`/`x` 的路径必须落在 L1 内，否则立即抛错 | 进程级审计钩子 |

**STA 允许**：M1–M9 全部注入、WAL 破坏、检查点破坏、锁破坏、快照破坏、尾部截断（仅在用例目录内）。
**STA 禁止**：任何 L0 路径的写模式打开；把测试快照写进项目 `backup\`；把钩子留在生产构建中；**使用或改写 L0-D 的三个 `roundtrip_*.assets`**。

### A.10.3 STA 与 PWA 的关系

> **STA 通过 ≠ PWA 满足。** 合成夹具上所有用例全部通过，不能推出真实文件写入安全、内存映射写者不存在、游戏进程无干扰、并发保护完整。PWA 只能在 P4 真实写入前由人工逐项确认；PWA-3 永远只能"风险接受"，不能"验证通过"。

## A.11 快照规范

### A.11.1 发布八步

```
① 写内容到 <snap>\<base>.<sha16>.assets.tmp.<pid>.<rand>
② flush + fsync tmp
③ 回读 tmp 全文件 SHA-256 == B          ← 不通过则中止，tmp 保留
④ os.replace(tmp → <base>.<sha16>.assets)
⑤ 回读最终内容文件 SHA-256 == B
⑥ 写 sidecar 到 sidecar.tmp.<pid>，flush + fsync
⑦ os.replace(sidecar.tmp → sidecar)
⑧ 回读 sidecar + 内容，三方交叉校验
```

### A.11.2 可用性

`SNAPSHOT_VALID` ✅；`SNAPSHOT_NO_SIDECAR` ❌ 默认不可用（丢失操作归属，须人工确认）；`SNAPSHOT_ORPHAN` / `SNAPSHOT_CORRUPT` / `SNAPSHOT_ABSENT` ❌。

硬规则：存在 ≠ 可用；不自动删除孤立/损坏快照；同名永不覆盖。

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
| 快照失效 | `#r1` 无终态、快照校验失败 | 保持；`CURRENT_STATE`；人工 |
| 一致性检查失败 | 存在未被覆盖的未解决 op | 保持；人工 |
| **检查点 `INCONSISTENT`** | — | **保持；禁止自动恢复；人工** |

### A.12.3 重试规则

| 规则 | 内容 |
|---|---|
| R-1 | 允许多个 `BEGIN(RECOVERY)` 并存，必须形成链：`#r2.supersedes_recovery_op_id = #r1` |
| R-2 | 一次 `RECOVERED` 可解决多个 op（含链上所有未解决 RECOVERY op 与未解决 WRITE op） |
| R-3 | `RECOVERY_REQUIRED` 下恢复是**唯一允许的内容写操作**（T4 只改检查点，不改内容）；WRITE 一律禁止 |
| R-4 | 恢复必须幂等：从同一 `SNAPSHOT_VALID` 覆盖到 B 可重复执行 |
| R-5 | 每次恢复尝试必须有独立 `BEGIN(RECOVERY)`。**成功** → `RECOVERED`（终态）；**失败** → `FAILED`（**非终态**）且 op **保持 `OP_UNRESOLVED`**。禁止写 `ABORTED`、禁止伪造 `RECOVERED` |
| R-6 | 不得进入 `READY`：`RECOVERY_VERIFIED` 未通过 / `consistency_check` false / 三集合关系不满足 / 检查点非 `VERIFIED` |

## A.13 恢复验证与重做验证

| 判定 | 对象 | 内容 |
|---|---|---|
| `RECOVERY_VERIFIED_BYTES` | 恢复后字节 | 快照身份现场重算通过；全文件 SHA-256 == B；`RECOVERED` 字段与实测一致；三集合关系正确；**检查点 `VERIFIED`** |
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
| 来源 | 执行写入的脚本字节；多文件时按 `relpath` 排序后对 `(relpath, sha256)` 聚合再算 SHA-256 | `importlib.metadata.version()` / `__version__`：python / unitypy / pillow / numpy |
| 记录时点 | 进程启动时计算，写入 `BEGIN.tool_sha256` | 同上，写入 `BEGIN.deps` |
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

**缺失与不一致处理**：签核文件不存在 / 任一条件 false / `statement` 缺失或措辞不符 / `wal_state_digest_at_signoff` ≠ 当前 / `signoff_id` 复用 / `observed_target_sha256` ≠ 当前目标哈希 / **`checkpoint_status` ≠ `VERIFIED`** → **T2 不适用**，保持 `RECOVERY_REQUIRED`，不自动重试。

## A.15 故障路径交叉核对表

**通用前提**：不得假设 `write()` 或 `fsync()` 失败意味着数据一定在盘上或一定不在盘上；失败只能推出"持久性未知"。

| # | 故障点 | 可能持久化的证据 | 重启扫描结果 | 允许的下一步 | 禁止的动作 | 预期运行状态 |
|---|---|---|---|---|---|---|
| 1 | 快照发布中途失败 | 半截 `.tmp`；或内容已发布无 sidecar；或三方不一致 | 无条目 / `SNAPSHOT_NO_SIDECAR` / `SNAPSHOT_CORRUPT` | 保留证据；本次写入终止；释放锁 | 删除 tmp/内容；用无 sidecar 快照恢复；重写 sidecar 覆盖 | `READY`（无 `BEGIN`，目标未触碰） |
| 2 | WAL 尾部修复中途失败 | `REPAIR_INTENT` / `REPAIR_DONE`；`wal_evidence` 尾部字节；`REPAIR` 记录；检查点 | 见 A.6.4 十种判定 | 按 A.6.4 对应行继续 | 再次截断；猜边界；删证据；无 INTENT 就截断；**未确认持久化就写 `REPAIR_DONE`** | 完成或可继续 → 继续扫描；否则 `RECOVERY_REQUIRED` + 人工 |
| 3 | **WAL 持久化失败** | 主 WAL 可见记录；检查点未推进（本身可能仍 `VERIFIED`）；`wal_failures` 可能有 `FAILED` | 记录为 `PROVISIONAL`；检查点 `VERIFIED` → `NO`；检查点 `ABSENT_DIRTY`/`INCONSISTENT` → `UNKNOWN` | **`NO`**：有未解决 op → **T1**；无未解决 op → **T4**。**`UNKNOWN`**：仅人工 | **不得**将持久化失败一律导向 T2；**不得**重写检查点消解 `INCONSISTENT`；不得假定已落盘；不得截断回滚 | `RECOVERY_REQUIRED`（`NO` 可经 T1/T4 转 `READY`；`UNKNOWN` 必须人工） |
| 4 | WRITE 中途崩溃 | `BEGIN(WRITE)` 无终态；目标部分内容；检查点停在 `BEGIN` 之后 | `OP_UNRESOLVED`；目标哈希 ∉ {B, A} | T1：校验快照 → 覆盖到 B → `RECOVERED`（三集合匹配） | 继续写；跳过该 target；用大小判成功 | `RECOVERY_REQUIRED` |
| 5 | RECOVERY 中途崩溃 | `BEGIN(RECOVERY)` 无终态；目标部分恢复 | `OP_UNRESOLVED`（可能多条，形成链） | 发起 `#r2`（`supersedes=#r1`），幂等重做 | 判断恢复到哪一步；伪造 `RECOVERED`；写 `ABORTED` | `RECOVERY_REQUIRED` |
| 6 | 连续多次 RECOVERY 失败后重启 | 多个 `BEGIN(RECOVERY)` 无终态；多个 `FAILED`；检查点停在最后成功点 | 未解决集合 = 全部未终结 op | 发起 `#rn`，`resolves_op_ids` 覆盖**全部**未解决 op；或人工 | 只解决最后一个；遗漏链上 op；把 `FAILED` 当终态 | `RECOVERY_REQUIRED`，直至 `#rn` 成功 |
| 7 | 快照与 WAL 状态不一致 | `BEGIN.snapshot_sha256` 与现存快照哈希不符；或 `SNAPSHOT_ORPHAN` | 快照不可用 → 无法自动恢复 | 生成 `CURRENT_STATE` 快照（标注非 B）；人工报告 | 用不符的快照恢复；自动删除孤立快照；把 `CURRENT_STATE` 当 B | `RECOVERY_REQUIRED` + 人工 |
| **8** | **检查点与 WAL 不一致** | 检查点存在但 V-1…V-5 失败；或 WAL 短于 marker；或末条记录不符；或前缀哈希不符 | `CHECKPOINT_STATUS = INCONSISTENT` → `WAL_STATE_COMPLETE = UNKNOWN` | 仅人工：核对 WAL 是否被截断/替换；决定是否放弃该 target | 重写检查点；T1；T2；T4；任何写入 | `RECOVERY_REQUIRED` + 人工 |

**表的使用规则**：本表是**设计判定表**，不是执行记录。每一条的实际结果须由对应用例产出；未产出即"未验证"。

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

### A.16.2 注入手段

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
| M9 屏障注入 | 在 H1–H4 精确定点让外部进程写入 | 不能证明系统能检测该写入 |
| **M10 检查点篡改** | 系统对 `INCONSISTENT` 的判定与阻断 | 真实外部篡改的动机与范围 |

`injection_kind`：`FAULT_INJECTED`（M1–M4、M6、M9）/ `STATE_CONSTRUCTED`（M8、M10）。

## A.17 场景 S0–S10（55 条）

### S0 路径安全与保护分类（**6 条**）

S0a 词法（`..`/`\\?\`/`\\.\`/UNC/`C:relative`/尾随点空格/`:stream`/设备名/异盘/`root` 自身/`root_evil`）｜S0b 重解析点内外｜S0c 句柄身份替换 + `st_ino==0`｜S0d 零副作用｜S0e 硬链接 `st_nlink>1`｜**S0f 静态保护分类断言（P0-4）**：仅读取保护清单与台账，**不访问任何 `.assets` 文件**，断言 34 个文件全部有且仅有一个 L0/L1 分类，3 个 `roundtrip_*.assets` 归为 **L0-D / `DECOY_EMPTY`**，且无任何用例清单条目解析到 L0-A/B/C/D。

**S0 不覆盖 W2**；W2 由 S5d/S5e 覆盖。

### S1 快照创建失败（5 条）

S1a tmp 写 ENOSPC｜S1b fsync 失败或回读 ≠ B｜S1c `os.replace` 失败｜S1d 内容已发布但 sidecar 失败｜S1e 三方交叉校验不一致。

全部：无 `BEGIN`；`READY`；目标 == B；残留物保留并标注。

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

S3a M8（BEGIN 无 END、目标 == A）｜S3b M8（末尾残行，须先按 A.6 修复；修复后若无未解决 op 且检查点 `VERIFIED` → 评估 T2；若有未解决 op → **T2 不适用**，走 T1）｜S3c M6（sink 模拟 END 未持久化）。

核心：不得因"目标 == A"推断已完成。

### S4 快照缺失/损坏（4 条）

S4a 删内容｜S4b 篡改内容｜S4c sidecar 缺失/篡改｜S4d 快照与目标双双被改。

全部：保持 `RECOVERY_REQUIRED`；生成 `CURRENT_STATE`（标注非 B）；人工报告。

### S5 外部并发（6 条）

| 用例 | 钩子 | 外部写入 | 相对写游标 | 最终哈希 | 期望 |
|---|---|---|---|---|---|
| **S5a** | **H1**（ST-7 算哈希**之前**） | `T-1M`：`[1024, 5120)`，4096 B | 尚未开始写 | ≠ B | ST-7 实算 ≠ B → 复检失败 → **不得写 `ABORTED`**（"目标未变"声明为假），写 `FAILED{stage:recheck}` → `OP_UNRESOLVED` → `RECOVERY_REQUIRED` |
| **S5b-1** | **H3**（k=32） | `T-64M`：`[4 MiB + 1024, +4096)` | **写游标之后**（已写区域） | **≠ A** | **必须检出** → `RECOVERY_REQUIRED` |
| **S5b-2** | **H3**（同上） | `T-64M`：`[40 MiB + 1024, +4096)` | **写游标之前**（待写区域） | **== A** | **不可检出**；要求实现与文档**明确声明未覆盖**；若声称"完整覆盖" → **判失败** |
| **S5c** | **H4** | `T-1M`：`[1024, 5120)` | 全部写完 | ≠ A | **必须检出** → `RECOVERY_REQUIRED` |
| **S5d** | **H2** | `T-1M-P`：`[0, 1024)` | **载荷范围之外** | **≠ A** | **必须检出** → `RECOVERY_REQUIRED` |
| **S5e** | **H2** | `T-1M-P`：`[512 KiB, 512 KiB+1024)` | **载荷范围之内**，被完整覆盖 | **== A** | **不可检出**；要求明确声明未覆盖；声称完整覆盖 → 判失败 |

**S5b 前置断言**：外部写入字节固定 `0xAB × 4096`；夹具必须断言 `payload[off:off+4096] != 0xAB×4096` 且 `B[off:off+4096] != 0xAB×4096`。不成立则换偏移。

**S5 统一规则**：

- 任何检出 → 进入/保持 `RECOVERY_REQUIRED`；禁止自动回滚/重试/解除/跳目标。
- 哈希、mtime、锁状态、屏障日志**仅为辅助证据**；`∈{B,A}` 不能证明未被外部修改。
- **不得声称哈希可以发现所有第三方写入**：S5b-2 与 S5e 是两个已证明的反例。
- 证据集：执行前后 WAL 快照与原文、检查点内容、目标前后完整哈希与 mtime、锁状态、屏障日志、helper 写入偏移/长度/字节摘要、目录树。
- 无对应钩子 → 记 **`UNCOVERED`**。

### S6 锁（5 条）

S6a pid 存活｜S6b pid 已死残留｜S6c 锁损坏｜S6d 锁目录缺失｜S6e 锁被占用（含 `LockFileEx` 获取失败）。

WAL 无变化；`READY`。禁止自动删锁、降级无锁、时间阈值判死、损坏锁视为无锁、先 `BEGIN` 后取锁。

### S7 磁盘/持久化失败（**8 条**）

| 用例 | 类别 | 期望 |
|---|---|---|
| S7a | 类1 快照创建失败 | 无 `BEGIN`；`READY`；不需人工 |
| S7b | 类2 `BEGIN` 持久化失败 | 按 A.7.5 四分支（b1–b4）；**目标 == B 不单独放行** |
| S7c-1 | 类3 写入 ENOSPC | `BEGIN` 无终态 → T1 |
| S7c-2 | 类3 **短写**（大小不变） | `BEGIN` 无终态 → T1；唯一拦截手段是写后全文件 SHA-256 |
| S7d | 类3 END 失败 | `BEGIN` 无终态 → T1 |
| S7e | fsync 失败且 `wal_failures` 不可写 | 按 A.7.5 三分支（e1–e3）；检查点 `VERIFIED` 时 → `NO`，有未解决 op → T1，无 → T4；检查点损坏 → `UNKNOWN` → 人工 |
| S7f | `.durable` 缺失/损坏/回退 | 按 A.7.5 三分支（f1–f3）；f1/f2 → `UNKNOWN` → **仅人工**；f3 → `NO` → T1/T4 |
| **S7g** | 存在 `PROVISIONAL` 记录且**无**未解决 op，检查点 `VERIFIED` | `NO` → **T4 检查点重同步** → `YES` → `READY`；断言 T4 不写任何 WAL 记录、不改目标内容 |

**三类故障不混同**：类1（快照失败）/ 类2（`BEGIN` 失败）/ 类3（目标已写）。

### S8 恢复关联与恢复崩溃（7 条）

S8a M4 恢复中途崩溃｜S8b M8 目标 == B、`RECOVERED` 缺失（**T2 不适用**，走 `#r2` + `resolves=[#1,#r1]`）｜S8c 恢复期间快照失效｜S8d 恢复后一致性检查失败｜S8e `resolves` 遗漏 → 仍保持｜S8f `resolves` 含已终结 op → 一致性失败 + 人工｜S8g 恢复链成功 → `READY`，历史完整、无伪造记录。

### S9 WAL 尾部修复（**6 条**）

| 用例 | 崩溃点 | 持久证据 | 期望 |
|---|---|---|---|
| S9a | RP-3（写 `REPAIR_INTENT`）之前 | 可能有证据文件，无 INTENT | 未开始；允许重做；主 WAL 原样；证据不覆盖；`RECOVERY_REQUIRED` |
| S9b | RP-3 之后、RP-4（截断）之前 | INTENT 存在、无 DONE；大小 == `wal_size_before`；tail 哈希匹配 | 从 RP-4 继续 |
| S9c | RP-4 之后、RP-6a 之前 | INTENT 存在、无 DONE；大小 == `tail_offset`；无 `REPAIR` | 从 RP-6a 继续；不得重复截断 |
| S9d | 截断到**中间值** | INTENT 存在、无 DONE；大小非两端值 | **边界不可确定** → `RECOVERY_REQUIRED` + 人工；禁止再截断/猜边界/删证据 |
| **S9e** | **RP-6a 之后、RP-6b 之前**（P0-3 情况②） | `REPAIR` 可见；检查点未覆盖或 `last_durable_record_seq < REPAIR.seq` | `PROVISIONAL`；**禁止写 `REPAIR_DONE`**；检查点 `VERIFIED` → 先完成 RP-6b 并复核，再写 DONE；`INCONSISTENT` → `UNKNOWN` + 人工；禁止再次截断 |
| **S9f** | **`REPAIR` 记录损坏或字段不一致**（P0-3 情况③） | `REPAIR` 行不可解析 / 字段缺失 / `seq` 非单调 / `repair_intent_id` 与 INTENT 不匹配 | 隔离；`WAL_STATE_COMPLETE = UNKNOWN`；**禁止 `REPAIR_DONE`**；**禁止再次修复**；`RECOVERY_REQUIRED` + **必须人工** |

**S9 统一禁止**：因主 WAL 写入失败而截断回滚（该场景属 S7e/S7f，不属 S9）。

### S10 检查点一致性（**4 条**，P0-1 新增）

| 用例 | 注入 | 构造状态 | 期望 |
|---|---|---|---|
| **S10a** | M10 篡改检查点中的 `wal_prefix_sha256` | 检查点字段自洽但前缀哈希与实际不符 | V-2 失败 → `INCONSISTENT` → 全部记录 `PROVISIONAL` → `WAL_STATE_COMPLETE = UNKNOWN` → `RECOVERY_REQUIRED`；**禁止** T1/T2/T4；禁止重写检查点；人工 |
| **S10b** | M10 截断主 WAL 使其短于 `wal_size_at_marker` | WAL 被外部截断 | V-1 失败 → `INCONSISTENT` → `UNKNOWN` → 人工；视为外部干扰信号 |
| **S10c** | M10 删除主 WAL 但保留检查点（反向：保留 WAL 删除检查点） | 二者之一缺失 | 检查点在、WAL 不在 → `INCONSISTENT`；WAL 在、检查点不在 → `ABSENT_DIRTY` → 均 `UNKNOWN` → 人工 |
| **S10d** | M4 在 CP-4 期间崩溃（tmp 已写、`os.replace` 未完成） | 旧检查点仍有效 | `VERIFIED`（旧前缀仍存在）→ 新记录 `PROVISIONAL` → `NO` → 视有无未解决 op 走 T1 / T4；**不得**因 tmp 存在而采信 tmp |

**S10 核心断言**：任何 `INCONSISTENT` 情形下，**不得把任何记录判为 `DURABLE`**，且 `WAL_STATE_COMPLETE` 必须为 `UNKNOWN`，且 `WRITE_PERMITTED = NO`。

## A.18 一致性自审

| 检查 | 结论 |
|---|---|
| `.durable` 定义 vs A.5.6/A.5.7 | 检查点不再独立可信，必须通过 V-1…V-5；`ABSENT_DIRTY`/`INCONSISTENT` 时不得判任何记录 `DURABLE` |
| 检查点 vs `wal_state_digest` | `wal_state_digest` 已纳入 `checkpoint_status`、`last_durable_record_seq`、`wal_prefix_sha256` |
| 检查点 vs T2-2 / T2-7 | T2-2 要求 `VERIFIED` 且覆盖修复后末尾；T2-7 摘要含 `checkpoint_status` → 检查点变化即失效 |
| `WAL_STATE_COMPLETE` 三值 vs 四条解除路径 | `YES` 无需转换；`NO` 可走 T1/T2/T4；`UNKNOWN` 仅人工 |
| A.15 第 3 行 vs P0-2 | 已删除"持久化失败一律评估 T2"的泛化表述，改为按 `NO`/`UNKNOWN` 分流 |
| RP-6a / RP-6b / RP-7 vs 情况①②③ | `REPAIR_DONE` 严格在 RP-6b 的 `VERIFIED` 之后；可见 `REPAIR` 不足以推进 |
| S7e 状态归属 | v5 的"一律 `UNKNOWN`"精化为"检查点 `VERIFIED` → `NO`"，故障触发条件未改 |
| L0-D vs STA-3 / STA-4 / S0f | 3 个 `roundtrip_*.assets` 已入边界；STA-3 显式覆盖 L0-D；S0f 静态断言分类 |
| 用例数 | 矩阵、通过标准、统计三处均为 55 |

## A.19 通过标准

1. **55/55 用例**产出预期状态，零静默通过。
2. 每用例证据包：前置 5 项、执行前后 WAL 快照与原文、**检查点内容与校验结果**、目标前后完整 SHA-256、mtime（仅辅助）、锁状态、屏障日志、目录树、注入点日志、`injection_kind`、所用钩子编号。
3. 恢复类用例：`BYTES`/`OBJECT`/`REDO_VERIFIED` 分别记录；`UNVERIFIED` 或未验证 → 判"部分通过"，不计入通过。
4. `RECOVERY_REQUIRED` 用例中无一次被自动降级为 `READY`；`UNKNOWN` 用例中无一次走 T1/T2/T4。
5. S0a–S0f 通过：拒绝逻辑零副作用；真实资产（含 L0-D 三个文件）未被写入入口接触。
6. 结束后 `snap\` 条目数 == 预期；除 S6d 的目录重建外无锁被自动删除；`wal_evidence\` 无删除。
7. 真实目录 34 个 `.assets` 完整 SHA-256 == `baseline_ledger.json`。
8. 报告明确声明：结果仅覆盖 L1；**STA 通过 ≠ PWA 满足**；**W2-b、S5b-2、S5e 为已证明的不可检出缺口**；不构成对现有脚本的保护证明。

## A.20 禁止的假通过

| 模式 | 原因 |
|---|---|
| 用大小判断写入成功 | 等长覆盖下恒真（S7c-2） |
| 用 mtime 判断是否被改 | 可保留/回填 |
| "目标看起来完整所以已完成" | S3a/S8b 考点 |
| 目标哈希 == B 即放行 | 仅 T2-5 一条 |
| 哈希 == A 即证明无并发写入 | S5b-2 / S5e 反例 |
| 哈希可以发现所有第三方写入 | 同上 |
| **仅比较 `seq <= last_durable_seq` 而不校验前缀** | P0-1：WAL 被截断/替换时会误判 `DURABLE` |
| **重写检查点来消解 `INCONSISTENT`** | 掩盖外部干扰 |
| **把 WAL 持久化失败一律导向 T2** | P0-2 |
| **看到 `REPAIR` 就写 `REPAIR_DONE`** | P0-3：可见 ≠ 已确认持久化 |
| 把 `expected` 与 `actual_after` 直接比较 | 三集合语义错误 |
| 用 `FAILED` 关闭恢复 op | R-5 禁止 |
| 声称 `realpath`/`fstat`/`TestPath` 提供完整并发保护 | A.9 |
| 快照存在即可回滚 | 未校验/无 sidecar 均不可用 |
| `fsync` 失败即断言磁盘有/无数据 | A.7.7 |
| 用内存标记代替持久证据 | A.5 |
| 因写入失败而截断回滚 | A.6.1 |
| 无钩子仍宣称 S5 已覆盖 | A.8.4 |
| 用 STA 结果推断 PWA 满足 | A.10.3 |
| 用 L0-D 文件做测试 | P0-4 |
| `os._exit` 结果表述为断电持久性 | M4 边界 |
| M8/M10 表述为真实故障 | `injection_kind` |

## A.21 未覆盖范围

真实 OS 级 ENOSPC；掉电/强制关机/真实 fsync 语义；跨卷快照；大文件 244 MB/1.3 GB；游戏进程持有句柄；多工具并发；硬链接"打开瞬间"窗口；**W2-b / S5b-2 / S5e 并发写入窗口**；对象级校验仅 `T-REAL`；**PWA-3（内存映射写者）**；**Windows 目录 fsync 无直接等价（CP-4 后的目录项持久化未覆盖）**；现有脚本的保护状态。

---

# B. 测试统计

| 口径 | v5 | **v6** | 变化原因 |
|---|---|---|---|
| 场景组数 | 10 | **11** | 新增 S10（检查点一致性） |
| 子场景数 | 47 | **55** | S0 +1（S0f 分类断言）；S7 +1（S7g T4）；S9 +2（S9e/S9f RP-6 崩溃）；S10 +4（新增组） |
| 独立执行用例数 | 47 | **55** | 与子场景 1:1 |
| 通用断言/用例 | 13 | **14** | 新增 C14：检查点验证结果已记录（`CHECKPOINT_STATUS` + 前缀哈希 + 末条一致性） |
| 通用断言小计 | 611 | **770** | 55 × 14 |
| 专项断言小计 | 122 | **145** | 见下 |
| **总断言数** | 733 | **915** | 770 + 145 |

**专项断言明细**：

| 组 | 用例数 | 每条 | 小计 |
|---|---|---|---|
| S0 | 6 | 3 | 18 |
| S1 | 5 | 2 | 10 |
| S2 | 1 | 4 | 4 |
| S3 | 3 | 2 | 6 |
| S4 | 4 | 3 | 12 |
| S5 | 6 | 3 | 18 |
| S6 | 5 | 2 | 10 |
| S7 | 8 | 2 | 16 |
| S8 | 7 | 3 | 21 |
| S9 | 6 | 3 | 18 |
| S10 | 4 | 3 | 12 |
| **合计** | **55** | — | **145** |

- 合计：**55 × 14 + 145 = 770 + 145 = 915**。
- **对照运行不计入**：5 次（T-1K / T-1M / T-1M-P / T-64M / T-REAL）× 3 条断言 = 15，作为夹具前置条件单独统计。
- 若实现偏离 `buffering=0`，须补 S3d → 56 用例 / 929 断言。
- 若 M9 钩子缺失：S5a/S5b-1/S5b-2/S5c/S5d/S5e 共 6 条记 `UNCOVERED` → **实际可执行用例 = 49**。
- 若 `tool_sha256`/`deps` 机制未建立：8 条重做相关用例只能"部分通过" → **可完全通过用例上界 = 47**（55 − 8）。

---

# C. 未解决 / 未验证事项（四分类）

### C.1 已知设计缺口（不可通过实现消除）

| # | 缺口 |
|---|---|
| 1 | **W2-b / S5b-2 / S5e**：外部写被本工具载荷完整覆盖时，最终哈希 == A，任何内容校验都无法发现 |
| 2 | **PWA-3**：无法断言"无其他进程持有内存映射"，只能转为具名风险接受 |
| 3 | `wal_failures` 与检查点在极端情况下可能都写不进去；此时只能 fail-closed，无法区分"从未写成功"与"刚写就被破坏" |
| 4 | 硬链接"打开瞬间创建"的极窄窗口 |
| 5 | **CP-4 之后的目录项持久化**：Windows 无 `fsync(dir)` 等价物，检查点文件的目录项在掉电场景下的持久性无法保证 |

### C.2 尚未实现

| # | 事项 |
|---|---|
| 6 | `tool_sha256` / `deps` 记录机制 |
| 7 | `wal\<key>.durable.json` 检查点机制（含 CP-1…CP-5 与 V-1…V-5） |
| 8 | `wal_repairs\` / `wal_evidence\` 目录与 RP-1…RP-7 流程 |
| 9 | T4 检查点重同步 |
| 10 | M9 屏障钩子 H1–H4；M10 检查点篡改注入器 |
| 11 | `signoffs\` 目录与签核流程 |
| 12 | 全局 `open()` 审计钩子（STA-6） |
| 13 | `inventory_digest` / `unresolved_set_digest` / `wal_state_digest` 计算代码 |
| 14 | L0-D 边界在工具层的强制（目前仅为文档约定） |

### C.3 尚未测试

| # | 事项 |
|---|---|
| 15 | 全部 55 条用例、915 条断言（全部 `NOT EXECUTED`） |
| 16 | `st_ino` 在 `%TEMP%` 卷上的稳定性 |
| 17 | junction / 符号链接创建权限 |
| 18 | `LockFileEx` 对内存映射写是否有效 |
| 19 | 实现是否按 1 MiB 升序分块（影响 S2 的 `inject_offset`） |
| 20 | 读取器版本与 `sharedassets3.assets` 兼容性 |
| 21 | `os.truncate` 在 NTFS 上的原子性（影响 S9d 判定边界） |
| 22 | 临时目录剩余空间（估算 < 1.4 GB） |
| 23 | 恢复链 ≥3 层的行为（未构造用例） |
| 24 | 检查点在高频写入下的额外 fsync 开销 |

### C.4 理论残余风险

| # | 事项 |
|---|---|
| 25 | `unresolved_set_digest` / `inventory_digest` / `wal_state_digest` / `wal_prefix_sha256` 的 SHA-256 碰撞（用 count + 完整列表 + 长度缓解，不声称绝对） |
| 26 | 生产构建中钩子残留的风险（靠 STA-5 构建标志断言缓解，非形式化证明） |
| 27 | 真实掉电 / 强制关机 / 真实 ENOSPC 语义完全未覆盖 |
| 28 | 若外部进程在 CP-2 与 CP-4 之间替换 WAL 文件，检查点会描述一个"新文件的前缀"，V-1…V-5 可能仍通过（前缀字节相同则哈希相同）。该情形需要文件身份（`st_ino` / 创建时间）参与校验，本版未纳入 |

### C.5 路径确认状态

| 文件 | 状态 | 依据 |
|---|---|---|
| `validation\roundtrip_sharedassets1.assets` | `PATH_VERIFIED` | CAP-014.4 台账 |
| `validation\roundtrip_sharedassets10.assets` | `PATH_VERIFIED` | CAP-014.4 台账 |
| `validation\roundtrip_sharedassets3.assets` | `PATH_VERIFIED` | CAP-014.4 台账 |

**无 `PATH_UNVERIFIED` 项。** 三个路径全部来自台账，未推测、未拼接、未运行脚本补查。

---

# D. 执行边界声明

- 本轮**仅完成文档修订**（v5 → v6），输出即本文件。
- **未执行任何 P1 测试**：S0a–S10d 共 55 条全部 `NOT EXECUTED`。
- **未编写或实现任何功能代码**：WAL、`.durable`、`LockFileEx`、恢复、快照、签核均未实现。
- **未修改任何项目源代码、配置文件、Git 状态或非本文档文件。**
- **未对任何真实 `.assets` 执行写入、删除、移动、重命名或覆盖**；含 17 个 L0-A、14 个 L0-B、3 个 L0-D。
- **未使用 `--apply`。**
- **未执行任何 Git 写操作**（add / commit / reset / clean / checkout / switch / stash）。
- **未调用 Hermes**，未引入新依赖。
- **未创建测试文件、快照、锁文件、WAL、检查点、临时目录或证据包。**
- 本轮只读核对动作：列出 `docs/` 目录、查找既有 CAP-014 文档、从 `F:\GGC_snapshots\baseline_ledger.json` 读取 3 条 `roundtrip` 记录以核实路径。均为只读。

**静态文档检查不等于测试通过。**

---

# E. 最终状态

```
REVIEW_REQUIRED — NOT AUTHORIZED FOR EXECUTION
```

v6 完成后即停止，等待人工审查。不进入 P1 测试执行、功能实现、基线认定或真实资产写入阶段。
