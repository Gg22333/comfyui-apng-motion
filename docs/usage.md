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

| 拍数 | 段数分配 | 节点数（xl） |
| --- | --- | --- |
| 3 | 8/8/8 | 61 |
| 4 | 6/7/6/5 | 63 |
| 5 | 5/6/5/4/4 | 65 |

命令行直接给参数（不写 JSON）：

```bash
python scripts/emit_workflow.py --base assets/workflow-sdxl.json \
  --beats 4 --segs 6,7,6,5 \
  --lock "masterpiece, 1girl, silver hair" --style "anime" \
  --actions "neutral|notice|react|settle" --out my.json
```

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

