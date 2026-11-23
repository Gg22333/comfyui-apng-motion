# assets 说明

这里放的是**可直接导入 ComfyUI 的完整工作流**，不是截图也不是片段。

## 工作流清单

| 文件 | 环境 | 拍数 | 节点数 | 模型 |
| --- | --- | --- | --- | --- |
| `workflow-sdxl.json` | SDXL | 3 | 61 | `CheckpointLoaderSimple` |
| `workflow-sdxl-4beat.json` | SDXL | 4 | 63 | 同上 |
| `workflow-moss.json` | Moss / DiT | 3 | 63 | `UNETLoader` + `CLIPLoader` + `VAELoader` |
| `workflow-moss-4beat.json` | Moss / DiT | 4 | 65 | 同上 |
| `workflow-sdxl-preview.json` | SDXL | 4 | 63 | 用于生成仓库预览图，近景表情四拍 |

四份都是同一套结构：`K 关键帧 → 24 × LatentInterpolate → 24 × VAEDecode → ImageBatchMulti(24) → 三输出`。
4 拍版本只是多了一对 `CLIPTextEncode` + `KSampler`，24 帧按 6/7/6/5 分配。

## 导入步骤

1. 打开对应环境的 ComfyUI。
2. 把 JSON 拖进画布，或用左侧工作流面板打开。
3. **改 loader 里的模型名**为你本机实际文件（`CheckpointLoaderSimple` / `UNETLoader` + `CLIPLoader` + `VAELoader`）。
4. 确认三个保存节点的 `filename_prefix` 是 `APNG/final/{apng,webp,gif}/...`。
5. **F5 刷新页面**，再 Queue —— 否则前端可能还持着旧 prefix。
6. 成品在 `output/APNG/final/` 下。

## 剧情卡

| 文件 | 用途 |
| --- | --- |
| `story.example.json` | 3 拍模板（中性 → 笑 → 大笑） |
| `story.4beat.json` | 4 拍模板（常态 → 察觉 → 反应 → 收） |
| `story.preview.json` | 仓库预览图用：近景、四拍、同 seed、denoise 0.5 |

```bash
python scripts/emit_workflow.py --base assets/workflow-sdxl.json --story assets/story.4beat.json --out my-4beat.json
```

## 其它

| 文件 | 用途 |
| --- | --- |
| `node_schema.json` | 节点定义兜底。某些节点（如 VHS）的 `/object_info` 整包过大，服务器会断连，此时 `emit_workflow.py` 回落到这份随包定义 |

## 注意

- 不要把这些文件留在 ComfyUI 的 `user/default/workflows` 里当"备份"——会和工作流同名混淆。
- 工作流里不含任何单帧保存节点；只接三个成品输出。
- 模型文件名是本机示例，导入后报红先改 loader。
