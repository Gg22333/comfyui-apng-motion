# 用法

## 剧情卡

一个 JSON 描述整段表演，`emit_workflow.py` 把它编译成关键帧提示词。

```json
{
  "name": "anim24-4beat",
  "beats": 4,
  "frames": 24,
  "segs": [6, 7, 6, 5],
  "fps": 10,
  "denoise": 0.4,
  "lock": "masterpiece, best quality, 1girl, solo, upper body, looking at viewer, simple background",
  "style": "anime screencap, clean lineart, flat cel shading",
  "negative": "worst quality, low quality, blurry, watermark, text, signature",
  "actions": [
    "neutral expression, mouth closed, head straight",
    "eyes widened, eyebrows raised, head tilted 8 degrees",
    "eyes half closed, mouth open, head tilted back 12 degrees",
    "flat expression, eyes half lidded, mouth closed, head straight"
  ]
}
```

编译规则取决于 `prompt_mode`：

| 模式 | 编译结果 | 用在 |
| --- | --- | --- |
| `tags`（默认） | `lock, actions[i], style` 英文逗号拼接 | SDXL / 传统 CLIP |
| `moss_zh` | `lock。\n action。\n style。` 中文散文，换行分段 | MOSS / Qwen-VL |

`tags` 模式下 `style` 必须放最后：CLIP 对末尾 token 权重最高，画风写在中段会被动作词挤掉，
出图会掉进写实照相模式（表现为拼贴照、色块闪）。

`moss_zh` 模式下三段都写中文，每段以「。」结尾；不要混英文标签，也不要堆 `masterpiece`。

`assets/story.diet.json` 是完整范例：

```bash
python scripts/emit_workflow.py --base workflows/workflow-moss.json \
  --story assets/story.diet.json --size 640 --out diet60.json
```

## 帧数怎么选

帧数是参数，不是另一套工作流。`--frames`（或剧情卡的 `"frames"`）会把
`LatentInterpolate` / `VAEDecode` / `ImageBatchMulti` 三件套自动扩缩到 N 个。

| 帧数 | fps | 时长 | 适合 | 4 拍 segs |
| --- | --- | --- | --- | --- |
| 8 | 8 | 1.0 s | 头像微动、聊天气泡 | `2,2,2,2` |
| 12 | 12 | 1.0 s | 轻量贴纸 | `3,3,3,3` |
| 24 | 10 | 2.4 s | 默认；表情循环 | `6,7,6,5` |
| 30 | 15 | 2.0 s | 五拍故事、半身动作 | `8,8,7,7` |
| 60 | 30 | 2.0 s | 网页/Discord 顺滑预览、五拍故事 | `15,15,15,15` |

`--segs` 之和必须等于 `frames`；不给 `--segs` 就按拍数平均分（余数给前几拍）。24 帧时保留旧预设
`3 拍 8/8/8`、`4 拍 6/7/6/5`、`5 拍 5/6/5/4/4`，其余帧数一律平均分。

```bash
python scripts/emit_workflow.py --base workflows/workflow-moss.json --story assets/story.preview.json \
  --frames 60 --segs 15,15,15,15 --fps 30 --out my-60f.json
```

## 生成工作流

```bash
python scripts/emit_workflow.py --base workflows/workflow-sdxl.json --story my-story.json --out my.json
```

| 拍数 | 段数分配（24 帧） | 节点数（SDXL） | 节点数（Moss） |
| --- | --- | --- | --- |
| 3 | 8/8/8 | 67 | 69 |
| 4 | 6/7/6/5 | 70 | 72 |
| 5 | 5/6/5/4/4 | 73 | 75 |

节点数比早期版本多，是因为多了全局动作层：每个关键帧一个 `ConditioningCombine`，
加一个共享的 `CLIPTextEncode` 和两个 `Note`（参数清单 + 提示词写法）。全局动作**留空时不建合并节点**（空提示参与
`ConditioningCombine` 会稀释本帧提示，小模型直接掉画质），填了动作则每多一拍再加 1 个。
帧数只改插值 / 解码 / 合批三件的数量，不改拍数。

命令行直接给参数（不写 JSON）：

```bash
python scripts/emit_workflow.py --base workflows/workflow-sdxl.json \
  --beats 4 --segs 6,7,6,5 \
  --lock "masterpiece, 1girl, silver hair" --style "anime" \
  --actions "neutral|notice|react|settle" --out my.json
```

