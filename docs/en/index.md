# comfyui-apng-motion

A ComfyUI skill and toolkit for **coherent APNG / WebP / GIF** animations — 8, 12, 24, 30 or 60 frames.

![preview](../assets/preview.webp)

> Preview: 60 frames at 30 fps, Moss/DiT — recipe in `assets/story.preview.json`.
> The primary preview is WebP q100 (true colour, all 60 frames; libwebp merges near-duplicates at q90); `preview.gif` remains for
> chat apps. The GIF is re-encoded with one global palette and dithering off, so 256-colour
> quantisation no longer reads as flicker. See [formats](formats.md#46-why-the-web-preview-is-webp).

## What it fixes

| Common approach | Result |
| --- | --- |
| `batch_size=24` | 24 independent noise samples; playback flickers, a fixed seed does not help |
| Frame-by-frame inheritance | Motion is smooth, but hair and eye colour drift across frames |
| Saving every frame | The output folder fills with hundreds of PNGs |

This project instead: **sample the first frame once → redraw every keyframe from that same first latent → interpolate N latents → decode N times → merge → write three files.**

## Three steps

```bash
python scripts/detect_env.py
python scripts/doctor.py
python scripts/emit_workflow.py --base assets/workflow-sdxl.json --story assets/story.4beat.json --out my.json
```

## More

- [Install](install.md)
- [Usage](usage.md)
- [Motion library: 16 sticker actions](motion-presets.md)
- [Output layout](output.md)
- [Approach comparison: APNG / GIF / Live2D / video](synthesis-comparison.md)
- [APNG, GIF and video-to-GIF](formats.md)
- [Architecture](architecture.md)
- [Troubleshooting](troubleshooting.md)
- [FAQ](faq.md)
