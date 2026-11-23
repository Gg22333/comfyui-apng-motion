# comfyui-apng-motion

[![CI](https://github.com/Gg22333/comfyui-apng-motion/actions/workflows/ci.yml/badge.svg)](https://github.com/Gg22333/comfyui-apng-motion/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-1.1.0-green.svg)](CHANGELOG.md)
[![Python](https://img.shields.io/badge/python-%3E%3D3.9-blue.svg)](https://www.python.org/)

An agent skill + toolkit for making **24-frame, coherent APNG / WebP / GIF** animations in ComfyUI.
No frame-by-frame scripts, no per-frame image dumps: three keyframes are interpolated in latent space,
decoded 24 times, batched, and saved as three single-file animations in one queue.

![preview](docs/assets/preview.gif)

## Why this exists

`batch_size=24` does **not** produce 24 consecutive frames — it produces 24 independent noise samples.
Fixed seeds only make the run reproducible, not continuous. This project replaces that with:

```
first frame (denoise 1.0)
   ├─ keyframe A (img2img from the first latent)
   └─ keyframe B / C / D ...
24 × LatentInterpolate → 24 × VAEDecode → ImageBatchMulti(24)
   ├─ SaveAnimatedPNG
   ├─ SaveAnimatedWEBP
   └─ VHS_VideoCombine (GIF)
```

Each keyframe is anchored to the **same** first-frame latent, so hair/eye color and composition
do not drift. Interpolation ratios are globally unique so Pillow never merges frames away.

## Quick start

```bash
git clone https://github.com/Gg22333/comfyui-apng-motion.git
cd comfyui-apng-motion

python scripts/detect_env.py      # find ComfyUI installs, write profiles/
python scripts/doctor.py          # check models, custom nodes, ports, output dir
python scripts/emit_workflow.py \
  --base assets/workflow-sdxl.json \
  --story assets/story.4beat.json \
  --out my-4beat.json
```

Drag `my-4beat.json` into ComfyUI, edit the prompts, hit Queue.

Headless (verify + run + check the produced files):

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
pip install -r requirements.txt          # Pillow
```

Tip: run verification with the Python bundled with ComfyUI — it already has Pillow.

## Repository layout

```
SKILL.md              the skill itself (principles, story cards, multi-character, troubleshooting)
skill.json            version, dependencies, entrypoints, install targets
scripts/              detect_env, doctor, emit_workflow, check_anim, make_curve, check_deps, install, package
assets/               workflow templates (3-beat / 4-beat), story cards, node schema fallback
docs/                 install, usage, architecture, troubleshooting, FAQ
tests/                offline unit tests (no GPU, no network)
profiles/             generated per machine, git-ignored
dist/                 packaging output, git-ignored
```

## Documentation

- [Install](docs/install.md)
- [Usage](docs/usage.md)
- [APNG vs GIF vs video](docs/formats.md)
- [Architecture](docs/architecture.md)
- [Troubleshooting](docs/troubleshooting.md)
- [FAQ](docs/faq.md)
- [Publishing this repo](docs/publishing.md)
- 中文说明：[README.zh-CN.md](README.zh-CN.md) · 完整方法：[SKILL.md](SKILL.md)

## Contributing

Issues and PRs are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) and
[CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md). Run `pytest -q` before opening a PR.

## License

MIT — see [LICENSE](LICENSE).

ComfyUI, ComfyUI-KJNodes and ComfyUI-VideoHelperSuite are separate projects under their own licenses.


