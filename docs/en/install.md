# Install

## 1 · Install as a skill

```bash
git clone https://github.com/Gg22333/comfyui-apng-motion.git
cd comfyui-apng-motion
python scripts/install.py
```

`install.py` reads the targets from `skill.json` and installs to:

- `~/.codex/skills/comfyui-apng-motion`
- `~/.config/magpie/library/skills/comfyui-apng-motion` (when the parent exists)

Custom location:

```bash
python scripts/install.py --dest /path/to/skills/comfyui-apng-motion
```

Upgrade: run it again. The previous `SKILL.md` is backed up as `.bak-<timestamp>`.

## 2 · Verify the install

```bash
python scripts/install.py --check
```

`SAME` means the source and installed trees match file by file; `DRIFT` lists the differences.

## 3 · Dependencies

```bash
python scripts/check_deps.py
pip install -r requirements.txt
```

| Dependency | Required | Notes |
| --- | --- | --- |
| Python ≥ 3.9 | yes | |
| Pillow ≥ 9 | verification only | Prefer the Python bundled with ComfyUI |
| ComfyUI ≥ 0.3 | yes | Needs native `SaveAnimatedPNG` / `SaveAnimatedWEBP` |
| comfyui-kjnodes | yes | `ImageBatchMulti` |
| ComfyUI-VideoHelperSuite | no | GIF output only |

## 4 · Detect the environment

```bash
python scripts/detect_env.py
python scripts/doctor.py
```

Results are written to `profiles/*.json` (not committed). Re-run on another machine.

## 5 · Package

```bash
python scripts/package.py
```

Artifacts land in `dist/`: `comfyui-apng-motion-<ver>.zip` and `.sha256`.
