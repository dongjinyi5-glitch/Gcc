# 生图通道（多后端 + 每日额度自动切换）

一条命令跑 T1 重绘时，图片由 `tools/scripts/imgrouter.py` 统一调度：按顺序试各家，
某家当天额度用尽就打标记、**当天不再碰**，自动落到下一家。第二天账本翻页，全部复活。

## 一、放密钥

密钥文件里**只放令牌**，不要引号、不要空格、不要换行外的字符。

| 通道 | 密钥文件 | 环境变量（备选） | 计费 |
|---|---|---|---|
| 阿里云百炼 | `.secrets/dashscope.txt` | `DASHSCOPE_API_KEY` | 新用户免费额度，按成功张数计费 |
| Google AI Studio | `.secrets/google.txt` | `GOOGLE_API_KEY` / `GEMINI_API_KEY` | 免费额度（RPM/RPD 限流） |
| 魔搭 ModelScope | `.secrets/modelscope.txt` | `MODELSCOPE_API_KEY` | 每日免费额度 |
| 硅基流动 | `.secrets/siliconflow.txt` | `SILICONFLOW_API_KEY` | 收费，¥0.30/张（兜底） |

默认顺序：`dashscope → modelscope → google → siliconflow`
（能直接吃本地图的在前，需要额外条件的在后，付费兜底最后）。
可用 `--backend` 或环境变量 `IMG_BACKEND` 覆盖。

### 百炼：API-KEY ≠ 阿里云 AccessKey（2026-10-26 实测）

这是最容易踩的一个坑，已用真实请求验证：

| 凭据 | 长相 | 能干什么 | 能不能调 qwen-image |
|---|---|---|---|
| 百炼 **API-KEY** | `sk-` + 32 位 | 模型推理（DashScope 端点） | **能** |
| 阿里云 **AccessKey** | `LTAI…` + 30 位 Secret | OpenAPI 签名（查余额、管资源） | **不能** |

用 AccessKey 当 `Authorization: Bearer` 发过去，DashScope 一律回
`401 InvalidApiKey` —— **这不是余额问题，是凭据类型不对**，充多少钱都没用。

AccessKey 的正确用法（脚本已实现 `tools/scripts/aliyun_ak_probe.py`）：

```bash
# 查账户可用余额（ACS3-HMAC-SHA256 签名，走 BSS OpenAPI）
python tools/scripts/aliyun_ak_probe.py --balance
```

AccessKey 放 `.secrets/aliyun_ak.txt`（格式 `AccessKeyId=… / AccessKeySecret=…`），
**不要**塞进 `dashscope.txt`。`imgrouter` 现在会拦下 `LTAI` 开头的值并给出提示，
不会再把畸形 header 发出去。

想「用 AccessKey 自动铸一个 API-KEY」是走不通的：百炼的 API-KEY 管理 OpenAPI
（产品码 `MaaS`，端点 `maas.cn-beijing.aliyuncs.com`）在 OpenAPI 门户上标注为
**deprecated**，实测 2023–2025 全部版本号均返回 `InvalidAction.NotFound` / `InvalidVersion`。
**只能在控制台手点**：<https://bailian.console.aliyun.com> → 右上角 API-KEY → 创建。

百炼免费额度：`qwen-image-edit` 新用户 **100 张**，不消耗账户余额；
但需先开通百炼并完成实名认证。

### 百炼：没有可用的免费图像额度（2026-10-26 两次核实）

**第一次事故**：`MODEL_CANDIDATES["dashscope"]` 把 `qwen-image-2.0-pro` 排第一，
路由器就选了它 —— 一张图直接扣 **0.50 元**，余额 0.01 → **-0.49（欠费）**。

BSS 账单实锤（`QueryBill`，BillingCycle=2026-10）：

| 字段 | 值 |
|---|---|
| ProductName | 大模型服务平台百炼 |
| ProductCode | `sfm` |
| UsageStartTime / End | 2026-10-26 18:08:00 → 18:09:00 |
| PretaxGrossAmount | **0.50 CNY** |
| DeductedByCoupons | **0（无免费额度抵扣）** |
| Status | PayUnsettle |

