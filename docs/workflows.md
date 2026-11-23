# 工作流

这一页只讲**把 JSON 拖进 ComfyUI** 这件事。脚本怎么生成剧情卡见[用法](usage.md)，每一拍怎么调见[动作库](motion-presets.md)。

源文件在仓库的 [`workflows/`](https://github.com/Gg22333/comfyui-apng-motion/tree/main/workflows)；
下面这些下载链接由 `scripts/sync_workflows.py` 在构建时同步到 `docs/assets/workflows/`。

## 下载

| 环境 | 3 拍 | 4 拍 | 说明 |
| --- | --- | --- | --- |
| SDXL | [workflow-sdxl.json](assets/workflows/workflow-sdxl.json) | [workflow-sdxl-4beat.json](assets/workflows/workflow-sdxl-4beat.json) | `CheckpointLoaderSimple`，20–30 步，cfg 5–7 |
| Moss / DiT | [workflow-moss.json](assets/workflows/workflow-moss.json) | [workflow-moss-4beat.json](assets/workflows/workflow-moss-4beat.json) | `UNETLoader` + `CLIPLoader` + `VAELoader`，8 步，cfg 1.0 |
| 预览用 | — | [workflow-sdxl-preview.json](assets/workflows/workflow-sdxl-preview.json) | 生成仓库那张预览图，同 seed、denoise 0.35 |

24 帧是默认。想要 8 / 30 / 60 帧不用换文件：

```bash
python scripts/emit_workflow.py --base workflows/workflow-moss.json \
    --story assets/story.diet.json --size 640 --out my-60.json
```

`--frames` 会改写插值、解码、合批三件套的节点数量，其它连线不动。

## 结构

```
K 个关键帧（KSampler，共用首帧 latent、同 seed）
  → N × LatentInterpolate
  → N × VAEDecode
  → ImageBatchMulti(N)
  → SaveAnimatedPNG + SaveAnimatedWEBP + VHS_VideoCombine(GIF)
```

N 就是总帧数。采样只做 K 次（每个关键帧一次），插值和解码是纯张量运算，所以帧数翻倍不等于算力翻倍。

## 画布上的三个旋钮

打开工作流，右侧能看到这些节点：

| 节点 | 改什么 |
| --- | --- |
| `CLIPTextEncode`「全局动作指导（所有关键帧共享）」 | 镜头、光照、构图、全片动作约束。改一处，K0..Kn 全部生效。留空 = 旁路 |
| `CLIPTextEncode`「K0 首帧提示」/「K1 提示」/ … | 这一拍发生什么。讲故事的地方 |
| 每个 `KSampler` | seed / steps / cfg / denoise / sampler / scheduler，逐拍可改 |
| `Note`「可调参数清单」 | 上面这些的速查表，直接写在画布上 |
| `Note`「提示词写法（SDXL / MOSS 两套）」 | 两套编码器的写法差异 + 帧数表 |

节拍长度由 `LatentInterpolate` 的分布决定：哪一段插值节点多，哪一拍就慢。
`emit_workflow.py --segs` 一次排好，不用手工数节点。

## 过渡帧怎么排

60 帧不是 60 张新图。采样只发生 K 次（每个关键帧一次），中间的帧由 `LatentInterpolate`
在两张关键帧 latent 之间取点，再各自解码。所以“过渡”分两层：

1. **拍内过渡**：一段里每一帧的 ratio 从源关键帧走向目标关键帧。这一段有几帧，动作就被切成几步。
2. **拍间衔接**：上一段末帧落在目标关键帧，下一段从这里继续往下一拍走。关键帧在时间线上只出现一次。

### 接缝停顿是怎么来的

旧曲线每段都从 `1.0` 排到 `0.0`：

```
段0: K0 … K1(0.0)
段1: K1(1.0) … K2(0.0)   ← K1 又出现一次
```

段尾和下一段段首是同一个关键帧，播放时就是同一张图连放两帧。实测接缝处相邻帧差只有 `0.06`，
看起来像卡住。现在的排法：

- 段 0 第 0 帧 `ratio=1.0` 是 K0 封面，段 0 末帧 `ratio=0.0` 正好是 K1；
- 中间段从 `1/cnt` 起步，末帧 `ratio=0.0` 正好是下一关键帧；
- 最后一段插回 K0，末帧停在 K0 前一格，循环播放接回第 0 帧时不会多停一帧。

### 给每一拍分帧

`segs` 是每段帧数，和必须等于 `frames`。判断标准只有一条：**这一拍两端的姿态差越大，给的帧越多。**

| 这一段在干什么 | 建议帧数（60 帧总量） |
| --- | --- |
| 只动肩、头、嘴角 | 4–5 |
| 抬手、转身、低头 | 5–6 |
| 跨半个身子去够东西、抱起大物件 | 7–8 |

十一拍《减肥破功》的分配是 `5,5,4,7,6,7,5,6,5,5,5`：
够手机（K3→K4）和抱炸鸡桶（K5→K6）各给 7 帧，只动肩膀和头的段给 4–5 帧，最后一拍用 5 帧插回 K0 收尾。

**想整体更慢**：帧数不用动，把三个保存节点的 fps 从 30 降到 24（2.5 s）或 20（3 s）。
插值帧数与每帧步长不变，只是播放速度变慢；这比继续拆拍更省事。

```bash
python scripts/check_anim.py output/apng/anim60_00001_.png \
    --segs 5,5,4,7,6,7,5,6,5,5,5 --fps 30
```

看三个数：

| 指标 | 含义 | 处理 |
| --- | --- | --- |
| `min < 0.5` | 有重复帧，接缝停住 | 查 `build_curve` 是否每段都走 1.0→0.0；查 `segs` 与 `beats` 是否对得上 |
| `max > 8` | 某一步跨太大，像硬切 | 给那一拍加 1–2 帧，不要先加 denoise |
| `drift > 20` | 颜色整体漂移 | 关键帧光照词是否变了；denoise 是否过高 |

## 导入


1. 打开对应环境的 ComfyUI。
2. 把 JSON 拖进画布。
3. 改 loader 里的模型名：
   - SDXL：`CheckpointLoaderSimple` → 你的 checkpoint
   - Moss / DiT：`UNETLoader` + `CLIPLoader`（`type=moss_image`）+ `VAELoader`
4. 确认三个保存节点的 `filename_prefix` 是 `APNG/final/{apng,webp,gif}/...`。
5. **F5 刷新页面**再 Queue，否则前端可能还持着旧 prefix。

## 两个环境的参数差异

| | SDXL | Moss / DiT |
| --- | --- | --- |
| 显存 | 6 GB 起 | 8 GB 起（512 / 640 实测可用） |
| steps | 20–30 | 8（DMD 蒸馏，别加） |
| cfg | 5–7 | 1.0 |
| 关键帧 denoise | 0.35–0.45 | 0.82–0.90（低于 0.80 几乎不动） |
| 文本编码器 | CLIP（英文逗号标签） | Qwen-VL（中文散文） |
| 提示词模式 | `tags` | `moss_zh` |

Moss 把 steps 提到 20、cfg 提到 6 只会更糊 —— 它是 8 步蒸馏模型，不是常规扩散。
SDXL 反过来，20 步以下和 cfg 5 以下会掉细节。

## 提示词写法

**SDXL（tags）**

```
1girl, solo, full body, black short hair, blue eyes, beige hoodie,
dark shorts, barefoot, bedroom at night, warm lamp light,
〈这一拍动作〉,
anime screencap, clean lineart, flat cel shading
```

- 英文逗号分隔，重要标签往前。
- 画风放最后：CLIP 对末尾 token 权重最高。
- 写画面不写效果：`eyes wide, pupils small` 而不是 `shocked`。
- 负向单独一个 `CLIPTextEncode`。

**MOSS（moss_zh）**

```
一间温馨的小卧室，深夜。画面右侧有一盏暖色台灯，光从右前方斜照下来，落在木地板上。
固定机位，平视，全身镜头，人物从头到脚完整入画，双手和双脚都留在画框里。
小满：黑色短发，蓝色眼睛，身材微胖，穿着宽松的米色连帽卫衣和深色短裤，赤脚。
小满盘腿坐在矮桌前，背挺得很直，双手叉在腰上，抬起下巴，嘴角只上扬几毫米。
动漫赛璐璐风格，干净黑色线稿，平涂上色，暖色调，柔和阴影。
```

- 中文散文，换行分段，每段以「。」结尾。
- 不堆 quality tag：`masterpiece` / `best quality` 对它是噪声。
- 用可测量的身体描述：`震惊 = 双眼睁大、瞳孔缩小、嘴张开`。
- 构图写死：固定机位、平视、全身镜头、从头到脚完整入画。
- 负向用中文。

`assets/story.diet.json` 是一个完整的十一拍 `moss_zh` 范例（60 帧 / 30fps）；
`python scripts/make_story.py --preset diet-betrayal --out my.json` 可以直接生成它。

## 帧数

| 帧数 | fps | 时长 | 适合 |
| --- | --- | --- | --- |
| 8 | 8 | 1.00 s | 单表情，体积最小 |
| 24 | 10 | 2.40 s | 默认，聊天表情包 |
| 30 | 15 | 2.00 s | 短动作 |
| 60 | 30 | 2.00 s | 完整小故事（十一拍用 `5,5,4,7,6,7,5,6,5,5,5`） |

三个保存节点的 fps 必须一致。`emit_workflow.py --fps` 会一次改三个。
