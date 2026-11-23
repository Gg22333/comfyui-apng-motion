# comfyui-apng-motion

ComfyUI 里做 **24 帧连贯 APNG / WebP / GIF** 的 skill 与工具箱。

![preview](assets/preview.gif)

## 它解决什么

| 错误做法 | 后果 |
| --- | --- |
| `batch_size=24` | 24 个独立噪声，播放必闪；固定 seed 也救不了 |
| 逐帧继承上一帧 | 动作顺了，但发色/瞳色会累积漂移 |
| 每帧都存图 | 输出目录被几百张 PNG 塞满 |

本项目的做法：**首帧一次采样 → 关键帧全部从同一份首帧 latent 重绘 → 24 个 latent 插值 → 24 次解码 → 合并 → 三个成品文件。**

## 三步

```bash
python scripts/detect_env.py
python scripts/doctor.py
python scripts/emit_workflow.py --base assets/workflow-sdxl.json --story assets/story.4beat.json --out my.json
```

## 进一步

- [安装](install.md)
- [用法](usage.md)
- [APNG、GIF 与视频转 GIF](formats.md)
- [架构](architecture.md)
- [排错](troubleshooting.md)
- [FAQ](faq.md)
- [发布](publishing.md)

