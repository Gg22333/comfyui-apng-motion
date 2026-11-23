# assets · 剧情卡、动作库、节点定义

工作流本身在 [`workflows/`](../workflows/)。这里只放**喂给脚本的数据**。

## 剧情卡

| 文件 | 用途 |
| --- | --- |
| `story.example.json` | 3 拍模板（中性 → 笑 → 大笑），英文 tags 模式 |
| `story.4beat.json` | 4 拍模板（常态 → 察觉 → 反应 → 收） |
| `story.preview.json` | 仓库 60 帧预览：4 拍 / 30fps / Moss / denoise 0.5 |
| `story.diet.json` | 六拍全身小故事《减肥破功》：60 帧 / 30fps / `moss_zh` 中文散文 |

字段：

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `name` | 是 | 输出文件名前缀，如 `anim24` |
| `beats` | 是 | 关键帧数 3–8；`actions` 条数必须相等 |
| `frames` | 否 | 总帧数，默认 24；8–60 |
| `segs` | 否 | 每段帧数，长度 = beats，和 = frames；缺省按拍平均分 |
| `fps` | 否 | 默认 10；三个保存节点用同一个值 |
| `width` / `height` | 否 | 覆盖 latent 尺寸；Moss 512 或 640 |
| `denoise` | 否 | 关键帧重绘强度；SDXL 0.35–0.45，Moss 0.50–0.80 |
| `steps` / `cfg` | 否 | 覆盖每个 KSampler；Moss 用 8 / 1.0 |
| `seed` | 否 | 所有关键帧共用 |
| `seed_mode` | 否 | `same`（默认）或 `offset` |
| `prompt_mode` | 否 | `tags`（默认）或 `moss_zh` |
| `lock` | 是 | 角色/场景/构图不变量 |
| `style` | 否 | 画风词；tags 模式放最后，moss_zh 模式作收口句 |
| `negative` | 否 | 负向提示；moss_zh 模式写中文 |
| `actions` | 是 | 每拍一句；`actions[0]` 是静息姿势，循环要回到它 |
| `motion` | 否 | 全片动作/镜头约束；留空则旁路合并层 |
| `curve` | 否 | `linear`（默认）/ `ease` / `snap` |
| `prefix` | 否 | 输出前缀，默认 `APNG/final` |

`assets/story.diet.json` 是 `moss_zh` 的完整范例：中文场景 → 人物 → 六拍动作 → 画风，负向也是中文。

## 动作库

`motion-presets.json`：17 组动作节拍。英文 tags 组（挥手、大笑、哭、震惊……）和 `moss_zh` 组（`diet-betrayal` 减肥破功）。

```bash
python scripts/make_story.py --list
python scripts/make_story.py --preset laugh --lock "masterpiece, 1girl, silver hair" --out assets/story.laugh.json
python scripts/make_story.py --preset diet-betrayal --out assets/story.diet.json   # 自带中文 lock/style
```

`prompt_mode=tags` 的预设用英文逗号标签；`prompt_mode=moss_zh` 的预设自带完整中文段落，不要往里混英文标签。

## 节点定义

| 文件 | 用途 |
| --- | --- |
| `node_schema.json` | 节点定义兜底。VHS 等节点的 `/object_info` 整包过大时服务器会断连，`emit_workflow.py` 回落到这份随包定义 |