**第二次核实（推翻「100 张免费」的说法）**：
`qwen-image-edit` 这个模型 ID **已经下线**，调用返回
`404 InvalidParameter: Model not exist`。
2026-10 的官方文档里，图生图/编辑已并入 `qwen-image-2.0` / `3.0` 系列
（`qwen-image-2.0`、`qwen-image-2.0-pro`、`qwen-image-3.0`、`qwen-image-3.0-pro`、
`wan2.7-image`、`z-image-turbo` 等），**全部按张计费**。
"新用户 100 张免费额度只给 qwen-image-edit" 是 2025 年的信息，已失效。

**结论：百炼对本项目 = 纯付费通道，已从默认顺序移除。**

- `ORDER_DEFAULT = ["modelscope", "google", "siliconflow"]`（不含 dashscope）
- 要用百炼必须 `--backend dashscope --paid-ok` 双重显式指定
- `MODEL_CANDIDATES["dashscope"]` 已更新为现存模型 `qwen-image-3.0`
- 用户明确要求：**没有免费额度就不用阿里云**（2026-10-26）

**欠费的连带后果**：欠费后所有 DashScope 调用直接 400
`{"code":"Arrearage","message":"Access denied, please make sure your account is in good standing"}`。

**教训**：免费额度是**按模型**给的，不是按账号。换模型名前必须先确认
① 该模型 ID 现在还存在；② 它有没有免费额度。


## 二、验证

```bash
# 看今天各家用了多少、谁被标记额度耗尽 / 网络不可达
python tools/scripts/imgrouter.py --status

# 每家各画一张（会消耗额度），验证 key 与链路
python tools/scripts/imgrouter.py --selftest

# 分离「密钥问题」与「网络问题」的深度诊断（不产图，成本≈0）
python tools/scripts/diag_backends.py
```

自检图落在 `art/gen/_selftest/`，文件名就是通道名，可以直接比对哪家画得好。
自检用的是合成的白描（一个方框 + 一道斜线），**不消耗真实构件的额度**。

**自检会额外打一次结构分**（`follow_check`）：光“返回了图”不算通过，必须证明它
**跟住了线稿**。纯文生图模型（如 Kolors）会忽略输入图自己另画，edge 会很低 —— 这正是
我们整套方法的命门，必须拦住。

## 三、正式跑

```bash
# 默认自动切换
python tools/scripts/redraw_t1.py --level level4 --max 20 --skip-registered

# 强制只用某一家（排查问题用）
python tools/scripts/redraw_t1.py --level level4 --backend google

# 指定顺序
python tools/scripts/redraw_t1.py --level level4 --backend google,dashscope
```

报告里每条记录带 `backend` 字段，能看出这张图是哪家画的。

## 四、额度账本

`.secrets/quota.json`，按日期分桶：

```json
{"2026-10-25": {"dashscope": {"ok": 12, "fail": 0, "exhausted": false,
                              "last_error": null, "model": "qwen-image-2.0-pro"}}}
```

- `exhausted: true` = 当天不再尝试这一家。
- `net` = 连续网络故障计数；`net >= 3 且 ok == 0` 时当天停用（`网络不可达`）。
  这条是为了避免 Google 这类连不上的通道，每张图都白等两轮超时。
- 判定为“额度问题”的依据：HTTP 402/429，或返回文本里含 quota / insufficient /
  balance / arrear / exhaust / free tier / throttl / rate limit / resource_exhausted /
  额度 / 余额。
- 其他错误（如 400 参数错、401 key 错）**只记失败次数，不打额度标记** —— 否则一个
  写错的 key 会把整家通道废掉一整天。
- 额度提前重置（换号、充值）时：`python tools/scripts/imgrouter.py --reset`。

## 四之二、2026-10-26 首次四家实测诊断（结论保留，供复用）

| 通道 | 结果 | 定性 | 怎么办 |
|---|---|---|---|
| 魔搭 | `/v1/models` **200**（token 有效）；生成 **401** `Please bind your Alibaba Cloud account before use` | 账号未绑定阿里云账号 | 去 modelscope.cn 绑定阿里云账号，2 分钟 |
| 阿里云百炼 | 国内站 / 国际站 / 文本模型 qwen-plus **三处全 401 InvalidApiKey** | 密钥被拒，与图像模型权限无关 | 控制台确认 key 状态与区域，或重新生成 |
| Google | 直连 `10060` 超时；走系统代理 `502 Tunnel connection failed` | **纯网络不可达**，key 未得到验证 | 需要可用代理/VPN |
| 硅基流动 | `402` 余额不足（`/v1/user/info` 已废弃，返回 410） | 欠费 | 充值 |

