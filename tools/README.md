# tools/ 脚本索引

> **本文件是分类索引，不是目录结构。** 91 个 `.py` + 2 个 `.ps1` **全部物理位于** `tools/scripts/`。
> 分类只用于阅读与检索；**不要据此移动文件**——脚本之间是 bare import（假设同目录），
> 迁移必须先有逐脚本方案并验证导入、入口、文档引用与旧命令兼容性。

调用约定：

```bash
python tools/scripts/<name>.py [args]
powershell -ExecutionPolicy Bypass -File tools/scripts/shot.ps1 -Tag L4
```

---

## 分类总表

| 类别 | 数量 | 职责 |
|---|---|---|
| `assets` | 14 | 游戏包读写与对象清单 |
| `characters` | 26 | 角色身份、部件、Hat、名单 |
| `scenes` | 18 | 场景图层、构件分档、T1 流水线 |
| `rendering` | 10 | 画风转换与生图通道 |
| `qa` | 15 | 度量、门禁、评审、证据 |
| `docs` | 8 | 文档与表格生成器 |
| `(ps1)` | 2 | `shot.ps1` / `shot_hotkey.ps1`：窗口截图与热键截图 |

---

## assets — 游戏包读写与对象清单（14）

| 脚本 | 用途（取 docstring 首行） | 依赖的本地模块 |
|---|---|---|
| `ggc_assets.py` | Shared access layer for Guns, Gore and Cannoli (Unity 4.3.4f1) assets. | — |
| `asset_inventory.py` | asset_inventory.py — 使用 UnityPy 对游戏 .assets 做完整资源清单提取 | — |
| `parse_assets_raw.py` | parse_assets_raw.py — 不依赖 UnityPy 的 .assets 对象表解析器 | — |
| `detect_unity_version.py` | detect_unity_version.py — 读取 .assets 文件二进制头，检测 Unity 引擎版本 | — |
| `locate_assets.py` | Locate every character's sprite/atlas assets inside the AssetStudio dump. | `characters_meta` |
| `dump_names.py` | Dump all object names from Unity .assets files for character roster discovery. | — |
| `find_go_node.py` | Who else references this sprite's texture? | `ggc_assets` |
| `try_repoint.py` | Try re-pointing one character's Hat sprite, render it, then restore. | `ggc_assets` |
| `transplant_check.py` | Compare one slot across two prefabs: transform, sprite identity, texture. | `ggc_assets` |
| `patch_textures.py` | Patch restyled textures into .assets **in place**, byte for byte. | — |
| `writeback.py` | Write the 重彩 textures back into the game's .assets files. | — |
| `patch_scene.py` | Patch restyled scene textures into .assets in place, byte for byte. | — |
| `patch_scene_textures.py` | 把路线 B 切回后的图集**定点写进游戏包**（字节数不变，不用 UnityPy 保存）。 | `ggc_assets`, `patch_textures`, `scene_stack` |
| `roundtrip_and_format_test.py` | roundtrip_and_format_test.py — 黄金回路往返测试 + 纹理格式分析 | — |

## characters — 角色身份、部件、Hat、名单（26）

