# 黄金回路往返测试 + 纹理格式分析报告

**日期**: 2026-10-19
**执行者**: Agent B (Developer) + Agent C (QA)

## 1. 黄金回路往返测试

| 文件 | 原始大小 | 字节一致 | 对象数一致 | 类型一致 |
|------|----------|---------|-----------|---------|
| sharedassets1.assets | 16,187,068 | ✅ | ✅ | ✅ |
| sharedassets3.assets | 4,104 | ✅ | ✅ | ✅ |
| sharedassets10.assets | 88,361,028 | ✅ | ✅ | ✅ |

### sharedassets1.assets

- file: `sharedassets1.assets`
- size: `16187068`
- original_sha256: `e8af9eb133c4a45ac8ff8b13d546b1df7c37d1ebb6061c885c7155bed3ea3680`
- original_object_count: `15`
- original_types: `{'PreloadData': 1, 'Material': 4, 'Texture2D': 5, 'Shader': 3, 'Sprite': 2}`
- output_sha256: `e8af9eb133c4a45ac8ff8b13d546b1df7c37d1ebb6061c885c7155bed3ea3680`
- byte_identical: `True`
- output_size: `16187068`
- output_object_count: `15`
- object_count_match: `True`
- types_match: `True`
- output_types: `{'PreloadData': 1, 'Material': 4, 'Texture2D': 5, 'Shader': 3, 'Sprite': 2}`

### sharedassets3.assets

- file: `sharedassets3.assets`
- size: `4104`
- original_sha256: `9688fd6d22b0b59a91870077be82921ad7224a3d71d32c82429fe52a3fd00da7`
- original_object_count: `1`
- original_types: `{'PreloadData': 1}`
- output_sha256: `9688fd6d22b0b59a91870077be82921ad7224a3d71d32c82429fe52a3fd00da7`
- byte_identical: `True`
- output_size: `4104`
- output_object_count: `1`
- object_count_match: `True`
- types_match: `True`
- output_types: `{'PreloadData': 1}`

### sharedassets10.assets

- file: `sharedassets10.assets`
- size: `88361028`
- original_sha256: `8e74b885af07e6cdf5edfecdffaeaff3ddfb93016053f4971726c6ad0c2cb35d`
- original_object_count: `73`
- original_types: `{'PreloadData': 1, 'Texture2D': 36, 'Sprite': 36}`
- output_sha256: `8e74b885af07e6cdf5edfecdffaeaff3ddfb93016053f4971726c6ad0c2cb35d`
- byte_identical: `True`
- output_size: `88361028`
- output_object_count: `73`
- object_count_match: `True`
- types_match: `True`
- output_types: `{'PreloadData': 1, 'Texture2D': 36, 'Sprite': 36}`

## 1b. 纹理级往返测试

| 纹理名 | 尺寸 | 格式 | PNG 重导入一致 |
|--------|------|------|----------------|
| Default-Particle | 64x64 | RGBA32 | ✅ |
| HeadScreamPain | 109x134 | RGBA32 | ✅ |
| BackLegDown | 59x101 | RGBA32 | ✅ |

## 2. 纹理格式分析

**分析纹理总数**: 489

### 格式分布

| 格式 | 数量 |
|------|------|
| ARGB32 | 452 |
| RGB24 | 31 |
| DXT5 | 2 |
| DXT1 | 2 |
| Unknown(2) | 1 |
| Unknown(7) | 1 |

### 尺寸分布 (Top 20)

| 尺寸 | 数量 |
|------|------|
| 1024x1024 | 65 |
| 512x512 | 45 |
| 109x134 | 13 |
| 256x256 | 13 |
| 1024x512 | 11 |
| 123x90 | 10 |
| 480x90 | 10 |
| 128x128 | 9 |
| 110x90 | 9 |
| 161x174 | 8 |
| 500x253 | 8 |
| 53x126 | 5 |
| 107x51 | 5 |
| 1024x693 | 4 |
| 151x131 | 3 |
| 89x47 | 3 |
| 49x108 | 3 |
| 1024x400 | 3 |
| 1024x213 | 3 |
| 104x114 | 3 |

## 3. 提取的样本纹理

| 名称 | 尺寸 | 路径 |
|------|------|------|
| Default-Particle | 64x64 | D:\AI\Guns, Gore and Cannoli from WB\extracted\primary\sample_textures\Default-Particle.png |
| HeadScreamPain | 109x134 | D:\AI\Guns, Gore and Cannoli from WB\extracted\primary\sample_textures\HeadScreamPain.png |
| BackLegDown | 59x101 | D:\AI\Guns, Gore and Cannoli from WB\extracted\primary\sample_textures\BackLegDown.png |
| zombie-burns (effects)_00013 | 512x512 | D:\AI\Guns, Gore and Cannoli from WB\extracted\primary\sample_textures\zombie-burns__effects__00013.png |
| FrontLegLow | 101x75 | D:\AI\Guns, Gore and Cannoli from WB\extracted\primary\sample_textures\FrontLegLow.png |
| Head | 114x105 | D:\AI\Guns, Gore and Cannoli from WB\extracted\primary\sample_textures\Head.png |
| water_splash_00017 | 1024x512 | D:\AI\Guns, Gore and Cannoli from WB\extracted\primary\sample_textures\water_splash_00017.png |
| HandBackPush | 67x71 | D:\AI\Guns, Gore and Cannoli from WB\extracted\primary\sample_textures\HandBackPush.png |
| TorsoChestDead | 84x82 | D:\AI\Guns, Gore and Cannoli from WB\extracted\primary\sample_textures\TorsoChestDead.png |
| TorsoChest | 151x131 | D:\AI\Guns, Gore and Cannoli from WB\extracted\primary\sample_textures\TorsoChest.png |