交叉验证排除了“贴错平台”：

- 把 `dashscope.txt` 的 key 拿去硅基流动 `/v1/models` → `401 Token is invalid`，
  说明它**不是**硅基的 key；
- 把 `siliconflow.txt` 的 key 打硅基流动 → `200`，说明硅基 key 本身仍有效，只是没钱；
- 百炼 key 打最便宜的文本模型 `qwen-plus` 也 401，说明**不是**图像模型没开权限。

百炼 key 长度 51（`sk-` + 48 位），官方文档示例是 `sk-` + 32 位。但既然来源已确认，
长度不作为结论，只作为排查线索之一。**最可能的三条**（按概率）：

1. 生成的是**临时 API Key**（官方明确：临时 key 最长 1800 秒），已过期；
2. key 在控制台被**删除/重置**过，旧 key 立即失效；
3. 该 key 属于**另一个阿里云账号**（国际站 alibabacloud.com 与中国站 aliyun.com 是
   两套独立账号体系）。

**不要**把 401 当成额度问题去切下一家 —— 代码里已经区分开，401 只记失败、不废通道。

## 五、各家的接口差异（已核对官方文档，写代码时别再猜）

**阿里云百炼 qwen-image**
- `POST https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation`
- **同步**，无异步轮询。返回 `output.choices[].message.content[].image` 是 OSS URL，
  **有效期 24 小时**，必须立刻下载。输出只有 URL，没有 base64。
- 输入图支持 **base64 data URI**，不用图床。
- 参数在 `parameters{}` 里：`size`（`"1024*1024"`，星号）、`negative_prompt`、
  `watermark:false`、`prompt_extend`、`seed`。
- 北京与新加坡的 key 与域名**互不通用**，混用会鉴权失败。

**Google Gemini 图像**
- `POST https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent`
- 头 `x-goog-api-key`；图走 `inline_data{mime_type,data}`，返回 `inlineData.data` 的 base64。
- `generationConfig.responseModalities: ["IMAGE"]`；个别模型只接受 `["TEXT","IMAGE"]`，
  代码里已做退回。
- 无水印（只有不可见的 SynthID）。

**魔搭 ModelScope**
- **异步**，且有三处必须精确匹配，少一个就报 `task not found`：
  1. 提交 `POST /v1/images/generations` 必须带 `X-ModelScope-Async-Mode: true`；
  2. 轮询 `GET /v1/tasks/{id}` 必须带 `X-ModelScope-Task-Type: image_generation`；
  3. 结果图在 **`output_images`**（URL 列表），不是 `output.images`。
- 提交响应里的 `task_status` 是占位值（会直接写 SUCCEED），**不可信**，以轮询为准。
- 一次约 65–75 秒。
- ⚠️ **`image_url` 必须是公网可达的 URL，base64 会被静默忽略**（2026-10-26 实测：
  字符串、数组两种形式都被忽略，模型退化成纯文生图；`image` / `images` 字段直接 400）。
  境外免费图床（uguu / catbox / 0x0 / tmpfiles）阿里后端抓不到，同样被忽略。
  要接魔搭必须先配 `IMG_PUBLIC_BASE` 指向**境内可访问**的图片目录：
  ```bash
  set IMG_PUBLIC_BASE=https://my-bucket.oss-cn-hangzhou.aliyuncs.com/lineart
  ```
  映射规则：`IMG_PUBLIC_BASE + "/" + 文件名`。没配时 `gen_modelscope` **直接报错不硬跑**，
  避免拿到一张跟线稿无关的图白烧额度。

**硅基流动**
- 同步；图片右下角有「AI生成」水印，必须 `strip_watermark`；生成的图要按原图 alpha
  重新蒙版（alpha 是碰撞契约）。

## 六、已知的坑

- **`--dry-run` 不写报告**。之前一次 dry-run 把整关的 `t1_report.json` 覆盖成一条记录，
  靠 `rescore_level.py` 从磁盘复算才恢复。
- **`rescore_level.py` 复算历史报告必须给 `--roi-cutoff`**：ROI 裁剪是 2026-10-24 22:10
  之后才加的，之前的模型图是按整张画布生成的，用新口径复算分数会全错。
- 报告里的 `backend` 字段可用于事后统计“哪家通过率高”，据此调整默认顺序。
