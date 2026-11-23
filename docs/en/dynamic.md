# Dynamic frame mode (control from the graph)

This page answers one question: **frame count, duration, frame-to-frame difference, seams and storyboard must be adjustable and visible inside ComfyUI, not only after export via a skill script.**

The static graph expands "N frames" into N `LatentInterpolate` + N `VAEDecode` nodes, so changing N means re-running `emit_workflow.py`.
Dynamic mode collapses that layer into **one interpolate node per beat, with the frame count as a widget on the canvas**.

## 1. Install the nodes

The nodes ship in `comfyui_nodes/`.

```bash
python scripts/install_nodes.py --profile xl      # reads comfy_root from profiles/xl.json
python scripts/install_nodes.py --all             # every machine in profiles/
python scripts/install_nodes.py --check           # compare only, write nothing
```

The target is always `<comfy_root>/custom_nodes/apng_motion_nodes/`. You can also copy the whole
`comfyui_nodes` folder there and rename it to `apng_motion_nodes`. **Restart ComfyUI**; the four nodes
appear under `APNG Motion`.

## 2. Emit a dynamic graph

```bash
python scripts/emit_workflow.py \
    --base workflows/workflow-sdxl.json \
    --story assets/story.example.json \
    --dynamic \
    --out my-dynamic.json
```

Add a whole-sequence camera move (pan / zoom / rotate; neutral by default, adjust on the canvas):

```bash
python scripts/emit_workflow.py \
    --base workflows/workflow-sdxl.json \
    --story assets/story.example.json \
    --dynamic --camera \
    --out my-dynamic-camera.json
```

3 beats at 24 frames produces **26 nodes / 39 links**, or 27 with `--camera` (the equivalent static graph is 67 nodes). The
keyframe chain is untouched; only the interpolate/decode/batch layer is replaced.

```
K keyframe KSamplers (same seed, first-frame latent)
  -> one APNGLatentInterpolateN per beat (frames = that beat's count)
  -> N-1 APNGLatentConcat (concatenate batches in beat order)
  -> one VAEDecode (decode all frames at once)
  -> [optional] one APNG Camera Move (--camera: whole-sequence pan / zoom / rotate)
  -> SaveAnimatedPNG + SaveAnimatedWEBP + VHS_VideoCombine
  -> APNGFrameStats (prints frames / duration / frame diff / seams)
```

## 3. Where each dimension is controlled

| Dimension | Where in the graph | How |
| --- | --- | --- |
| **Frame count** | `frames` widget on each `APNG Latent Interpolate N` | Change the number. Total = sum of all beats, 1–240 |
| **Duration** | `fps` on the three save nodes and on `APNGFrameStats` | Duration = total frames / fps; the stats node prints `duration=2.40s` |
| **Frame-to-frame diff** | `APNGFrameStats` output | Prints `diff min/max/avg` and `identical_pairs`; identical frames trigger an APNG merge warning |
| **Seam uniqueness** | `segs` widget on `APNGFrameStats` | Comma list of per-beat frames (e.g. `8,8,8`); prints per-beat `full/lower` OK/FAIL plus loop `K_N->K0` |
| **Storyboard** | the K `KSampler` + `CLIPTextEncode` pairs | One keyframe is one beat, same as static mode; adding a beat still means copying one pair |
| **Camera motion** | `x` / `y` / `zoom` / `angle` / `easing` / `loop` on `APNG Camera Move` | One transform for the whole sequence; orthogonal to the storyboard (see next section) |

`APNGFrameStats` uses the same thresholds as `scripts/check_anim.py`: within a beat `full >= 2.0 && lower >= 1.0`,
loop seam `0.3 <= full <= 6.0`.

## 4. Camera motion (whole-sequence pan / zoom / rotate)

`--camera` inserts one `APNG Camera Move` after `VAEDecode`: **a single camera path applied to every
frame**. It is a pure pixel affine transform — no re-sampling, no new dependency, no sampler call.
Defaults are neutral; adjust on the canvas after emitting.

| Widget | Meaning | Range / values |
| --- | --- | --- |
| `x` | Total horizontal travel in pixels; positive moves right | -2048…2048 |
| `y` | Total vertical travel in pixels; positive moves down | -2048…2048 |
| `zoom` | **Last-frame** scale; `>1` pushes in, `<1` pulls out | 0.5…4.0 |
| `angle` | Total rotation in degrees; positive is counter-clockwise | -360…360 |
| `easing` | `linear` `sine` `cubic` `quint` `back` `elastic` `bounce` | default `sine` |
| `loop` | `True` runs 0→1→0, so first and last frame match exactly | default `True` |
| `border` | Out-of-range sampling: `reflection` / `border` / `zeros` | default `reflection` |

