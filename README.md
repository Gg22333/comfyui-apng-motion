**English** · [简体中文](README.zh-CN.md)

# comfyui-apng-motion

[![CI](https://github.com/Gg22333/comfyui-apng-motion/actions/workflows/ci.yml/badge.svg)](https://github.com/Gg22333/comfyui-apng-motion/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/Gg22333/comfyui-apng-motion)](https://github.com/Gg22333/comfyui-apng-motion/releases)
[![License: MIT](https://img.shields.io/github/license/Gg22333/comfyui-apng-motion)](LICENSE)
[![Python](https://img.shields.io/badge/python-%3E%3D3.9-blue)](pyproject.toml)

Make **coherent APNG / WebP / GIF** animations in ComfyUI by interpolating three to five keyframes in
latent space — **8, 12, 24, 30 or 60 frames** out of the same graph, no frame-by-frame scripts, no
per-frame image dumps, one queue → three files.

![preview](docs/assets/preview.webp)

---

## Contents

- [At a glance](#at-a-glance)
- [Model support](#model-support)
- [Frame count](#frame-count)
- [Motion library](#motion-library)
- [Tunable parameters](#tunable-parameters)
- [Why not `batch_size`](#why-not-batch_size)
- [Why it is cheap](#why-it-is-cheap)
- [Quick start](#quick-start)
- [Where files land](#where-files-land)
- [Requirements](#requirements)
- [Repository layout](#repository-layout)
- [How it works](#how-it-works)
- [Documentation](#documentation)
- [Limits](#limits)
- [Contributing](#contributing)
- [Credits](#credits)
- [License](#license)

---

## At a glance

| | |
| --- | --- |
| **Input** | 3–5 keyframe prompts (a "story card": lock + style + per-beat actions) |
| **Engine** | ComfyUI + `LatentInterpolate` ×N + `ImageBatchMulti(N)` |
| **Output** | APNG, WebP and GIF — one file each; 8 / 12 / 24 / 30 / 60 frames; loop infinite |
| **Models** | any: SDXL checkpoint or Moss/DiT stack (loader-agnostic) |
| **Scripts** | pure stdlib + Pillow, no GPU needed for tooling |
| **Runs on** | Windows / macOS / Linux; paths come from `profiles/*.json` |

## Model support

The workflow contract is model-agnostic: **one `denoise=1.0` KSampler, 2-4 keyframe KSamplers,
N `LatentInterpolate`, N `VAEDecode`, `ImageBatchMulti(N)`, three savers**, where N is the frame count
(`--frames`, 8-60). Swapping the loader is the only structural change; `emit_workflow.py` resizes the
interpolation / decoder / batch trio to match N automatically.

| Family | Loader nodes | Keyframe denoise | Notes |
| --- | --- | --- | --- |
| SD 1.5 | `CheckpointLoaderSimple` | 0.45-0.55 | 512x512 native |
| SDXL / Illustrious / NoobAI | `CheckpointLoaderSimple` | 0.35-0.45 | 1024x1024 native; 512 also fine |
| FLUX.1 | `UNETLoader` + `DualCLIPLoader` + `VAELoader` | 0.45-0.55 | add `FluxGuidance` before the sampler |
| Moss / DiT | `UNETLoader` + `CLIPLoader` (`type=moss_image`) + `VAELoader` | 0.50-0.70 | 8-step DMD, cfg 1.0; 0.5 is nearly static, 0.7 gives visible head motion, >0.8 drifts |
| Any fine-tune | same as its base | start 0.35 | lower = stable, higher = expressive |

Denoise ranges are field experience, not hard rules. For the same seed, **0.35 is the stability
ceiling on SDXL**: above ~0.42 the keyframe redraw starts changing clothes and background, and latent
interpolation mixes the two textures into colour blotches. If you need bigger expressions, raise
denoise and accept drift, or inpaint the face region only.

## Frame count

Frame count is a parameter, not a fork of the method. `--frames 8|12|24|30|60` (or `"frames"` in the
story card) rewires `LatentInterpolate` / `VAEDecode` / `ImageBatchMulti` to N; `--segs` splits N across
the beats, and if you omit it the split is even.

| Frames | fps | Duration | Best for | 4-beat `segs` |
| --- | --- | --- | --- | --- |
| 8 | 8 | 1.0 s | avatar twitch, chat reaction | `2,2,2,2` |
| 12 | 12 | 1.0 s | light sticker | `3,3,3,3` |
| 24 | 12 | 2.0 s | default; expression loop | `6,7,6,5` |
| 30 | 15 | 2.0 s | five-beat story, half-body action | `8,8,7,7` |
| 60 | 30 | 2.0 s | smooth web/Discord preview, five-beat story | `15,15,15,15` |

Sampling cost stays at K passes (one per keyframe) no matter which row you pick — only decode count and
file size scale with N. For the same content a 60-frame APNG is roughly 2.5x the size of 24; see [docs/formats.md](docs/formats.md).
The preview at the top of this page is 60 frames, 30 fps, Moss/DiT, `assets/story.preview.json`.

## Motion library

`assets/motion-presets.json` ships 16 ready-to-use beat recipes: 9 emotions (laugh / cry / shock / angry / smug / sigh / panic / sleepy / heart hands),
5 gestures (wave / nod / shake / thumbs up / think), and 2 five-beat stories (rainy walk / morning coffee).
`scripts/make_story.py` merges a preset with your character lock and writes a story card for `emit_workflow.py`:

```bash
python scripts/make_story.py --list
python scripts/make_story.py --preset laugh --lock "masterpiece, 1girl, silver hair, blue eyes" --out story.laugh.json
python scripts/make_story.py --preset rainy-walk --lock "masterpiece, 1girl" --frames 60 --fps 30 --out story.rain.json
```

Beat grammar, platform specs (Telegram 512/≤3 s/60 fps, LINE APNG 5–20 frames/≤4 s/≤1 MB, WeChat GIF 240²/≤500 KB)
and the seven common failures: [docs/en/motion-presets.md](docs/en/motion-presets.md).

## Tunable parameters

Everything below is editable inside the workflow, no script required.

| Scope | Node | What it controls |
| --- | --- | --- |
| Whole clip | `CLIPTextEncode` "global motion" | action, camera, lighting, style; one edit affects every keyframe |
| Per keyframe | `CLIPTextEncode` "K0 / K1 / ..." | expression, pose, gaze |
| Per keyframe sampling | each `KSampler` | seed, steps, cfg, sampler, scheduler, denoise |
| Pacing | N x `LatentInterpolate` ratio | easing curve; `linear` is the most even |
| Speed | three save nodes `fps` | set the same value in all three; `fps x frames` = duration (24 @ 12 fps = 2.0 s) |
| Naming | `filename_prefix` | `apng/`, `webp/`, `gif/` subfolders |
| Quality | APNG `compress_level`, WebP `lossless`/`quality`, VHS `loop`/`pingpong` | file size and playback behaviour |

The workflow ships with a `Note` node listing the same table, so you can find the knobs on the canvas.

## Why not `batch_size`

`batch_size=24` produces **24 independent noise samples**. A fixed seed makes the run reproducible,
not continuous — playback flickers. This project instead pins every keyframe to the *same* first-frame
latent, so hair colour, eye colour and composition do not drift:

```
first frame (denoise 1.0, fixed seed)
   ├─ keyframe A (img2img from the first latent, denoise 0.4/0.5)
   ├─ keyframe B … (same latent)
   └─ keyframe C … (optional, 4–5 beats)
N × LatentInterpolate → N × VAEDecode → ImageBatchMulti(N)
   ├─ SaveAnimatedPNG
   ├─ SaveAnimatedWEBP
   └─ VHS_VideoCombine (GIF)
```

## Why it is cheap

A run costs **K sampling passes, not N** — frame count never changes that:

| Beats | Sampling passes (steps=20) | Versus 24-frame frame-by-frame (480) | Versus 60-frame frame-by-frame (1200) |
| --- | --- | --- | --- |
| 3 beats | 3 × 20 = 60 | 87.5% fewer | 95.0% fewer |
| 4 beats | 4 × 20 = 80 | 83.3% fewer | 93.3% fewer |
| 5 beats | 5 × 20 = 100 | 79.2% fewer | 91.7% fewer |

Going from 24 to 60 frames therefore costs **zero extra sampling**. What scales with N is VAE decoding
and file size, not diffusion.

Decoding is still 24 passes, but interpolation is just 24 linear blends on `64×64×4` latents — no model calls, tens of MB of buffers, not gigabytes. That is the trade: no real motion trajectory, but a sticker that plays anywhere for a fraction of the sampling cost.

Full comparison with Live2D / Spine, video generation, sprite sheets and Lottie: [docs/en/synthesis-comparison.md](docs/en/synthesis-comparison.md).

## Quick start

```bash
git clone https://github.com/Gg22333/comfyui-apng-motion.git
cd comfyui-apng-motion

python scripts/detect_env.py      # find ComfyUI installs → profiles/*.json
python scripts/doctor.py          # check models, custom nodes, ports, output dir
python scripts/emit_workflow.py \
  --base assets/workflow-sdxl.json \
  --story assets/story.4beat.json \
  --out my-4beat.json
```

Drag `my-4beat.json` into ComfyUI, edit the prompts, hit **Queue**.
Finished files land in `output/APNG/final/{apng,webp,gif}/` — exactly three per run.
Check the tree (and archive stray files) with:

```bash
python scripts/check_output.py --profile profiles/xl.json
python scripts/check_output.py --profile profiles/xl.json --fix
```

Headless — validate, run, and verify the produced files:

```bash
python scripts/emit_workflow.py --validate my-4beat.json --run --profile profiles/xl.json
```

## Requirements

| Dependency | Version | Required | If missing |
| --- | --- | --- | --- |
| Python | ≥ 3.9 | yes | scripts won't run |
| Pillow | ≥ 9.0 | verification only | `check_anim.py` unavailable; rendering still works |
| ComfyUI | ≥ 0.3 | yes | no native `SaveAnimatedPNG` / `SaveAnimatedWEBP` |
| [comfyui-kjnodes](https://github.com/kijai/ComfyUI-KJNodes) | any | yes | `ImageBatchMulti` node missing |
| [ComfyUI-VideoHelperSuite](https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite) | any | no | GIF output unavailable, APNG/WebP fine |

```bash
python scripts/check_deps.py
pip install -r requirements.txt
```

Tip: run verification with the Python bundled with ComfyUI — it already has Pillow.

## Repository layout

```
SKILL.md              the skill itself (principles, story cards, multi-character, troubleshooting)
skill.json            version, dependencies, entrypoints, install targets
scripts/              detect_env · doctor · emit_workflow · make_story · check_anim · check_output
                      make_curve · check_deps · install · package · comfy_lib
assets/               workflow templates (SDXL + Moss), 16 motion presets, story cards, node schema
docs/                 docs in Chinese, English under docs/en/
tests/                offline unit tests — no GPU, no network
profiles/             generated per machine (git-ignored)
dist/                 packaging output (git-ignored)
```

## How it works

1. **Keyframes** — the first frame is txt2img; every other keyframe is img2img *from the first latent*.
2. **Interpolation** — 24 `LatentInterpolate` nodes walk from keyframe to keyframe with a slowed-in/out curve.
3. **Decode & batch** — N decodes, merged into one batch, then three encoders read the same batch.
4. **Verification** — `check_anim.py` reports frames, duration, loop, neighbour difference and colour drift.

The hard-won details (curve values, why identical ratios get merged by Pillow, why GIF is 1/100 s)
are in [docs/formats.md](docs/formats.md) and [SKILL.md](SKILL.md).

## Documentation

| | English | 中文 |
| --- | --- | --- |
| Overview | [docs/en/index.md](docs/en/index.md) | [docs/index.md](docs/index.md) |
| Install | [docs/en/install.md](docs/en/install.md) | [docs/install.md](docs/install.md) |
| Usage | [docs/en/usage.md](docs/en/usage.md) | [docs/usage.md](docs/usage.md) |
| Motion library (16 presets) | [docs/en/motion-presets.md](docs/en/motion-presets.md) | [docs/motion-presets.md](docs/motion-presets.md) |
| Output layout | [docs/en/output.md](docs/en/output.md) | [docs/output.md](docs/output.md) |
| Approach comparison | [docs/en/synthesis-comparison.md](docs/en/synthesis-comparison.md) | [docs/synthesis-comparison.md](docs/synthesis-comparison.md) |
| APNG vs GIF vs video | [docs/en/formats.md](docs/en/formats.md) | [docs/formats.md](docs/formats.md) |
| Architecture | [docs/en/architecture.md](docs/en/architecture.md) | [docs/architecture.md](docs/architecture.md) |
| Troubleshooting | [docs/en/troubleshooting.md](docs/en/troubleshooting.md) | [docs/troubleshooting.md](docs/troubleshooting.md) |
| FAQ | [docs/en/faq.md](docs/en/faq.md) | [docs/faq.md](docs/faq.md) |

## Where files land

One Queue writes **three deliverables** into ComfyUI's own `output/` directory, never into this repository:

```
<ComfyUI>/output/APNG/final/
├─ apng/anim24_00001_.png      # lossless APNG; frame 1 doubles as a still
├─ webp/anim24_00001_.webp     # alpha, smallest
└─ gif/anim24_00001.gif        # chat
   └─ anim24_00001.png         # VHS first-frame preview, safe to delete
```

Three rules keep it that way:

1. All three save nodes read the **same** `ImageBatchMulti` output; no `SaveImage` / `PreviewImage` anywhere.
2. Each node has its own prefix: `APNG/final/apng|webp|gif/anim24`.
3. After editing a prefix, **press F5** before Queue. The frontend caches old values, and a stale prefix is exactly how a PNG ends up directly under `output/APNG/`.

`anim24` in those names is the story card's `name` field — set it to `anim60` (or anything) for other
frame counts; the three savers all read the same prefix root.

A PNG without its WebP/GIF siblings is a half-finished run or an old-prefix leftover, not a deliverable.
`check_output.py` reports `stray_root`, `incomplete`, `outside_apng` and the expected `vhs_sidecar`, and `--fix` moves strays into `output/APNG/archive/stray-<timestamp>/`.

Full details: [docs/output.md](docs/output.md) · [English](docs/en/output.md).

## Limits

- Latent interpolation has **no real motion trajectory**: great for expressions, breathing and small head
  moves; not for walking, turning around or camera moves. For those, use a ControlNet pose sequence or a
  video model (Wan / LTX).
- Frame count is a budget, not a quality dial: 8-60 frames all work, decode time scales linearly with N.
  24 is the default sweet spot; 60 is for a 2 s narrative beat at 30 fps. The method still has no real
  motion trajectory at any frame count — more frames smooth the transition, they do not create new poses.
- APNG is large (full-frame PNGs). For chat, ship GIF; for alpha, ship WebP.

## Contributing

Issues and PRs are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) and
[CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md). Run `pytest -q` before opening a PR.

## Credits

Built on ComfyUI, [ComfyUI-KJNodes](https://github.com/kijai/ComfyUI-KJNodes) and
[ComfyUI-VideoHelperSuite](https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite).
Repository layout is inspired by [book-to-skill](https://github.com/virgiliojr94/book-to-skill).

## License

MIT — see [LICENSE](LICENSE).
