# 进游戏截图怎么截

## 结论先行

`Win + PrtScn`、`PrtScn`、`Win + Alt + PrtScn` 在这台机器上**都不可靠或不可用**：

| 方式 | 现状 | 原因 |
|---|---|---|
| `PrtScn` | 可能全黑 | Unity 独占全屏时前台缓冲在交换链里，GDI 抓不到 |
| `Win + PrtScn` | 可能全黑；且 `Pictures\Screenshots` 目录不存在 | 同上，且系统未初始化该目录 |
| `Win + Alt + PrtScn`（Xbox Game Bar） | **完全没反应** | 本机 `GameDVR_Enabled = 0`，截图功能是关的 |
| `Win + Shift + S`（区域截图） | 可用，但要手拖框、多一步编辑 | 走 DWM 合成层，能抓到 |

所以用项目里已经写好的脚本：**`tools/scripts/shot.ps1`**。已自测通过。

## 用法

在项目根目录 `D:\AI\Guns, Gore and Cannoli from WB` 打开 PowerShell：

```powershell
# 5 秒倒计时，抓 ggc 窗口的客户区，存到 art/scene_shots/ggc_<时间戳>.png
powershell -ExecutionPolicy Bypass -File tools\scripts\shot.ps1
```

```powershell
# 15 秒倒计时（够你从菜单走到港口关）
powershell -ExecutionPolicy Bypass -File tools\scripts\shot.ps1 -Delay 15

# 抓整屏（窗口找不到时的兜底）
powershell -ExecutionPolicy Bypass -File tools\scripts\shot.ps1 -FullScreen

# 指定文件名
powershell -ExecutionPolicy Bypass -File tools\scripts\shot.ps1 -Delay 10 -Out art\scene_shots\level3_quay.png
```

跑起来后：**切回游戏，摆好画面，等倒计时归零**，脚本自动截图。

## 它怎么工作

1. **按进程名匹配**（默认 `-Proc ggc`），找不到才退回按标题模糊匹配（`-Title "Guns"`）；
   最小化了会先还原并置前。
   > 标题匹配在这里是个陷阱：AssetStudio 打开本作文件后，窗口标题是
   > `Studio v1.36... - Guns Gore and Cannoli - 4.3.4f1 - StandaloneWindows`，
   > 用 `*Guns*` 会**抓到 AssetStudio**。所以进程名优先。
2. 用 `PrintWindow(PW_RENDERFULLCONTENT)` 让**游戏自己重画一遍**到我们的画布——窗口被别的程序挡住也能截；
3. 如果返回全黑（独占全屏会这样，本作实测就会），自动退回 `CopyFromScreen` 抓同一块矩形；
4. 抓的是**客户区**，不是整个桌面，所以出来的就是游戏渲染尺寸。

DPI 感知已开（`SetProcessDPIAware`），本机实测：抓整屏得到 1920×1080，与物理分辨率完全一致，不会被 150% 缩放虚化。

实测记录：游戏窗口 `ggc` pid 32652，客户区 **1360×768**（游戏默认窗口化，不是 1080p），
`PrintWindow` 返回全黑 → 自动走 `CopyFromScreen`，截图正常。

## 为什么要客户区而不是桌面

我需要的是**原生渲染尺寸**的图。只有这样才能和 `art/scene_sheets/scene_level3_restyled.png`（我的合成器输出）逐区域比对：色调映射差多少、UI 盖住多少、光照晕有没有位移。带桌面边框或缩放过的图，比对结论就不可信了。

## 如果抓到全黑

说明游戏在独占全屏。两种解法：

1. 游戏内设置里改成**窗口化 / 无边框**（GGC 主菜单通常有 Resolution / Fullscreen 选项）；
2. 命令行强制窗口化启动：
   ```
   ggc.exe -screen-width 1920 -screen-height 1080 -screen-fullscreen 0
   ```
   窗口化之后 `Win + Shift + S` 也能用了。

## 回滚

截图不碰游戏文件，不需要回滚。若美术写回出问题，见 `RESTYLE_SCENE.md` 第 7 节。
