# 安装

## 1 · 作为 skill 安装

```bash
git clone https://github.com/yourname/comfyui-apng-motion.git
cd comfyui-apng-motion
python scripts/install.py
```

`install.py` 会读取 `skill.json` 里的目标，装到：

- `~/.codex/skills/comfyui-apng-motion`
- `~/.config/magpie/library/skills/comfyui-apng-motion`（父目录存在时）

指定位置：

```bash
python scripts/install.py --dest /path/to/skills/comfyui-apng-motion
```

升级：重新跑一次。旧 `SKILL.md` 自动备份成 `.bak-<时间戳>`。

## 2 · 校验安装

```bash
python scripts/install.py --check
```

输出 `SAME` 表示源目录与安装目录逐文件一致；`DRIFT` 会列出差异文件。

## 3 · 依赖

```bash
python scripts/check_deps.py
pip install -r requirements.txt
```

| 依赖 | 必需 | 说明 |
| --- | --- | --- |
| Python ≥ 3.9 | 是 | |
| Pillow ≥ 9 | 仅校验 | 建议直接用 ComfyUI 自带 Python |
| ComfyUI ≥ 0.3 | 是 | 需原生 `SaveAnimatedPNG` / `SaveAnimatedWEBP` |
| comfyui-kjnodes | 是 | `ImageBatchMulti` |
| ComfyUI-VideoHelperSuite | 否 | 只影响 GIF |

## 4 · 探测环境

```bash
python scripts/detect_env.py
python scripts/doctor.py
```

探测结果写到 `profiles/*.json`（不进版本库）。换机器重跑即可。

## 5 · 分发

```bash
python scripts/package.py
```

产物在 `dist/`：`comfyui-apng-motion-<ver>.zip` 与 `.sha256`。
