# 安装

## 1 · 作为 skill 安装

```bash
git clone https://github.com/Gg22333/comfyui-apng-motion.git
cd comfyui-apng-motion
python scripts/install.py
```

`install.py` 会读取 `skill.json` 里的目标，装到：

- `~/.codex/skills/comfyui-apng-motion`
- `~/.config/magpie/library/skills/comfyui-apng-motion`（父目录存在时）
- `~/.claude/skills/comfyui-apng-motion`（`~/.claude/skills` 存在时）
- `~/.dsh/skills/comfyui-apng-motion`（`~/.dsh/skills` 存在时，DSH / DeepSeek harness）
- `~/.workbuddy/skills/comfyui-apng-motion`（`~/.workbuddy/skills` 存在时）

指定位置：

```bash
python scripts/install.py --dest /path/to/skills/comfyui-apng-motion
```

`SKILL.md` 是 Agent Skills 格式（`name` + `description` frontmatter），没有 Codex 私有字段。其它客户端放进各自的 skill 目录即可：

| 客户端 | 目标 |
| --- | --- |
| Codex | `~/.codex/skills/comfyui-apng-motion` |
| Claude Code | `~/.claude/skills/comfyui-apng-motion`（bootstrap 自动装；或项目内 `.claude/skills/`；未在本仓库 CI 实测） |
| DSH（DeepSeek harness） | `~/.dsh/skills/comfyui-apng-motion`（bootstrap 自动装） |
| WorkBuddy | `~/.workbuddy/skills/comfyui-apng-motion`（用户级 skills 目录；bootstrap 自动装） |
| 任意目录 | `python scripts/install.py --dest <dir>/comfyui-apng-motion` |

脚本只依赖 Python ≥3.9 + Pillow，Windows / Linux 都能跑；ComfyUI 本身按目标机器单独安装。

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