Semantics:

- **Parameters are totals for the whole clip, not per-frame increments.** Frame i advances by
  `p = ease(i / (N-1))`; translation, scale and rotation all follow `p`. `x=20` means "drift 20 px to
  the right over the entire clip".
- `loop=True` uses `p = ease((1 - cos(2πt)) / 2)`, so both ends return to 0 and the loop does not jump.
  `loop=False` is a single one-way move.
- `zoom` is the **last-frame** scale (peak scale when `loop=True`). "Push in then come back" is
  `loop=True` with `zoom=1.2`.
- `loop=True` with only N=2 frames returns to the origin on both frames, i.e. no motion; use
  `loop=False` or add frames.
- Camera and storyboard are different layers: the **storyboard** changes keyframe content (K
  KSamplers with their own prompts); the **camera** transforms already-decoded pixels. They compose.
- Finished output only: with `--camera`, the three savers and `APNGFrameStats` all read the camera
  node, so the diff / seam verdicts describe the final pixels.

> The whole-sequence camera + easing idea was inspired by
> [ShmuelRonen/ComfyUI-AstralAnimator](https://github.com/ShmuelRonen/ComfyUI-AstralAnimator).
> That project has no license file and **no code was reused**; this node is an independent
> `torch.nn.functional.affine_grid` + `grid_sample` implementation.

## 5. Node reference

| Node | Inputs | Output | Notes |
| --- | --- | --- | --- |
| `APNG Latent Interpolate N` | `samples1`, `samples2`, `frames`, `role`, `curve` | `LATENT` (batch=frames) | Same math as native `LatentInterpolate`; `role` follows beat order first/middle/last |
| `APNG Latent Concat` | `samples1`, `samples2` | `LATENT` | Concatenates on the batch dimension only |
| `APNG Frame Stats` | `images`, `fps`, `segs` | `STRING` + UI text | `OUTPUT_NODE`; runs even with no downstream link |

`segs` must match the sum of all `frames` widgets or `--validate` fails:

```
frame report segs sum 24 != sum of per-beat frames 20
```

## 6. Changing frame count end to end

From 3 beats / 24 frames (`8,8,8`) to 12 frames:

1. Set `frames` to `4` on all three interpolate nodes.
2. Set `segs` on `APNGFrameStats` to `4,4,4`.
3. Leave `fps` at 10 on the save nodes; duration becomes 1.20s.
4. Queue. The stats node prints `frames=12`, `duration=1.20s`, frame diff and seam verdicts.

If you change `frames` but not `segs`, `--validate` rejects the graph. Running it directly in ComfyUI
still prints the real frame count, but the seam checks are skipped because `segs` no longer sums to it.

## 7. Boundaries

- **Per-frame dwell and per-beat ease stay outside the graph.** ComfyUI save nodes accept one global
  `fps`, so per-frame delays cannot be expressed. Use `scripts/retime.py` after export; it only rewrites
  APNG `fcTL` delays and leaves pixels untouched.
- **Dynamic mode does not need KJNodes `ImageBatchMulti`**, static mode still does.
- `APNGLatentInterpolateN` requires batch=1 per keyframe latent; keyframe KSamplers already produce 1.
- The nodes are plain tensor ops; CPU or GPU both work. Peak VRAM scales with the total decoded frames,
  so 60 frames costs more than 24.

## 8. Troubleshooting

| Symptom | Cause | Fix |
| --- | --- | --- |
| No APNG Motion category | Not installed or ComfyUI not restarted | Run `install_nodes.py --check`, then restart |
| `--validate` says bad role | Hand-edited to another string | Only `first` / `middle` / `last` |
| Frame count did not change | Only one interpolate node edited | Every beat has its own `frames` widget |
| No seam report | `segs` sum != actual frames | Update `segs` to the new comma list |
| Output has fewer frames | Identical adjacent pixels, APNG merged them | Check `identical_pairs`, adjust ratio or curve |
| Camera moves the wrong way | Treated a total as a per-frame step | `x`/`y` are totals; +x right, +y down |
| Loop jumps at the seam | `loop=False` | Turn on `loop=True`; first and last frames match |
| Black edges appear | `border=zeros` | Use `reflection` or `border` |
