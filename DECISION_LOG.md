# 决策日志 — Guns, Gore and Cannoli 美术资产逆向替换

---

## 2026-10-19 22:08 - [Agent A] 项目初始化与基线确认

### 背景
用户发起项目：将 Guns, Gore and Cannoli 的角色与场景替换为中国国画（水墨）风格。要求按顶尖专家标准执行，建立多角色协作，以逆向文档为第一个里程碑。

### 产品决定

| # | 决策项 | 产品决定 |
|---|--------|----------|
| 1 | 游戏安装路径 | `D:\BaiduNetdiskDownload\意大利黑1\Guns, Gore and Cannoli` |
| 2 | 目标平台 | 仅 Windows |
| 3 | 游戏引擎 | 通过实际程序解析确认 → **Unity 5.x (2015), Mono 后端, 非 IL2CPP** |
| 4 | 替换范围优先级 | 角色全动作集 → 场景图层 → UI/粒子 → 调色板动画（暂不动） |
| 5 | 目标美术风格 | 中国国画风格（水墨五色、留白、笔触肌理） |
| 6 | 工具下载授权 | 授权通过 |
| 7 | 工作目录 | `D:\AI\DAIGuns, Gore and Cannoli from WB`（全部资料） |
| 8 | 规则目录 | `D:\AI\Guns, Gore and Cannoli on China`（AI Agent 规则） |
| 9 | 目录内授权 | 永久有效；目录外每次确认 |

### 引擎确认证据（一手）
```
ggc_Data/
├── Managed/
│   ├── Assembly-CSharp.dll      # Unity 主游戏代码（C#，可反编译）
│   ├── Assembly-CSharp-firstpass.dll
│   ├── UnityEngine.dll
│   └── mscorlib.dll, System*.dll
├── Mono/mono.dll                # Mono 运行时（非 IL2CPP）
├── resources.assets (1.3 GB)    # Unity 主资源包
├── sharedassets0-15.assets      # 分场景资源
├── level0-14                    # 关卡场景数据
├── mainData
├── StreamingAssets/
├── Plugins/ (CSteamworks.dll, AVProWindowsMedia.dll)
└── Resources/
```

### 不可变四项（逆向确认后锁定）
1. 碰撞盒数据位置 → 逆向时发现即记录
2. 调色板动画实现 → 逆向时发现即记录
3. 场景分层渲染顺序/Z-Order → 逆向时发现即记录
4. 音频/本地化同包体 → 保持

### 技术路线
选择最成熟、适用性最广、编译后硬件要求最低的逆向工具链：
- 资源解析：UnityPy（Python，一手字节解析）
- 资源浏览：AssetRipper
- 代码反编译：dnSpy/ILSpy
- GPU 捕获：RenderDoc
- 美术创作：Krita + Aseprite + DragonBones

### 影响范围
- M1 逆向文档里程碑立即启动
- 所有格式判断基于实际字节解析，不接受二手结论
- 黄金回路往返测试作为修改前的强制前置门

---

*记录者：Agent A (Architect / Tech Lead)*
