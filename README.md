**English** · [简体中文](README.zh-CN.md)

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

## Workflows

Five JSON files, drop one into ComfyUI and queue:

| Environment | 3 beats | 4 beats |
| --- | --- | --- |
| UNet family (SDXL) | [`workflow-sdxl.json`](workflows/workflow-sdxl.json) | [`workflow-sdxl-4beat.json`](workflows/workflow-sdxl-4beat.json) |
| DiT family (MOSS-Image) | [`workflow-moss.json`](workflows/workflow-moss.json) | [`workflow-moss-4beat.json`](workflows/workflow-moss-4beat.json) |

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
