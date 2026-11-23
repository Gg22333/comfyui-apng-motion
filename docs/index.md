<div class="hero" markdown>

# comfyui-apng-motion

<p class="lead">在 ComfyUI 里把 3–8 个关键帧合成<strong>能讲故事</strong>的 APNG / WebP / GIF。
同一张工作流切 <strong>8 / 24 / 30 / 60 帧</strong>，UNet 系与 DiT 系两套环境都有可直接导入的 JSON。</p>

</div>

![60 帧预览](assets/preview.webp)

![十一拍分镜](assets/storyboard-diet.webp)

> **预览**：60 帧 / 20fps / 3.0 秒 / MOSS-Image（DiT + DMD），十一拍全身故事《减肥破功》。
> 配方在 `assets/story.diet.json`（`prompt_mode: moss_zh`），节拍 `5/5/4/7/6/7/5/6/5/5/5`。
> 分镜图是按 `--segs` 从成片里抽出的真实关键拍，不是示意图。
>
> 网页主预览用 WebP q100（真彩、保住 60 帧）；`preview.gif` 留给聊天工具。
> GIF 用全局固定调色板 + 关抖动重编码，避免 256 色量化造成的色块闪动。
> 细节见[格式对比](formats.md#46-网页预览为什么最终用-webp)。

<div class="grid cards" markdown>

- :material-filmstrip: **一条工作流，四种帧数**

    `--frames 8|24|30|60` 只改插值、解码、合批的节点数量，连线与模型不动。

- :material-camera-lock: **关键帧共用首帧 latent**

    每个 KSampler 都从同一份首帧 latent 重绘，发色、瞳色、构图不漂。

- :material-transition: **拍与拍之间补过渡帧**

    `LatentInterpolate` 在关键帧之间插值；`segs` 决定每拍占几帧，大动作多给帧，接缝不重复。

- :material-file-multiple: **一次出三个文件**

    APNG、WebP、GIF 同源输出，不再把几百张中间 PNG 塞满 `output/`。

</div>

## 它解决什么

| 错误做法 | 后果 |
| --- | --- |
| `batch_size=24` | 24 个独立噪声，播放必闪；固定 seed 也救不了 |
| 逐帧继承上一帧 | 动作顺了，但发色/瞳色会累积漂移 |
| 每帧都存图 | 输出目录被几百张 PNG 塞满 |
| 每段 ratio 都从 1.0 排到 0.0 | 段尾和下一段段首是同一关键帧，接缝停一帧 |

本项目的做法：**首帧一次采样 → 关键帧全部从同一份首帧 latent 重绘 → N 个 latent 插值 → N 次解码 → 合并 → 三个成品文件。**
每个关键帧在时间线上只出现一次；过渡帧由前后两拍的 latent 连线补出来。

## 三步

```bash
python scripts/detect_env.py
python scripts/doctor.py
python scripts/emit_workflow.py --base workflows/workflow-sdxl.json --story assets/story.4beat.json --out my.json
```

## 进一步

- [安装](install.md)
- [用法](usage.md)（含 [帧数怎么选](usage.md)、[提示词怎么写](workflows.md#提示词写法)）
- [工作流：五份可直接导入的 JSON](workflows.md) · [过渡帧怎么排](workflows.md#过渡帧怎么排)
- [动作库：17 组表情包动作](motion-presets.md)
- [成品落盘](output.md)
- [方案对比：APNG / GIF / Live2D / 视频](synthesis-comparison.md)
- [APNG、GIF 与视频转 GIF](formats.md)
- [架构](architecture.md)
- [排错](troubleshooting.md)
- [FAQ](faq.md)
- [发布](publishing.md)
