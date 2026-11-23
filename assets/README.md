# assets 说明

这里放的是**可直接导入 ComfyUI 的完整工作流**，不是截图也不是片段。

## 工作流清单

| 文件 | 环境 | 拍数 | 节点数 | 模型 |
| --- | --- | --- | --- | --- |
| `workflow-sdxl.json` | SDXL | 3 | 66 | `CheckpointLoaderSimple` |
| `workflow-sdxl-4beat.json` | SDXL | 4 | 69 | 同上 |
| `workflow-moss.json` | Moss / DiT | 3 | 68 | `UNETLoader` + `CLIPLoader` + `VAELoader` |
| `workflow-moss-4beat.json` | Moss / DiT | 4 | 71 | 同上 |
| `workflow-sdxl-preview.json` | SDXL | 4 | 69 | 生成仓库预览图；同 seed、denoise 0.35 |

四份都是同一套结构：`K 关键帧 → N × LatentInterpolate → N × VAEDecode → ImageBatchMulti(N) → 三输出`。
N 默认 24，用 `--frames 8..60` 改；`emit_workflow.py` 会自动扩缩插值/解码/batch 节点。
4 拍版本只是多了一组 `CLIPTextEncode` + `KSampler` + `ConditioningCombine`，24 帧按 6/7/6/5 分配。

每个文件都带一层的全局动作控制：

- `CLIPTextEncode`「全局动作指导（所有关键帧共享）」—— 改一处，所有关键帧生效；
- 每个关键帧一个 `ConditioningCombine`，把全局动作和该帧提示合并；
- 一个 `Note` 节点，把可调参数写在画布上。

所以节点数比只有插值结构的版本多 `拍数 + 2`。

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
| `story.preview.json` | 仓库 60 帧预览：4 拍 / 30fps / Moss / denoise 0.5 |
| `motion-presets.json` | 16 组动作节拍库（情绪 / 动作 / 五拍故事） |

剧情卡字段：

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `name` | 是 | 输出文件名前缀，如 `anim24` |
| `beats` | 是 | 关键帧数 3–5；`actions` 条数必须相等 |
| `frames` | 否 | 总帧数，默认 24；8–60 |
| `segs` | 否 | 每段帧数，长度 = beats，和 = frames；缺省按拍平均分 |
| `fps` | 否 | 默认 10；三个保存节点会用同一个值 |
| `denoise` | 否 | 关键帧重绘强度；SDXL 0.35–0.45，Moss 0.50–0.70 |
| `seed_mode` | 否 | `same`（默认）或 `different` |
| `lock` | 是 | 角色/构图不变量 |
| `style` | 否 | 画风词，编译时放末尾 |
| `negative` | 否 | 负向提示 |
| `actions` | 是 | 每拍一句，`actions[0]` 必须是静息姿势 |
| `motion` | 否 | 全局动作/镜头约束；留空则旁路合并层 |
| `curve` | 否 | `linear`（默认）/ `ease` / `snap` |
| `prefix` | 否 | 输出前缀，默认 `APNG/final` |

从动作库生成剧情卡：

```bash
python scripts/make_story.py --list
python scripts/make_story.py --preset laugh --lock "masterpiece, 1girl, silver hair" --out assets/story.laugh.json
python scripts/make_story.py --preset rainy-walk --lock "masterpiece, 1girl" --frames 60 --fps 30 --out assets/story.rain.json
```

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
