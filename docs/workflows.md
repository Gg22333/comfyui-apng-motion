# 工作流

这一页只讲**把 JSON 拖进 ComfyUI** 这件事。脚本怎么生成剧情卡见[用法](usage.md)，每一拍怎么调见[动作库](motion-presets.md)。

源文件在仓库的 [`workflows/`](https://github.com/Gg22333/comfyui-apng-motion/tree/main/workflows)；
下面这些下载链接由 `scripts/sync_workflows.py` 在构建时同步到 `docs/assets/workflows/`。

## 下载

| 环境 | 3 拍 | 4 拍 | 说明 |
| --- | --- | --- | --- |
| UNet 系（SDXL） | [workflow-sdxl.json](assets/workflows/workflow-sdxl.json) | [workflow-sdxl-4beat.json](assets/workflows/workflow-sdxl-4beat.json) | `CheckpointLoaderSimple`，20–30 步，cfg 5–7 |
| DiT 系（MOSS-Image） | [workflow-moss.json](assets/workflows/workflow-moss.json) | [workflow-moss-4beat.json](assets/workflows/workflow-moss-4beat.json) | `UNETLoader` + `CLIPLoader` + `VAELoader`，8 步，cfg 1.0。换 FLUX / SD3 / Krea / Anima 只换三个加载器 |
| 预览用（SDXL，60 帧 4 拍） | — | [workflow-sdxl-preview.json](assets/workflows/workflow-sdxl-preview.json) | SDXL 预览样例，同 seed、`denoise 0.5`、30fps |
| 预览用（MOSS，60 帧 11 拍） | — | [workflow-moss-preview.json](assets/workflows/workflow-moss-preview.json) | 生成仓库那张预览图，同 seed、`denoise 0.85`、20fps、3.00 秒 |
| 动态帧数（UNet，3 拍 24 帧） | [workflow-sdxl-dynamic.json](assets/workflows/workflow-sdxl-dynamic.json) | — | 先跑 `install_nodes.py` 装 `comfyui_nodes`，重启 ComfyUI；每拍 `frames` 是图上 widget |
| 动态帧数（DiT，3 拍 24 帧） | [workflow-moss-dynamic.json](assets/workflows/workflow-moss-dynamic.json) | — | 同上；换 FLUX / SD3 / Krea / Anima 只换三个加载器 |

24 帧是默认。想要 8 / 30 / 60 帧不用换文件：

```bash
python scripts/emit_workflow.py --base workflows/workflow-moss.json \
    --story assets/story.diet.json --size 640 --out my-60.json
```

`--frames` 会改写插值、解码、合批三件套的节点数量，其它连线不动。

要在图上直接改每拍帧数、并在存盘前看相邻帧差与接缝，用[动态帧数模式](dynamic.md)：每拍一个 `APNG Latent Interpolate N`，`frames` 是 widget。

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
| `Note`「提示词写法（按架构分方言）」 | 三种编码器方言 + Layout 规则 + 帧率表 |

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

**想整体更慢**：帧数不用动，把三个保存节点的 fps 从 30 降到 20（3 s）。
插值帧数与每帧步长不变，只是播放速度变慢；这也比继续拆拍更省事。
定好总时长后，再用剧情卡的 `dwell` 决定哪几拍多停——见[节奏](#节奏fps-与每拍停留)。

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
   - DiT 系：`UNETLoader` + `CLIPLoader`（MOSS-Image 填 `type=moss_image`）+ `VAELoader`
4. 确认三个保存节点的 `filename_prefix` 是 `APNG/final/{apng,webp,gif}/...`。
5. **F5 刷新页面**再 Queue，否则前端可能还持着旧 prefix。

## 两个环境的参数差异

| | UNet 系（SDXL） | DiT 系（MOSS-Image） |
| --- | --- | --- |
| 显存 | 6 GB 起 | 8 GB 起（512 / 640 实测可用） |
| steps | 20–30 | 8（DMD 蒸馏，别加） |
| cfg | 5–7 | 1.0 |
| 关键帧 denoise | 0.35–0.45 | 0.82–0.90（低于 0.80 几乎不动） |
| 文本编码器 | CLIP（英文逗号标签） | Qwen3.5-9B（中文散文） |
| 提示词模式 | `tags` | `moss_zh` |

MOSS-Image 把 steps 提到 20、cfg 提到 6 只会更糊 —— 它是 8 步 DMD 蒸馏模型，不是常规扩散。
SDXL 反过来，20 步以下和 cfg 5 以下会掉细节。

**MOSS-Image 是 DiT 的一种，SDXL 不是 DiT。** 把「Moss / DiT」并列是分类错误：
DiT 是架构（arXiv:2212.09748，把 U-Net 主干换成 transformer），MOSS 是具体模型。
换 FLUX / SD3 / Krea / Anima 时，denoise 走 DiT 那档 0.45–0.55，不是 0.85。逐个模型见 [模型与架构](models.md)。

## 提示词写法

写法跟**文本编码器**走，不跟模型名走。三种方言覆盖全部模型，完整规则在
[提示词写法](prompting.md)。

| 编码器 | 谁在用 | 方言 | 一句话记法 |
| --- | --- | --- | --- |
| CLIP | SD 1.5、SDXL、Illustrious、NoobAI | `tags` | 逗号堆词，画风放最后 |
| Qwen-VL 系 | MOSS-Image、Krea 2、Qwen-Image、Anima | `moss_zh` | 分段散文，每段句号结尾 |
| T5 | FLUX.1、SD3 / SD3.5 | 散文 | 完整英文句子，不用 `(word:1.3)` |

```text
CLIP    : 1girl, solo, full body, … , 〈这一拍动作〉, anime screencap, clean lineart
Qwen-VL : 一间温馨的小卧室，深夜。／固定机位，平视，全身镜头……／小满：黑色短发……
T5      : A young woman with short black hair sits upright behind a low wooden table …
```

三条硬规则：

1. **每一拍只改一个变量**。改两个，插值出来就是两张不同的脸。
2. **写画面，不写效果**。`shocked` 换成 `双眼睁大、瞳孔缩小、嘴张开`。
3. **构图写死**。`固定机位，平视，全身镜头，从头到脚完整入画`，否则模型会自作主张切半身。

画面里要出现文字（招牌、海报、气泡）时用绝对像素 bbox，画布边长取 16 的倍数——细则见
[提示词写法](prompting.md#画面里要出现文字时)。

`assets/story.diet.json` 是一个完整的十一拍 `moss_zh` 范例（60 帧 / 20fps / 3 秒）；
`python scripts/make_story.py --preset diet-betrayal --out my.json` 可以直接生成它。

## 节奏：fps 与每拍停留

节奏是两层，不要混：

| 层 | 谁决定 | 效果 |
| --- | --- | --- |
| **总时长** | 保存节点的 `fps`（剧情卡 `fps`） | `frames / fps`。60 帧 @20fps = 3 秒 |
| **每拍停留** | 剧情卡 `dwell`（每拍一个权重） | 关键帧多停、过渡快过。总时长不变 |
| **拍内缓动** | 剧情卡 `ease`（0–0.8，默认 0.3） | 每拍开头和结尾的帧延时加长，中段加速 |

**ComfyUI 的保存节点只接受一个全局 fps**，逐帧停留表达不出来。所以：

```bash
# 1) 先出片（三个保存节点用同一个 fps）
python scripts/emit_workflow.py --base workflows/workflow-moss.json \
    --story assets/story.diet.json --size 640 --out diet60.json

# 2) 出片后重写逐帧延时：像素一个都不动，不重跑采样
python scripts/retime.py output/apng/anim60_00001_.png --story assets/story.diet.json

# 3) 网页预览用同一套时长
python scripts/make_preview.py output/apng/anim60_00001_.retimed.png \
    --story assets/story.diet.json --out-dir docs/assets --width 384
```

### 帧数 × 帧率

| 帧数 | 慢（叙事） | 标准 | 快（弹幕感） |
| --- | --- | --- | --- |
| 8 | 6 fps / 1.33 s | 8 fps / 1.00 s | 10 fps / 0.80 s |
| 24 | 8 fps / 3.00 s | 10 fps / 2.40 s | 12 fps / 2.00 s |
| 30 | 10 fps / 3.00 s | 15 fps / 2.00 s | 20 fps / 1.50 s |
| 60 | **20 fps / 3.00 s（默认）** | 25 fps / 2.40 s | 30 fps / 2.00 s |

**GIF 的帧延时只能量化到 10 ms（1 厘秒）**，所以：

| fps | 每帧 | GIF 实际写入 | 60 帧实际时长 |
| --- | --- | --- | --- |
| 8 | 125 ms | 120 ms | 7.2 s（24 帧时 2.9 s） |
| 10 | 100 ms | 100 ms ✓ | 6.0 s（24 帧时 2.4 s） |
| 20 | 50 ms | 50 ms ✓ | 3.00 s |
| 25 | 40 ms | 40 ms ✓ | 2.40 s |
| 24 | 41.7 ms | 40 ms | 2.40 s（不是 2.5 s） |
| 30 | 33.3 ms | 30 ms | 1.80 s（不是 2.0 s） |

打 ✓ 的是整除档，GIF 不会悄悄改速。APNG 与 WebP 是毫秒精度，任何 fps 都准。

### 每拍至少 0.20 秒

十一拍 60 帧 @20fps，平均每拍 0.27 秒。只动肩头的拍可以给 4 帧（0.20 秒），
再少就是一闪而过。`retime.py` 与 `check_anim.py` 都会把低于 200 ms 的拍标出来。

《减肥破功》的 `dwell` 是：

```
0.95, 0.95, 1.1, 1.3, 1.0, 1.3, 0.95, 1.0, 0.9, 0.95, 0.95
```

够手机（K3→K4）和抱炸鸡桶（K5→K6）各 1.3，这两拍动作跨度最大，多停一点才看得清；
只动肩头和嘴角的拍压到 0.9。

### 想更慢，先降 fps 再加停顿

帧数不动、只降 fps，插值步长不变，只是整体播放变慢——这是最省事的一档。
再想「某几拍多停」，才去调 `dwell`。两条都只动导出，不重跑采样。

**不要**靠加帧数来解决「太快」：加帧只会让过渡更细，不会让每一拍停留更久。

