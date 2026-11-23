# comfyui-apng-motion

[![CI](https://github.com/yourname/comfyui-apng-motion/actions/workflows/ci.yml/badge.svg)](https://github.com/yourname/comfyui-apng-motion/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-1.1.0-green.svg)](CHANGELOG.md)

ComfyUI 里用「首帧 + 关键帧 latent 插值」做 **24 帧连贯 APNG / WebP / GIF** 的 skill 与工具箱。
不靠 `batch_size` 堆帧，不逐帧落盘，一次 Queue 出三个成品文件。

![预览](docs/assets/preview.gif)

## 为什么不是 batch_size

`batch_size=24` 是 **24 个互相独立的噪声样本**。固定 seed 只保证可复现，不会让它们变成连续帧。
正确结构是：首帧采样一次 → A/B（可扩到 C/D）都从同一份首帧 latent 重绘 → 24 个 `LatentInterpolate`
在关键帧之间插值 → 24 次解码 → 合并 → 三格式输出。所有关键帧锚在同一份 latent 上，发色/瞳色/构图不漂。

## 快速开始

```powershell
git clone https://github.com/yourname/comfyui-apng-motion.git
cd comfyui-apng-motion

python scripts/detect_env.py      # 扫本机 ComfyUI，写 profiles/
python scripts/doctor.py          # 体检模型、插件、端口、输出目录
python scripts/emit_workflow.py --base assets/workflow-sdxl.json --story assets/story.4beat.json --out my-4beat.json
```

把 `my-4beat.json` 拖进 ComfyUI，改提示词，Queue。

不开界面：

```powershell
python scripts/emit_workflow.py --validate my-4beat.json --run --profile profiles/xl.json
```

## 依赖

| 依赖 | 版本 | 必需 | 缺了会怎样 |
| --- | --- | --- | --- |
| Python | ≥ 3.9 | 是 | 脚本跑不起来 |
| Pillow | ≥ 9.0 | 仅校验 | `check_anim.py` 不可用，出片不受影响 |
| ComfyUI | ≥ 0.3 | 是 | 没有 `SaveAnimatedPNG` / `SaveAnimatedWEBP` |
| `comfyui-kjnodes` | 任意 | 是 | `ImageBatchMulti` 爆红 |
| `ComfyUI-VideoHelperSuite` | 任意 | 否 | 只少 GIF |

```powershell
python scripts/check_deps.py
pip install -r requirements.txt
```

建议用 ComfyUI 自带的 Python 跑校验——它已经装了 Pillow。

## 仓库结构

```
SKILL.md              完整方法（原理 / 剧情卡 / 多角色 / 排错 / 移植）
skill.json            版本、依赖、入口、安装目标
scripts/              探测、体检、生成工作流、校验、曲线、安装、打包
assets/               3 拍 / 4 拍工作流模板、剧情卡、节点定义兜底
docs/                 安装、用法、架构、排错、FAQ
tests/                离线单测（不联网、不用 GPU）
profiles/             每台机器生成，已 gitignore
dist/                 打包产物，已 gitignore
```

## 文档

- [安装](docs/install.md)
- [用法](docs/usage.md)
- [APNG、GIF 与视频转 GIF](docs/formats.md)
- [架构](docs/architecture.md)
- [排错](docs/troubleshooting.md)
- [FAQ](docs/faq.md)
- [发布这个仓库](docs/publishing.md)
- English: [README.md](README.md)

## 贡献

见 [CONTRIBUTING.md](CONTRIBUTING.md) 与 [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)。提 PR 前先跑 `pytest -q`。

## 许可

MIT，见 [LICENSE](LICENSE)。ComfyUI、ComfyUI-KJNodes、ComfyUI-VideoHelperSuite 是各自独立项目，遵循各自许可。

