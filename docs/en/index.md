<div class="hero" markdown>

# comfyui-apng-motion

<p class="lead">Story-shaped <strong>APNG / WebP / GIF</strong> from 3–8 keyframes in ComfyUI.
One graph, <strong>8 / 24 / 30 / 60 frames</strong>, importable JSON for both the UNet family and the DiT family.</p>

</div>

![60-frame preview](../assets/preview.webp)

![eleven-beat storyboard](../assets/storyboard-diet.webp)

> **Preview**: the eleven-beat full-body story *Diet Betrayal*, 60 frames at 20 fps (3.0 s), MOSS-Image (DiT + DMD).
> Recipe: `assets/story.diet.json` (`prompt_mode: moss_zh`), segments `5/5/4/7/6/7/5/6/5/5/5`.
> The contact sheet is sampled from the real output by `--segs`, not a mock-up.
>
> The primary preview is WebP q100 (true colour, all 60 frames); `preview.gif` stays for chat apps.
> The GIF is re-encoded with one global palette and dithering off, so 256-colour quantisation no longer
> reads as flicker. See [formats](formats.md#46-why-the-web-preview-is-webp).

<div class="grid cards" markdown>

- :material-filmstrip: **One graph, four frame counts**

    `--frames 8|24|30|60` only resizes the interpolate / decode / merge nodes. Models and links stay put.

- :material-camera-lock: **Every keyframe shares the first latent**

    Each KSampler redraws from the same first-frame latent, so hair, eye colour and framing do not drift.

- :material-transition: **Transition frames between beats**

    `LatentInterpolate` fills the gap between keyframes; `segs` decides how many frames each beat gets.
    Big moves get more frames, and no beat is rendered twice at a seam.

- :material-file-multiple: **Three files per run**

    APNG, WebP and GIF from the same source. No hundreds of intermediate PNGs in `output/`.

</div>

## What it fixes

| Common approach | Result |
| --- | --- |
| `batch_size=24` | 24 independent noise samples; playback flickers, a fixed seed does not help |
| Frame-by-frame inheritance | Motion is smooth, but hair and eye colour drift across frames |
| Saving every frame | The output folder fills with hundreds of PNGs |
| Every segment ramps 1.0 → 0.0 | The segment end and the next segment start are the same keyframe, so playback stalls for one frame |

This project instead: **sample the first frame once → redraw every keyframe from that same first latent →
interpolate N latents → decode N times → merge → write three files.**
Each keyframe appears once on the timeline; the in-betweens come from the latent line between two beats.

## Three steps

```bash
python scripts/detect_env.py
python scripts/doctor.py
python scripts/emit_workflow.py --base workflows/workflow-sdxl.json --story assets/story.4beat.json --out my.json
```

## More

- [Install](install.md)
- [Usage](usage.md) · [How to lay out transition frames](workflows.md#how-to-lay-out-transition-frames)
- [Workflows: importable graphs](workflows.md)
- [Motion library: 17 sticker actions](motion-presets.md)
- [Output layout](output.md)
- [Approach comparison: APNG / GIF / Live2D / video](synthesis-comparison.md)
- [APNG, GIF and video-to-GIF](formats.md)
- [Architecture](architecture.md)
- [Troubleshooting](troubleshooting.md)
- [FAQ](faq.md)
