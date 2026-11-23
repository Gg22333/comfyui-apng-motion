# Workflows

This page only covers **dropping a JSON into ComfyUI**. For story cards see [usage](usage.md), for per-beat tuning see [motion library](motion-presets.md).

The source files live in [`workflows/`](https://github.com/Gg22333/comfyui-apng-motion/tree/main/workflows).
The download links below are mirrored into `docs/assets/workflows/` by `scripts/sync_workflows.py` at build time.

## Download

| Environment | 3 beats | 4 beats | Notes |
| --- | --- | --- | --- |
| UNet family (SDXL) | [workflow-sdxl.json](../assets/workflows/workflow-sdxl.json) | [workflow-sdxl-4beat.json](../assets/workflows/workflow-sdxl-4beat.json) | `CheckpointLoaderSimple`, 20–30 steps, cfg 5–7 |
| DiT family (MOSS-Image) | [workflow-moss.json](../assets/workflows/workflow-moss.json) | [workflow-moss-4beat.json](../assets/workflows/workflow-moss-4beat.json) | `UNETLoader` + `CLIPLoader` + `VAELoader`, 8 steps, cfg 1.0. Swap three loaders for FLUX / SD3 / Krea / Anima |
| Preview | — | [workflow-sdxl-preview.json](../assets/workflows/workflow-sdxl-preview.json) | Builds the repo preview; same seed, denoise 0.35 |

24 frames is the default. For 8 / 30 / 60 frames you do not switch files:

```bash
python scripts/emit_workflow.py --base workflows/workflow-moss.json \
    --story assets/story.diet.json --size 640 --out my-60.json
```

`--frames` rebuilds the interpolate / decode / batch triplet; nothing else is rewired.

## Structure

```
K keyframe KSamplers (shared first latent, shared seed)
  → N × LatentInterpolate
  → N × VAEDecode
  → ImageBatchMulti(N)
  → SaveAnimatedPNG + SaveAnimatedWEBP + VHS_VideoCombine(GIF)
```

N is the frame count. Sampling happens K times (once per keyframe); interpolation and decoding are
plain tensor ops, so doubling frames does not double compute.

## Knobs on the canvas

| Node | What to change |
| --- | --- |
| `CLIPTextEncode` "全局动作指导（所有关键帧共享）" | Camera, lighting, framing, whole-clip motion. One edit applies to K0..Kn. Empty = bypass |
| `CLIPTextEncode` "K0 首帧提示" / "K1 提示" / … | What happens in this beat |
| Every `KSampler` | seed / steps / cfg / denoise / sampler / scheduler, per beat |
| `Note` "可调参数清单" | Cheat sheet written on the canvas |
| `Note` "提示词写法（按架构分方言）" | Three encoder dialects + Layout rules + frame table |

Beat length follows the `LatentInterpolate` distribution: more interpolation nodes in a segment means
a slower beat. `emit_workflow.py --segs` lays this out for you.

## How to lay out transition frames

Sixty frames are not sixty new images. Sampling still runs K times (once per keyframe); the frames in
between are points on the latent line between two keyframes, decoded one by one. So "transition" has two
layers:

1. **Inside a beat** — each frame's ratio moves from the source keyframe toward the target keyframe.
   The segment's frame count is how many steps that move is cut into.
2. **Between beats** — the last frame of a segment lands on the target keyframe; the next segment
   continues from there. A keyframe appears exactly once on the timeline.

### Where the seam stall came from

The old curve ramped every segment from `1.0` to `0.0`:

```
seg0: K0 … K1(0.0)
seg1: K1(1.0) … K2(0.0)   ← K1 again
```

The end of one segment and the start of the next were the same keyframe, i.e. the same image twice.
Measured adjacent-frame difference at those seams was `0.06` — it reads as a freeze. The current layout:

- segment 0 frame 0 is `ratio=1.0` (the K0 cover), and its last frame is `ratio=0.0`, exactly K1;
- every middle segment starts at `1/cnt` and ends at `ratio=0.0`, exactly the next keyframe;
- the last segment interpolates back to K0 but stops one step short, so looping into frame 0 does not
  hold the same image for an extra frame.

### Budget the frames per beat

`segs` holds the frame count of each segment and must sum to `frames`. One rule: **the bigger the pose
change between the two ends of a beat, the more frames it gets.**

| What the beat does | Frames (out of 60) |
| --- | --- |
| shoulders, head or mouth only | 4–5 |
| raise a hand, turn, bow the head | 5–6 |
| reach across the body, lift a large prop | 7–8 |

The eleven-beat *Diet Betrayal* uses `5,5,4,7,6,7,5,6,5,5,5`: reaching for the phone (K3→K4) and
lifting the chicken bucket (K5→K6) get 7 frames each; shoulder/head beats get 4–5; the final beat uses 5
frames to interpolate back to K0.

**To slow the whole film down**, keep the frame count and drop fps on all three save nodes from 30 to 20
(3 s). The in-between count and per-frame step stay the same; only playback speed changes. Once the total
length is set, use the story card's `dwell` to decide which beats hold longer — see
[Pace](#pace-fps-and-per-beat-dwell).

```bash
python scripts/check_anim.py output/apng/anim60_00001_.png \
    --segs 5,5,4,7,6,7,5,6,5,5,5 --fps 20 --story assets/story.diet.json
```

| Reading | Meaning | Fix |
| --- | --- | --- |
| `min < 0.5` | duplicate frame, the seam stalls | check that each segment does not ramp 1.0→0.0; check `segs` vs `beats` |
| `max > 8` | one step is too large, reads as a cut | give that beat 1–2 more frames before touching denoise |
| `drift > 20` | colour drifts across the film | check lighting words per keyframe and whether denoise is too high |

## Import


1. Open the matching ComfyUI instance.
2. Drag the JSON onto the canvas.
3. Point the loader at your local models:
   - SDXL: `CheckpointLoaderSimple`
   - DiT family: `UNETLoader` + `CLIPLoader` (use `type=moss_image` for MOSS-Image) + `VAELoader`
4. Confirm the three save nodes use `APNG/final/{apng,webp,gif}/...`.
5. **Press F5** before queueing, or the frontend may keep the old prefix.

## Environment differences

| | UNet family (SDXL) | DiT family (MOSS-Image) |
| --- | --- | --- |
| VRAM | from 6 GB | from 8 GB (512 / 640 verified) |
| steps | 20–30 | 8 (DMD distilled, do not raise) |
| cfg | 5–7 | 1.0 |
| keyframe denoise | 0.35–0.45 | 0.82–0.90 (below 0.80 the keyframes barely move) |
| text encoder | CLIP (comma tags) | Qwen3.5-9B (Chinese prose) |
| prompt mode | `tags` | `moss_zh` |

Raising MOSS-Image steps to 20 or cfg to 6 only makes it muddier. SDXL is the opposite: below 20 steps
or cfg below 5 it loses detail.

**MOSS-Image is one DiT model; SDXL is not DiT at all.** Writing "Moss / DiT" side by side is a
categorisation error: DiT is the architecture (arXiv:2212.09748, U-Net backbone replaced by a
transformer), MOSS is a specific model. Swap in FLUX / SD3 / Krea / Anima and the denoise range is the
DiT one (0.45–0.55), not 0.85. Per-model detail: [Models](models.md).

## Prompt dialects

The dialect follows the **text encoder**, not the model name. Three dialects cover every model in the
table; full rules in [Prompting](prompting.md).

| Encoder | Models | Mode | One-line rule |
| --- | --- | --- | --- |
| CLIP | SD 1.5, SDXL, Illustrious, NoobAI | `tags` | comma tags, style last |
| Qwen-VL family | MOSS-Image, Krea 2, Qwen-Image, Anima | `moss_zh` | paragraphs, one full stop each |
| T5 | FLUX.1, SD3 / SD3.5 | prose | full sentences, no `(word:1.3)` |

```text
CLIP    : 1girl, solo, full body, … , <this beat>, anime screencap, clean lineart
Qwen-VL : 一间温馨的小卧室，深夜。 / 固定机位，平视，全身镜头…… / 小满：黑色短发……
T5      : A young woman with short black hair sits upright behind a low wooden table …
```

Three hard rules:

1. **Change exactly one variable per beat.** Change two and the interpolation gives you two people.
2. **Describe pixels, not feelings.** `shocked` becomes `eyes wide, pupils small, mouth open`.
3. **Nail the framing.** `fixed camera, eye level, full-body, head to toe inside the frame`, or the
   model crops to half body on its own.

When text must appear in the frame (sign, poster, speech bubble), use absolute-pixel bboxes on a canvas
whose sides are multiples of 16 — see [Prompting](prompting.md#when-text-must-appear-in-the-frame).

`assets/story.diet.json` is a complete eleven-beat `moss_zh` example (60 frames / 20 fps / 3 s);
`python scripts/make_story.py --preset diet-betrayal --out my.json` regenerates it.

## Pace: fps and per-beat dwell

Pace has three independent layers:

| Layer | Decided by | Effect |
| --- | --- | --- |
| **Total length** | `fps` on the save nodes (story card `fps`) | `frames / fps`. 60 frames @20 fps = 3 s |
| **Per-beat dwell** | story card `dwell` (one weight per beat) | keyframes hold longer, transitions move faster; total unchanged |
| **In-beat easing** | story card `ease` (0–0.8, default 0.3) | first and last frames of a beat get longer delays |

**ComfyUI's save nodes accept one global fps only** — per-frame dwell cannot be expressed there. So:

```bash
# 1) render (all three save nodes share one fps)
python scripts/emit_workflow.py --base workflows/workflow-moss.json \
    --story assets/story.diet.json --size 640 --out diet60.json

# 2) rewrite per-frame delays after export: pixels untouched, no resampling
python scripts/retime.py output/apng/anim60_00001_.png --story assets/story.diet.json

# 3) web preview with the same timing
python scripts/make_preview.py output/apng/anim60_00001_.retimed.png \
    --story assets/story.diet.json --out-dir docs/assets --width 384
```

### Frames x frame rate

| Frames | Slow (narrative) | Standard | Fast (chat) |
| --- | --- | --- | --- |
| 8 | 6 fps / 1.33 s | 8 fps / 1.00 s | 10 fps / 0.80 s |
| 24 | 8 fps / 3.00 s | 10 fps / 2.40 s | 12 fps / 2.00 s |
| 30 | 10 fps / 3.00 s | 15 fps / 2.00 s | 20 fps / 1.50 s |
| 60 | **20 fps / 3.00 s (default)** | 25 fps / 2.40 s | 30 fps / 2.00 s |

**GIF frame delay quantises to 10 ms (1 centisecond)**, so:

| fps | Per frame | Written to GIF | Real 60-frame length |
| --- | --- | --- | --- |
| 8 | 125 ms | 120 ms | 7.2 s (2.9 s at 24 frames) |
| 10 | 100 ms | 100 ms ✓ | 6.0 s (2.4 s at 24 frames) |
| 20 | 50 ms | 50 ms ✓ | 3.00 s |
| 25 | 40 ms | 40 ms ✓ | 2.40 s |
| 24 | 41.7 ms | 40 ms | 2.40 s (not 2.5 s) |
| 30 | 33.3 ms | 30 ms | 1.80 s (not 2.0 s) |

Tick-marked rows divide evenly, so GIF will not silently change speed. APNG and WebP are millisecond
precise and accept any fps.

### At least 0.20 s per beat

Eleven beats over 60 frames at 20 fps averages 0.27 s per beat. A shoulder-only beat can take 4 frames
(0.20 s); less than that is a flicker. `retime.py` and `check_anim.py` both flag beats under 200 ms.

*Diet Betrayal* uses:

```
0.95, 0.95, 1.1, 1.3, 1.0, 1.3, 0.95, 1.0, 0.9, 0.95, 0.95
```

The phone reach (K3→K4) and the chicken bucket (K5→K6) get 1.3 — the two widest moves — while
shoulder-and-mouth beats drop to 0.9.

### To slow down, drop fps first, then add dwell

Same frame count, lower fps: the interpolation step per frame is unchanged, the whole clip just plays
slower. That is the cheapest lever. Then use `dwell` for "these two beats should hold longer". Both are
export-time only; neither resamples.

**Do not** add frames to fix "too fast": more frames make the transition finer, not each beat longer.