| 脚本 | 用途（取 docstring 首行） | 依赖的本地模块 |
|---|---|---|
| `characters_meta.py` | Canonical identity table for every combat unit in Guns, Gore and Cannoli. | — |
| `extract_parts.py` | Extract every sprite part of a character, including inactive variants. | `ggc_assets` |
| `render_characters.py` | Render character previews + metadata from Unity 4.3.4f1 assets. | — |
| `render_characters_v2.py` | Render character previews with a correct 2D TRS transform chain. | — |
| `render_compare.py` | Render a character twice -- original art vs 重彩 restyle -- and stack them. | `ggc_assets` |
| `build_roster.py` | Build character roster deliverables from roster.json + rendered PNGs. | — |
| `build_roster_v2.py` | Build the integrated character roster (HTML + Markdown + CSV). | `characters_meta` |
| `draft_briefs.py` | 为 42 个角色生成"国画重彩替代描述"草稿，预填进清单页。 | `characters_meta` |
| `import_briefs_csv.py` | 把填好的 CSV 读回 validation/roster_briefs.json（与网页填写同一条落地路径）。 | `characters_meta` |
| `make_blank_csv.py` | 生成一份"空白"的替代描述表（CSV，带 BOM，Excel 直接双击打开不乱码）。 | `characters_meta` |
| `brief_server.py` | 本地填写服务：把清单页上的"国画重彩替代描述"即时写进工程目录。 | `characters_meta` |
| `hat_plan.py` | Roll the Hat split out to every character -- consolidate, then repaint. | `characters_meta`, `factions`, `ggc_assets`, `restyle_ink`, `split_hat`, `theme_cbi` |
| `split_hat.py` | Split the shared Hat so the hero and the villains can wear different helmets. | `ggc_assets`, `restyle_ink`, `theme_cbi` |
| `transplant_hat.py` | Give a character a real steel helmet by transplanting an in-game sprite. | `ggc_assets` |
| `survey_hats.py` | Survey every character's headgear sprite, so a helmet can be borrowed. | `characters_meta`, `ggc_assets` |
| `redraw_parts.py` | Redraw pipeline (plan B): replace part art with newly drawn sprites. | `ggc_assets`, `theme_cbi`, `touchup` |
| `redraw_weapons.py` | Redraw a weapon family from one generated concept image. | `ggc_assets`, `redraw_parts` |
| `weapon_layout.py` | Build per-family weapon reference composites + placement manifests. | `ggc_assets` |
| `touchup.py` | Post-slice art fixes, declared per character in touchup.json. | `transplant_hat` |
| `fix_head_net_proto.py` | Prototype: strip the camo net off Gangster1's forehead. | — |
| `head_fix_diag.py` | Diagnose what the head sprite wastes on headwear the Hat sprite already draws. | — |
| `debug_hands.py` | Tint each hand sprite a different colour and composite, to see the overlaps. | `ggc_assets` |
| `montage.py` | Quick labelled montage for visual identification of roster PNGs. | — |
| `faction_survey.py` | Survey the 33 characters and report the real colour make-up of each faction. | `factions`, `ggc_assets`, `style_metrics` |
| `factions.py` | Single source of truth for character -> faction. | — |
| `theme_cbi.py` | CBI 题材改造：通用历史身份方案（唯一执行稿来源）。 | — |

## scenes — 场景图层、构件分档、T1 流水线（18）

| 脚本 | 用途（取 docstring 首行） | 依赖的本地模块 |
|---|---|---|
| `scene_survey.py` | Survey what the 15 level files actually contain. | `ggc_assets` |
| `scene_stats.py` | Measure how much art is really there: alpha coverage per scene texture. | `ggc_assets` |
| `scene_sheets.py` | Scene-layer catalog: per-level contact sheets, FX and UI batches. | `ggc_assets` |
| `scene_render.py` | Composite a whole level's SpriteRenderers into one picture. | `ggc_assets` |
| `scene_stack.py` | 整层合成重绘 → 按层 alpha 切回（路线 B 的脚手架）。 | `ggc_assets`, `scene_render` |
| `scene_textures.py` | Inventory of every texture the level files actually put on screen. | `ggc_assets` |
| `scene_colliders.py` | Which scene textures sit on a GameObject that carries a Collider2D. | `ggc_assets` |
| `chapter_cards.py` | Export the chapter-select cards and annotate them with the level mapping. | `ggc_assets` |
| `redraw_scene.py` | 路线 B 第 2 步：把整层合成图交给模型重绘，再把结果切回各层贴图。 | `ggc_assets`, `gitee_host`, `imgrouter`, `scene_stack` |
| `preview_sliced.py` | 零成本验收：把切回后的图集重新合成一遍，看「游戏里真正会看到的样子」。 | `ggc_assets`, `scene_stack` |
| `component_taxonomy.py` | One place that decides what a scene component *is*. | `ggc_assets` |
| `component_tiers.py` | 替换层级 T1–T4。 | `component_taxonomy` |
| `component_metrics.py` | Per-component numbers behind the "my recommendation" column. | `ggc_assets` |
| `export_component_thumbs.py` | Export one thumbnail per scene component, original and restyled. | `ggc_assets` |
| `redraw_targets.py` | 构件 -> 重绘目标形态。 | — |
| `make_jobs.py` | T1 重绘作业生成器 —— 把「目标形态」写成能直接用的提示词。 | — |
| `redraw_t1.py` | T1 重绘流水线：原图 -> 白描 -> 模型上色 -> 回贴 -> 打分。 | `component_taxonomy`, `component_tiers`, `fidelity`, `ggc_assets`, `imgrouter`, `lineart`, `make_jobs`, `recompose`, `redraw_targets` |
| `register_t1_versions.py` | 把通过的 T1 重绘登记进版本库 art/component_versions.json。 | `ggc_assets` |

