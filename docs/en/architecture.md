# Architecture

## Data flow

```
EmptyLatentImage(512,512,1)
        │
   KSampler K0   denoise 1.0, seed 123456789
        │  LATENT ─────────────────────────┐
        ├──────────────► CLIPTextEncode K1 ─┐
        ├──────────────► CLIPTextEncode K2 ─┤
        ├──────────────► CLIPTextEncode K3 ─┤
        │                                   │
   CLIPTextEncode "global motion" ──► ConditioningCombine (one per keyframe)
                                          │
                     KSampler K1/K2/K3 take the merged conditioning
                     denoise 0.35-0.4, same seed and same first latent
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
   All KSamplers also share one seed: different seeds bring different noise paths, which interpolation turns into blotches.
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
| `make_preview.py` | finished APNG | global-palette GIF + WebP web preview |
| `package.py` | repository tree | deterministic zip + SHA256 |

## Curve

Default `linear`: every segment walks from 1.0 down to 0.0 with a constant per-frame step.

```
segment 1: 1.0 0.857 0.714 0.571 0.429 0.286 0.143 0.0
segment 2: 0.996 0.861 ... 0.004      (almost flush with the previous segment)
segment 3: 0.992 0.853 ... 0.008
```

`ease` uses smootherstep: slow at both ends, fast in the middle, with a per-frame peak about
1.9x the linear version. `snap` is the legacy power curve: nearly frozen at the start, a rush at
the end, easily read as a jump. Segments keep a 0.004 gap so Pillow never merges identical frames.

## UI to API

`--run` converts a UI workflow into an API prompt. `comfy_lib.ui_to_api`:

1. fetches required/optional definitions via `/object_info/<type>`;
2. walks `input_order`, wiring link inputs (MODEL/LATENT/...) and reading the rest from `widgets_values`;
3. skips one extra slot for `control_after_generate` (for example KSampler's seed);
4. writes each input as `[origin_node_id, origin_slot]`.

## Why not generate every frame with a script

Frame-by-frame img2img needs one sample per frame: 24 samples for 24 frames. Interpolation needs 3–5 samples plus 24 decodes; VRAM is unchanged and time grows linearly, while in-between frames come from a mathematical transition and are more evenly spaced.
The trade-off is no real motion trajectory, which is why this route is for micro-performance only.
