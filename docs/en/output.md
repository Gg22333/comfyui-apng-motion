# Output layout: three files, one path

This page covers one thing: **where files should appear after one Queue, why they sometimes land in the wrong place, and how to check and clean up.**

Companion script: `scripts/check_output.py` (structure check plus optional archiving).

---

## 1 · What the correct tree looks like

The output root is always **ComfyUI's own `output/`**, never the repository and never the skill directory:

```
<ComfyUI>/output/
└─ APNG/
   ├─ final/
   │  ├─ apng/anim24_00001_.png      ← APNG (lossless; first frame works as a still)
   │  ├─ webp/anim24_00001_.webp     ← WebP (alpha, smallest)
   │  └─ gif/anim24_00001.gif        ← GIF (chat)
   │     └─ anim24_00001.png         ← VHS first-frame preview, safe to delete
   └─ archive/
      ├─ frames/                     ← single frames kept on purpose (not produced by default)
      ├─ tests/                      ← tuning samples
      └─ stray-<timestamp>/             ← stray files archived by check_output --fix
```

One successful Queue produces **three deliverables**. The same-named `.png` inside `gif/` is the first-frame preview written by VHS; it is not a fourth deliverable and does not mean per-frame saving is back.

`<ComfyUI>` is the `comfy_root` in your profile. Each install has its own output:

| Profile | Output root |
| --- | --- |
| `profiles/xl.json` | `D:\ComfyUI-aki-v3.2-xl\ComfyUI\output` |
| `profiles/dit.json` | `D:\ComfyUI-aki-v3.2-DiT\ComfyUI\output` |

On another machine, regenerate paths with `detect_env.py`; do not copy the drive letters above.

---

## 2 · Hard rules for the three save nodes

| Rule | Why |
| --- | --- |
| **Same batch** | `SaveAnimatedPNG`, `SaveAnimatedWEBP` and `VHS_VideoCombine` must read from the **same** `ImageBatchMulti` output. Separate batches produce different frame orders. |
| **No single-frame savers** | Do not add `SaveImage` or `PreviewImage`. They are how per-frame dumps and full folders happen. |
| **Prefix carries the path** | A `/` in `filename_prefix` creates subdirectories: `APNG/final/apng/anim24`. |
| **Three different prefixes** | Use `.../apng/anim24`, `.../webp/anim24`, `.../gif/anim24`. Identical prefixes overwrite each other. |
| **Refresh after editing** | After changing `filename_prefix`, press **F5** in the browser before Queue. The frontend caches old node values; a stale prefix is exactly how files end up in `output/APNG/` root. |
| **Same fps everywhere** | All three nodes take the same value, otherwise durations diverge. |
| **Counters are normal** | ComfyUI always appends `_00001_`. Fix the stem, accept the counter. Renaming by hand makes `check_output.py` report `odd_name`. |

Node parameters (same as `SKILL.md` §3):

| Node | Key parameters | Recommended |
| --- | --- | --- |
| `SaveAnimatedPNG` | `filename_prefix` / `fps` / `compress_level` | `APNG/final/apng/anim24` / 10 / 4 |
| `SaveAnimatedWEBP` | `filename_prefix` / `fps` / `lossless` / `quality` | `APNG/final/webp/anim24` / 10 / True / 90 |
| `VHS_VideoCombine` | `frame_rate` / `loop_count` / `filename_prefix` / `format` | 10 / 0 / `APNG/final/gif/anim24` / `image/gif` |

---

## 3 · Why a file can land in `output/APNG/` root

It happened on this machine once: `output/APNG/anim24_00001_.png` sat directly under `APNG/`, with no matching WebP or GIF. The save node was not misconfigured; **the run used a stale prefix**.

Four common sources:

| Source | Symptom | Fix |
| --- | --- | --- |
| Cached prefix in the browser | Artifact at `output/APNG/anim24_00001_.png` | Confirm all three prefixes → **F5** → rerun |
| Old workflow | Old names such as `anim_base_*`, `anim24_1_*` | Regenerate from `workflows/workflow-*.json` or `emit_workflow.py` |
| Historical `SaveImage` | `output/anim_base_00001_.png` at the output root | Remove the save node; archive the file |
| Old script intermediate frames | Names containing `_1_`, `_2_` | Historical frames; move to `archive/frames/` |

