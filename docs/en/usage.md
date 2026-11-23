# Usage

## Story card

One JSON file describes the whole performance; `emit_workflow.py` compiles it into keyframe prompts.

```json
{
  "name": "anim24-4beat",
  "beats": 4,
  "frames": 24,
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

Compile rule: `keyframe_i = lock + actions[i] + style`, fixed order, only the action changes.

`style` last is deliberate: Moss's LLM text encoder weights the tail tokens most, so
`anime screencap, clean lineart, flat cel shading` placed mid-prompt gets buried by the action words
and the render falls back to photographic mode (visible as collage frames and colour blotches).

## Choosing a frame count

Frame count is a parameter, not a second workflow. `--frames` (or `"frames"` in the story card) resizes
`LatentInterpolate` / `VAEDecode` / `ImageBatchMulti` to N.

| Frames | fps | Duration | Best for | 4-beat segs |
| --- | --- | --- | --- | --- |
| 8 | 8 | 1.0 s | avatar twitch, chat reaction | `2,2,2,2` |
| 12 | 12 | 1.0 s | light sticker | `3,3,3,3` |
| 24 | 12 | 2.0 s | default; expression loop | `6,7,6,5` |
| 30 | 15 | 2.0 s | five-beat story, half-body action | `8,8,7,7` |
| 60 | 30 | 2.0 s | smooth web/Discord preview, five-beat story | `15,15,15,15` |

`--segs` must sum to `frames`; omit it and the frames are split evenly across beats (remainder to the
first beats). At 24 frames the classic presets stay: 3 beats 8/8/8, 4 beats 6/7/6/5, 5 beats 5/6/5/4/4.

```bash
python scripts/emit_workflow.py --base assets/workflow-moss.json --story assets/story.preview.json \
  --frames 60 --segs 15,15,15,15 --fps 30 --out my-60f.json
```

## Generate a workflow

```bash
python scripts/emit_workflow.py --base assets/workflow-sdxl.json --story my-story.json --out my.json
```

| Beats | Segment split (24 frames) | Nodes (xl) | Nodes (moss) |
| --- | --- | --- | --- |
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
| Pacing | N x `LatentInterpolate` ratio | easing curve; `linear` is the most even |
| Speed | three save nodes `fps` | same value in all three; `fps x frames` = duration (24 @ 12 fps = 2 s) |
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

Checks: link integrity, interpolation count = decode count = `ImageBatchMulti` links, unique ratios
within one latent pair, three outputs on the same source, keyframes sharing one latent, no `SaveImage`.

## Run

UI: drag the JSON into ComfyUI and press Queue.

Headless:

```bash
python scripts/emit_workflow.py --validate my.json --run --profile profiles/xl.json
```

It submits the API prompt, polls, prints the artifact paths and runs `check_anim.py` automatically.

## Inspect the artifacts

```bash
python scripts/check_anim.py output/APNG/final/apng/anim60_00001_.png --expect 60
```

Watch four values: `frames=N` (matching `--frames`), `loop=0`, `identical_pairs=0`, and `color_drift`.
Moss at denoise 0.5 measures around 18 and still looks fine; SDXL at 0.35 measures about 2.6. Above 20
means the keyframe redraw is changing too much.

## Where files land

See [Output layout](output.md). Short version: `output/APNG/final/{apng,webp,gif}/`, three files per run, plus one VHS first-frame preview PNG in `gif/`.
