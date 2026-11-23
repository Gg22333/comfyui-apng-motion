# Troubleshooting

## Generation

| Symptom | Cause | Fix |
| --- | --- | --- |
| `emit_workflow.py` says "fewer than 2 keyframe KSamplers" | The base is not a three-keyframe graph | Use `assets/workflow-*.json` as the template |
| "base has N LatentInterpolate nodes, must be 24" | The base was edited | Restore the template or add nodes up to 24 |
| "segs must sum to 24" | Wrong split | 3 beats `8/8/8`, 4 beats `6/7/6/5`, 5 beats `5/6/5/4/4` |
| "duplicate ratio within one latent pair" | Same decimal inside a segment | Recompute with `make_curve.py` (it deduplicates globally) |
| `VALIDATE FAIL: the three save nodes are not on one batch` | Outputs split across batches | Connect all three to the `ImageBatchMulti` output |

## Runtime

| Symptom | Cause | Fix |
| --- | --- | --- |
| `--run` says "server is missing a node" | Missing plugin | Run `doctor.py`; install `comfyui-kjnodes` |
| `--run` hangs / stays pending | Queue busy or model loading | Open ComfyUI and check the queue |
| `connection reset` | Local HTTP intercepted or node definitions too large | The script already has a curl fallback and node_schema fallback |
| Port conflict | A previous validation instance is still alive | `netstat -ano | findstr :8188` → `Stop-Process -Id` |

## Output

| Symptom | Cause | Fix |
| --- | --- | --- |
| N frames become fewer (24 → 19) | Identical ratios; Pillow merges them | See the curve section in `architecture.md` |
| Only one static PNG | `images` has one entry | `ImageBatchMulti` needs `inputcount=24` and all 24 inputs wired |
| Artifact lands in `output/APNG/` root | Stale prefix | Confirm all three prefixes, **press F5**, rerun |
| APNG/WebP but no GIF | VHS missing | Install `ComfyUI-VideoHelperSuite` and restart |
| Eye colour slowly changes | `eyes closed` or changing lighting words in keyframes | Use `eyes half closed`; add `color shift, different eye color` to the negative |
| Two characters blur on interaction | Micro-motion route used for interaction | Use a ControlNet pose sequence |
| Windows Photos does not animate | It does not support APNG | Use GIF, a browser, or BandiView |
| Extra PNG in `gif/` | VHS first-frame preview | Expected; safe to delete |

## Verification scripts

```bash
python scripts/check_anim.py <file> --expect 24
python scripts/check_output.py --profile profiles/xl.json
```

| Field | Expected |
| --- | --- |
| `frames` | 24 |
| `loop` | 0 |
| `identical_pairs` | 0 |
| `diff_avg` | 0.3–3.0 (lower is subtler) |
| `color_drift` | < 6 (above means colour is drifting) |
| `check_output` FAIL count | 0 |
