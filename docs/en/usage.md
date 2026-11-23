# Usage

## Story card

One JSON file describes the whole performance; `emit_workflow.py` compiles it into keyframe prompts.

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

Compile rule: `keyframe_i = lock + style + actions[i]`, fixed order, only the action changes.

## Generate a workflow

```bash
python scripts/emit_workflow.py --base assets/workflow-sdxl.json --story my-story.json --out my.json
```

| Beats | Segment split | Node count (xl) |
| --- | --- | --- |
| 3 | 8/8/8 | 61 |
| 4 | 6/7/6/5 | 63 |
| 5 | 5/6/5/4/4 | 65 |

Straight from the command line:

```bash
python scripts/emit_workflow.py --base assets/workflow-sdxl.json   --beats 4 --segs 6,7,6,5   --lock "masterpiece, 1girl, silver hair" --style "anime"   --actions "neutral|notice|react|settle" --out my.json
```

`--seed-mode same` (default) pins every keyframe to the same seed. `offset` adds +1 per keyframe and reintroduces flicker.

## Validate

```bash
python scripts/emit_workflow.py --validate my.json
```

Checks: link integrity, 24 interpolations / 24 decodes, unique ratios within one latent pair, three outputs on the same source, keyframes sharing one latent, no `SaveImage`.

## Run

UI: drag the JSON into ComfyUI and press Queue.

Headless:

```bash
python scripts/emit_workflow.py --validate my.json --run --profile profiles/xl.json
```

It submits the API prompt, polls, prints the artifact paths and runs `check_anim.py` automatically.

## Inspect the artifacts

```bash
python scripts/check_anim.py output/APNG/final/apng/anim24_00001_.png --expect 24
```

Watch four values: `frames=24`, `loop=0`, `identical_pairs=0`, `color_drift` no higher than 6.

## Where files land

See [Output layout](output.md). Short version: `output/APNG/final/{apng,webp,gif}/`, three files per run, plus one VHS first-frame preview PNG in `gif/`.
