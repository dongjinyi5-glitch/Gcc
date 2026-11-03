# 接入硅基流动（SiliconFlow）生图

内置 ImageGen 工具目前不可用 —— 每次调用都返回
`Image model [gpt-image-2.5-sunburst] route config not found`，
这是平台侧的路由配置问题，不是提示词或额度问题，本地无法绕过。
改用硅基流动：它是 OpenAI 风格的 HTTPS 接口，**不需要装插件，也不需要 connector**。

## 一、放密钥

把令牌**单独一行**写进这个文件（不要引号、不要空格、不要 `Bearer`）：

```
D:\AI\Guns, Gore and Cannoli from WB\.secrets\siliconflow.txt
```

`.secrets/` 已加进 `.gitignore`，不会入库。
也可以设环境变量 `SILICONFLOW_API_KEY`，脚本优先读环境变量。

## 二、验证

```powershell
$PY = "C:\Users\Dell\.workbuddy-ai\binaries\python\envs\daiggc\Scripts\python.exe"
$S  = "D:\AI\Guns, Gore and Cannoli from WB\tools\scripts\sfimg.py"

& $PY $S --balance                 # 余额（防跑到一半 403）
& $PY $S --list                    # 这个 key 能用哪些图像模型
& $PY $S --probe --model Kwai-Kolors/Kolors     # 免费模型试一张
```

## 三、价格（2026-10 官方价格页）

| 模型 | 单价 | 备注 |
|---|---|---|
| **Kwai-Kolors/Kolors** | **免费** | 快手的模型，中文提示词友好，画风偏插画 |
| Tongyi-MAI/Z-Image-Turbo | ¥0.10 / 张 | 最快，出草稿用 |
| Tongyi-MAI/Z-Image | ¥0.30 / 张 | 细节更足 |
| Qwen/Qwen-Image | ¥0.30 / 张 | 中文语义最准，招牌文字不乱 |
| Qwen/Qwen-Image-Edit(-2509) | ¥0.30 / 张 | **图生图/指令改图，保形** |

按本项目的量算：

| 范围 | 张数 | Kolors | Z-Image-Turbo | Qwen-Image / Edit |
|---|---|---|---|---|
| P1 重绘 | 319 | ¥0 | ¥32 | ¥96 |
| 全部 1450 | 1450 | ¥0 | ¥145 | ¥435 |

**结论：免费方案够用，付费方案也不到 100 块。** 成本不是瓶颈。

## 四、接口

```
POST https://api.siliconflow.cn/v1/images/generations
Authorization: Bearer <token>
Content-Type: application/json
```

```json
{
  "model": "Kwai-Kolors/Kolors",
  "prompt": "...",
  "negative_prompt": "...",
  "image_size": "1024x1024",
  "batch_size": 1,
  "num_inference_steps": 20,
  "guidance_scale": 7.5,
  "seed": 1
}
```

返回 `{"images":[{"url":"https://...?签名"}],"seed":...}`。
**URL 约 1 小时后失效**，脚本落盘保存，不要存链接。

图生图是否走 `image` 字段（base64 data URL）取决于模型，
`sfimg.py` 已按 `image` 字段实现；第一次用图生图时先拿一张试，
返回 400 就说明该模型不支持，换 `Qwen/Qwen-Image-Edit`。

## 五、这个项目特有的硬约束

**alpha 是碰撞契约。** `restyle_scene` 的输出 alpha 与原图逐位相同，物理碰撞盒是按那个
轮廓建的。扩散模型会改轮廓，所以每张生成图落盘前都要用原图 alpha 重新蒙版 ——
`sfimg.py` 的 `alpha_key` 就是干这个的，不给它就会产出一批"好看但游戏不能玩"的图。

因此按构件类型分两条路：

| 类型 | 例子 | 做法 | 模型 |
|---|---|---|---|
| **大面积材质** | 墙面、地面、水面、天空、船壳钢板 | 文生图产"笔触/宣纸/颜料"材质层，Python 按原图 L* 合成，alpha 完全不动 | Kolors（免费） |
| **离散物件** | 吊车、木箱、锅炉、阀门 | 图生图 / 指令改图保形，再用原 alpha 蒙版 | Qwen-Image-Edit（¥0.30） |
| **P3 小件** | 酒瓶、玻璃碴、小招牌 | 现有 restyle 就够，不生成 | — |

## 六、批量

```powershell
& $PY $S --gen jobs.json --max 20 --out "D:\AI\Guns, Gore and Cannoli from WB\art\gen"
```

`jobs.json` 是一组对象，字段见 `sfimg.py` 文件头。
`--max` 是防误刷的闸门，先小批量出样，看过再放量。
每张图的 model / seed / 耗时 / 提示词都会写进 `art/gen/manifest.json`，
再进 `art/component_versions.json` 变成 `G1`、`G2`… 版本号。

---

