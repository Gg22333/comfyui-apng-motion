# Workflows

This page only covers **dropping a JSON into ComfyUI**. For story cards see [usage](usage.md), for per-beat tuning see [motion library](motion-presets.md).

The source files live in [`workflows/`](https://github.com/Gg22333/comfyui-apng-motion/tree/main/workflows).
The download links below are mirrored into `docs/assets/workflows/` by `scripts/sync_workflows.py` at build time.

## Download

| Environment | 3 beats | 4 beats | Notes |
| --- | --- | --- | --- |
| SDXL | [workflow-sdxl.json](../assets/workflows/workflow-sdxl.json) | [workflow-sdxl-4beat.json](../assets/workflows/workflow-sdxl-4beat.json) | `CheckpointLoaderSimple`, 20–30 steps, cfg 5–7 |
| Moss / DiT | [workflow-moss.json](../assets/workflows/workflow-moss.json) | [workflow-moss-4beat.json](../assets/workflows/workflow-moss-4beat.json) | `UNETLoader` + `CLIPLoader` + `VAELoader`, 8 steps, cfg 1.0 |
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
| `Note` "提示词写法（SDXL / MOSS 两套）" | Two prompt dialects + frame table |

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

```bash
python scripts/check_anim.py output/apng/anim60_00001_.png \
    --segs 5,5,4,7,6,7,5,6,5,5,5 --fps 30
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
   - Moss / DiT: `UNETLoader` + `CLIPLoader` (`type=moss_image`) + `VAELoader`
4. Confirm the three save nodes use `APNG/final/{apng,webp,gif}/...`.
5. **Press F5** before queueing, or the frontend may keep the old prefix.

## Environment differences

| | SDXL | Moss / DiT |
| --- | --- | --- |
| VRAM | from 6 GB | from 8 GB (512 / 640 verified) |
| steps | 20–30 | 8 (DMD distilled, do not raise) |
| cfg | 5–7 | 1.0 |
| keyframe denoise | 0.35–0.45 | 0.82–0.90 (below 0.80 the keyframes barely move) |
| text encoder | CLIP (comma tags) | Qwen-VL (Chinese prose) |
| prompt mode | `tags` | `moss_zh` |

Raising Moss steps to 20 or cfg to 6 only makes it muddier. SDXL is the opposite: below 20 steps or
cfg below 5 it loses detail.

## Prompt dialects

**SDXL (tags)** — comma tags, subject first, style last, describe pixels not feelings:

```
1girl, solo, full body, black short hair, blue eyes, beige hoodie,
〈this beat〉,
anime screencap, clean lineart, flat cel shading
```

**MOSS (moss_zh)** — Chinese prose, one paragraph per idea, every paragraph ends with 「。」,
no quality tags, framing stated explicitly:

```
一间温馨的小卧室，深夜。画面右侧有一盏暖色台灯，光从右前方斜照下来，落在木地板上。
固定机位，平视，全身镜头，人物从头到脚完整入画，双手和双脚都留在画框里。
小满：黑色短发，蓝色眼睛，身材微胖，穿着宽松的米色连帽卫衣和深色短裤，赤脚。
小满盘腿坐在矮桌前，背挺得很直，双手叉在腰上，抬起下巴，嘴角只上扬几毫米。
动漫赛璐璐风格，干净黑色线稿，平涂上色，暖色调，柔和阴影。
```

`assets/story.diet.json` is a complete eleven-beat `moss_zh` example (60 frames / 30 fps);
`python scripts/make_story.py --preset diet-betrayal --out my.json` regenerates it.

## Frame counts

| Frames | fps | Duration | Use |
| --- | --- | --- | --- |
| 8 | 8 | 1.00 s | single expression, smallest file |
| 24 | 10 | 2.40 s | default, chat sticker |
| 30 | 15 | 2.00 s | short action |
| 60 | 30 | 2.00 s | full mini story (eleven beats: `5,5,4,7,6,7,5,6,5,5,5`) |

All three save nodes must share the same fps. `emit_workflow.py --fps` sets all three at once.
