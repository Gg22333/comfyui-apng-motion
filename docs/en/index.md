# comfyui-apng-motion

A ComfyUI skill and toolkit for **24-frame, coherent APNG / WebP / GIF** animations.

![preview](../assets/preview.gif)

## What it fixes

| Common approach | Result |
| --- | --- |
| `batch_size=24` | 24 independent noise samples; playback flickers, a fixed seed does not help |
| Frame-by-frame inheritance | Motion is smooth, but hair and eye colour drift across frames |
| Saving every frame | The output folder fills with hundreds of PNGs |

This project instead: **sample the first frame once → redraw every keyframe from that same first latent → interpolate 24 latents → decode 24 times → merge → write three files.**

## Three steps

```bash
python scripts/detect_env.py
python scripts/doctor.py
python scripts/emit_workflow.py --base assets/workflow-sdxl.json --story assets/story.4beat.json --out my.json
```

## More

- [Install](install.md)
- [Usage](usage.md)
- [Output layout](output.md)
- [Approach comparison: APNG / GIF / Live2D / video](synthesis-comparison.md)
- [APNG, GIF and video-to-GIF](formats.md)
- [Architecture](architecture.md)
- [Troubleshooting](troubleshooting.md)
- [FAQ](faq.md)