## 可调参数

| 范围 | 节点 | 控制什么 |
| --- | --- | --- |
| 全片动作 | `CLIPTextEncode`「全局动作指导（所有关键帧共享）」 | 动作、镜头、光照、风格。改一处，K0..Kn 全部生效；留空即不加额外条件 |
| 每帧提示 | `CLIPTextEncode`「K0 / K1 / … 提示」 | 表情、姿态、视线，逐帧独立 |
| 每帧采样 | 每个 `KSampler` | seed、steps、cfg、采样器、调度器、denoise |
| 节奏 | N 个 `LatentInterpolate` 的 ratio | 缓动曲线。`linear` 每帧步长恒定，最稳 |
| 速度 | 三个保存节点的 `fps` | 必须改成同一个值；`fps × 帧数` = 时长（24 帧 @10fps = 2.4 秒，60 帧 @30fps = 2 秒） |
| 提示词方言 | `--prompt-mode tags|moss_zh` / 剧情卡 `prompt_mode` | `tags` = 英文标签；`moss_zh` = 中文散文 |
| 尺寸 | latent 宽高 / `--size 640` | Moss 512 或 640；SDXL 512–1024 |
| 命名 | `filename_prefix` | 分别落在 `apng/`、`webp/`、`gif/` |
| 画质 | APNG `compress_level`、WebP `lossless`/`quality`、VHS `loop`/`pingpong` | 体积与播放行为 |

命令行也能一次改：

```bash
python scripts/emit_workflow.py --base workflows/workflow-sdxl.json --story my-story.json \
  --motion "slow head tilt, stable lighting" \
  --seed 777777 --denoise 0.35 --steps 24 --cfg 5.5 \
  --curve linear --out my.json
```

### 曲线怎么选

| 值 | 行为 | 什么时候用 |
| --- | --- | --- |
| `linear`（默认） | 每帧步长恒定 | 最不容易看出跳帧，适合表情包 |
| `ease` | 两端慢、中间快 | 想要「起势—爆发—收住」的动作感 |
| `snap` | 前段几乎静止、末段猛冲 | 旧版行为，只在对比时用 |

### 换模型

结构不变，只换加载器：

| 模型族 | 加载器 | 关键帧 denoise |
| --- | --- | --- |
| SD 1.5 | `CheckpointLoaderSimple` | 0.45–0.55 |
| SDXL / Illustrious / NoobAI | `CheckpointLoaderSimple` | 0.35–0.45 |
| FLUX.1 | `UNETLoader` + `DualCLIPLoader` + `VAELoader` | 0.45–0.55 |
| Moss / DiT | `UNETLoader` + `CLIPLoader`（`type=moss_image`）+ `VAELoader` | 0.50–0.55 |

denoise 是经验值。同 seed 下 SDXL 超过 0.42 就开始改衣服和背景，插值时出现色斑；
要更大表情用 0.45–0.5 并接受漂移，或改用面部局部重绘。

## 校验

```bash
python scripts/emit_workflow.py --validate my.json
```

检查：连线完整性、插值数 = 解码数 = `ImageBatchMulti` 接线数、同一对 latent 上 ratio 唯一、
三个输出同源、关键帧共享同一 latent、无 `SaveImage`。

## 跑起来

界面：把 JSON 拖进 ComfyUI，Queue。

无界面：

```bash
python scripts/emit_workflow.py --validate my.json --run --profile profiles/xl.json
```

会提交 API、轮询、打印成品路径，并自动跑 `check_anim.py`。

## 校验成品

```bash
python check_anim.py output/APNG/final/apng/anim60_00001_.png --expect 60
```

关注四项：`frames=N`（与 `--frames` 一致）、`loop=0`、`identical_pairs=0`、`color_drift` 尽量低
（Moss 0.5 档实测 18 上下仍可看，SDXL 0.35 档约 2.6；超过 20 基本就是关键帧重绘过头）。

## 落盘验收

```bash
python scripts/check_output.py --profile profiles/xl.json
```

三格式同批、`output/APNG/` 根目录无游离文件、`FAIL 总数: 0` 才算完成。细则见 [成品落盘](output.md)。

