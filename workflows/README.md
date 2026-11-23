# workflows · 可直接导入的 ComfyUI 工作流

这里是**成品工作流**，拖进 ComfyUI 就能跑，不是截图，也不是片段。
网页上的下载地址：<https://gg22333.github.io/comfyui-apng-motion/workflows/>（构建时由 `scripts/sync_workflows.py` 从本目录同步）。

## 清单

| 文件 | 架构 / 模型 | 拍数 | 帧数 | 节点数 | 加载方式 |
| --- | --- | --- | --- | --- | --- |
| `workflow-sdxl.json` | UNet（SDXL） | 3 | 24 | 67 | `CheckpointLoaderSimple` |
| `workflow-sdxl-4beat.json` | UNet（SDXL） | 4 | 24 | 70 | 同上 |
| `workflow-moss.json` | DiT（MOSS-Image） | 3 | 24 | 69 | `UNETLoader` + `CLIPLoader` + `VAELoader` |
| `workflow-moss-4beat.json` | DiT（MOSS-Image） | 4 | 24 | 72 | 同上 |
| `workflow-sdxl-preview.json` | UNet（SDXL） | 4 | 60 | 142 | SDXL 预览样例：同 seed、`denoise 0.5`、30fps |
| `workflow-moss-preview.json` | DiT（MOSS-Image） | 11 | 60 | 157 | 生成仓库那张预览图：同 seed、`denoise 0.85`、20fps |

`workflow-moss-preview.json` 就是 `assets/story.diet.json`（60 帧 / 11 拍 / 20fps / 3.00 秒）对应的图，
网页首页那张 `preview.webp` / `preview.gif` 由它出片后用 `scripts/make_preview.py` 缩到 384 生成。

全部是同一套骨架：

```
K 个关键帧（KSampler，共用首帧 latent、同 seed）
  → N × LatentInterpolate（N = 总帧数）
  → N × VAEDecode
  → ImageBatchMulti(N)
  → SaveAnimatedPNG + SaveAnimatedWEBP + VHS_VideoCombine(GIF)
```

N 默认 24，8 / 24 / 30 / 60 都能用：`emit_workflow.py --frames N --segs ...` 会自动扩缩插值 / 解码 / batch 节点。
4 拍版本只是多一组 `CLIPTextEncode` + `KSampler` + `ConditioningCombine`。

## 画布上有哪些旋钮

每个文件都带三层：

1. **`CLIPTextEncode`「全局动作指导（所有关键帧共享）」**
   改一处，所有关键帧生效。写镜头、光照、构图、全片动作约束。留空 = 旁路，不稀释单帧提示。
2. **`CLIPTextEncode`「K0 首帧提示」/「K1 提示」/ …**
   每一拍独立可改。这是讲故事的地方。
3. **`Note`「可调参数清单」+ `Note`「提示词写法（按架构分方言）」**
   直接把可调项、三种方言、帧数与 fps 表写在画布上，不用翻文档。

采样参数（seed / steps / cfg / denoise / sampler / scheduler）在每个 `KSampler` 上，逐拍可改。

## 导入步骤

1. 打开对应环境的 ComfyUI。
2. 把 JSON 拖进画布，或用左侧工作流面板打开。
3. **改 loader 里的模型名**为你本机实际文件：
   - UNet 系：`CheckpointLoaderSimple`（SD1.5 / SDXL）
   - DiT 系：`UNETLoader` + `CLIPLoader` + `VAELoader`（MOSS-Image；换 FLUX / SD3 / Krea / Anima 只换这三个加载器）
4. 确认三个保存节点的 `filename_prefix` 是 `APNG/final/{apng,webp,gif}/...`。
5. **F5 刷新页面**，再 Queue —— 否则前端可能还持着旧 prefix。
6. 成品落在 ComfyUI 自己的 `output/APNG/final/` 下。

## 环境要求

| | UNet 系（SDXL） | DiT 系（MOSS-Image） |
| --- | --- | --- |
| 显存 | 6 GB 起 | 8 GB 起（512/640 实测可用） |
| 步数 | 20–30 | 8（DMD 蒸馏） |
| CFG | 5–7 | 1.0 |
| 关键帧 denoise | 0.35–0.45 | 0.82–0.90 |
| 文本编码器 | CLIP（逗号标签） | Qwen-VL（中文散文） |
| 自定义节点 | VHS、KJNodes | 同左 |

**DiT 是架构，MOSS-Image 只是其中一个模型。** 写「Moss / DiT」并列等于把架构当成模型之外的类别。
Flux、SD3、Krea、Anima 同样跑在 DiT 上，逐模型参数与出处见 [`docs/models.md`](../docs/models.md)。

MOSS 是 8 步蒸馏模型，**不要**把 steps 提到 20、cfg 提到 6 —— 只会更糊。
SDXL 是常规扩散，反而需要 20 步以上和 5 以上的 cfg。

## 帧数怎么选

| 帧数 | 慢（叙事） | 标准 | 快（弹幕感） |
| --- | --- | --- | --- |
| 8 | 6 fps / 1.33 s | 8 fps / 1.00 s | 10 fps / 0.80 s |
| 24 | 8 fps / 3.00 s | 10 fps / 2.40 s | 12 fps / 2.00 s |
| 30 | 10 fps / 3.00 s | 15 fps / 2.00 s | 20 fps / 1.50 s |
| 60 | **20 fps / 3.00 s（默认）** | 25 fps / 2.40 s | 30 fps / 2.00 s |

GIF 的帧延时只能量化到 10 ms（1 厘秒）：24fps 会被写成 40 ms（整片 2.4 s 不是 2.5 s），30fps 变成 1.8 s。
20 / 25 fps 整除，不会走样；APNG / WebP 是毫秒精度，不受限。
逐拍停留用剧情卡的 `dwell` / `ease`，出片后跑 `scripts/retime.py` 写入，像素不动、不重跑采样。

不改节点也能改：`python scripts/emit_workflow.py --base workflows/workflow-moss.json --story assets/story.diet.json --frames 60 --segs 10,12,4,12,10,12 --out my60.json`

## 提示词写法

三种方言按**文本编码器**分，不是按模型名分：

| 文本编码器 | 模型例子 | 写法 |
| --- | --- | --- |
| CLIP | SD1.5 / SDXL | 英文逗号标签，重要标签往前，画风放最后 |
| Qwen-VL | MOSS-Image / Krea 2 / Qwen-Image | 中文散文，换行分段，每段「。」结尾，不堆 quality tag |
| T5 | FLUX.1 / SD3 | 英文自然语言句子，少堆标签 |

完整规则、逐拍三段式、Layout 的 bbox 与 16 倍数约束见
[`docs/prompting.md`](../docs/prompting.md) · [`docs/en/prompting.md`](../docs/en/prompting.md)。

## 不要做的事

- 不要把工作流留在 ComfyUI 的 `user/default/workflows` 里当备份 —— 会和仓库版本混淆。
- 工作流里不放单帧保存节点；只接三个成品输出。
- 不要改 `ImageBatchMulti` 的计数却不改接线，`emit_workflow.py --validate` 会报。
