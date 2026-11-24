**English** · [简体中文](#简体中文)

# comfyui-apng-motion

[![CI](https://github.com/Gg22333/comfyui-apng-motion/actions/workflows/ci.yml/badge.svg)](https://github.com/Gg22333/comfyui-apng-motion/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/Gg22333/comfyui-apng-motion)](https://github.com/Gg22333/comfyui-apng-motion/releases)
[![License: MIT](https://img.shields.io/github/license/Gg22333/comfyui-apng-motion)](LICENSE)
[![Python](https://img.shields.io/badge/python-%3E%3D3.9-blue)](pyproject.toml)

Make **coherent APNG / WebP / GIF** animations in ComfyUI from **3–8 keyframes** — story-shaped, not
just a face wiggling. One graph, **8 / 24 / 30 / 60 frames**, ready-to-import JSON for both the UNet
family (SDXL) and the DiT family (MOSS-Image, FLUX, SD3, Krea, Anima). No frame-by-frame scripts, no
per-frame image dumps, one queue → three files.

Docs site: [gg22333.github.io/comfyui-apng-motion](https://gg22333.github.io/comfyui-apng-motion/) — the header language selector switches zh/en in place.

![preview](docs/assets/preview.webp)

![eleven-beat storyboard](docs/assets/storyboard-diet.webp)

---

## Contents

- [At a glance](#at-a-glance)
- [Model support](#model-support)
- [Frame count](#frame-count)
- [Dynamic frame mode](#dynamic-frame-mode-in-graph)
- [Workflows](#workflows)
- [How to write prompts](#how-to-write-prompts)
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
- [简体中文](#简体中文)

---

## At a glance

| | |
| --- | --- |
| **Input** | 3–5 keyframe prompts (a "story card": lock + style + per-beat actions) |
| **Engine** | ComfyUI + `LatentInterpolate` ×N + `ImageBatchMulti(N)` |
| **Output** | APNG, WebP and GIF — one file each; 8 / 12 / 24 / 30 / 60 frames; loop infinite |
| **Models** | any: SDXL checkpoint (UNet) or a DiT stack — MOSS-Image, FLUX, SD3, Krea, Anima (loader-agnostic) |
| **Scripts** | pure stdlib + Pillow, no GPU needed for tooling |
| **Runs on** | Windows / macOS / Linux; paths come from `profiles/*.json` |

## Model support

The workflow contract is model-agnostic: **one `denoise=1.0` KSampler, 2-4 keyframe KSamplers,
N `LatentInterpolate`, N `VAEDecode`, `ImageBatchMulti(N)`, three savers**, where N is the frame count
(`--frames`, 8-60). Swapping the loader is the only structural change; `emit_workflow.py` resizes the
interpolation / decoder / batch trio to match N automatically.

**DiT is an architecture; MOSS is a model.** DiT (Diffusion Transformer, arXiv:2212.09748) is the
family that replaces the U-Net backbone with a transformer. SDXL is UNet; MOSS-Image, FLUX, SD3, Krea
and Anima are DiT. Three independent layers decide what you configure: architecture (denoise range),
text encoder (how you write), step paradigm (steps/cfg).

| Family | Architecture | Text encoder | Loader nodes | Keyframe denoise | Notes |
| --- | --- | --- | --- | --- | --- |
| SD 1.5 | UNet | CLIP | `CheckpointLoaderSimple` | 0.45-0.55 | 512x512 native |
| SDXL / Illustrious / NoobAI | UNet | CLIP-L + CLIP-G | `CheckpointLoaderSimple` | 0.35-0.45 | 1024x1024 native; 512 also fine |
| FLUX.1 | DiT | CLIP-L + T5-XXL | `UNETLoader` + `DualCLIPLoader` + `VAELoader` | 0.45-0.55 | add `FluxGuidance` (3.5) before the sampler, cfg 1.0 |
| SD3 / SD3.5 | MMDiT | CLIP-L + CLIP-G + T5-XXL | `CheckpointLoaderSimple` or three-piece | 0.40-0.50 | cfg 4-7 |
| MOSS-Image | DiT + 8-step DMD | Qwen3.5-9B | `UNETLoader` + `CLIPLoader` (`type=moss_image`) + `VAELoader` | 0.82-0.90 | steps 8, cfg 1.0; below 0.80 nearly static, above 0.90 drifts |
| Krea 2 | DiT | Qwen3-VL 4B | `UNETLoader` + `CLIPLoader` + `VAELoader` | 0.45-0.55 | Raw 20-30 steps / Turbo 4-8 |
| Anima 2B | DiT | Qwen3-0.6B | `UNETLoader` + `CLIPLoader` + `VAELoader` | 0.45-0.55 | Base 30-50 steps / Turbo 8-12 |
| Any fine-tune | same as its base | same as its base | same as its base | start 0.35 | lower = stable, higher = expressive |

Full per-model breakdown, loaders and citations: [docs/en/models.md](docs/en/models.md) ·
[中文](docs/models.md).

Denoise ranges are field experience, not hard rules. For the same seed, **0.35 is the stability
ceiling on SDXL**: above ~0.42 the keyframe redraw starts changing clothes and background, and latent
interpolation mixes the two textures into colour blotches. If you need bigger expressions, raise
denoise and accept drift, or inpaint the face region only.

## Frame count

Frame count is a parameter, not a fork of the method. `--frames 8|12|24|30|60` (or `"frames"` in the
story card) rewires `LatentInterpolate` / `VAEDecode` / `ImageBatchMulti` to N; `--segs` splits N across
the beats, and if you omit it the split is even.

`fps` sets the total length (`frames / fps`); `dwell` distributes that time across beats. GIF frame
delay quantises to 10 ms, so 24 fps becomes 40 ms per frame and a "2.5 s" GIF actually runs 2.4 s.
20 / 25 fps divide evenly and do not drift.

| Frames | Slow (narrative) | Standard | Fast (chat) | 4-beat `segs` |
| --- | --- | --- | --- | --- |
| 8 | 6 fps / 1.33 s | 8 fps / 1.00 s | 10 fps / 0.80 s | `2,2,2,2` |
| 24 | 8 fps / 3.00 s | 10 fps / 2.40 s | 12 fps / 2.00 s | `6,7,6,5` |
| 30 | 10 fps / 3.00 s | 15 fps / 2.00 s | 20 fps / 1.50 s | `8,8,7,7` |
| 60 | **20 fps / 3.00 s** (default) | 25 fps / 2.40 s | 30 fps / 2.00 s | `5,5,4,7,6,7,5,6,5,5,5` |

Sampling cost stays at K passes (one per keyframe) no matter which row you pick — only decode count and
file size scale with N. For the same content a 60-frame APNG is roughly 2.5x the size of 24; see [docs/formats.md](docs/formats.md).
The preview above is the eleven-beat story *Diet Betrayal* — 60 frames, 20 fps, 3.0 s, MOSS-Image
(DiT + DMD): sits up
determined → shoulders drop → face down on the table → looks at the floor → reaches for the phone →
stares at the screen → hugs the chicken bucket → reaches inside → sneaks a bite → puts it down → holds
the salad bowl, fist raised, "tomorrow for sure". Recipe: `assets/story.diet.json`,
`prompt_mode: moss_zh`, segments `5,5,4,7,6,7,5,6,5,5,5`, denoise 0.85, 640×640.
Per-beat dwell is `0.95, 0.95, 1.1, 1.3, 1.0, 1.3, 0.95, 1.0, 0.9, 0.95, 0.95` with `ease: 0.3`:
the two big reaches (phone, chicken bucket) hold longer, shoulder-only beats move faster.
`LatentInterpolate` fills the in-betweens; each keyframe appears once on the timeline, so no seam holds
the same frame twice. Frame budgeting: [docs/en/workflows.md](docs/en/workflows.md#how-to-lay-out-transition-frames).
The contact sheet below it is sampled from the real output by `--segs`, not a mock-up.

## Motion library

`assets/motion-presets.json` ships 17 ready-to-use beat recipes: 9 emotions (laugh / cry / shock / angry / smug / sigh / panic / sleepy / heart hands),
5 gestures (wave / nod / shake / thumbs up / think), 2 five-beat stories (rainy walk / morning coffee),
and one eleven-beat full-body story (`diet-betrayal`, `moss_zh` Chinese prose).
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
| Speed | three save nodes `fps` | same value in all three; `fps x frames` = duration. ComfyUI only takes one global fps — apply per-beat dwell after export with `retime.py` |
| Per-beat dwell | story card `dwell` + `ease` | how long each beat holds; applied by `retime.py` / `make_preview.py`, pixels untouched |
| Prompt dialect | `--prompt-mode tags|moss_zh` | `tags` = CLIP comma tags; `moss_zh` = Qwen-VL Chinese prose |
| Size | latent width/height or `--size 640` | MOSS-Image 512 or 640; SDXL 512–1024 |
| Naming | `filename_prefix` | `apng/`, `webp/`, `gif/` subfolders |
| Quality | APNG `compress_level`, WebP `lossless`/`quality`, VHS `loop`/`pingpong` | file size and playback behaviour |

The workflow ships with a `Note` node listing the same table, so you can find the knobs on the canvas.

## Dynamic frame mode (in-graph)

Frame count is a node widget, not a graph shape. Install the bundled nodes once:

```bash
python scripts/install_nodes.py --profile xl   # -> <comfy_root>/custom_nodes/apng_motion_nodes
```

Then emit a graph with `--dynamic`:

```bash
python scripts/emit_workflow.py --base workflows/workflow-sdxl.json \
    --story assets/story.example.json --dynamic --out my-dynamic.json
```

Add a whole-sequence camera move (pan / zoom / rotate, driven by an easing curve):

```bash
python scripts/emit_workflow.py --base workflows/workflow-sdxl.json \
    --story assets/story.example.json --dynamic --camera --out my-dynamic-camera.json
```

3 beats / 24 frames becomes **26 nodes / 39 links** instead of 67, or 27 with `--camera`. Each beat is one
`APNG Latent Interpolate N` with `frames`, `role`, `curve` widgets; one `VAEDecode` decodes the whole
batch; `APNG Frame Stats` prints frames, `frames/fps` duration, adjacent-frame diff (min/max/avg and
identical pairs), per-beat seam checks and the loop seam before anything is written to disk — same
thresholds as `check_anim.py`.

| Dimension | In-graph control |
| --- | --- |
| Frame count | `frames` on each interpolate node |
| Duration | `fps` on the three savers and the stats node |
| Adjacent-frame diff | `APNG Frame Stats` output |
| Seam uniqueness | `segs` on the stats node |
| Storyboard | the K keyframe KSamplers, unchanged |
| Camera motion | `x` / `y` / `zoom` / `angle` / `easing` / `loop` on `APNG Camera Move` |

Per-frame dwell and per-beat ease still cannot be expressed because ComfyUI savers take one global
`fps`; use `retime.py` after export. Full page: [docs/en/dynamic.md](docs/en/dynamic.md).

## Workflows

Ten JSON files, drop one into ComfyUI and queue (the four dynamic ones need the bundled `comfyui_nodes` first):

| Environment | 3 beats | 4 beats |
| --- | --- | --- |
| UNet family (SDXL) | [`workflow-sdxl.json`](workflows/workflow-sdxl.json) | [`workflow-sdxl-4beat.json`](workflows/workflow-sdxl-4beat.json) |
| DiT family (MOSS-Image) | [`workflow-moss.json`](workflows/workflow-moss.json) | [`workflow-moss-4beat.json`](workflows/workflow-moss-4beat.json) |
| Dynamic frames (UNet, 3 beats / 24f) | [`workflow-sdxl-dynamic.json`](workflows/workflow-sdxl-dynamic.json) | — |
| Dynamic frames (DiT, 3 beats / 24f) | [`workflow-moss-dynamic.json`](workflows/workflow-moss-dynamic.json) | — |
| Dynamic + camera (UNet, 3 beats / 24f) | [`workflow-sdxl-dynamic-camera.json`](workflows/workflow-sdxl-dynamic-camera.json) | — |
| Dynamic + camera (DiT, 3 beats / 24f) | [`workflow-moss-dynamic-camera.json`](workflows/workflow-moss-dynamic-camera.json) | — |

The `moss` file names are historical; the graph holds any DiT model — swap the three loaders for FLUX,
SD3, Krea or Anima and keep the structure.

Each graph carries two `Note` nodes on the canvas: "tunable parameters" and "prompt dialect (by architecture)",
so the prompt rules and the frame table are inside the file, not only in the docs.
Download page and import steps: [docs/en/workflows.md](docs/en/workflows.md).

## How to write prompts

The dialect follows the **text encoder**, not the model name. Three of them cover everything in the
table above; the full rules live in [docs/en/prompting.md](docs/en/prompting.md) ·
[中文](docs/prompting.md).

| Encoder | Models | Dialect | One-line rule |
| --- | --- | --- | --- |
| CLIP | SD 1.5, SDXL, Illustrious, NoobAI | `tags` | comma tags, style last |
| Qwen-VL | MOSS-Image, Krea 2, Qwen-Image, Anima | `moss_zh` | paragraphs, every one ends with a full stop |
| T5 | FLUX.1, SD3 / SD3.5 | prose | full English sentences, no `(word:1.3)` |

**CLIP tags**

```
1girl, solo, full body, black short hair, blue eyes, beige hoodie, dark shorts,
barefoot, bedroom at night, warm lamp light, 〈this beat〉,
anime screencap, clean lineart, flat cel shading
```

Describe pixels, not feelings: `eyes wide, pupils small`, not `shocked`.

**Qwen-VL prose**

```
一间温馨的小卧室，深夜。画面右侧有一盏暖色台灯，光从右前方斜照下来，落在木地板上。
固定机位，平视，全身镜头，人物从头到脚完整入画，双手和双脚都留在画框里。
小满：黑色短发，蓝色眼睛，身材微胖，穿着宽松的米色连帽卫衣和深色短裤，赤脚。
小满盘腿坐在矮桌前，背挺得很直，双手叉在腰上，抬起下巴，嘴角只上扬几毫米。
动漫赛璐璐风格，干净黑色线稿，平涂上色，暖色调，柔和阴影。
```

No quality tags — `masterpiece` / `best quality` are noise to a Qwen-VL encoder. Measure the body
instead of naming the emotion.

**T5 sentences** — one idea per sentence, no weight brackets.

Every beat changes **exactly one variable**. If you change two, interpolation gives you two different
people. Need text inside the frame? Use absolute-pixel bboxes on a canvas whose sides are multiples of
16 — details in the prompting page.

Full eleven-beat example: [`assets/story.diet.json`](assets/story.diet.json);
`python scripts/make_story.py --preset diet-betrayal --out my.json` regenerates it.

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
  --base workflows/workflow-sdxl.json \
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
workflows/            importable graphs (UNet/SDXL + DiT/MOSS, 3/4 beats each)
assets/               17 motion presets, story cards (incl. a moss_zh story with dwell), node schema
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
| Motion library (17 presets) | [docs/en/motion-presets.md](docs/en/motion-presets.md) | [docs/motion-presets.md](docs/motion-presets.md) |
| Output layout | [docs/en/output.md](docs/en/output.md) | [docs/output.md](docs/output.md) |
| Models and architectures | [docs/en/models.md](docs/en/models.md) | [docs/models.md](docs/models.md) |
| Prompt writing | [docs/en/prompting.md](docs/en/prompting.md) | [docs/prompting.md](docs/prompting.md) |
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
  24 is the default sweet spot; 60 frames at 20 fps is a 3 s narrative beat. The method still has no
  real motion trajectory at any frame count — more frames smooth the transition, they do not create new poses.
- APNG is large (full-frame PNGs). For chat, ship GIF; for alpha, ship WebP.

## Contributing

Issues and PRs are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) and
[CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md). Run `pytest -q` before opening a PR.

## Credits

Built on ComfyUI, [ComfyUI-KJNodes](https://github.com/kijai/ComfyUI-KJNodes) and
[ComfyUI-VideoHelperSuite](https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite).
Repository layout is inspired by [book-to-skill](https://github.com/virgiliojr94/book-to-skill).

The whole-sequence camera idea (one pan / zoom / rotate path with an easing curve over the frame
index) was inspired by [ShmuelRonen/ComfyUI-AstralAnimator](https://github.com/ShmuelRonen/ComfyUI-AstralAnimator).
That project ships no license file, so **no code was copied**; `APNGCameraMove` is an independent
`torch.nn.functional.affine_grid` + `grid_sample` implementation that never re-samples frames.

KJNodes, VideoHelperSuite and ComfyUI are GPL-3.0 projects. They are used here as
runtime dependencies through their ComfyUI nodes only; no GPL source code is copied
into this repository. Everything in `scripts/`, `tests/`, `workflows/`, `assets/` and
`docs/` is original and MIT-licensed. See [NOTICE](NOTICE) for details.

## License

MIT — see [LICENSE](LICENSE) and [NOTICE](NOTICE).

Using the code, workflows or docs in your own project? Keep the copyright and
permission notice — that is the only condition MIT puts on you — and a link back is
appreciated but not required. Forking, modifying and commercial use are all allowed.

Two things MIT does **not** grant: the project name (`comfyui-apng-motion`) and the
logo. Forks must not present themselves as the official repository or imply
endorsement by the original author.

If you cite this in published work, use the citation metadata in
[CITATION.cff](CITATION.cff) — GitHub shows a "Cite this repository" button in the
sidebar.

---

## 简体中文

<details>
<summary><b>展开中文说明</b></summary>

[![CI](https://github.com/Gg22333/comfyui-apng-motion/actions/workflows/ci.yml/badge.svg)](https://github.com/Gg22333/comfyui-apng-motion/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/Gg22333/comfyui-apng-motion)](https://github.com/Gg22333/comfyui-apng-motion/releases)
[![License: MIT](https://img.shields.io/github/license/Gg22333/comfyui-apng-motion)](LICENSE)
[![Python](https://img.shields.io/badge/python-%3E%3D3.9-blue)](pyproject.toml)

在 ComfyUI 里用 **3–8 个关键帧 + latent 插值**做**能讲故事的 APNG / WebP / GIF**。
同一个工作流，**8 / 24 / 30 / 60 帧**随便切；UNet 系（SDXL）与 DiT 系（MOSS-Image、FLUX、SD3、Krea、Anima）
两套环境都有可直接导入的 JSON。
不靠 `batch_size` 堆帧，不逐帧落盘，一次 Queue 出三个成品文件。

文档站：[gg22333.github.io/comfyui-apng-motion](https://gg22333.github.io/comfyui-apng-motion/)（右上角语言选择器可在原地切中/英）。

![预览](docs/assets/preview.webp)

![十一拍分镜](docs/assets/storyboard-diet.webp)

---

### 目录

- [一眼看懂](#一眼看懂)
- [模型支持](#模型支持)
- [帧数怎么选](#帧数怎么选)
- [动态帧数模式](#动态帧数模式图上直接调)
- [工作流](#工作流)
- [提示词怎么写](#提示词怎么写)
- [动作库](#动作库)
- [可调参数](#可调参数)
- [为什么不用 batch_size](#为什么不用-batch_size)
- [为什么省算力](#为什么省算力)
- [快速开始](#快速开始)
- [成品落在哪](#成品落在哪)
- [依赖](#依赖)
- [仓库结构](#仓库结构)
- [工作原理](#工作原理)
- [文档](#文档)
- [限制](#限制)
- [贡献](#贡献)
- [致谢](#致谢)
- [许可](#许可)

---

### 一眼看懂

| | |
| --- | --- |
| **输入** | 3–5 个关键帧提示词，写成一张「剧情卡」（主体锁定 + 画风锁定 + 每拍动作） |
| **引擎** | ComfyUI + `LatentInterpolate` ×N + `ImageBatchMulti(N)` |
| **输出** | APNG、WebP、GIF 各一个文件；8 / 12 / 24 / 30 / 60 帧；无限循环 |
| **模型** | 不限：SDXL checkpoint（UNet）或 DiT 三件套——MOSS-Image / FLUX / SD3 / Krea / Anima（只认结构不认模型名） |
| **脚本** | 纯标准库 + Pillow，工具链不需要 GPU |
| **平台** | Windows / macOS / Linux，路径全部来自 `profiles/*.json` |

### 模型支持

工作流的结构契约与模型无关：**1 个 `denoise=1.0` 的 KSampler + 2–4 个关键帧 KSampler +
N 个 `LatentInterpolate` + N 个 `VAEDecode` + `ImageBatchMulti(N)` + 3 个保存节点**，N 就是帧数
（`--frames`，8–60）。换模型只换加载器，不动结构；`emit_workflow.py` 会自动把插值 / 解码 / 合批
三件套扩缩到 N。

**DiT 是架构，MOSS 是模型。** DiT（Diffusion Transformer，arXiv:2212.09748）是把 U-Net 主干换成
transformer 的那一族；SDXL 是 UNet，MOSS-Image / FLUX / SD3 / Krea / Anima 是 DiT。
配置时真正独立的是三层：架构（决定 denoise 区间）、文本编码器（决定怎么写提示词）、步数范式（决定 steps 与 cfg）。

| 模型族 | 架构 | 文本编码器 | 加载器 | 关键帧 denoise | 说明 |
| --- | --- | --- | --- | --- | --- |
| SD 1.5 | UNet | CLIP | `CheckpointLoaderSimple` | 0.45–0.55 | 原生 512×512 |
| SDXL / Illustrious / NoobAI | UNet | CLIP-L + CLIP-G | `CheckpointLoaderSimple` | 0.35–0.45 | 原生 1024×1024，512 也能跑 |
| FLUX.1 | DiT | CLIP-L + T5-XXL | `UNETLoader` + `DualCLIPLoader` + `VAELoader` | 0.45–0.55 | 采样器前加 `FluxGuidance`（3.5），cfg 1.0 |
| SD3 / SD3.5 | MMDiT | CLIP-L + CLIP-G + T5-XXL | `CheckpointLoaderSimple` 或三件套 | 0.40–0.50 | cfg 4–7 |
| MOSS-Image | DiT + 8 步 DMD | Qwen3.5-9B | `UNETLoader` + `CLIPLoader`（`type=moss_image`）+ `VAELoader` | 0.82–0.90 | steps 8，cfg 1.0；低于 0.80 几乎不动（整片相邻帧差 0.03），超过 0.90 开始漂 |
| Krea 2 | DiT | Qwen3-VL 4B | `UNETLoader` + `CLIPLoader` + `VAELoader` | 0.45–0.55 | Raw 20–30 步 / Turbo 4–8 |
| Anima 2B | DiT | Qwen3-0.6B | `UNETLoader` + `CLIPLoader` + `VAELoader` | 0.45–0.55 | Base 30–50 步 / Turbo 8–12 |
| 任意微调模型 | 跟随其基座 | 跟随其基座 | 跟随其基座 | 先 0.35 | 越低越稳，越高越自由 |

逐个模型的加载器、步数与出处：[docs/models.md](docs/models.md) · [English](docs/en/models.md)。

denoise 区间是实拍经验，不是硬性规格。同 seed 下 **SDXL 的稳定上限约 0.35**：
超过 0.42 后关键帧重绘会开始改衣服和背景，latent 插值再把两套纹理混成色斑。
要更大表情就提 denoise 并接受漂移，或者只对面部做局部重绘。

### 帧数怎么选

帧数是参数，不是另一套方法。`--frames 8|12|24|30|60`（或剧情卡里的 `"frames"`）会把
`LatentInterpolate` / `VAEDecode` / `ImageBatchMulti` 重建成 N 个；`--segs` 决定 N 怎么分到每一拍，
不给就平均分。

`fps` 决定总时长（`frames / fps`），`dwell` 决定这段时间怎么分给每一拍。
GIF 的帧延时只能量化到 10ms：24fps 会被写成 40ms，「2.5 秒」实际跑 2.4 秒。20 / 25fps 能整除，不会走样。

| 帧数 | 慢（叙事） | 标准 | 快（弹幕感） | 4 拍 segs 示例 |
| --- | --- | --- | --- | --- |
| 8 | 6fps / 1.33 s | 8fps / 1.00 s | 10fps / 0.80 s | `2,2,2,2` |
| 24 | 8fps / 3.00 s | 10fps / 2.40 s | 12fps / 2.00 s | `6,7,6,5` |
| 30 | 10fps / 3.00 s | 15fps / 2.00 s | 20fps / 1.50 s | `8,8,7,7` |
| 60 | **20fps / 3.00 s**（默认） | 25fps / 2.40 s | 30fps / 2.00 s | `5,5,4,7,6,7,5,6,5,5,5` |

不管选哪一行，采样次数都还是 K 次（每个关键帧一次），只有解码次数和文件体积随 N 线性增长。
同内容下 60 帧 APNG 约为 24 帧的 2.5 倍；画面细节越多单帧越大，实测雨夜 60 帧 APNG 为 17 MB。见 [docs/formats.md](docs/formats.md)。
上面是 **60 帧 / 20fps / 3.0 秒 / MOSS-Image（DiT + DMD）** 的十一拍故事《减肥破功》：坐直立志 → 肩塌 → 趴桌 → 抬头看地板 →
侧身够手机 → 低头看屏 → 抱炸鸡桶 → 伸手进桶 → 举鸡腿偷吃 → 放下 → 扶住沙拉碗握拳「明天再减」。
配方在 [`assets/story.diet.json`](assets/story.diet.json)，`prompt_mode: moss_zh`，
节拍 `5,5,4,7,6,7,5,6,5,5,5`，denoise 0.85，640×640。
每拍停留权重 `0.95, 0.95, 1.1, 1.3, 1.0, 1.3, 0.95, 1.0, 0.9, 0.95, 0.95`，`ease: 0.3`：
够手机和抱炸鸡桶这两拍多停，只动肩头的拍快过。
每拍之间由 `LatentInterpolate` 补过渡帧，关键帧在时间线上只出现一次，接缝不会停一帧；
分帧方法见 [docs/workflows.md](docs/workflows.md#过渡帧怎么排)。
下面那张联系表是按 `--segs` 从成片里抽出来的真实关键拍，不是示意图。

### 动作库

`assets/motion-presets.json` 带 17 组可直接用的动作节拍：9 组情绪（大笑 / 大哭 / 震惊 / 生气 / 得意 / 无语 / 慌张 / 困 / 比心）、
5 组动作（打招呼 / 点头 / 摇头 / 点赞 / 思考）、2 组五拍小故事（雨天出门 / 早八续命）、1 组十一拍全身故事（减肥破功，`moss_zh` 中文散文）。
`scripts/make_story.py` 把它们和你的角色锁定句拼成剧情卡，再交给 `emit_workflow.py`：

```bash
python scripts/make_story.py --list
python scripts/make_story.py --preset laugh --lock "masterpiece, 1girl, silver hair, blue eyes" --out story.laugh.json
python scripts/make_story.py --preset rainy-walk --lock "masterpiece, 1girl" --frames 60 --fps 30 --out story.rain.json
```

动作语法、平台规格（Telegram 512/≤3 秒/60fps、LINE APNG 5–20 帧/≤4 秒/≤1 MB、微信 GIF 240²/≤500 KB）
与七个常见翻车点见 [docs/motion-presets.md](docs/motion-presets.md)。

### 可调参数

下面这些都能在 ComfyUI 里直接改，不需要跑脚本。

| 范围 | 节点 | 控制什么 |
| --- | --- | --- |
| 全片 | `CLIPTextEncode`「全局动作指导」 | 动作、镜头、光照、风格；改一处，所有关键帧生效 |
| 每帧 | `CLIPTextEncode`「K0 / K1 / … 提示」 | 表情、姿态、视线 |
| 每帧采样 | 每个 `KSampler` | seed、steps、cfg、采样器、调度器、denoise |
| 节奏 | N 个 `LatentInterpolate` 的 ratio | 缓动曲线；`linear` 最均匀 |
| 速度 | 三个保存节点的 `fps` | 三处必须一致；`fps × 帧数` = 时长（24 帧 @12fps = 2.0 秒） |
| 提示词方言 | `--prompt-mode tags|moss_zh` | `tags` = CLIP 英文标签；`moss_zh` = Qwen-VL 中文散文 |
| 每拍停留 | 剧情卡 `dwell` + `ease` | 每拍停多久；由 `retime.py` / `make_preview.py` 施加，像素不动 |
| 尺寸 | latent 节点的宽高 / `--size 640` | MOSS-Image 512 或 640；SDXL 512–1024 |
| 命名 | `filename_prefix` | `apng/`、`webp/`、`gif/` 子目录 |
| 画质 | APNG `compress_level`、WebP `lossless`/`quality`、VHS `loop`/`pingpong` | 体积与播放行为 |

工作流里自带一个 `Note` 节点，把这张表写在画布上，不用翻文档找旋钮。

### 动态帧数模式（图上直接调）

帧数是节点上的数字，不是图的结构。先装一次随包节点：

```bash
python scripts/install_nodes.py --profile xl   # 装到 <comfy_root>/custom_nodes/apng_motion_nodes
```

再用 `--dynamic` 出图：

```bash
python scripts/emit_workflow.py --base workflows/workflow-sdxl.json \
    --story assets/story.example.json --dynamic --out my-dynamic.json
```

加整段镜头运动（平移 / 缩放 / 旋转，缓动曲线驱动）：

```bash
python scripts/emit_workflow.py --base workflows/workflow-sdxl.json \
    --story assets/story.example.json --dynamic --camera --out my-dynamic-camera.json
```

3 拍 24 帧从 67 个节点变成 **26 个节点 / 39 条连线**，加 `--camera` 是 27 个。每拍一个 `APNG Latent Interpolate N`，
`frames` / `role` / `curve` 都是图上的 widget；一个 `VAEDecode` 解完全部帧；`APNG Frame Stats`
在存盘前打印帧数、`frames/fps` 时长、相邻帧差（min/max/avg、相同帧对数）、每拍接缝和循环接缝，
阈值与 `check_anim.py` 一致。

| 维度 | 图上位置 |
| --- | --- |
| 帧数 | 每个插值节点的 `frames` |
| 时长 | 三个保存节点 + 报告节点的 `fps` |
| 相邻帧差 | `APNG Frame Stats` 输出 |
| 接缝唯一性 | 报告节点的 `segs` |
| 分镜 / 故事板 | K 个关键帧 KSampler，结构不变 |
| 镜头运动 | `APNG Camera Move` 的 `x`/`y`/`zoom`/`angle`/`easing`/`loop`，整段统一变换 |

逐帧停留和拍内缓动仍不能在工作流里表达（保存节点只有一个全局 `fps`），出片后用 `retime.py`。
完整页：[docs/dynamic.md](docs/dynamic.md)。

### 工作流

十份 JSON，拖进 ComfyUI 就能跑（四份动态帧数的先装 `comfyui_nodes`）：

懒得搭图也可以用单节点 `APNG One Shot`：`model/clip/vae/positive/negative` 直接出 `IMAGE`，内部等价于动态图（K 拍各采样一次，不是逐帧重绘）。

| 环境 | 3 拍 | 4 拍 |
| --- | --- | --- |
| SDXL | [`workflow-sdxl.json`](workflows/workflow-sdxl.json) | [`workflow-sdxl-4beat.json`](workflows/workflow-sdxl-4beat.json) |
| DiT 系（MOSS-Image） | [`workflow-moss.json`](workflows/workflow-moss.json) | [`workflow-moss-4beat.json`](workflows/workflow-moss-4beat.json) |
| 动态帧数（UNet，3 拍 24 帧） | [`workflow-sdxl-dynamic.json`](workflows/workflow-sdxl-dynamic.json) | — |
| 动态帧数（DiT，3 拍 24 帧） | [`workflow-moss-dynamic.json`](workflows/workflow-moss-dynamic.json) | — |
| 动态帧数 + 镜头（UNet，3 拍 24 帧） | [`workflow-sdxl-dynamic-camera.json`](workflows/workflow-sdxl-dynamic-camera.json) | — |
| 动态帧数 + 镜头（DiT，3 拍 24 帧） | [`workflow-moss-dynamic-camera.json`](workflows/workflow-moss-dynamic-camera.json) | — |

`moss` 只是历史文件名，图里装的是任何 DiT 模型：换成 FLUX / SD3 / Krea / Anima 只换三个加载器，结构不动。

画布上自带两个 `Note`：一个是「可调参数清单」，一个是「提示词写法（按架构分方言）」，
两套编码器的写法和帧数表都写在节点里，不用翻文档。
下载页与导入细节：[docs/workflows.md](docs/workflows.md)。

### 提示词怎么写

写法跟**文本编码器**走，不跟模型名走。三种方言覆盖上表全部模型，完整规则在
[docs/prompting.md](docs/prompting.md) · [English](docs/en/prompting.md)。

| 编码器 | 谁在用 | 方言 | 一句话记法 |
| --- | --- | --- | --- |
| CLIP | SD 1.5、SDXL、Illustrious、NoobAI | `tags` | 逗号堆词，画风放最后 |
| Qwen-VL | MOSS-Image、Krea 2、Qwen-Image、Anima | `moss_zh` | 分段散文，每段句号结尾 |
| T5 | FLUX.1、SD3 / SD3.5 | 散文 | 完整英文句子，不用 `(word:1.3)` |

**CLIP 标签**

```
1girl, solo, full body, black short hair, blue eyes, beige hoodie, dark shorts,
barefoot, bedroom at night, warm lamp light, 〈这一拍动作〉,
anime screencap, clean lineart, flat cel shading
```

写画面不写效果：`eyes wide, pupils small`，不写 `shocked`。

**Qwen-VL 中文散文**

```
一间温馨的小卧室，深夜。画面右侧有一盏暖色台灯，光从右前方斜照下来，落在木地板上。
固定机位，平视，全身镜头，人物从头到脚完整入画，双手和双脚都留在画框里。
小满：黑色短发，蓝色眼睛，身材微胖，穿着宽松的米色连帽卫衣和深色短裤，赤脚。
小满盘腿坐在矮桌前，背挺得很直，双手叉在腰上，抬起下巴，嘴角只上扬几毫米。
动漫赛璐璐风格，干净黑色线稿，平涂上色，暖色调，柔和阴影。
```

不堆 quality tag——`masterpiece` / `best quality` 对 Qwen-VL 是噪声。用可测量的身体描述代替形容词。

**T5 句子**：一句话一件事，不加权重括号。

每一拍**只改一个变量**。改两个，插值出来就是两张不同的脸。画面里要出现文字时，用绝对像素
bbox，画布边长取 16 的倍数——细则在提示词那一页。

### 为什么不用 batch_size

`batch_size=24` 是 **24 个互相独立的噪声样本**。固定 seed 只保证可复现，不会让它们变成连续帧，
播放必然闪。本项目的做法是把每个关键帧都锚在**同一份首帧 latent** 上，发色、瞳色、构图都不漂：

```
首帧（denoise 1.0，固定 seed）
   ├─ 关键帧 A（从首帧 latent 重绘，denoise 0.4/0.5）
   ├─ 关键帧 B …（同一份 latent）
   └─ 关键帧 C …（可选，做 4–5 拍）
N × LatentInterpolate → N × VAEDecode → ImageBatchMulti(N)
   ├─ SaveAnimatedPNG
   ├─ SaveAnimatedWEBP
   └─ VHS_VideoCombine（GIF）
```

### 为什么省算力

一次只花 **K 次采样，不是 N 次**——帧数怎么改都不影响这一条：

| 拍数 | 采样次数（steps=20） | 相对 24 帧逐帧（480 次） | 相对 60 帧逐帧（1200 次） |
| --- | --- | --- | --- |
| 3 拍 | 3 × 20 = 60 | 少 87.5% | 少 95.0% |
| 4 拍 | 4 × 20 = 80 | 少 83.3% | 少 93.3% |
| 5 拍 | 5 × 20 = 100 | 少 79.2% | 少 91.7% |

所以从 24 帧加到 60 帧，**采样成本一点没涨**；随 N 增长的只有 VAE 解码次数和文件体积。

解码仍然是 N 次，但插值只是 N 次 `64×64×4` latent 线性混合，不调用模型，占用是几十 MB 级缓冲而不是几 GB。代价是没有真实运动轨迹；换来的是采样成本降到零头、成品到处能播。

和 Live2D / Spine、视频生成、序列帧、Lottie 的完整对比：[docs/synthesis-comparison.md](docs/synthesis-comparison.md)。

### 快速开始

```powershell
git clone https://github.com/Gg22333/comfyui-apng-motion.git
cd comfyui-apng-motion

python scripts/detect_env.py      # 扫本机 ComfyUI，写 profiles/
python scripts/doctor.py          # 体检模型、插件、端口、输出目录
python scripts/emit_workflow.py --base workflows/workflow-sdxl.json --story assets/story.4beat.json --out my-4beat.json
```

把 `my-4beat.json` 拖进 ComfyUI，改提示词，Queue。
成品在 `output/APNG/final/{apng,webp,gif}/`，一次 Queue 三个文件。
检查目录结构、归档游离文件：

```powershell
python scripts/check_output.py --profile profiles/xl.json
python scripts/check_output.py --profile profiles/xl.json --fix
```

不开界面（校验 + 提交 + 自动验片）：

```powershell
python scripts/emit_workflow.py --validate my-4beat.json --run --profile profiles/xl.json
```

### 依赖

| 依赖 | 版本 | 必需 | 缺了会怎样 |
| --- | --- | --- | --- |
| Python | ≥ 3.9 | 是 | 脚本跑不起来 |
| Pillow | ≥ 9.0 | 仅校验 | `check_anim.py` 不可用，出片不受影响 |
| ComfyUI | ≥ 0.3 | 是 | 没有 `SaveAnimatedPNG` / `SaveAnimatedWEBP` |
| [comfyui-kjnodes](https://github.com/kijai/ComfyUI-KJNodes) | 任意 | 是 | `ImageBatchMulti` 爆红 |
| [ComfyUI-VideoHelperSuite](https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite) | 任意 | 否 | 只少 GIF |

```powershell
python scripts/check_deps.py
pip install -r requirements.txt
```

建议用 ComfyUI 自带的 Python 跑校验——它已经装了 Pillow。

### 仓库结构

```
SKILL.md              完整方法（原理 / 剧情卡 / 多角色 / 排错 / 移植）
skill.json            版本、依赖、入口、安装目标
scripts/              探测、体检、生成工作流、动作库→剧情卡、校验成品、曲线、安装、打包
workflows/            可直接导入的工作流（UNet/SDXL + DiT/MOSS，各 3/4 拍）
assets/               17 组动作库、剧情卡（含带 dwell 的 moss_zh 故事卡）、节点定义兜底
docs/                 中文文档；英文在 docs/en/
tests/                离线单测（不联网、不用 GPU）
profiles/             每台机器生成（已 gitignore）
dist/                 打包产物（已 gitignore）
```

### 工作原理

1. **关键帧**：首帧 txt2img；其余关键帧都从首帧 latent 做 img2img。
2. **插值**：24 个 `LatentInterpolate` 沿缓入缓出曲线在关键帧之间走。
3. **解码与合批**：24 次解码合成一个 batch，三个编码器读同一份 batch。
4. **验片**：`check_anim.py` 报告帧数、时长、循环、相邻帧差异与颜色漂移。

曲线取值、Pillow 为什么会合并相同帧、GIF 为什么是 1/100 秒，见
[docs/formats.md](docs/formats.md) 与 [SKILL.md](SKILL.md)。

### 文档

| | 中文 | English |
| --- | --- | --- |
| 总览 | [docs/index.md](docs/index.md) | [docs/en/index.md](docs/en/index.md) |
| 安装 | [docs/install.md](docs/install.md) | [docs/en/install.md](docs/en/install.md) |
| 用法 | [docs/usage.md](docs/usage.md) | [docs/en/usage.md](docs/en/usage.md) |
| 模型与架构 | [docs/models.md](docs/models.md) | [docs/en/models.md](docs/en/models.md) |
| 提示词写法 | [docs/prompting.md](docs/prompting.md) | [docs/en/prompting.md](docs/en/prompting.md) |
| 工作流 | [docs/workflows.md](docs/workflows.md) | [docs/en/workflows.md](docs/en/workflows.md) |
| 动作库（17 组） | [docs/motion-presets.md](docs/motion-presets.md) | [docs/en/motion-presets.md](docs/en/motion-presets.md) |
| 成品落盘 | [docs/output.md](docs/output.md) | [docs/en/output.md](docs/en/output.md) |
| 方案对比 | [docs/synthesis-comparison.md](docs/synthesis-comparison.md) | [docs/en/synthesis-comparison.md](docs/en/synthesis-comparison.md) |
| 格式对比 | [docs/formats.md](docs/formats.md) | [docs/en/formats.md](docs/en/formats.md) |
| 架构 | [docs/architecture.md](docs/architecture.md) | [docs/en/architecture.md](docs/en/architecture.md) |
| 排错 | [docs/troubleshooting.md](docs/troubleshooting.md) | [docs/en/troubleshooting.md](docs/en/troubleshooting.md) |
| FAQ | [docs/faq.md](docs/faq.md) | [docs/en/faq.md](docs/en/faq.md) |

### 成品落在哪

一次 Queue 只往 **ComfyUI 自己的 `output/`** 写三个成品，不写进仓库：

```
<ComfyUI>/output/APNG/final/
├─ apng/anim24_00001_.png      # 无损 APNG，首帧可当静态图
├─ webp/anim24_00001_.webp     # 透明、体积最小
└─ gif/anim24_00001.gif        # 聊天用
   └─ anim24_00001.png         # VHS 首帧预览，可删
```

三条硬规则：

1. 三个保存节点接**同一个** `ImageBatchMulti` 输出；工作流里不放 `SaveImage` / `PreviewImage`。
2. 三个节点各用各的前缀：`APNG/final/apng|webp|gif/anim24`。
3. 改完前缀必须 **F5 刷新**再 Queue。前端会缓存旧值，旧前缀就是成品落到 `output/APNG/` 根目录的原因。

上面名字里的 `anim24` 是剧情卡 `name` 字段，换帧数时改成 `anim60` 之类即可，三个保存节点共用同一个前缀根。

没有同批 WebP/GIF 的单张 PNG，只是半次运行或旧前缀残留，不是成品。
`check_output.py` 会报 `stray_root`、`incomplete`、`outside_apng`，并识别正常的 `vhs_sidecar`；加 `--fix` 把游离文件移进 `output/APNG/archive/stray-<时间戳>/`。

仓库和 skill 目录里不放任何成品，也不放原始 APNG；`docs/assets/` 只有 `make_preview.py` 与 `make_storyboard.py` 生成的网页素材。
细则：[docs/output.md](docs/output.md)。

### 限制

- latent 插值**没有真实运动轨迹**：适合表情、呼吸、轻微头部动作；不适合走位、转身、镜头运动。
  这类需求要上 ControlNet 骨骼序列或视频模型（Wan / LTX）。
- 帧数是预算，不是画质旋钮：8–60 帧都能跑，解码耗时随 N 线性增长。24 帧是默认甜点，
  60 帧配 20fps 是 3 秒的叙事节拍。帧数再多也不会变出新姿势——它平滑的是过渡，不是轨迹。
- APNG 体积偏大（每帧整帧 PNG）。聊天发 GIF，要透明发 WebP。

### 贡献

见 [CONTRIBUTING.md](CONTRIBUTING.md) 与 [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)。提 PR 前先跑 `pytest -q`。

### 致谢

基于 ComfyUI、[ComfyUI-KJNodes](https://github.com/kijai/ComfyUI-KJNodes)、
[ComfyUI-VideoHelperSuite](https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite)。
仓库结构参考 [book-to-skill](https://github.com/virgiliojr94/book-to-skill)。

整段镜头（一条平移 / 缩放 / 旋转路径 + 按帧号取缓动）的思路参考
[ShmuelRonen/ComfyUI-AstralAnimator](https://github.com/ShmuelRonen/ComfyUI-AstralAnimator)。
该仓库没有许可证文件，**未复用任何代码**；`APNGCameraMove` 是
`torch.nn.functional.affine_grid` + `grid_sample` 的独立实现，不重新采样。

KJNodes、VideoHelperSuite 与 ComfyUI 本体都是 GPL-3.0。这里只在 workflow 里调用它们的节点，
没有把 GPL 源码抄进本仓库；`scripts/`、`tests/`、`workflows/`、`assets/`、`docs/` 全部是原创、
按 MIT 发布。细节见 [NOTICE](NOTICE)。

### 许可

MIT，见 [LICENSE](LICENSE) 与 [NOTICE](NOTICE)。

把代码、工作流或文档用到自己项目里：保留版权行和许可声明就行——这是 MIT 唯一的附加条件，
回链不强制、但欢迎。fork、修改、商用都允许。

MIT **不**授予两样东西：项目名 `comfyui-apng-motion` 和 Logo。fork 不得冒充官方仓库，
也不得暗示原作者背书。

要在论文或文章里引用，用 [CITATION.cff](CITATION.cff) 里的元数据——GitHub 侧栏会显示
"Cite this repository" 按钮。

</details>
