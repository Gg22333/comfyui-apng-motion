# 用法

## 剧情卡

一个 JSON 描述整段表演，`emit_workflow.py` 把它编译成关键帧提示词。

```json
{
  "name": "anim24-4beat",
  "beats": 4,
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

编译规则：`关键帧_i = lock + style + actions[i]`，字段顺序固定，每帧只改动作。

## 生成工作流

```bash
python scripts/emit_workflow.py --base assets/workflow-sdxl.json --story my-story.json --out my.json
```

| 拍数 | 段数分配 | 节点数（SDXL） | 节点数（Moss） |
| --- | --- | --- | --- |
| 3 | 8/8/8 | 66 | 68 |
| 4 | 6/7/6/5 | 69 | 71 |
| 5 | 5/6/5/4/4 | 72 | 74 |

节点数比早期版本多，是因为多了全局动作层：每个关键帧一个 `ConditioningCombine`，
加一个共享的 `CLIPTextEncode` 和一个 `Note`。

命令行直接给参数（不写 JSON）：

```bash
python scripts/emit_workflow.py --base assets/workflow-sdxl.json \
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
| 节奏 | 24 个 `LatentInterpolate` 的 ratio | 缓动曲线。`linear` 每帧步长恒定，最稳 |
| 速度 | 三个保存节点的 `fps` | 必须改成同一个值；10fps × 24 帧 = 2.4 秒 |
| 命名 | `filename_prefix` | 分别落在 `apng/`、`webp/`、`gif/` |
| 画质 | APNG `compress_level`、WebP `lossless`/`quality`、VHS `loop`/`pingpong` | 体积与播放行为 |

命令行也能一次改：

```bash
python scripts/emit_workflow.py --base assets/workflow-sdxl.json --story my-story.json \
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

检查：连线完整性、24 插值 / 24 解码、同一对 latent 上 ratio 唯一、三个输出同源、关键帧共享同一 latent、无 `SaveImage`。

## 跑起来

界面：把 JSON 拖进 ComfyUI，Queue。

无界面：

```bash
python scripts/emit_workflow.py --validate my.json --run --profile profiles/xl.json
```

会提交 API、轮询、打印成品路径，并自动跑 `check_anim.py`。

## 校验成品

```bash
python check_anim.py output/APNG/final/apng/anim24_00001_.png --expect 24
```

关注四项：`frames=24`、`loop=0`、`identical_pairs=0`、`color_drift` 不超过 6。

## 落盘验收

```bash
python scripts/check_output.py --profile profiles/xl.json
```

三格式同批、`output/APNG/` 根目录无游离文件、`FAIL 总数: 0` 才算完成。细则见 [成品落盘](output.md)。