## rendering — 画风转换与生图通道（10）

| 脚本 | 用途（取 docstring 首行） | 依赖的本地模块 |
|---|---|---|
| `restyle_ink.py` | Restyle Guns, Gore and Cannoli sprite parts into 重彩 Chinese ink painting. | `factions`, `theme_cbi` |
| `restyle_scene.py` | Scene restyle: pigment ramps driven by luminance, after a cast removal. | `ggc_assets`, `restyle_ink`, `style_metrics` |
| `lineart.py` | 白描底稿 —— 从原图抽出线描，作为重绘的输入。 | — |
| `recompose.py` | 白描 -> 重彩上色 -> 回贴原图。 | `restyle_scene` |
| `brush_overlay.py` | Put real brushwork on a restyled component without touching its shape. | `ggc_assets`, `restyle_scene` |
| `imgrouter.py` | 多通道图片生成后端：阿里云百炼 / Google AI Studio / 魔搭 / 硅基流动。 | `fidelity`, `ggc_assets`, `sfimg` |
| `sfimg.py` | SiliconFlow image client -- the replacement for the dead ImageGen route. | `ggc_assets` |
| `gitee_host.py` | 把本地图传到 Gitee 仓库，换一个「境内可访问的公网图片 URL」。 | `ggc_assets` |
| `diag_backends.py` | 诊断四家通道：分离「密钥问题」与「网络问题」。 | — |
| `aliyun_ak_probe.py` | 阿里云 AK/SK 探针。 | — |

## qa — 度量、门禁、评审、证据（15）

| 脚本 | 用途（取 docstring 首行） | 依赖的本地模块 |
|---|---|---|
| `acceptance.py` | Run the 重彩 acceptance gate on a rendered character pair. | `factions`, `style_metrics`, `theme_cbi` |
| `style_metrics.py` | Quantified style metrics for 重彩 (heavy-colour) Chinese ink painting. | — |
| `fidelity.py` | 重绘保真度打分 —— 判断模型有没有真的照着白描底稿画。 | `lineart`, `recompose` |
| `faction_summary.py` | Aggregate the per-character acceptance reports into one three-faction sheet. | — |
| `qa_cells.py` | 疑问 / 答复的单元格内富文本。 | — |
| `qa_report.py` | 看看用户提了哪些疑问还没答复，以及「待确认」页回答了没有。 | `build_component_xlsx`, `qa_cells` |
| `t1_review.py` | T1 重绘评审页 —— 把一批 T1 重绘做成一张可点的表。 | `component_taxonomy`, `ggc_assets` |
| `rescore_level.py` | 从存盘文件复算 T1 分数（不调 API），与 redraw_t1 运行时判分一致。 | `component_taxonomy`, `component_tiers`, `fidelity`, `ggc_assets`, `lineart`, `redraw_t1`, `redraw_targets` |
| `patch_verdicts.py` | 手术式写回判定列：只改 sheet XML 里那几个 <t>文字</t>，其余 zip 条目字节原样复制。 | — |
| `apply_confirmations.py` | 把用户的确认结论写回 背景构件替换总表.xlsx（就地写，不重建，不动格式）。 | — |
| `three_way.py` | Side-by-side verdict sheet: original vs palette route vs redraw route. | `ggc_assets` |
| `compare_sheet.py` | Build a before/after comparison sheet for restyled sprite parts. | — |
| `organize_shots.py` | Sort the in-engine screenshots into per-level, per-zone folders and build an index. | — |
| `render_ingame.py` | Render the character straight out of the *patched game files*. | `ggc_assets` |
| `render_live.py` | Render characters straight from the LIVE data dir (not backup/), so a patch | `ggc_assets` |

## docs — 文档与表格生成器（8）

