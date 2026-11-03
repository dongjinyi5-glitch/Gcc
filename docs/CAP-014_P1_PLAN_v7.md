# CAP-014 P1 防护方案 v7

> **REVIEW_REQUIRED — NOT AUTHORIZED FOR EXECUTION**
>
> 本文档为纯设计文本。全部测试用例处于 `NOT EXECUTED` 状态。
> 未经人工审查与书面授权，不得进入 P1 测试执行、功能实现或真实资产写入阶段。

| 项 | 值 |
|---|---|
| 文档版本 | **v7** |
| 上游版本 | v6（`docs\CAP-014_P1_PLAN_v6.md`，62,854 B，SHA-256 `73c02d66fb7846095f310e7c2e804392c90ace3762c66fc75861f1b44facc5b2`，未被修改） |
| 修订依据 | 本轮 4 项：P0-1 WAL 文件身份连续性 / P0-2 故障日志不可用时的统一处理 / P0-3 目标持久化先于 WAL END / P1-1 空 WAL 与检查点初始组合 |
| 文档性质 | PLAN-ONLY，静态文本 |
| 执行状态 | 全部用例 `NOT EXECUTED` |
| **P0 阻塞项** | **4 项（A.22），阻断真实写入，需人工决策** |

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
| `ST-<n>` | 被测操作步骤（A.8，v7 扩为 12 步） |
| `H<n>` | M9 屏障钩子位置（v7 扩为 6 个） |
| `RP-<n>` | 尾部修复步骤（A.6） |
| `CP-<n>` | 检查点更新步骤（A.5.5） |
| `V-<n>` / `V-T` | 启动扫描校验项（A.5.6；空态组合另见 A.5.9） |
| `T-<id>` | 测试目标类型 |
| `T1–T5` | 状态解除途径（v7 新增 T5 人工重置） |
| `PWA-<n>` / `STA-<n>` | 生产 / 测试准入条件 |
| `C<n>` / `M<n>` | 通用断言（v7 扩为 17 条）/ 注入手段 |
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
| 快照状态 | `SNAPSHOT_VALID` / `SNAPSHOT_ORPHAN` / `SNAPSHOT_NO_SIDECAR` / `SNAPSHOT_CORRUPT` / `SNAPSHOT_ABSENT` |
| 操作状态（派生） | `OP_COMMITTED` / `OP_ABORTED` / `OP_RECOVERED` / `OP_SUPERSEDED` / `OP_UNRESOLVED` / **`OP_MANUAL_RESET`（v7 新增）** |
| 记录持久性（派生） | `DURABLE` / `PROVISIONAL` |
| 检查点状态 | `VERIFIED` / `ABSENT_CLEAN` / `ABSENT_DIRTY` / `INCONSISTENT` |
| **WAL 身份状态（v7 新增）** | `IDENTITY_VERIFIED` / `IDENTITY_MISMATCH` / `IDENTITY_UNVERIFIABLE` / `IDENTITY_NOT_APPLICABLE` |
| **故障日志状态（v7 新增）** | `FAIL_READABLE_EMPTY` / `FAIL_READABLE_WITH_RECORDS` / `FAIL_UNREADABLE` / `FAIL_CORRUPT` / `FAIL_ABSENT_CONSISTENT` / `FAIL_ABSENT_INCONSISTENT` |
| **运行状态（v7 三值）** | `READY` / `RECOVERY_REQUIRED` / **`MANUAL_BLOCKED`** |

**`RECOVERY_REQUIRED` vs `MANUAL_BLOCKED`**：前者存在自动出口（T1 / T4）或人工出口（T2 / T5）；后者**只有** T5 人工出口，任何自动路径一律禁止。

### A.2.2 十二条术语红线

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
| 操作 | `END` | 是（WRITE） | `seq, op_id, op_kind, target_sha256_after, target_persisted:true, readback_verified:true, verify_summary, elapsed_ms`<br>**（v7）`target_persisted` 与 `readback_verified` 必须为 `true`，否则不得写 `END`** |
| 异常 | `ABORTED` | 是（WRITE） | `seq, op_id, op_kind, reason, target_sha256_observed` |
| 异常 | `FAILED` | **否** | `seq, op_id(可空), stage, error_class, errno, target_sha256_observed, wal_durable, ts` |
| 恢复 | `RECOVERED` | 是（RECOVERY） | `seq, op_id, op_kind, snapshot_id_used, snapshot_sha256_used, snapshot_recomputed_sha256, pre_recovery_target_sha256, target_sha256_after, target_persisted, readback_verified, resolves_op_ids[], resolves_set_digest, resolves_count, recovery_verified:true, consistency_check:true` |
| 日志修复 | `REPAIR` | **否** | `seq, repaired_file, repair_of, repair_intent_id, discarded_bytes, discarded_lines, torn_tail_hex_prefix, evidence_path, reason, operator, ts` |
| **人工重置（v7 新增）** | **`MANUAL_RESET`** | 是（`op_kind=MANUAL`） | `seq, op_id, op_kind=MANUAL, override_reason, overridden_status{checkpoint_status, wal_identity_status, failure_log_status}, state_digest_at_override, target_sha256_observed, signoff_id, operator, ts` |

`REPAIR` 与 `MANUAL_RESET` 无 `op_id` 意义上的业务操作（`MANUAL_RESET` 自带独立 `op_id`）。检查点中 `last_durable_op_id` 对 `REPAIR` 记 `null`。

### A.4.2 合法序列