# 实测结果（2026-10-23 20:30，用你的令牌跑过）

## 1. 令牌与模型

`--balance` 接口已下线（HTTP 410），不影响生图。
`--list` 返回 6 个模型，全部可用：

```
Tongyi-MAI/Z-Image-Turbo      Tongyi-MAI/Z-Image
Qwen/Qwen-Image-Edit-2509     Qwen/Qwen-Image-Edit
Qwen/Qwen-Image               Kwai-Kolors/Kolors
```

## 2. 免费模型实测：能用，质量不错

`Kwai-Kolors/Kolors` 出一张 1024×1024 用 **16.3 秒**，笔触、宣纸质感、赭石朱红都到位，
风格方向是对的。缺点：**提示词遵从度偏松**（写了"夜间"它给了暖色黄昏）。

## 3. 三个必须记下来的坑

### 坑一：Kolors 静默忽略 `image` 字段

传了输入图 + "保持构图与形状不变"，返回的是一张**完全无关的梅花**，而且 **HTTP 200 不报错**。
这比报错更危险 —— 批量跑会得到 300 张跟原图毫无关系的图，还以为成功了。

**结论：Kolors 只能文生图，不能图生图。** 判断某个模型是否支持图生图，
必须用特征图验证（见下），不能看返回值。

### 坑二：Qwen-Image-Edit 支持 `image`，保形很好

特征图验证（品红底 + 白色十字，指令"十字形状位置不变，背景改深蓝"）：
十字**形状与位置完全保留**，背景精确变深蓝。**接口和字段都是对的。**

但拿真实的夜景贴图去跑，前两次都失败（一次出白底两个灯笼，一次出纯宣纸）。
原因不是接口，是输入预处理：

- 带大块透明区的 RGBA 压成白底 → 模型把白色当画面内容
- 1024×624 塞进 1024×1024 → 比例被拉或模型自己补
- 提示词里带"宣纸质感" → 模型直接画了张宣纸

已在 `b64img()` 修掉：透明区按**不透明像素的中位色**铺底、按目标比例**居中补边**不拉伸。

### 坑三：每张图都带「AI生成」水印

Kolors 和 Qwen 都有，固定在右下角，半透明。对游戏贴图是硬伤 ——
一张铺满整面墙的纹理上会反复出现这四个字。

已在 `strip_watermark()` 自动修掉：取水印左侧等宽条带镜像翻转，四边羽化贴回。
实测接缝不可见。不需要额外花钱。

## 4. 离散物件与费用

判据：**填充率 < 0.6**（纹理矩形里超过 40% 是透明的，说明它是带轮廓的独立物件，
不是铺满的材质）。数据来自 `scene_inventory.json` 的 `fill` 字段。

| 档 | 离散物件（需 Edit 保形） | 材质（可免费路线） | 合计 | Edit 费用 |
|---|---|---|---|---|
| P1 | **92** | 224 | 316 | **¥27.6** |
| P2 | 113 | 210 | 323 | ¥33.9 |
| P3 | 286 | 429 | 715 | ¥85.8 |
| 全部 | **491** | 863 | — | **¥147.3** |

注：`Harbour_013` 是完全空白纹理（0 有效像素），已从队列剔除。

**P1 只要 28 块，全部离散物件也就 147 块。** 留 50% 返工余量，P1 约 ¥41。

## 5. 能不能一次跑成

**不能。** 四个原因：

1. **每个构件的提示词不一样。** 吊车和木箱不能共用一个提示词。
2. **提示词模板要迭代。** 上面两个失败案例说明，夜景 + 透明区的输入需要针对性处理，
   第一轮一定要小批量看效果。
3. **水印修补对平涂区域要复核**（镜像补丁在渐变上可能有痕）。
4. **alpha 必须回填**，回填后轮廓和原图一致，但内部笔触要人眼确认。

现实节奏：**先出 6 张样（每类一张）→ 定提示词模板 → 按类别分批跑 → 每批人工过一遍**。

## 6. Qwen-Image-Edit 有没有免费替代

**没有免费的同功能模型。** 硅基流动上：

- Kolors —— 免费，但**不支持图生图**（坑一）
- Z-Image / Z-Image-Turbo —— 文生图，¥0.10 起
- 只有 Qwen-Image-Edit 系列能做保形改图，¥0.30

**但有免费的方法**，而且覆盖大头：

| 类型 | 免费做法 | 代价 |
|---|---|---|
| 材质类 863 个 | Kolors 免费生成 20~30 张笔触/宣纸/颜料贴图，**反复复用**；Python 按原图 L\* 合成，alpha 完全不动 | ¥0 |
| 离散物件 491 个 | 只能 Edit 保形 | ¥147（P1 只要 ¥28） |

所以推荐的分工是：**材质类走免费路线，离散物件才花钱**。
P1 整体成本 ≈ ¥28，加返工 ≈ ¥40。