| 脚本 | 用途（取 docstring 首行） | 依赖的本地模块 |
|---|---|---|
| `build_l3_brief.py` | Render docs/L3_RANGOON_BRIEF.html from the hand-written briefs. | `ggc_assets`, `l3_brief_data` |
| `build_restyle_doc.py` | Build docs/RESTYLE_ALL.html -- the whole game, restyled, level by level. | `build_scene_plan`, `ggc_assets` |
| `build_scene_doc.py` | Build docs/SCENE_LAYERS.html -- the reviewable scene-layer catalog. | `ggc_assets` |
| `build_scene_plan.py` | Build docs/SCENE_PLAN.html -- the historical remap, level by level. | `ggc_assets` |
| `build_component_xlsx.py` | Build the component replacement workbook. | `component_taxonomy`, `component_tiers`, `ggc_assets`, `historical_map`, `qa_cells`, `redraw_targets` |
| `export_theme.py` | Export the CBI re-theme execution spec in three formats. | `characters_meta`, `theme_cbi` |
| `l3_brief_data.py` | L3 仰光港 —— 14 张地标的改造内容（人工撰写，逐张对过原图）。 | — |
| `historical_map.py` | 章节 -> 历史原型。权威来源是 docs/CHAPTERS.md，这里只是它的代码形态。 | — |

---

## 依赖关系

**没有包结构，没有 `__init__.py`**：所有跨脚本引用都是 bare import（`from ggc_assets import …`），
依赖“同目录”这一前提。因此 `tools/scripts/` 内的文件彼此不可随意拆开。

| 被依赖的模块 | 被几个脚本 import |
|---|---|
| `ggc_assets` | 45 |
| `characters_meta` | 9 |
| `theme_cbi` | 6 |
| `component_taxonomy` | 5 |
| `factions` | 4 |
| `component_tiers` | 3 |
| `fidelity` | 3 |
| `lineart` | 3 |
| `redraw_targets` | 3 |
| `restyle_ink` | 3 |
| `scene_stack` | 3 |
| `style_metrics` | 3 |

- 被其他脚本 import 的模块（共享层）：**30 个** —— `build_component_xlsx`, `build_scene_plan`, `characters_meta`, `component_taxonomy`, `component_tiers`, `factions`, `fidelity`, `ggc_assets`, `gitee_host`, `historical_map`, `imgrouter`, `l3_brief_data`, `lineart`, `make_jobs`, `patch_textures`, `qa_cells`, `recompose`, `redraw_parts`, `redraw_t1`, `redraw_targets`, `restyle_ink`, `restyle_scene`, `scene_render`, `scene_stack`, `sfimg`, `split_hat`, `style_metrics`, `theme_cbi`, `touchup`, `transplant_hat`
- 不被任何脚本 import 的（顶层入口 / 独立脚本）：**61 个**
- 依赖边总数：**112 条**

---

## 入口安全性

**不能用 `--help` 当探针**：部分脚本不解析参数，传 `--help` 也会照常跑完并写文件。

- 含 `argparse` / `sys.argv` 判断（可安全 `--help`）：**48 个**
- 不含参数解析（**执行即全量运行，可能写文件**）：**43 个**

<details>
<summary>不含参数解析的脚本清单</summary>

- `asset_inventory.py`
- `build_component_xlsx.py`
- `build_l3_brief.py`
- `build_restyle_doc.py`
- `build_roster.py`
- `build_roster_v2.py`
- `build_scene_doc.py`
- `build_scene_plan.py`
- `characters_meta.py`
- `component_metrics.py`
- `component_taxonomy.py`
- `component_tiers.py`
- `detect_unity_version.py`
- `diag_backends.py`
- `draft_briefs.py`
- `dump_names.py`
- `export_component_thumbs.py`
- `export_theme.py`
- `faction_summary.py`
- `faction_survey.py`
- `factions.py`
- `fidelity.py`
- `fix_head_net_proto.py`
- `ggc_assets.py`
- `historical_map.py`
- `l3_brief_data.py`
- `lineart.py`
- `locate_assets.py`
- `make_blank_csv.py`
- `organize_shots.py`
- `parse_assets_raw.py`
- `qa_cells.py`
- `qa_report.py`
- `recompose.py`
- `redraw_targets.py`
- `render_characters.py`
- `render_characters_v2.py`
- `roundtrip_and_format_test.py`
- `scene_colliders.py`
- `scene_survey.py`
- `scene_textures.py`
- `survey_hats.py`
- `theme_cbi.py`

</details>

---

## PowerShell 入口

| 脚本 | 用途 |
|---|---|
| `shot.ps1` | 单次窗口截图（`-Title` / `-Delay` / `-FullScreen` / `-Out`） |
| `shot_hotkey.ps1` | 热键截图：F9 拍一张，F10 退出（`-Tag` 决定文件名前缀） |

输出目录默认 `art/scene_shots/`。

---

*本文件由实际文件树与 AST 生成；新增脚本后需重新生成本表。*
