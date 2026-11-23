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
| 3 | 8/8/8 | 66 | 68 |
| 4 | 6/7/6/5 | 69 | 71 |
| 5 | 5/6/5/4/4 | 72 | 74 |

The node count grew with the global-motion layer: one `ConditioningCombine` per keyframe,
plus one shared `CLIPTextEncode` and one `Note`.

Straight from the command line:

```bash
python scripts/emit_workflow.py --base assets/workflow-sdxl.json   --beats 4 --segs 6,7,6,5   --lock "masterpiece, 1girl, silver hair" --style "anime"   --actions "neutral|notice|react|settle" --out my.json
```

`--seed-mode same` (default) pins every keyframe to the same seed. `offset` adds +1 per keyframe and reintroduces flicker.

## Tunable parameters

| Scope | Node | What it controls |
| --- | --- | --- |
| Whole clip | `CLIPTextEncode` "global motion" | action, camera, lighting, style; one edit affects every keyframe |
| Per keyframe | `CLIPTextEncode` "K0 / K1 / ..." | expression, pose, gaze |
| Per keyframe sampling | each `KSampler` | seed, steps, cfg, sampler, scheduler, denoise |
| Pacing | 24 x `LatentInterpolate` ratio | easing curve; `linear` is the most even |
| Speed | three save nodes `fps` | same value in all three (10 fps x 24 = 2.4 s) |
| Naming | `filename_prefix` | `apng/`, `webp/`, `gif/` |
| Quality | APNG `compress_level`, WebP `lossless`/`quality`, VHS `loop`/`pingpong` | size and playback |

From the CLI:

```bash
python scripts/emit_workflow.py --base assets/workflow-sdxl.json --story my-story.json \
  --motion "slow head tilt, stable lighting" \
  --seed 777777 --denoise 0.35 --steps 24 --cfg 5.5 \
  --curve linear --out my.json
```

### Curve choice

| Value | Behaviour | When |
| --- | --- | --- |
| `linear` (default) | constant per-frame step | least visible stepping; best for stickers |
| `ease` | slow-fast-slow | when you want anticipation and follow-through |
| `snap` | nearly frozen then a rush | legacy behaviour, comparison only |

### Switching models

The contract is loader-agnostic:

| Family | Loader nodes | Keyframe denoise |
| --- | --- | --- |
| SD 1.5 | `CheckpointLoaderSimple` | 0.45-0.55 |
| SDXL / Illustrious / NoobAI | `CheckpointLoaderSimple` | 0.35-0.45 |
| FLUX.1 | `UNETLoader` + `DualCLIPLoader` + `VAELoader` | 0.45-0.55 |
| Moss / DiT | `UNETLoader` + `CLIPLoader` (`type=moss_image`) + `VAELoader` | 0.50-0.55 |

Denoise values are field experience. On SDXL, above ~0.42 the keyframe redraw starts changing
clothes and background, and latent interpolation turns that into colour blotches.

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