| 序列 | 结果 |
|---|---|
| `BEGIN(WRITE) → END` | `OP_COMMITTED` |
| `BEGIN(WRITE) → ABORTED` | `OP_ABORTED`（须复核 `observed == before`；不等则声明为假 → `OP_UNRESOLVED`） |
| `BEGIN(RECOVERY) → RECOVERED` | `OP_RECOVERED` |
| `BEGIN(RECOVERY) → FAILED` | **`OP_UNRESOLVED`**（`FAILED` 不关闭 op） |
| `BEGIN(RECOVERY) → ABORTED` | ❌ 非法 |
| `BEGIN(MANUAL) → MANUAL_RESET` | `OP_MANUAL_RESET`（**前提**：`OP_UNRESOLVED == ∅`；否则非法） |
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
  "checkpoint_version": 2,
  "target_key": "<32 hex>",
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
CP-5  写 <key>.durable.json.tmp.<pid> → fsync → os.replace → <key>.durable.json
CP-6  重新打开检查点并回读校验（含 CP-3 的哈希、CP-4 的身份）；失败即视为未推进
```

**崩溃方向性**：检查点永远描述一个**仍然存在且身份未变**的前缀，因此任何时刻崩溃只会导致"更多记录被判 `PROVISIONAL`"（保守），**不会**导致"未持久化或来自另一文件的记录被判 `DURABLE`"（乐观）。

| 崩溃点 | 结果 |
|---|---|
| CP-1 前 | 无新记录；旧检查点仍 `VERIFIED` |
| CP-1 后、CP-2 前 | 新记录可见但未 fsync；检查点未推进 → 新记录 `PROVISIONAL` |
| CP-2 后、CP-5 前 | 新记录实际已持久，但检查点未推进 → 仍判 `PROVISIONAL`（保守方向） |
| CP-4 检测到身份变化 | 中止，不发布检查点 → 见 A.5.7 |
| CP-5 中（tmp 已写、replace 未完成） | 旧 `.durable.json` 未被替换 → 仍 `VERIFIED`，新记录 `PROVISIONAL` |
| CP-5 后、CP-6 前 | 新检查点已生效；若回读失败则下次扫描发现不一致 |

**关键语义（T4 的基础）**：一次成功的 `fsync` 会把该文件此前所有未确认的字节一并持久化。因此后续的检查点推进**合法地**把此前的 `PROVISIONAL` 记录转为 `DURABLE` —— 这不是掩盖，而是该 fsync 的真实效果。

### A.5.6 启动扫描的校验序列（V-0…V-6 + V-T）

| 项 | 校验 | 失败后果 |
|---|---|---|
| **V-0（v7 新增）** | WAL 文件存在性与可打开性；取当前文件身份 | 缺失且检查点描述非空前缀 → `INCONSISTENT`；身份不可得 → `IDENTITY_UNVERIFIABLE` |
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

| 情形 | `WAL_IDENTITY_STATUS` | `CHECKPOINT_STATUS` | `WAL_STATE_COMPLETE` | 运行状态 | 允许 |
|---|---|---|---|---|---|
| 身份一致 | `IDENTITY_VERIFIED` | 由 V-1…V-6 决定 | 由记录与 op 状态决定 | — | 按 A.7 |
| 身份不一致 | `IDENTITY_MISMATCH` | `INCONSISTENT` | `UNKNOWN` | `MANUAL_BLOCKED` | **仅 T5** |
| 身份不可得（`st_ino == 0` 且无 `file_index`） | `IDENTITY_UNVERIFIABLE` | `INCONSISTENT` | `UNKNOWN` | `MANUAL_BLOCKED` | **仅 T5** |
| WAL 与检查点均不存在 | `IDENTITY_NOT_APPLICABLE` | `ABSENT_CLEAN` | `YES` | `READY` | 正常写入 |
| 句柄视图与路径视图矛盾 | `IDENTITY_MISMATCH` | `INCONSISTENT` | `UNKNOWN` | `MANUAL_BLOCKED` | **仅 T5** |

**硬规则**：`IDENTITY_MISMATCH` / `IDENTITY_UNVERIFIABLE` 时**不得自动推进 durable checkpoint，不得允许新写入**。

#### A.5.7.5 设计 vs 实现的分离声明

> 以上 ID-1…ID-6、V-0 / V-1b、`wal_identity` 字段、身份比对逻辑**全部为设计层面要求，尚未实现，尚未测试**。本文档不得被理解为"身份连续性已经保证"。相关验证见 S11a–S11d，全部 `NOT EXECUTED`。

#### A.5.7.6 平台可行性 → P0 阻塞项

若在目标卷上无法获得**稳定、非零、可区分**的文件身份（`st_ino == 0` 或索引复用不可忽略），则本方案**不能提供 WAL 身份连续性保证**，该情形列为 **BLK-1（A.22）**，必须阻断真实写入，不得以文字描述视为已解决。

### A.5.8 纳入 `wal_state_digest` 与 T2

```json
{"wal_size": 0, "last_seq": 0,
 "checkpoint_status": "VERIFIED|ABSENT_CLEAN|ABSENT_DIRTY|INCONSISTENT",
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

### A.5.9 空 WAL / 检查点的六种初始组合（P1-1）

**空前缀常量**：`EMPTY_PREFIX_SHA256 = e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`。

**"干净初始"判定辅助条件（ALL-GONE）**：以下五项**全部**不成立才可判干净 ——
① `wal_evidence\<key>.*` 存在；② `wal_repairs\<key>.jsonl` 存在且非空；③ `wal_failures\<key>.jsonl` 存在且非空；④ `lock\<key>.lock` 存在；⑤ 快照目录存在该 target 的快照。

| # | 组合 | 分类名 | 干净初始 | 允许创建/初始化检查点 | 人工 | 允许 `READY` | 允许目标写入 | "无末条记录"的处理 |
|---|---|---|---|---|---|---|---|---|
| **1** | WAL 不存在 + checkpoint 不存在 | `EMPTY_CLEAN` | **是** | **允许**（惰性：首次写 `BEGIN` 时按 CP-1…CP-6 创建，`prefix_record_count=0` 只是从未落盘的状态） | 否 | **允许** | 允许（PWA 全通过时） | 不涉及末条记录；首次检查点在 `BEGIN` 落盘后创建，`prefix_record_count=1` |
| **2** | WAL 存在但 0 字节 + checkpoint 不存在 | `EMPTY_UNCHECKPOINTED` | **是**，**当且仅当 ALL-GONE 成立** | **允许**（同上） | ALL-GONE 不成立 → **必须** | ALL-GONE 成立 → 允许；否则禁止 | 同上 | 同 #1；0 字节与"不存在"在语义上等价 |
| **3a** | WAL 0 字节 + checkpoint 存在且描述**空前缀** | `VERIFIED`（空态） | 是 | 已存在，不新建 | 否 | **允许** | 允许 | 走 A.5.4 第 4 条空态一致性（`prefix_record_count==0`、`size==0`、`sha==EMPTY_PREFIX`、`seq==0`、`kind==null`、`op_id==null`），**不比对末条记录** |
| **3b** | WAL 0 字节 + checkpoint 描述**非空前缀** | `INCONSISTENT` | 否 | **禁止** | **必须** | 禁止 | 禁止 | V-1 失败（`0 < wal_size_at_marker`） |
| **4** | WAL 有记录 + checkpoint 不存在 | `ABSENT_DIRTY` | 否 | **禁止**（不得凭空创建检查点） | **必须** | 禁止 | 禁止 | 无检查点可依，不涉及 |
| **5a** | WAL 不存在 + checkpoint 描述**空前缀** | `VERIFIED`（空态，WAL 视作空） | 是 | 已存在 | 否 | **允许** | 允许 | 同 #3a |
| **5b** | WAL 不存在 + checkpoint 描述**非空前缀** | `INCONSISTENT` | 否 | **禁止** | **必须** | 禁止 | 禁止 | V-0 失败（文件缺失但声明非空前缀） |
| **6** | WAL 有记录 + checkpoint 存在，但 seq / 前缀哈希 / 计数 / **文件身份**任一不一致 | `INCONSISTENT` | 否 | **禁止** | **必须** | 禁止 | 禁止 | 见 V-1…V-6 / V-1b |

**三条硬规则**：

1. **禁止虚构末条记录**：`prefix_record_count == 0` 时不得用"假想的一条记录"通过 V-4 / V-5，必须走空态一致性（A.5.4 第 4 条）。
2. 组合 #2 的"干净"判定**依赖 ALL-GONE**：0 字节 WAL 无法与"被截断到 0"区分，只能靠旁证；旁证不成立即转 `MANUAL_BLOCKED`。
3. 组合 #3b / #4 / #5b / #6 一律不得自动创建或重写检查点。

## A.6 WAL 尾部残缺行修复流程

### A.6.1 适用范围与禁止范围

| | 内容 |
|---|---|
| **允许修复** | 主 WAL **末尾**存在无法解析为记录的字节，且该残行是**最后一行** |
| **禁止** | 因主 WAL 写入失败（短写 / 异常 / fsync 失败）而主动截断回滚——这些字节**可能是完整记录**，截断即销毁证据 |
| **禁止** | 非末行不可解析时自动修复 |
| **禁止** | 手工编辑 WAL；不经 A.6 直接 `truncate`；删除或重写历史以掩盖不确定状态 |
| **禁止（v7）** | 在 `WAL_IDENTITY_STATUS != IDENTITY_VERIFIED` 时执行任何修复步骤 |

### A.6.2 九步流程（v7：RP-4 后加身份复核）

| 步 | 动作 | 持久化要求 |
|---|---|---|
| **RP-1 识别** | 经已校验句柄逐行解析，定位第一条失败行；断言它是最后一行；计算 `tail_offset`、`tail_len` | 只读 |
| **RP-2 保存证据** | 复制 `[tail_offset, EOF)` 到 `wal_evidence\<key>.<ts>.tail.bin`；flush + fsync；回读算 `tail_sha256`；记录 `tail_hex_prefix` | 证据文件必须 fsync 后才可继续 |
| **RP-3 写修复意图** | 向 `wal_repairs\<key>.jsonl` 追加 `REPAIR_INTENT{repair_intent_id, wal_size_before, tail_offset, tail_len, tail_sha256, evidence_path, wal_identity_before, tool_sha256, ts}`；fsync | 必须先于任何截断 |
| **RP-4 截断** | `os.truncate(wal, tail_offset)`（经同一路径；若实现支持，用句柄 `SetEndOfFile`） | — |
| **RP-4b 身份复核（v7）** | 重新取 WAL 身份，必须等于 `wal_identity_before`；不等 → 中止，`MANUAL_BLOCKED` | 只读 |
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
| RP-3 完成、RP-4 之前 | INTENT 存在、无 DONE；大小 == `wal_size_before`；tail 哈希匹配 | 已开始未截断 | 从 RP-4 继续 | 重写 INTENT；删证据 |
| **RP-4b 检测到身份变化** | INTENT 存在、无 DONE；身份 ≠ `wal_identity_before` | **身份不可信** | 停止 → `MANUAL_BLOCKED` | 任何自动动作 |
| RP-4 进行中，大小 ∈ (`tail_offset`, `wal_size_before`) | INTENT 存在、无 DONE；大小非两端值 | **边界不可确定** | 停止 → `RECOVERY_REQUIRED` + 人工 | 再次截断；猜边界；删证据 |
| RP-4 完成、RP-6a 之前 | INTENT 存在、无 DONE；大小 == `tail_offset`；无 `REPAIR` | 已截断未记录 | 从 RP-6a 继续 | 重复截断 |
| RP-6a 完成、RP-6b 之前 | INTENT 存在、无 DONE；`REPAIR` 可见；检查点未覆盖 | 情况 ② | 先完成 RP-6b 并复核 | 写 `REPAIR_DONE`；再次截断 |
| RP-6b 完成、RP-7 之前 | INTENT 存在、无 DONE；`VERIFIED` 且覆盖 `REPAIR` | 情况 ① | 写 `REPAIR_DONE` | 再写一条 `REPAIR` |
| RP-7 之后 | INTENT + DONE；检查点覆盖 `REPAIR` | 完成 | 常规扫描 | — |
| 任何时刻大小 ∉ {`wal_size_before`, `tail_offset`} | — | **不可确定** | 停止 → `RECOVERY_REQUIRED` + 人工 | 任何自动动作 |
| `REPAIR_DONE` 存在但无匹配 `REPAIR` 或检查点未覆盖 | — | 不一致 | 停止 → 人工 | 自动补写 |

**总则**：任何一步无法确定 → 保持 `RECOVERY_REQUIRED` 或转 `MANUAL_BLOCKED`，证据全部保留，不得静默忽略。

## A.7 持久化判定与状态转移

### A.7.1 `WAL_STATE_COMPLETE` 三值（v7 扩充失败日志条件）

| 值 | 条件 |
|---|---|
| **`YES`** | `CHECKPOINT_STATUS ∈ {VERIFIED, ABSENT_CLEAN}` **且** `WAL_IDENTITY_STATUS ∈ {IDENTITY_VERIFIED, IDENTITY_NOT_APPLICABLE}` **且** `FAILURE_LOG_STATUS ∈ {FAIL_READABLE_EMPTY, FAIL_ABSENT_CONSISTENT}` **且** 所有记录 `DURABLE` **且** 无 `OP_UNRESOLVED` **且** 无结构异常 **且** V-T 通过 |
| **`NO`** | 检查点与身份均可验证；但存在 `OP_UNRESOLVED` 或存在 `PROVISIONAL` 记录，**且** `FAILURE_LOG_STATUS ∈ {FAIL_READABLE_EMPTY, FAIL_READABLE_WITH_RECORDS, FAIL_ABSENT_CONSISTENT}` 且其中若为 `FAIL_READABLE_WITH_RECORDS`，每条记录均能对应到已识别的失败阶段 |
| **`UNKNOWN`** | `CHECKPOINT_STATUS ∈ {ABSENT_DIRTY, INCONSISTENT}`；或 `WAL_IDENTITY_STATUS ∈ {IDENTITY_MISMATCH, IDENTITY_UNVERIFIABLE}`；或 `FAILURE_LOG_STATUS ∈ {FAIL_UNREADABLE, FAIL_CORRUPT, FAIL_ABSENT_INCONSISTENT}`；或 V-T 失败；或存在无法判定的结构异常 |

**关键区分**：`NO` = 已知不完整、可走受控自动路径；`UNKNOWN` = 状态不可判定、**只能人工**。

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
| **T1** | 自动 | `WAL_STATE_COMPLETE == NO`；检查点 `VERIFIED`；身份 `IDENTITY_VERIFIED`；`FAILURE_LOG_STATUS ∈ {FAIL_READABLE_EMPTY, FAIL_READABLE_WITH_RECORDS, FAIL_ABSENT_CONSISTENT}`；**存在** `OP_UNRESOLVED`；快照 `SNAPSHOT_VALID` | 一次完整 `RECOVERY` 操作，`resolves_op_ids` 覆盖全部未解决 op |
| **T2** | **必须人工签核** | A.7.5 的 7 条全部成立 | 修复 + 签核 |
| **T3** | 无需转换 | 本就 `READY` | — |
| **T4** | 自动 | `WAL_STATE_COMPLETE == NO`；检查点 `VERIFIED`；身份 `IDENTITY_VERIFIED`；故障日志同上三值之一；**无** `OP_UNRESOLVED`；无结构异常；唯一缺陷是存在 `PROVISIONAL` 记录 | 检查点重同步：`fsync(H_wal)` → 重算前缀哈希 → 复核身份（CP-4）→ 按 CP-5/CP-6 发布 → 复核 `VERIFIED`。**不写任何 WAL 记录，不改动目标内容** |
| **T5** | **仅人工**（v7 新增） | `OP_UNRESOLVED == ∅`；存在 T5 签核文件；人工已核对 `overridden_status` 三项 | 写 `BEGIN(MANUAL) → MANUAL_RESET`，记录被覆盖的三项状态、`state_digest_at_override`、`operator`、`signoff_id`；推进检查点；目标**不被改动** |

**T4 的合法性依据**：A.5.5 已确立"一次成功 `fsync` 会把此前所有未确认字节一并持久化"。T4 只把这一事实记录进检查点。它**不能**用于 `UNKNOWN`。

**T5 的边界**：T5 **不是**"把 UNKNOWN 变成已验证"，而是"人工确认后带印记地接受现状"。`MANUAL_RESET` 记录永久保留，`wal_state_digest` 因此带上人工印记，后续任何自动路径都能看到该印记。T5 **不得**用于跳过 T1（存在未解决 op 时非法）。

### A.7.4 状态转移闭包表（P0-2 第 4 条：证明不存在 UNKNOWN → READY 的自动路径）

| 起点 | 出口 | 是否自动 | 条件 |
|---|---|---|---|
| `READY` | `READY` | — | 正常 |
| `READY` | `RECOVERY_REQUIRED` | 自动 | 出现 `OP_UNRESOLVED` / `PROVISIONAL` / V-T 失败 |
| `READY` | `MANUAL_BLOCKED` | 自动 | 身份 / 检查点 / 故障日志进入不可判定 |
| `RECOVERY_REQUIRED` | `READY` | 自动 | **T1** 或 **T4** 成功（A.7.3 前提全满足） |
| `RECOVERY_REQUIRED` | `READY` | **人工** | **T2** 签核 / **T5** 签核 |
| `RECOVERY_REQUIRED` | `MANUAL_BLOCKED` | 自动 | 身份 / 故障日志 / 检查点恶化 |
| **`MANUAL_BLOCKED`** | **`READY`** | **仅人工 T5** | `OP_UNRESOLVED == ∅` + T5 签核；**无任何自动出口** |
| `MANUAL_BLOCKED` | `RECOVERY_REQUIRED` | **不允许** | 不得降级；只能经 T5 出 |
| 任意 | `UNKNOWN`（子状态） | — | `WAL_STATE_COMPLETE` 是派生值，不是运行状态 |

**结论**：`WAL_STATE_COMPLETE == UNKNOWN` 的三个来源（检查点 / 身份 / 故障日志）全部映射到 `MANUAL_BLOCKED`，而 `MANUAL_BLOCKED` **没有自动出口**。因此**不存在从未知状态自动回到 `READY` 的路径**。

### A.7.5 T2 的 7 条（v7 强化 T2-2 / T2-6）

| # | 条件 |
|---|---|
| **T2-1** | 唯一结构缺陷是末尾不可解析残行，且已按 A.6 完成修复（`REPAIR` 含 `repair_intent_id` 与 `evidence_path`） |
| **T2-2** | 修复后文件完全可解析、seq 严格单调、无重复 `op_id`、无未知事件类型；**且 `CHECKPOINT_STATUS == VERIFIED` 覆盖到修复后末尾（V-0…V-6 全通过）；且 `WAL_IDENTITY_STATUS == IDENTITY_VERIFIED`** |
| **T2-3** | **不存在任何 `OP_UNRESOLVED`**。不放宽 |
| **T2-4** | 三集合语义校验成立（A.9），且 `actual_unresolved_set_after == ∅`；**不得把恢复前集合与恢复后空集直接比较** |
| **T2-5** | 目标全文件 SHA-256 == B，B 为现场重算的快照内容哈希 |
| **T2-6** | `FAILURE_LOG_STATUS ∈ {FAIL_READABLE_EMPTY, FAIL_ABSENT_CONSISTENT}`（v7：`FAIL_READABLE_WITH_RECORDS` 也可，但每条记录须已闭合；`FAIL_UNREADABLE` / `FAIL_CORRUPT` / `FAIL_ABSENT_INCONSISTENT` 一律不成立） |
| **T2-7** | 存在有效签核，且其 `wal_state_digest_at_signoff` == **当前** `wal_state_digest`（含 `checkpoint_status` / `wal_identity_status` / `failure_log_status`） |

**推论**：`WAL_STATE_COMPLETE == UNKNOWN` 时 T2-2 与 T2-6 必然不成立，因此 **T2 永不适用于 `UNKNOWN`**。

### A.7.6 S7b / S7e / S7f / S7g / S7h 的分支处理

| 用例 | 故障 | 分支 | 检查点 | 身份 | 故障日志 | `WAL_STATE_COMPLETE` | 允许路径 |
|---|---|---|---|---|---|---|---|
| **S7b** | `BEGIN` 持久化失败 | b1 完整可见 + 已覆盖 | `VERIFIED` | `VERIFIED` | 任一可判定值 | `NO` | T1 |
| | | b2 完整可见 + 未覆盖 | `VERIFIED` | `VERIFIED` | 同上 | `NO` | T1 |
| | | b3 不完整（残行） | `VERIFIED` | `VERIFIED` | 同上 | `NO` | 先按 A.6 修复 → b1/b2 或 T2 |
| | | b4 检查点 `INCONSISTENT` | `INCONSISTENT` | — | — | `UNKNOWN` | **仅 T5** |
| **S7e** | `fsync` 失败 **且** `wal_failures` 不可写 | e1 有未解决 op | `VERIFIED` | `VERIFIED` | `FAIL_ABSENT_INCONSISTENT` | `UNKNOWN` | **仅 T5** |
| | | e2 无未解决 op | `VERIFIED` | `VERIFIED` | `FAIL_ABSENT_INCONSISTENT` | `UNKNOWN` | **仅 T5** |
| | | e3 检查点也损坏 | `INCONSISTENT` | — | — | `UNKNOWN` | **仅 T5** |
| **S7f** | `.durable` 缺失 / 损坏 / 回退 | f1 缺失 + WAL 有记录 | `ABSENT_DIRTY` | — | — | `UNKNOWN` | **仅 T5** |
| | | f2 损坏或不可解析 | `INCONSISTENT` | — | — | `UNKNOWN` | **仅 T5** |
| | | f3 回退（合法更早前缀） | `VERIFIED` | `VERIFIED` | 任一可判定值 | `NO` | T1 / T4 |
| **S7g** | `PROVISIONAL` 且无未解决 op | — | `VERIFIED` | `VERIFIED` | 任一可判定值 | `NO` | T4 |
| **S7h（v7 新增）** | `fsync` 失败 **但** `wal_failures` 可写且含对应 `FAILED` | h1 有未解决 op | `VERIFIED` | `VERIFIED` | `FAIL_READABLE_WITH_RECORDS` | `NO` | T1 |
| | | h2 无未解决 op | `VERIFIED` | `VERIFIED` | `FAIL_READABLE_WITH_RECORDS` | `NO` | T4 |

> **v6 → v7 的收紧**：v6 把 S7e 判为 `NO`（可走 T1/T4）。v7 依 P0-2 第 6 条"不得用检查点已验证替代缺失的故障证据"改为 `UNKNOWN` → **仅 T5**；同时新增 S7h 承载"失败日志可写"的合法自动路径。二者共同覆盖"故障日志可用 / 不可用"两侧。

### A.7.7 持久化失败情形总表

| 情形 | 主 WAL | 检查点 | 身份 | 故障日志 | 记录判定 | `WAL_STATE_COMPLETE` | 放行 |
|---|---|---|---|---|---|---|---|
| fsync 失败 + 日志可写 + 有对应记录 | 可见 | 未推进但 `VERIFIED` | `VERIFIED` | `FAIL_READABLE_WITH_RECORDS` | `PROVISIONAL` | `NO` | 否（须先 T1/T4） |
| fsync 失败 + 日志不可写 | 可见 | 未推进但 `VERIFIED` | `VERIFIED` | `FAIL_ABSENT_INCONSISTENT` | `PROVISIONAL` | `UNKNOWN` | **否，仅 T5** |
| 日志与检查点均不可持久化 | 可见 | 不可用 | 可能 `VERIFIED` | `FAIL_UNREADABLE` | `PROVISIONAL` | `UNKNOWN` | **否，仅 T5** |
| 日志损坏 | 可见 | 视情况 | 视情况 | `FAIL_CORRUPT` | 视情况 | `UNKNOWN` | **否，仅 T5** |
| 检查点 `INCONSISTENT` / 身份不一致 | 可见 | 不可用 | 不一致 | 视情况 | `PROVISIONAL` | `UNKNOWN` | **否，仅 T5** |
| 正常完成 | 可见 | 已推进 `VERIFIED` | `VERIFIED` | `FAIL_READABLE_EMPTY` | `DURABLE` | 由 op 状态决定 | 视 op 状态 |

### A.7.8 `WRITE_PERMITTED`

```
WRITE_PERMITTED = YES 仅当：
  WAL_STATE_COMPLETE == YES
  AND CHECKPOINT_STATUS ∈ {VERIFIED, ABSENT_CLEAN}
  AND WAL_IDENTITY_STATUS ∈ {IDENTITY_VERIFIED, IDENTITY_NOT_APPLICABLE}
  AND FAILURE_LOG_STATUS ∈ {FAIL_READABLE_EMPTY, FAIL_ABSENT_CONSISTENT}
  AND V-T 通过
  AND 快照 == SNAPSHOT_VALID
  AND 锁已获取（LockFileEx + 工具锁）
  AND 无待人工签核项
  AND 游戏进程未运行
  AND PWA 准入通过（A.10.1）
```

**不得假设 `write()` 或 `fsync()` 失败意味着数据一定在盘上，或一定不在盘上**；失败只能推出"持久性未知"。

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
ST-8   写入                等长原地覆盖，1 MiB 固定块、升序、每块一次 write
ST-9   目标持久化          flush + os.fsync(目标句柄) / FlushFileBuffers
ST-10  回读验证            长度 + 全文件 SHA-256 == A + 对象级回读
ST-11  提交前复检          紧贴 END，再次全文件 SHA-256（捕捉 ST-10 之后的变化）
ST-12  写 END + fsync + 检查点推进
```

### A.8.2 目标持久化与 END 的顺序（P0-3 核心）

| 规则 | 内容 |
|---|---|
| **ORD-1** | `ST-9` 必须对**目标文件句柄**执行 `flush` + `os.fsync(fd)`（Windows 上 `os.fsync` 走 `_commit` → `FlushFileBuffers`）。仅有 `flush()` 不算持久化 |
| **ORD-2** | `ST-10` 必须重新读取目标（经同一句柄或重新打开后经 ST-3 身份确认），验证：文件长度 == 预期、全文件 SHA-256 == A、对象级可解析（`T-REAL`） |
| **ORD-3** | `ST-12` 写 `END` 的**前提**是 `ST-9` 与 `ST-10` 均成功；`END.target_persisted` 与 `END.readback_verified` 必须为 `true` |
| **ORD-4** | `ST-11` 是"提交前最后一道门"：再次计算全文件哈希，若 ≠ A 则**不写 `END`**，写 `FAILED{stage:precommit_recheck}` |
| **ORD-5** | `ST-9` / `ST-10` / `ST-11` / `ST-12` 任一步失败 → op 保持 `OP_UNRESOLVED`，写 `FAILED{stage:...}`，**禁止**写 `END`，进入 T1 |
| **ORD-6** | `ST-12` 中 `END` 已持久但检查点未推进 → `END` 为 `PROVISIONAL`，op 已 `OP_COMMITTED`，`NO` → **T4**（不得视为失败重写） |

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
| **H3** | `ST-8` 内部，**块边界 k 处** | S5b-1、S5b-2 |
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
| PWA-6 | `WAL_STATE_COMPLETE == YES` ∧ `CHECKPOINT_STATUS ∈ {VERIFIED, ABSENT_CLEAN}` ∧ `WAL_IDENTITY_STATUS ∈ {IDENTITY_VERIFIED, IDENTITY_NOT_APPLICABLE}` ∧ `FAILURE_LOG_STATUS ∈ {FAIL_READABLE_EMPTY, FAIL_ABSENT_CONSISTENT}` | PASS / FAIL / UNKNOWN |
| PWA-7 | 用户对该文件、该次写入的书面授权 | PASS / FAIL |
| **PWA-8（v7）** | 无 `BLK-1…BLK-4` 未决阻塞项（A.22） | PASS / FAIL |

**规则**：① PWA-1/2/4/5/6/7/8 必须全部 `PASS`，任一 `FAIL`/`UNKNOWN` → 阻止真实写入；② PWA-3 恒为 `UNVERIFIABLE`，真实写入必须另有用户具名风险接受并写入台账 `risk_acceptance`；③ PWA 全满足也不代表并发保护完整（`W2-b` 部分不可检出，仅 V-T 延迟检出）。

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
                        "failure_log_status": "..."},
  "state_digest_at_override": "...",
  "observed_target_sha256": "...",
  "unresolved_set_empty": true,
  "operator": "...", "ts_wall": "...", "tool_sha256": "...",
  "statement": "我已知悉该 target 的持久化状态不可由机器判定；本次重置仅重建状态记录，不修复任何数据，且不会使该 target 恢复为已验证状态。"
}
```

**前提**：`unresolved_set_empty == true`（存在未解决 op 时必须先走 T1，T5 非法）。

**缺失处理**：签核不存在 / `unresolved_set_empty` 为 false / `state_digest_at_override` ≠ 当前 / `signoff_id` 复用 → **T5 不可执行**。

## A.15 故障路径交叉核对表

**通用前提**：不得假设 `write()` 或 `fsync()` 失败意味着数据一定在盘上或一定不在盘上；失败只能推出"持久性未知"。

| # | 故障点 | 可能持久化的证据 | 重启扫描结果 | 允许的下一步 | 禁止的动作 | 预期运行状态 |
|---|---|---|---|---|---|---|
| 1 | 快照发布中途失败 | 半截 `.tmp`；内容已发布无 sidecar；三方不一致 | 无条目 / `SNAPSHOT_NO_SIDECAR` / `SNAPSHOT_CORRUPT` | 保留证据；本次写入终止；释放锁 | 删除 tmp/内容；用无 sidecar 快照恢复；重写 sidecar 覆盖 | `READY`（无 `BEGIN`，目标未触碰） |
| 2 | WAL 尾部修复中途失败 | `REPAIR_INTENT` / `REPAIR_DONE`；`wal_evidence`；`REPAIR` 记录；检查点 | 见 A.6.4 | 按 A.6.4 对应行继续 | 再次截断；猜边界；删证据；无 INTENT 就截断；未确认持久化就写 `REPAIR_DONE` | 完成或可继续 → 继续扫描；否则 `RECOVERY_REQUIRED` / `MANUAL_BLOCKED` |
| 3 | WAL 持久化失败（日志可写） | 主 WAL 可见记录；检查点未推进；`wal_failures` 有 `FAILED` | `PROVISIONAL`；`FAIL_READABLE_WITH_RECORDS`；`NO` | 有未解决 op → **T1**；无 → **T4** | 一律导向 T2；假定已落盘；截断回滚 | `RECOVERY_REQUIRED` |
| 4 | **WAL 持久化失败（日志不可写）** | 主 WAL 可见；检查点未推进；`wal_failures` 缺失/不可读 | `PROVISIONAL`；`FAIL_ABSENT_INCONSISTENT` / `FAIL_UNREADABLE`；`UNKNOWN` | **仅 T5** | T1；T2；T4；任何写入；用"检查点已验证"替代故障证据 | **`MANUAL_BLOCKED`** |
| 5 | WRITE 中途崩溃 | `BEGIN(WRITE)` 无终态；目标部分内容 | `OP_UNRESOLVED`；目标哈希 ∉ {B, A} | T1 | 继续写；跳过该 target；用大小判成功 | `RECOVERY_REQUIRED` |
| 6 | RECOVERY 中途崩溃 | `BEGIN(RECOVERY)` 无终态；目标部分恢复 | `OP_UNRESOLVED`（可能多条链） | `#r2`（`supersedes=#r1`），幂等重做 | 判断恢复到哪一步；伪造 `RECOVERED`；写 `ABORTED` | `RECOVERY_REQUIRED` |
| 7 | 连续多次 RECOVERY 失败后重启 | 多个 `BEGIN(RECOVERY)` 无终态；多个 `FAILED` | 未解决集合 = 全部未终结 op | `#rn` 覆盖**全部**未解决 op；或人工 | 只解决最后一个；遗漏链上 op；把 `FAILED` 当终态 | `RECOVERY_REQUIRED`，直至 `#rn` 成功 |
| 8 | 快照与 WAL 状态不一致 | `BEGIN.snapshot_sha256` 与现存快照不符；`SNAPSHOT_ORPHAN` | 快照不可用 | 生成 `CURRENT_STATE`（标注非 B）；人工报告 | 用不符快照恢复；删孤立快照；把 `CURRENT_STATE` 当 B | `RECOVERY_REQUIRED` + 人工 |
| 9 | 检查点与 WAL 不一致 | V-1…V-6 失败；WAL 短于 marker；末条不符；前缀哈希不符 | `INCONSISTENT` → `UNKNOWN` | **仅 T5** | 重写检查点；T1；T2；T4；任何写入 | **`MANUAL_BLOCKED`** |
| **10（v7）** | **WAL 文件身份变化** | 前缀哈希相同但 `st_ino` / `file_index` / `creation_time` 不同；或句柄视图与路径视图矛盾 | `IDENTITY_MISMATCH` / `IDENTITY_UNVERIFIABLE` → `INCONSISTENT` → `UNKNOWN` | **仅 T5** | 自动推进检查点；T1；T4；任何写入；择一采信冲突视图 | **`MANUAL_BLOCKED`** |
| **11（v7）** | **故障日志不可用** | `wal_failures` 缺失/不可读/损坏；WAL 有无法解释的 `PROVISIONAL` | `FAIL_UNREADABLE` / `FAIL_CORRUPT` / `FAIL_ABSENT_INCONSISTENT` → `UNKNOWN` | **仅 T5** | T1；T2；T4；用检查点 `VERIFIED` 替代缺失证据 | **`MANUAL_BLOCKED`** |
| **12（v7）** | **目标持久化 / 回读 / 提交前复检失败** | `BEGIN` 无终态；目标内容可能是 A 但持久性未知；无 `END` | `OP_UNRESOLVED` | T1 | 写 `END`；宣告成功；跳过 ST-9/10/11 | `RECOVERY_REQUIRED` |

**表的使用规则**：本表是设计判定表，不是执行记录。每一条的实际结果须由对应用例产出；未产出即"未验证"。

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

## A.17 场景 S0–S14（76 条）

### S0 路径安全与保护分类（6 条）

S0a 词法｜S0b 重解析点内外｜S0c 句柄身份替换 + `st_ino==0`｜S0d 零副作用｜S0e 硬链接 `st_nlink>1`｜S0f 静态保护分类断言（仅读清单与台账，不访问任何 `.assets`，断言 34 个文件各归一个级别、3 个 `roundtrip` 归 L0-D / `DECOY_EMPTY`、无用例清单解析到 L0-A/B/C/D）。

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

S3a M8（BEGIN 无 END、目标 == A）｜S3b M8（末尾残行，须先按 A.6 修复；修复后若无未解决 op 且检查点 `VERIFIED` 且身份 `IDENTITY_VERIFIED` → 评估 T2；否则走 T1）｜S3c M6（sink 模拟 END 未持久化）。

核心：不得因"目标 == A"推断已完成。

### S4 快照缺失/损坏（4 条）

S4a 删内容｜S4b 篡改内容｜S4c sidecar 缺失/篡改｜S4d 快照与目标双双被改。

全部：保持 `RECOVERY_REQUIRED`；生成 `CURRENT_STATE`（标注非 B）；人工报告。

### S5 外部并发（**8 条**，v7 扩 2 条）

| 用例 | 钩子 | 外部写入 | 相对写游标 | 最终哈希 | 期望 |
|---|---|---|---|---|---|
| S5a | H1 | `T-1M`：`[1024, 5120)` | 尚未开始写 | ≠ B | 复检失败 → **不得写 `ABORTED`**，写 `FAILED{stage:recheck}` → `OP_UNRESOLVED` → `RECOVERY_REQUIRED` |
| S5b-1 | H3（k=32） | `T-64M`：`[4 MiB+1024, +4096)` | **写游标之后** | **≠ A** | **必须检出** |
| S5b-2 | H3 | `T-64M`：`[40 MiB+1024, +4096)` | **写游标之前** | **== A** | **写时不可检出**；须声明；声称完整覆盖 → 判失败 |
| S5c | H4 | `T-1M`：`[1024, 5120)` | 全部写完、未持久化 | ≠ A | **必须检出**（ST-9 之后的 ST-10 回读会看到外部字节） |
| S5d | H2 | `T-1M-P`：`[0, 1024)` | **载荷范围之外** | **≠ A** | **必须检出** |
| S5e | H2 | `T-1M-P`：`[512 KiB, 512 KiB+1024)` | **载荷范围之内**，被覆盖 | **== A** | **写时不可检出**；须声明 |
| **S5f** | **H5** | `T-1M`：`[1024, 5120)` | 已回读通过、未写 END | ≠ A | **必须检出**：ST-11 提交前复检发现 ≠ A → `FAILED{stage:precommit_recheck}` → `OP_UNRESOLVED` → `RECOVERY_REQUIRED`；**禁止写 `END`** |
| **S5g** | **H6** | `T-1M`：`[1024, 5120)` | 提交前复检通过、END 未写 | **写时 == A，之后 ≠ A** | **写时不可检出**；但**下次扫描的 V-T 必须检出**（目标 ≠ `END.target_sha256_after`）→ `RECOVERY_REQUIRED`；若实现未做 V-T → 判失败 |

**S5b 前置断言**：外部字节固定 `0xAB × 4096`；夹具必须断言 `payload[off:off+4096] != 0xAB×4096` 且 `B[off:off+4096] != 0xAB×4096`。

**S5 统一规则**：检出 → 进入/保持 `RECOVERY_REQUIRED`，禁止自动回滚/重试/解除/跳目标；哈希、mtime、锁状态、屏障日志仅为辅助证据；`∈{B,A}` 不能证明未被外部修改；**不得声称哈希可以发现所有第三方写入**（S5b-2、S5e 为写时反例；S5g 依赖 V-T 延迟检出）；无对应钩子 → `UNCOVERED`。

### S6 锁（5 条）

S6a pid 存活｜S6b pid 已死残留｜S6c 锁损坏｜S6d 锁目录缺失｜S6e 锁被占用（含 `LockFileEx` 获取失败）。

WAL 无变化；`READY`。禁止自动删锁、降级无锁、时间阈值判死、损坏锁视为无锁、先 `BEGIN` 后取锁。

### S7 磁盘/持久化失败（**9 条**，v7 加 S7h）

| 用例 | 类别 | 期望 |
|---|---|---|
| S7a | 类1 快照创建失败 | 无 `BEGIN`；`READY`；不需人工 |
| S7b | 类2 `BEGIN` 持久化失败 | 按 A.7.6 四分支（b1–b4）；**目标 == B 不单独放行** |
| S7c-1 | 类3 写入 ENOSPC | `BEGIN` 无终态 → T1 |
| S7c-2 | 类3 **短写**（大小不变） | `BEGIN` 无终态 → T1；唯一拦截手段是写后全文件 SHA-256 |
| S7d | 类3 END 失败 | `BEGIN` 无终态 → T1 |
| S7e | fsync 失败 **且** `wal_failures` 不可写 | `FAIL_ABSENT_INCONSISTENT` → `UNKNOWN` → **`MANUAL_BLOCKED`，仅 T5**（v7 收紧） |
| S7f | `.durable` 缺失/损坏/回退 | f1/f2 → `UNKNOWN` → **仅 T5**；f3 → `NO` → T1/T4 |
| S7g | `PROVISIONAL` 且无未解决 op | `NO` → **T4** → `YES` → `READY`；断言 T4 不写 WAL 记录、不改目标 |
| **S7h** | fsync 失败 **但** `wal_failures` 可写且含对应 `FAILED` | `FAIL_READABLE_WITH_RECORDS` → `NO`；h1 有未解决 op → T1；h2 无 → T4 |

**三类故障不混同**：类1（快照失败）/ 类2（`BEGIN` 失败）/ 类3（目标已写）。

### S8 恢复关联与恢复崩溃（7 条）

S8a M4 恢复中途崩溃｜S8b M8 目标 == B、`RECOVERED` 缺失（**T2 不适用**，走 `#r2` + `resolves=[#1,#r1]`）｜S8c 恢复期间快照失效｜S8d 恢复后一致性检查失败｜S8e `resolves` 遗漏 → 仍保持｜S8f `resolves` 含已终结 op → 一致性失败 + 人工｜S8g 恢复链成功 → `READY`，历史完整、无伪造记录。

### S9 WAL 尾部修复（**7 条**，v7 加 S9g）

| 用例 | 崩溃点 | 持久证据 | 期望 |
|---|---|---|---|
| S9a | RP-3 之前 | 可能有证据文件，无 INTENT | 未开始；允许重做；主 WAL 原样；证据不覆盖；`RECOVERY_REQUIRED` |
| S9b | RP-3 之后、RP-4 之前 | INTENT 无 DONE；大小 == `wal_size_before`；tail 哈希匹配 | 从 RP-4 继续 |
| S9c | RP-4 之后、RP-6a 之前 | INTENT 无 DONE；大小 == `tail_offset`；无 `REPAIR` | 从 RP-6a 继续；不得重复截断 |
| S9d | 截断到中间值 | 大小非两端值 | **边界不可确定** → `RECOVERY_REQUIRED` + 人工 |
| S9e | RP-6a 之后、RP-6b 之前 | `REPAIR` 可见；检查点未覆盖 | `PROVISIONAL`；**禁止 `REPAIR_DONE`**；`VERIFIED` → 先完成 RP-6b；否则 `MANUAL_BLOCKED` |
| S9f | `REPAIR` 损坏或字段不一致 | 行不可解析 / 字段缺失 / seq 非单调 / `repair_intent_id` 不匹配 | 隔离；`UNKNOWN`；禁止 `REPAIR_DONE`；禁止再次修复；**`MANUAL_BLOCKED`** |
| **S9g（v7）** | **RP-4b 检测到 WAL 身份变化** | INTENT 无 DONE；身份 ≠ `wal_identity_before` | **`MANUAL_BLOCKED`**；禁止任何后续修复步骤；证据保留 |

> S9 条数：v7 由 6 条扩为 **7 条**（新增 S9g）。上表 7 行。

### S10 检查点一致性（4 条）

| 用例 | 注入 | 构造状态 | 期望 |
|---|---|---|---|
| S10a | M10 篡改 `wal_prefix_sha256` | 字段自洽但前缀哈希不符 | V-2 失败 → `INCONSISTENT` → `UNKNOWN` → **仅 T5** |
| S10b | M10 截断 WAL 短于 marker | WAL 被外部截断 | V-1 失败 → `INCONSISTENT` → **仅 T5** |
| S10c | M10 删除 WAL 保留检查点 / 反向 | 二者之一缺失 | `INCONSISTENT` / `ABSENT_DIRTY` → **仅 T5** |
| S10d | M4 在 CP-5 期间崩溃（tmp 已写、replace 未完成） | 旧检查点仍有效 | `VERIFIED` → 新记录 `PROVISIONAL` → `NO` → T1/T4；**不得因 tmp 存在而采信 tmp** |

**S10 核心断言**：任何 `INCONSISTENT` 情形下不得判任何记录为 `DURABLE`，`WAL_STATE_COMPLETE` 必须 `UNKNOWN`，`WRITE_PERMITTED = NO`。

### S11 WAL 文件身份（**4 条**，v7 新增）

| 用例 | 注入 | 构造状态 | 期望 |
|---|---|---|---|
| **S11a** | M11：把 WAL 替换为**内容完全相同**的新文件（复制后 `os.replace`） | 前缀哈希仍相等，但 `st_ino` / `file_index` / `creation_time_ns` 改变 | V-1b 失败 → `IDENTITY_MISMATCH` → `INCONSISTENT` → `UNKNOWN` → **`MANUAL_BLOCKED`，仅 T5**；**禁止**因"哈希相同"判 `VERIFIED` |
| **S11b** | M11：重命名 WAL 后新建同名空文件 | V-0 通过（存在），身份全变，`creation_time_ns` 晚于检查点 `ts_wall` | 同上；且不得把新文件当作"空态" |
| **S11c** | M11：构造 `st_ino == 0` 且无 `file_index` 的卷/桩 | 身份不可得 | `IDENTITY_UNVERIFIABLE` → `INCONSISTENT` → `UNKNOWN` → **`MANUAL_BLOCKED`**；不得"降级为只比哈希" |
| **S11d** | M11：CP-2 与 CP-3 之间替换 WAL（句柄仍指旧文件，路径指新文件） | 句柄视图与路径视图矛盾 | `IDENTITY_MISMATCH` → `INCONSISTENT` → `UNKNOWN` → **`MANUAL_BLOCKED`**；**不得择一采信** |

**S11 核心断言**：任何 `IDENTITY_MISMATCH` / `IDENTITY_UNVERIFIABLE` 情形下，**不得自动推进 durable checkpoint，不得允许新写入**。

### S12 故障日志可用性（**4 条**，v7 新增）

| 用例 | 注入 | 构造状态 | 期望 |
|---|---|---|---|
| **S12a** | M11：`wal_failures` 存在但含不可解析行 | `FAIL_CORRUPT` | `UNKNOWN` → **`MANUAL_BLOCKED`，仅 T5**；禁止 T1/T2/T4 |
| **S12b** | M11：`wal_failures` 被独占打开 / 权限拒绝 | `FAIL_UNREADABLE` | 同上 |
| **S12c** | WAL 干净（全 `DURABLE`、无未解决 op、无结构异常）+ `wal_failures` 缺失 | `FAIL_READABLE_EMPTY`（由 WAL 侧独立证明） | **允许** `YES` → `READY` → 允许写入；断言：不得因为"日志缺失"而误判 `UNKNOWN` |
| **S12d** | WAL 含 `PROVISIONAL` 记录（来自上一次运行）+ `wal_failures` 缺失 | `FAIL_ABSENT_INCONSISTENT` | `UNKNOWN` → **`MANUAL_BLOCKED`，仅 T5**；断言：**不得**因检查点 `VERIFIED` 就判 `NO` |

### S13 目标持久化先于 END（**3 条**，v7 新增）

| 用例 | 注入 | 构造状态 | 期望 |
|---|---|---|---|
| **S13a** | M1：ST-9 `os.fsync(目标句柄)` 抛异常 | 目标内容可能已写，持久性未知 | `FAILED{stage:target_fsync}` → `OP_UNRESOLVED` → `RECOVERY_REQUIRED` → T1；**禁止写 `END`**；断言 `END` 不存在 |
| **S13b** | M1：ST-10 回读哈希 ≠ A（注入短写或内容偏移） | 目标内容与预期不符 | `FAILED{stage:target_verify}` → `OP_UNRESOLVED` → T1；**禁止写 `END`** |
| **S13c** | M4：ST-12 写 `END` 并 fsync 成功后、CP 推进前崩溃 | `END` 可见；检查点未覆盖 | `END` 为 `PROVISIONAL`；op `OP_COMMITTED`；`NO` → **T4**；**禁止**视为失败并重写 `END` |

**S13 核心断言**：`END` 的 `target_persisted` 与 `readback_verified` 必须为 `true`；构造出 `false` 的 `END` 记录 → 判失败。

### S14 空 WAL / 检查点初始组合（**6 条**，v7 新增）

| 用例 | 构造 | 分类 | 期望 |
|---|---|---|---|
| **S14a** | WAL 不存在 + 检查点不存在 | `EMPTY_CLEAN` | `READY`；允许写入；首次 `BEGIN` 时惰性创建检查点（`prefix_record_count=1`） |
| **S14b** | WAL 0 字节 + 检查点不存在 + ALL-GONE 成立 | `EMPTY_UNCHECKPOINTED` | `READY`；允许写入；不得因"0 字节"判 `ABSENT_DIRTY` |
| **S14c** | WAL 0 字节 + 检查点不存在 + 存在 `wal_evidence` / `wal_repairs` / 残留锁之一 | ALL-GONE 不成立 | `UNKNOWN` → **`MANUAL_BLOCKED`**；**不得**判干净 |
| **S14d** | WAL 0 字节 + 检查点描述**空前缀** | `VERIFIED`（空态） | `READY`；走 A.5.4 第 4 条空态一致性；**不得**要求"末条记录" |
| **S14e** | WAL 0 字节 + 检查点描述**非空前缀** | `INCONSISTENT` | `UNKNOWN` → **`MANUAL_BLOCKED`**；V-1 失败 |
| **S14f** | WAL 不存在 + 检查点描述非空前缀 | `INCONSISTENT` | `UNKNOWN` → **`MANUAL_BLOCKED`**；V-0 失败 |

**S14 核心断言**：`prefix_record_count == 0` 时**禁止虚构末条记录**；空态一致性必须由 `prefix_record_count` / `wal_size_at_marker` / `wal_prefix_sha256 == EMPTY_PREFIX` / `seq == 0` / `kind == null` / `op_id == null` 六项共同成立。

**S14 覆盖说明（如实标注）**：S14a–S14f 覆盖组合 **#1 / #2（干净与不干净两侧）/ #3a / #3b / #5b**；组合 **#4**（WAL 有记录 + 无检查点）由 **S10c** 覆盖；组合 **#6** 由 **S10a / S10b / S10c** 覆盖；组合 **#5a**（WAL 不存在 + 检查点描述空前缀）**当前无独立用例**，列为已知测试缺口，不计入"已覆盖"。

## A.18 一致性自审（v7）

| 检查 | 结论 |
|---|---|
| `.durable` 定义 vs A.5.6 | 检查点不独立可信，必须通过 V-0…V-6 + V-T；身份不通过时不得判 `DURABLE` |
| **身份 vs 检查点** | `wal_identity` 写入检查点；V-1b 校验；CP-4 发布前复核；冲突视图不择一采信 |
| **身份 vs T1/T2/T4** | 三条自动路径均要求 `IDENTITY_VERIFIED`；不一致时唯一出口是 T5 |
| **故障日志 vs `WAL_STATE_COMPLETE`** | `YES` 要求 `FAIL_READABLE_EMPTY` / `FAIL_ABSENT_CONSISTENT`；`FAIL_*` 三值一律 `UNKNOWN` |
| **故障日志 vs T1/T2/T4** | 不可读/损坏/不一致时三条自动路径全部关闭；T2-6 显式排除 |
| **UNKNOWN → READY 闭包** | A.7.4 已逐条列出；`MANUAL_BLOCKED` 无自动出口 → 无自动回环 |
| **目标持久化 vs END** | ORD-1…ORD-6；`END.target_persisted` / `readback_verified` 必须为 true；ST-9/10/11 任一失败禁写 `END` |
| **空态 vs 检查点校验** | `prefix_record_count == 0` 走 A.5.4 第 4 条，禁止虚构末条记录 |
| **空态 vs 干净判定** | 组合 #2 依赖 ALL-GONE 五项旁证 |
| RP-4b vs A.6.3 | 身份变化 → `MANUAL_BLOCKED`，与情况②③一致 |
| S7e vs S7h | 日志不可写 → `UNKNOWN`（仅 T5）；日志可写 → `NO`（T1/T4）；两侧互补不重叠 |
| 用例数 | 矩阵、通过标准、统计三处均为 **76** |

## A.19 通过标准

1. **76/76 用例**产出预期状态，零静默通过。
2. 每用例证据包：前置 5 项、执行前后 WAL 快照与原文、**检查点内容 + 身份字段 + 校验结果**、**故障日志状态**、目标前后完整 SHA-256、mtime（仅辅助）、锁状态、屏障日志、目录树、注入点日志、`injection_kind`、所用钩子编号、ST-9/10/11 的时序记录。
3. 恢复类用例：`BYTES`/`OBJECT`/`REDO_VERIFIED` 分别记录；`UNVERIFIED` 或未验证 → 判"部分通过"，不计入通过。
4. `RECOVERY_REQUIRED` 用例中无一次被自动降级为 `READY`；`MANUAL_BLOCKED` 用例中无一次走 T1/T2/T4。
5. S0a–S0f 通过：拒绝逻辑零副作用；真实资产（含 L0-D 三个文件）未被写入入口接触。
6. 结束后 `snap\` 条目数 == 预期；除 S6d 的目录重建外无锁被自动删除；`wal_evidence\` 无删除。
7. 真实目录 34 个 `.assets` 完整 SHA-256 == `baseline_ledger.json`。
8. 报告明确声明：结果仅覆盖 L1；**STA 通过 ≠ PWA 满足**；**W2-b / S5b-2 / S5e 写时不可检出，S5g 仅靠 V-T 延迟检出**；不构成对现有脚本的保护证明；**A.22 四项阻塞项未解决前不得真实写入**。

## A.20 禁止的假通过

| 模式 | 原因 |
|---|---|
| 用大小判断写入成功 | 等长覆盖下恒真（S7c-2） |
| 用 mtime 判断是否被改 | 可保留/回填 |
| "目标看起来完整所以已完成" | S3a/S8b |
| 目标哈希 == B 即放行 | 仅 T2-5 一条 |
| 哈希 == A 即证明无并发写入 | S5b-2 / S5e 反例 |
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

真实 OS 级 ENOSPC；掉电/强制关机/真实 fsync 语义；跨卷快照；大文件 244 MB/1.3 GB；游戏进程持有句柄；多工具并发；硬链接"打开瞬间"窗口；**W2-b / S5b-2 / S5e 写时不可检出**；对象级校验仅 `T-REAL`；**PWA-3（内存映射写者）**；Windows 目录 fsync 无直接等价（CP-5 后目录项持久化）；**文件身份字段的可伪造性**；现有脚本的保护状态。

## A.22 P0 阻塞项（阻断真实写入，需人工决策）

| ID | 阻塞项 | 性质 | 不解决的后果 |
|---|---|---|---|
| **BLK-1** | **WAL 文件身份连续性无法在目标卷上可靠保证**（`st_ino == 0` / 索引复用 / 无 `file_index`） | 平台能力未验证 | 无法区分"同一文件"与"同内容替换"；S11a/S11b/S11c 无法通过；`WRITE_PERMITTED` 恒为 NO |
| **BLK-2** | **目标持久化与 WAL END 的持久化顺序无法被形式化证明**（Windows/NTFS `FlushFileBuffers` 语义边界、硬件写缓存） | 语义边界未验证 | 断电场景下可能"END 已持久但目标未持久"；只能声明为未覆盖 |
| **BLK-3** | **故障日志与检查点可能同时不可持久化** | 设计缺口 | 该时刻的失败无法被任何持久证据记录；只能 fail-closed 到 `MANUAL_BLOCKED` |
| **BLK-4** | **CP-5 之后的目录项持久化无 Windows 等价机制** | 平台缺口 | 检查点文件可能在掉电后"消失"而内容文件仍在，导致 `INCONSISTENT` |

**规则**：`BLK-1…BLK-4` 任一未决（PWA-8 = FAIL）时，**禁止真实目标写入**。合成夹具（STA）仍可在 L1 内运行，但其结果**不能**用于推断真实写入安全。

---

# B. 测试统计

| 口径 | v6 | **v7** | 变化原因 |
|---|---|---|---|
| 场景组数 | 11 | **15** | 新增 S11（WAL 身份）/ S12（故障日志）/ S13（目标持久化顺序）/ S14（空态组合） |
| 子场景数 | 55 | **76** | S5 +2（S5f/S5g，新钩子 H5/H6）；S7 +1（S7h）；S9 +1（S9g）；S11 +4；S12 +4；S13 +3；S14 +6（合计 +21） |
| 独立执行用例数 | 55 | **76** | 与子场景 1:1 |
| 通用断言/用例 | 14 | **17** | 新增 C15（WAL 身份验证记录）/ C16（故障日志状态记录）/ C17（ST-9→ST-10→ST-12 时序记录） |
| 通用断言小计 | 770 | **1292** | 76 × 17 |
| 专项断言小计 | 145 | **201** | 见下 |
| **总断言数** | 915 | **1493** | 1292 + 201 |

**专项断言明细**：

| 组 | 用例数 | 每条 | 小计 |
|---|---|---|---|
| S0 | 6 | 3 | 18 |
| S1 | 5 | 2 | 10 |
| S2 | 1 | 4 | 4 |
| S3 | 3 | 2 | 6 |
| S4 | 4 | 3 | 12 |
| S5 | **8** | 3 | **24** |
| S6 | 5 | 2 | 10 |
| S7 | **9** | 2 | **18** |
| S8 | 7 | 3 | 21 |
| S9 | **7** | 3 | **21** |
| S10 | 4 | 3 | 12 |
| S11 | **4** | 3 | **12** |
| S12 | **4** | 3 | **12** |
| S13 | **3** | 3 | **9** |
| S14 | **6** | 2 | **12** |
| **合计** | **76** | — | **201** |

- 合计：**76 × 17 + 201 = 1292 + 201 = 1493**。
- **对照运行不计入**：5 次（T-1K / T-1M / T-1M-P / T-64M / T-REAL）× 3 条断言 = 15，作为夹具前置条件单独统计。
- 若实现偏离 `buffering=0`，须补 S3d → **77 用例 / 1512 断言**（77 × 17 + 203）。
- 若 M9 钩子缺失：S5a/S5b-1/S5b-2/S5c/S5d/S5e/S5f/S5g 共 8 条记 `UNCOVERED` → **实际可执行用例 = 68**。
- 若 `tool_sha256`/`deps` 机制未建立：8 条重做相关用例只能"部分通过" → **可完全通过用例上界 = 68**（76 − 8）。
- 若 BLK-1 未决：S11a–S11d 无法通过 → **可完全通过用例上界进一步降为 64**（68 − 4）。

---

# C. 未解决 / 未验证事项（四分类）

### C.1 已知设计缺口（不可通过实现消除）

| # | 缺口 |
|---|---|
| 1 | W2-b / S5b-2 / S5e：外部写被载荷完整覆盖时写时不可检出（S5g 类可经 V-T 延迟检出，S5e 类仍可能永不检出） |
| 2 | PWA-3：无法断言"无其他进程持有内存映射" |
| 3 | 故障日志与检查点可能同时不可持久化（BLK-3） |
| 4 | 硬链接"打开瞬间创建"的极窄窗口 |
| 5 | CP-5 之后目录项持久化无 Windows 等价机制（BLK-4） |
| 6 | **文件身份字段可被伪造 / 索引可被复用**，身份校验只能降低概率 |

### C.2 尚未实现

| # | 事项 |
|---|---|
| 7 | `tool_sha256` / `deps` 记录机制 |
| 8 | 检查点机制（CP-1…CP-6、V-0…V-6、V-T） |
| 9 | **`wal_identity` 采集与比对（ID-1…ID-6）** |
| 10 | **`FAILURE_LOG_STATUS` 六值判定逻辑** |
| 11 | **T5 / `MANUAL_RESET` 与签核流程** |
| 12 | **ST-9 目标持久化 / ST-10 回读 / ST-11 提交前复检** |
| 13 | `wal_repairs\` / `wal_evidence\` 与 RP-1…RP-7（含 RP-4b） |
| 14 | T4 检查点重同步 |
| 15 | M9 钩子 H1–H6；M10 检查点篡改；M11 身份替换 / 故障日志破坏注入器 |
| 16 | `signoffs\` 目录（T2 与 T5 两种签核） |
| 17 | 全局 `open()` 审计钩子（STA-6） |
| 18 | `inventory_digest` / `unresolved_set_digest` / `wal_state_digest` 计算代码 |
| 19 | L0-D 边界在工具层的强制 |

### C.3 尚未测试

| # | 事项 |
|---|---|
| 20 | 全部 76 条用例、1493 条断言（全部 `NOT EXECUTED`） |
| 21 | **`st_ino` / `file_index` 在 `%TEMP%` 卷上的稳定性与复用行为（BLK-1 的判定前提）** |
| 22 | **`os.fsync(目标句柄)` 在 NTFS 上的实际保证边界（BLK-2）** |
| 23 | junction / 符号链接创建权限 |
| 24 | `LockFileEx` 对内存映射写是否有效 |
| 25 | 实现是否按 1 MiB 升序分块（影响 S2 偏移） |
| 26 | 读取器版本与 `sharedassets3.assets` 兼容性 |
| 27 | `os.truncate` 在 NTFS 上的原子性（影响 S9d） |
| 28 | 临时目录剩余空间（估算 < 1.4 GB） |
| 29 | 恢复链 ≥3 层的行为 |
| 30 | 检查点与身份采集在高频写入下的额外开销 |

### C.4 理论残余风险

| # | 事项 |
|---|---|
| 31 | 各 digest 的 SHA-256 碰撞（用 count + 完整列表 + 长度缓解，不声称绝对） |
| 32 | 生产构建中钩子残留（靠 STA-5 缓解，非形式化证明） |
| 33 | 真实掉电 / 强制关机 / 真实 ENOSPC 语义完全未覆盖 |
| 34 | 身份字段四元组（`st_dev` + `st_ino` + `volume_serial` + `creation_time`）叠加仍非形式化证明 |
| 35 | V-T 只能在**下一次扫描**发现"END 之后"的改动；两次扫描之间的窗口不可检出 |

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
| **P0-1** | WAL 文件身份连续性：新增 `wal_identity` 检查点字段、ID-1…ID-6、V-0 / V-1b、CP-4 身份复核、`WAL_IDENTITY_STATUS` 四值、A.5.7 专节（含 `st_ino` 限制与 fail-closed 表）、`WAL_IDENTITY_STATUS` 进入 `wal_state_digest`、新增 S11a–S11d、BLK-1 | A.2.1 / A.2.2 / A.5.2 / A.5.4 / A.5.5 / A.5.6 / A.5.7 / A.5.8 / A.6.2 / A.6.4 / A.7.1 / A.7.5 / A.7.6 / A.8.1 / A.15 / A.17-S11 / A.18 / A.22 |
| **P0-2** | 故障日志不可用统一处理：新增 `FAILURE_LOG_STATUS` 六值、A.7.2 判定表与四条硬规则、`MANUAL_BLOCKED` 运行状态、A.7.4 状态转移闭包表、T5 / `MANUAL_RESET` 事件、S7e 收紧为 `UNKNOWN`、新增 S7h / S12a–S12d、T2-6 强化 | A.2.1 / A.2.2 / A.4.1 / A.4.2 / A.7.1 / A.7.2 / A.7.3 / A.7.4 / A.7.5 / A.7.6 / A.7.7 / A.7.8 / A.14.4 / A.15 / A.17-S7 / A.17-S12 |
| **P0-3** | 目标持久化先于 END：ST 由 9 步扩为 12 步（新增 ST-9 持久化 / ST-10 回读 / ST-11 提交前复检）、ORD-1…ORD-6、`END.target_persisted` / `readback_verified` 字段、Windows 持久化机制与边界表、新增 H5/H6 与 S5f/S5g、新增 S13a–S13c、V-T 目标一致性校验 | A.4.1 / A.5.6 / A.8.1 / A.8.2 / A.8.3 / A.12.2 / A.13 / A.15 / A.17-S5 / A.17-S13 / A.22-BLK-2 |
| **P1-1** | 空 WAL / 检查点六种组合：新增 `prefix_record_count` 字段、空前缀常量与空态一致性（A.5.4 第 4 条）、A.5.9 组合表（含 ALL-GONE 旁证）、`EMPTY_CLEAN` / `EMPTY_UNCHECKPOINTED` 分类、新增 S14a–S14f | A.5.2 / A.5.3 / A.5.4 / A.5.6 / A.5.9 / A.7.1 / A.17-S14 |
| 连带 | 步骤/钩子重编号、`MANUAL_RESET` 第 7 类事件、T5、`MANUAL_BLOCKED`、A.22 阻塞项、统计与自审更新 | 全局 |
| **自检修正（v7 内部）** | ① **用例数由 75 修正为 76**：S9 标题声明 6 条但实列 7 条（S9a–S9g），B 表行内合计亦为 76；相应断言数 1275/198/1473 → **1292 / 201 / 1493**，派生上界 67/67/63 → **68 / 68 / 64**，`buffering=0` 变体 76/1490 → **77 / 1512**；② 修正 2 处 `V-T` 交叉引用（A.5.9 → **A.5.6**）；③ 新增 **S14 覆盖说明**，如实标注组合 **#5a 无独立用例** | A.17 / A.18 / A.19 / B / C.3 / D.2 / E |

### D.2 执行边界声明

- 本轮**仅完成文档修订**（v6 → v7），输出即本文件。
- **未执行任何 P1 测试**：S0a–S14f 共 76 条全部 `NOT EXECUTED`。
- **未编写或实现任何功能代码**：WAL、`.durable`、身份采集、`LockFileEx`、恢复、快照、签核、T5 均未实现。
- **未修改任何项目源代码、配置文件、Git 状态或其他文件**；v6 未被覆盖、删除或改名。
- **未对任何真实 `.assets` 执行写入、删除、移动、重命名或覆盖**（含 17 个 L0-A、14 个 L0-B、3 个 L0-D）。
- **未写入或修改任何备份、快照、WAL、检查点或验证数据。**
- **未使用 `--apply`，未运行任何资产写回入口。**
- **未创建测试资产、临时资产或测试输出。**
- **未修改 baseline ledger。**
- **未执行任何 Git 写操作**（add / commit / reset / clean / checkout / switch / stash）。
- **未调用 Hermes**，未安装或更新依赖。
- 本轮只读动作：确认项目根、列出 `docs/`、检查 v7 是否存在、计算 v6 的 SHA-256、完整读取 v6 全文（969 行）。

**静态文档检查不等于测试通过。**

---

# E. 最终状态

```
REVIEW_REQUIRED — NOT AUTHORIZED FOR EXECUTION
```

**后续审查要求**：

1. 人工逐条审查 P0-1…P0-4 的修订是否闭合，特别是 A.5.7 的身份校验链与 A.7.4 的闭包表。
2. 对 **BLK-1（文件身份）** 与 **BLK-2（持久化顺序）** 作出决策：接受为"未覆盖"、另行设计，或放弃该保护路径。
3. 76 条用例、1493 条断言仍全部 `NOT EXECUTED`；未实现项 13 类、未测试项 11 项、残余风险 5 项，均需保持标注。
4. v7 审查通过前，不得进入 P1 测试执行、功能实现、基线认定或真实资产写入阶段。
