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
`comfyui_nodes` folder there and rename it to `apng_motion_nodes`. **Restart ComfyUI**; the three nodes
appear under `APNG Motion`.

## 2. Emit a dynamic graph

```bash
python scripts/emit_workflow.py \
    --base workflows/workflow-sdxl.json \
    --story assets/story.example.json \
    --dynamic \
    --out my-dynamic.json
```

3 beats at 24 frames produces **26 nodes / 39 links** (the equivalent static graph is 67 nodes). The
keyframe chain is untouched; only the interpolate/decode/batch layer is replaced.

```
K keyframe KSamplers (same seed, first-frame latent)
  -> one APNGLatentInterpolateN per beat (frames = that beat's count)
  -> N-1 APNGLatentConcat (concatenate batches in beat order)
  -> one VAEDecode (decode all frames at once)
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

`APNGFrameStats` uses the same thresholds as `scripts/check_anim.py`: within a beat `full >= 2.0 && lower >= 1.0`,
loop seam `0.3 <= full <= 6.0`.

## 4. Node reference

| Node | Inputs | Output | Notes |
| --- | --- | --- | --- |
| `APNG Latent Interpolate N` | `samples1`, `samples2`, `frames`, `role`, `curve` | `LATENT` (batch=frames) | Same math as native `LatentInterpolate`; `role` follows beat order first/middle/last |
| `APNG Latent Concat` | `samples1`, `samples2` | `LATENT` | Concatenates on the batch dimension only |
| `APNG Frame Stats` | `images`, `fps`, `segs` | `STRING` + UI text | `OUTPUT_NODE`; runs even with no downstream link |

`segs` must match the sum of all `frames` widgets or `--validate` fails:

```
frame report segs sum 24 != sum of per-beat frames 20
```

## 5. Changing frame count end to end

From 3 beats / 24 frames (`8,8,8`) to 12 frames:

1. Set `frames` to `4` on all three interpolate nodes.
2. Set `segs` on `APNGFrameStats` to `4,4,4`.
3. Leave `fps` at 10 on the save nodes; duration becomes 1.20s.
4. Queue. The stats node prints `frames=12`, `duration=1.20s`, frame diff and seam verdicts.

If you change `frames` but not `segs`, `--validate` rejects the graph. Running it directly in ComfyUI
still prints the real frame count, but the seam checks are skipped because `segs` no longer sums to it.

## 6. Boundaries

- **Per-frame dwell and per-beat ease stay outside the graph.** ComfyUI save nodes accept one global
  `fps`, so per-frame delays cannot be expressed. Use `scripts/retime.py` after export; it only rewrites
  APNG `fcTL` delays and leaves pixels untouched.
- **Dynamic mode does not need KJNodes `ImageBatchMulti`**, static mode still does.
- `APNGLatentInterpolateN` requires batch=1 per keyframe latent; keyframe KSamplers already produce 1.
- The nodes are plain tensor ops; CPU or GPU both work. Peak VRAM scales with the total decoded frames,
  so 60 frames costs more than 24.

## 7. Troubleshooting

| Symptom | Cause | Fix |
| --- | --- | --- |
| No APNG Motion category | Not installed or ComfyUI not restarted | Run `install_nodes.py --check`, then restart |
| `--validate` says bad role | Hand-edited to another string | Only `first` / `middle` / `last` |
| Frame count did not change | Only one interpolate node edited | Every beat has its own `frames` widget |
| No seam report | `segs` sum != actual frames | Update `segs` to the new comma list |
| Output has fewer frames | Identical adjacent pixels, APNG merged them | Check `identical_pairs`, adjust ratio or curve |