The test is simple: **a real deliverable exists as a set of three.** A PNG without its WebP/GIF siblings is a half-finished run or a stale-prefix leftover.

---

## 4 · Check and clean

```powershell
# Check only (dry run by default)
python scripts/check_output.py --profile profiles/xl.json

# Move strays from APNG root / output root into archive/stray-<timestamp>/
python scripts/check_output.py --profile profiles/xl.json --fix

# Machine-readable
python scripts/check_output.py --profile profiles/xl.json --json
```

Exit codes: `0` no FAIL, `1` has FAIL, `2` path missing.

| Level | Meaning |
| --- | --- |
| `FAIL stray_root` | Files directly under `output/APNG/` → stale prefix or unrefreshed frontend |
| `FAIL incomplete` | A run has only one or two formats → outputs not on the same batch, or one node failed |
| `WARN outside_apng` | `anim*` leftovers at `output/` root → historical `SaveImage` or old prefix |
| `WARN odd_name` | Name does not match `<name>_<5 digits>.<ext>` → manual rename or fixed stem |
| `INFO vhs_sidecar` | Same-named `.png` in `gif/`, VHS first-frame preview, safe to delete |
| `INFO archive` | Archive file count, not part of the verdict |

Manual cleanup (look before touching):

```powershell
$apng = 'D:\ComfyUI-aki-v3.2-xl\ComfyUI\output\APNG'
Get-ChildItem -LiteralPath $apng -File | Select-Object Name, Length, LastWriteTime
# Once confirmed as strays, archive with the script rather than deleting by hand
python scripts/check_output.py --profile profiles/xl.json --fix
```

---

## 5 · Acceptance checklist

1. `output/APNG/` root contains **no files**.
2. `final/apng`, `final/webp`, `final/gif` contain the **same counter** for the three formats.
3. The same-named `.png` in `gif/` is the first-frame preview; keeping or deleting it does not affect the animation.
4. Run `check_anim.py`:

```powershell
& '<ComfyUI-python>' scripts\check_anim.py `
  '<ComfyUI>\output\APNG\final\apng\anim24_00001_.png' --expect 24
```

Expected: `frames=24`, `loop=0`, `identical_pairs=0`, `color_drift < 6`.

5. Run `check_output.py` again: `FAIL 总数: 0`.

---

## 6 · Archive conventions

| Directory | Contents | Produced by |
| --- | --- | --- |
| `final/` | Three deliverables | The three save nodes |
| `gif/*.png` | VHS first-frame preview | VHS plugin |
| `archive/tests/` | Tuning samples, comparison runs | Manual |
| `archive/frames/` | Single frames kept on purpose | Manual (none by default) |
| `archive/stray-<timestamp>/` | Strays and old-prefix leftovers | `check_output.py --fix` |

Do not keep workflow backups in `ComfyUI/user/default/workflows/`. A same-named `-v1.json` shows up as a second workflow in the UI; keep backups under `archive/` and leave only the active file in the workflows directory.

---

## 7 · What must not land in the repo

The repo and the skill folder hold **source and web assets only**. Run outputs stay in ComfyUI's own
`output/`:

| Path | Should contain | Should not contain |
| --- | --- | --- |
| `<ComfyUI>/output/APNG/final/` | the three finals | single-frame PNGs, stale prefixes |
| repo `docs/assets/` | `preview.webp` / `preview.gif` / `storyboard-*.webp` | raw APNG, `_00001_` outputs |
| repo root | sources, docs, `workflows/` | any copy of `output/` |
| scratch dirs | one-off scripts, test renders | long-lived PNG / WebP |

Only two scripts write into `docs/assets/`, and both write **web assets**, not finals:

- `make_preview.py` → `docs/assets/preview.{webp,gif}`
- `make_storyboard.py` → `docs/assets/storyboard-<name>.webp`

Check: `git status` should show no image changes other than those two files.
