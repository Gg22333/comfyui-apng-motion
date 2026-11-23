# Architecture

## Data flow

```
EmptyLatentImage(512,512,1)
        │
   KSampler K0   denoise 1.0, seed 123456789
        │  LATENT ─────────────────────────┐
        ├──────────────► CLIPTextEncode K1 ─► KSampler K1  denoise 0.4, same seed
        ├──────────────► CLIPTextEncode K2 ─► KSampler K2  denoise 0.4, same seed
        └──────────────► CLIPTextEncode K3 ─► KSampler K3  denoise 0.4, same seed (4 beats)
                                          │
        24 × LatentInterpolate (one ratio per frame; unique within a latent pair)
                                          │
        24 × VAEDecode ◄── VAE
                                          │
        ImageBatchMulti(inputcount=24)
                ├──► SaveAnimatedPNG   → output/APNG/final/apng/
                ├──► SaveAnimatedWEBP  → output/APNG/final/webp/
                └──► VHS_VideoCombine  → output/APNG/final/gif/
```

Hard constraints:

1. **Every keyframe's `latent_image` points at K0's LATENT**, never chained from the previous keyframe, or colour drifts cumulatively.
2. **Ratios within one latent pair are unique.** Different segments may reuse a value because the pair of images differs; only a collision inside one segment makes Pillow merge frames.
3. **All three outputs read the same batch**, otherwise frame order diverges.

## Scripts

| Script | Input | Output |
| --- | --- | --- |
| `detect_env.py` | ComfyUI installs on disk | `profiles/*.json` |
| `doctor.py` | profile + workflow | PASS/WARN/FAIL report |
| `emit_workflow.py` | base workflow + story card | K-beat workflow JSON (validated) |
| `emit_workflow.py --run` | the above + profile | API submit, polling, artifact paths, auto check |
| `check_anim.py` | artifact file | frames/duration/loop/diff/colour drift |
| `check_output.py` | output tree | stray files, incomplete trios, archive suggestions |
| `make_curve.py` | segment counts | 24 ratios |
| `package.py` | repository tree | deterministic zip + SHA256 |

## Curve

Each segment runs from "hugging the previous keyframe" to "hugging the next":

```
segment 1: 1.0 → 0.05   segment 2: 0.94 → 0.04   segment 3: 0.92 → 0.03   segment 4: 0.90 → 0.01
```

Adjacent segments end and start close together, producing a 1–2 frame pause at each keyframe.
Three-beat cards keep the historical defaults (`1.0/0.92/0.88` → `0.08/0.0/0.01`).

## UI to API

`--run` converts a UI workflow into an API prompt. `comfy_lib.ui_to_api`:

1. fetches required/optional definitions via `/object_info/<type>`;
2. walks `input_order`, wiring link inputs (MODEL/LATENT/...) and reading the rest from `widgets_values`;
3. skips one extra slot for `control_after_generate` (for example KSampler's seed);
4. writes each input as `[origin_node_id, origin_slot]`.

## Why not generate every frame with a script

Frame-by-frame img2img needs one sample per frame: 24 samples for 24 frames. Interpolation needs 3–5 samples plus 24 decodes; VRAM is unchanged and time grows linearly, while in-between frames come from a mathematical transition and are more evenly spaced.
The trade-off is no real motion trajectory, which is why this route is for micro-performance only.
