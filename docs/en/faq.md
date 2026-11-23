# FAQ

**Why not `batch_size`?**
`batch_size=N` is N independent noise samples. A fixed seed makes them reproducible, not continuous.

**Why not generate every frame like a video?**
Frame-by-frame img2img needs 24 samples and accumulates drift (black hair turning cyan). Interpolation needs 3–5 samples; in-between frames come from a mathematical transition.

**Why 24 frames?**
2.4 s at 10 fps, enough for "start → turn → settle". Below 16 frames looks like a slideshow; above 32 the returns diminish.

**Why 10 fps by default?**
GIF delay is in 1/100 s; 10 fps = 10cs exactly. 12 fps becomes 8cs (12.5 fps).

**Why is the motion so small?**
Raise keyframe `denoise` (xl 0.4 → 0.45, Moss 0.5 → 0.55) or increase the difference between A/B prompts. Do not add frames.

**Can the character walk?**
No. This route has no real trajectory. Walking and turning need a ControlNet pose sequence or a video model (Wan / LTX).

**Does it support Flux / SD1.5 / other models?**
Yes. `emit_workflow.py` only cares about structure (one denoise=1 KSampler + ≥2 keyframes + 24 interpolations + 24 decodes + a 24-way merge + 3 outputs); swap the model names.

**Is a GPU required?**
For rendering, yes. `detect_env` / `doctor` / `emit_workflow` / `check_anim` / `check_output` are CPU-side tools.

**APNG or GIF?**
See [APNG, GIF and video-to-GIF](formats.md). Short version: GIF for chat, WebP for web/transparency, APNG for documents and lossless.

**Why is GIF sometimes smaller than APNG?**
GIF is 256 colours plus LZW, which suits flat anime very well; APNG stores every frame losslessly.

**Where do the files go?**
`output/APNG/final/{apng,webp,gif}/`. See [Output layout](output.md).

**Commercial use?**
The code is MIT. Models and generated content follow their own licences and local law.
