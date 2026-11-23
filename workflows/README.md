# workflows · 可直接导入的 ComfyUI 工作流

这里是**成品工作流**，拖进 ComfyUI 就能跑，不是截图，也不是片段。
网页上的下载地址：<https://gg22333.github.io/comfyui-apng-motion/workflows/>（构建时由 `scripts/sync_workflows.py` 从本目录同步）。

## 清单

| 文件 | 环境 | 拍数 | 节点数 | 加载方式 |
| --- | --- | --- | --- | --- |
| `workflow-sdxl.json` | SDXL | 3 | 67 | `CheckpointLoaderSimple` |
| `workflow-sdxl-4beat.json` | SDXL | 4 | 70 | 同上 |
| `workflow-moss.json` | Moss / DiT | 3 | 70 | `UNETLoader` + `CLIPLoader` + `VAELoader` |
| `workflow-moss-4beat.json` | Moss / DiT | 4 | 73 | 同上 |
| `workflow-sdxl-preview.json` | SDXL | 4 | 70 | 生成仓库预览图；同 seed、denoise 0.35 |

全部是同一套骨架：

```
K 个关键帧（KSampler，共用首帧 latent、同 seed）
  → N × LatentInterpolate（N = 总帧数）
  → N × VAEDecode
  → ImageBatchMulti(N)
  → SaveAnimatedPNG + SaveAnimatedWEBP + VHS_VideoCombine(GIF)
```

N 默认 24，`emit_workflow.py --frames N --segs ...` 会自动扩缩插值/解码/batch 节点。
4 拍版本只是多一组 `CLIPTextEncode` + `KSampler` + `ConditioningCombine`。

## 画布上有哪些旋钮

每个文件都带三层：

1. **`CLIPTextEncode`「全局动作指导（所有关键帧共享）」**
   改一处，所有关键帧生效。写镜头、光照、构图、全片动作约束。留空 = 旁路，不稀释单帧提示。
2. **`CLIPTextEncode`「K0 首帧提示」/「K1 提示」/ …**
   每一拍独立可改。这是讲故事的地方。
3. **`Note`「可调参数清单」+ `Note`「提示词写法（SDXL / MOSS 两套）」**
   直接把可调项、两套提示词写法、帧数表写在画布上，不用翻文档。

采样参数（seed / steps / cfg / denoise / sampler / scheduler）在每个 `KSampler` 上，逐拍可改。

## 导入步骤

1. 打开对应环境的 ComfyUI。
2. 把 JSON 拖进画布，或用左侧工作流面板打开。
3. **改 loader 里的模型名**为你本机实际文件：
   - SDXL：`CheckpointLoaderSimple`
   - Moss / DiT：`UNETLoader` + `CLIPLoader` + `VAELoader`
4. 确认三个保存节点的 `filename_prefix` 是 `APNG/final/{apng,webp,gif}/...`。
5. **F5 刷新页面**，再 Queue —— 否则前端可能还持着旧 prefix。
6. 成品落在 ComfyUI 自己的 `output/APNG/final/` 下。

## 环境要求

| | SDXL | Moss / DiT |
| --- | --- | --- |
| 显存 | 6 GB 起 | 8 GB 起（512/640 实测可用） |
| 步数 | 20–30 | 8（DMD 蒸馏） |
| CFG | 5–7 | 1.0 |
| 关键帧 denoise | 0.35–0.45 | 0.50–0.80 |
| 文本编码器 | CLIP（逗号标签） | Qwen-VL（中文散文） |
| 自定义节点 | VHS、KJNodes | 同左 |

Moss 是 8 步蒸馏模型，**不要**把 steps 提到 20、cfg 提到 6 —— 只会更糊。
SDXL 是常规扩散，反而需要 20 步以上和 5 以上的 cfg。

## 帧数怎么选

| 帧数 | fps | 时长 | 用途 |
| --- | --- | --- | --- |
| 8 | 8 | 1.00 s | 单表情，体积最小 |
| 24 | 10 | 2.40 s | 默认，聊天表情包 |
| 30 | 15 | 2.00 s | 短动作 |
| 60 | 30 | 2.00 s | 完整小故事，最顺 |

不改节点也能改：`python scripts/emit_workflow.py --base workflows/workflow-moss.json --story assets/story.diet.json --frames 60 --segs 10,12,4,12,10,12 --out my60.json`

## 提示词写法

两套编码器的手感完全不同，别混。

**SDXL / 传统 CLIP（tags）**

```
1girl, solo, full body, black short hair, blue eyes, beige hoodie,
dark shorts, barefoot, bedroom at night, warm lamp light,
〈这一拍动作〉,
anime screencap, clean lineart, flat cel shading
```

- 英文逗号分隔，重要标签往前放。
- 画风放最后：CLIP 对末尾 token 权重最高，写在中段会被动作词冲掉。
- 写画面不写效果：`eyes wide, pupils small` 而不是 `shocked`。
- 负向单独一个 `CLIPTextEncode`。

**MOSS / Qwen-VL（moss_zh）**

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
- 负向同样用中文。

## 不要做的事

- 不要把工作流留在 ComfyUI 的 `user/default/workflows` 里当备份 —— 会和仓库版本混淆。
- 工作流里不放单帧保存节点；只接三个成品输出。
- 不要改 `ImageBatchMulti` 的计数却不改接线，`emit_workflow.py --validate` 会报。
