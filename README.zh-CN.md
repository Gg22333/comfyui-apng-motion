[English](README.md) · **简体中文**

# comfyui-apng-motion

[![CI](https://github.com/Gg22333/comfyui-apng-motion/actions/workflows/ci.yml/badge.svg)](https://github.com/Gg22333/comfyui-apng-motion/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/Gg22333/comfyui-apng-motion)](https://github.com/Gg22333/comfyui-apng-motion/releases)
[![License: MIT](https://img.shields.io/github/license/Gg22333/comfyui-apng-motion)](LICENSE)
[![Python](https://img.shields.io/badge/python-%3E%3D3.9-blue)](pyproject.toml)

在 ComfyUI 里用「3–5 个关键帧 + latent 插值」做 **24 帧连贯 APNG / WebP / GIF**。
不靠 `batch_size` 堆帧，不逐帧落盘，一次 Queue 出三个成品文件。

![预览](docs/assets/preview.gif)

---

## 目录

- [一眼看懂](#一眼看懂)
- [为什么不用 batch_size](#为什么不用-batch_size)
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

## 一眼看懂

| | |
| --- | --- |
| **输入** | 3–5 个关键帧提示词，写成一张「剧情卡」（主体锁定 + 画风锁定 + 每拍动作） |
| **引擎** | ComfyUI + `LatentInterpolate` ×24 + `ImageBatchMulti` |
| **输出** | APNG、WebP、GIF 各一个文件，24 帧，无限循环 |
| **模型** | 不限：SDXL checkpoint 或 Moss/DiT 三件套都可以（只认结构不认模型名） |
| **脚本** | 纯标准库 + Pillow，工具链不需要 GPU |
| **平台** | Windows / macOS / Linux，路径全部来自 `profiles/*.json` |

## 为什么不用 batch_size

`batch_size=24` 是 **24 个互相独立的噪声样本**。固定 seed 只保证可复现，不会让它们变成连续帧，
播放必然闪。本项目的做法是把每个关键帧都锚在**同一份首帧 latent** 上，发色、瞳色、构图都不漂：

```
首帧（denoise 1.0，固定 seed）
   ├─ 关键帧 A（从首帧 latent 重绘，denoise 0.4/0.5）
   ├─ 关键帧 B …（同一份 latent）
   └─ 关键帧 C …（可选，做 4–5 拍）
24 × LatentInterpolate → 24 × VAEDecode → ImageBatchMulti(24)
   ├─ SaveAnimatedPNG
   ├─ SaveAnimatedWEBP
   └─ VHS_VideoCombine（GIF）
```

## 快速开始

```powershell
git clone https://github.com/Gg22333/comfyui-apng-motion.git
cd comfyui-apng-motion

python scripts/detect_env.py      # 扫本机 ComfyUI，写 profiles/
python scripts/doctor.py          # 体检模型、插件、端口、输出目录
python scripts/emit_workflow.py --base assets/workflow-sdxl.json --story assets/story.4beat.json --out my-4beat.json
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

## 依赖

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

## 仓库结构

```
SKILL.md              完整方法（原理 / 剧情卡 / 多角色 / 排错 / 移植）
skill.json            版本、依赖、入口、安装目标
scripts/              探测、体检、生成工作流、校验成品、检查落盘、曲线、安装、打包
assets/               3 拍 / 4 拍工作流模板（SDXL + Moss）、剧情卡、节点定义兜底
docs/                 中文文档；英文在 docs/en/
tests/                离线单测（不联网、不用 GPU）
profiles/             每台机器生成（已 gitignore）
dist/                 打包产物（已 gitignore）
```

## 工作原理

1. **关键帧**：首帧 txt2img；其余关键帧都从首帧 latent 做 img2img。
2. **插值**：24 个 `LatentInterpolate` 沿缓入缓出曲线在关键帧之间走。
3. **解码与合批**：24 次解码合成一个 batch，三个编码器读同一份 batch。
4. **验片**：`check_anim.py` 报告帧数、时长、循环、相邻帧差异与颜色漂移。

曲线取值、Pillow 为什么会合并相同帧、GIF 为什么是 1/100 秒，见
[docs/formats.md](docs/formats.md) 与 [SKILL.md](SKILL.md)。

## 文档

| | 中文 | English |
| --- | --- | --- |
| 总览 | [docs/index.md](docs/index.md) | [docs/en/index.md](docs/en/index.md) |
| 安装 | [docs/install.md](docs/install.md) | [docs/en/install.md](docs/en/install.md) |
| 用法 | [docs/usage.md](docs/usage.md) | [docs/en/usage.md](docs/en/usage.md) |
| 成品落盘 | [docs/output.md](docs/output.md) | [docs/en/output.md](docs/en/output.md) |
| 格式对比 | [docs/formats.md](docs/formats.md) | [docs/en/formats.md](docs/en/formats.md) |
| 架构 | [docs/architecture.md](docs/architecture.md) | [docs/en/architecture.md](docs/en/architecture.md) |
| 排错 | [docs/troubleshooting.md](docs/troubleshooting.md) | [docs/en/troubleshooting.md](docs/en/troubleshooting.md) |
| FAQ | [docs/faq.md](docs/faq.md) | [docs/en/faq.md](docs/en/faq.md) |

## 成品落在哪

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

没有同批 WebP/GIF 的单张 PNG，只是半次运行或旧前缀残留，不是成品。
`check_output.py` 会报 `stray_root`、`incomplete`、`outside_apng`，并识别正常的 `vhs_sidecar`；加 `--fix` 把游离文件移进 `output/APNG/archive/stray-<时间戳>/`。

细则：[docs/output.md](docs/output.md)。

## 限制

- latent 插值**没有真实运动轨迹**：适合表情、呼吸、轻微头部动作；不适合走位、转身、镜头运动。
  这类需求要上 ControlNet 骨骼序列或视频模型（Wan / LTX）。
- 24 帧是刻意定的预算：10fps 下 2.4 秒；帧数越多解码耗时线性增长。
- APNG 体积偏大（每帧整帧 PNG）。聊天发 GIF，要透明发 WebP。

## 贡献

见 [CONTRIBUTING.md](CONTRIBUTING.md) 与 [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)。提 PR 前先跑 `pytest -q`。

## 致谢

基于 ComfyUI、[ComfyUI-KJNodes](https://github.com/kijai/ComfyUI-KJNodes)、
[ComfyUI-VideoHelperSuite](https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite)。
仓库结构参考 [book-to-skill](https://github.com/virgiliojr94/book-to-skill)。

## 许可

MIT，见 [LICENSE](LICENSE)。
