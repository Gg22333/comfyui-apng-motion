# Animation approaches compared: APNG, GIF, Live2D and video generation

This page answers three questions:

1. **What APNG actually is**, and how it differs from GIF.
2. How this project's "keyframes + latent interpolation" relates to **Live2D / Spine**, frame-by-frame AI and video generation.
3. Why this route is significantly cheaper in **compute**.

---

## 1 · The short answer

| Approach | How it is made | Interactive | Runtime dependency | Relative cost | Best for |
| --- | --- | --- | --- | --- | --- |
| **This project** | 3–5 keyframes → latent interpolation → N frames (8–60, default 24) → APNG/WebP/GIF | No | None; browsers and chat apps play it | **Low**: K samples + N decodes | Stickers, micro-performance, docs |
| Frame-by-frame AI | 24 independent img2img runs | No | None | High: 24 samples | Per-frame precision |
| `batch_size=24` | One sample, 24 independent noise images | No | None | Medium, but always flickers | Not recommended |
| Video generation → GIF | Video model → MP4/WebM → frame extraction/quantization | No | None (deliverable) | Very high: temporal model + transcode | Walking, turning, real motion |
| **Live2D / Spine** | Layered art + mesh rigging + parameter curves, deformed at runtime | **Yes** | Needs an SDK/player | High art/rigging cost; interactive at runtime | VTubers, game sprites, interactive characters |
| Hand-drawn sequence | An artist draws every frame | No | None | Highest labour cost | High-budget animation |
| Lottie / Rive | Vector keyframes + runtime interpolation | Yes | Needs a runtime | Tiny files, unsuitable for painterly raster art | UI motion, vector illustration |

In one sentence: **Live2D brings a character to life and accepts input; this project bakes one micro-performance into an image that plays anywhere.**

---

## 2 · What APNG is

APNG is not a new format; it is an **extension of PNG**. Insert three chunk types into an ordinary PNG and it becomes an animation:

| Chunk | Purpose |
| --- | --- |
| `acTL` | Animation control: `num_frames`, `num_plays` (0 = infinite) |
| `fcTL` | Per-frame control: size, offset, `delay_num` / `delay_den`, `dispose_op`, `blend_op` |
| `fdAT` | Image data for frame 2 and later, with a 4-byte sequence number |

Hard facts from the specification (Mozilla APNG Specification):

- `acTL` must appear before the first `IDAT` for the file to be recognised as APNG.
- Frame 1 is an ordinary PNG `IDAT`, the **default image**; decoders without APNG support show that still instead of a broken image.
- Frame duration = `delay_num / delay_den` seconds; `delay_den = 0` is treated as **100**, so the unit becomes 1/100 s.
- `num_plays = 0` means loop forever.
- `fcTL` / `fdAT` share increasing sequence numbers to detect dropped or reordered frames.

MDN states the positioning plainly:

> "Good choice for lossless animation sequences (GIF is less performant). AVIF and WebP have better performance but less broad browser support."

In other words: **APNG is the safe lossless animation sequence; use WebP/AVIF for size and GIF for maximum compatibility.**

### APNG vs GIF

| Dimension | APNG | GIF |
| --- | --- | --- |
| Colour | 24-bit true colour + true alpha | ≤256-colour palette per frame, 1-bit transparency |
| Compression | DEFLATE, lossless | LZW, lossy quantization |
| Frame delay | Millisecond-level (`delay_num/delay_den`) | 1/100 s (GIF89a GCE) |
| Still fallback | Frame 1 is an ordinary PNG | Frame 1 is an ordinary GIF |
| Compatibility | Broad browser support; Windows Photos does not animate | Plays almost everywhere |
| Size | Full PNG per frame, larger | Often smaller for flat anime |
| Alpha edges | Smooth semi-transparency | Hard or white edges |

For the chunk layout, GIF's 256-colour and 1/100 s limits, and the four losses in APNG→GIF, see [APNG, GIF and video-to-GIF](formats.md).

---

## 3 · The difference from Live2D / Spine

Live2D's official positioning (as summarised by Wikipedia): a **proprietary 2D animation library** by Live2D Ltd. that builds **rigged models** from layered 2D textures, using tweening and warping to produce 2.5D motion; models integrate through an SDK, and Live2D Cubism is the authoring tool. It is common in visual novels, gacha games and facial-capture apps such as VTube Studio.

| Dimension | Live2D / Spine | This project |
| --- | --- | --- |
| Input | Layered PSD/art + mesh + parameter curves | 3–5 prompts + one story card |
| Authoring | A rigger adjusts weights per part | No rigging; edit a prompt |
| Runtime | SDK/engine/player deforms in real time | None; the image plays directly |
| Interactivity | Blinks, gaze, lip-sync, face capture | None; frames are baked |
| Motion range | Joint-level, composable, loopable | Interpolation between keyframes; micro-performance only |
| Output | Model + textures (not a single image) | One APNG / WebP / GIF file |
| Cost | Art + rigging + integration | One Queue, seconds to tens of seconds |
| Best for | VTubers, game sprites, interactive characters | Stickers, emotes, documentation |

**Be explicit about the boundary**: this project cannot do Live2D's real-time interaction or true joint articulation. It removes rigging and runtime, and in exchange gives you one image that plays anywhere.

---

## 4 · The difference from other animation routes

### 4.1 Frame-by-frame AI (24 samples)

Run img2img once per frame. Maximum freedom, but:

- 24 samples;
- no shared latent, so hair colour, eye colour and line width drift cumulatively;
- extra constraints (ControlNet, optical flow, reference images) are needed to stop flicker.

### 4.2 `batch_size=24`

One sample produces 24 **independent** noise images. A fixed seed makes the run reproducible, not continuous; playback always flickers. It is batch image generation, not an animation method.

### 4.3 Video generation → GIF

Generate video with AnimateDiff / SVD / Wan / LTX, extract frames and quantize to GIF.

- Pros: real motion, camera moves, complex interaction.
- Cons: a temporal model is far heavier than 3–5 samples; GIF conversion adds a 256-colour quantization pass that loses colour and alpha.

### 4.4 Hand-drawn sequence / sprite sheet

An artist draws every frame: the highest quality ceiling and the highest cost. A sprite sheet also needs a player to slice frames; it is not "one image that plays".

### 4.5 Lottie / Rive

Vector keyframes plus runtime interpolation: tiny files and interactivity, but they describe vector shapes. Painterly shading, hair strands and soft light do not fit.

---

## 5 · The compute bill: where the saving comes from

### 5.1 Sampling passes

ComfyUI's `KSampler` does **not** run only `denoise × steps` iterations when `denoise < 1`. In `comfy/samplers.py`, `set_steps()` computes `new_steps = int(steps / denoise)` and then keeps the last `steps + 1` sigmas, so **every KSampler still performs `steps` model evaluations**; denoise changes the starting sigma, not the iteration count.

With `steps=20`:

| Route | Sampling passes | Versus 24-frame frame-by-frame (baseline 480) |
| --- | --- | --- |
| This project, 3 beats | 3 × 20 = **60** | **87.5% fewer** |
| This project, 4 beats | 4 × 20 = **80** | **83.3% fewer** |
| This project, 5 beats | 5 × 20 = **100** | **79.2% fewer** |
| 24-frame frame-by-frame | 24 × 20 = **480** | baseline |

Interpolation itself is N linear blends on latents and calls no model. Decoding is still N passes; that part is not saved.
Key point: **going from 24 to 60 frames does not add sampling passes** (only beat count matters); only decode time and file size grow.

### 5.2 VRAM and memory

An SDXL 512×512 latent is `64×64×4`:

- one fp16 latent ≈ 32 KB; 24 ≈ 768 KB, 60 ≈ 1.9 MB;
- 24 decoded 512×512 RGBA images ≈ 25 MB, 60 ≈ 63 MB;
- interpolation nodes hold latents, not decoded images.

So the added footprint is **tens of megabytes of image buffers, not gigabytes of model or video cache**. The real cost remains one model load plus K sampling passes.

### 5.3 File size (measured here, 512²)

| Stack / content | Frames | APNG | GIF | WebP (lossless) |
| --- | --- | --- | --- | --- |
| SDXL / silver hair | 24 | 6.61 MB | 2.41 MB | 0.80 MB |
| Moss / silver hair | 24 | 4.15 MB | 2.72 MB | 2.88 MB |
| Moss / rainy neon | 60 | 17.23 MB | 7.21 MB | 12.76 MB |

GIF is often smaller than lossless APNG because LZW plus 256 colours suits flat anime very well. For smaller files, turn off WebP `lossless` and use quality 80–90.

### 5.4 When it does not save

- Real walking, turning or camera moves: interpolation cannot do it; use a video model or a ControlNet sequence.
- Real-time interaction, face capture, lip-sync: use Live2D / Spine.
- Precise composition on every frame: frame-by-frame is more direct.

---

## 6 · Choosing a route

| Need | Choose |
| --- | --- |
| Chat stickers, emotes, documentation GIFs | **This project → GIF / WebP / APNG** |
| Web, transparency, size-sensitive | **This project → WebP** |
| Documents, still-image fallback, lossless | **This project → APNG** |
| VTubers, interactive sprites, face capture | **Live2D / Spine** |
| Real motion, camera moves | **Video model → MP4/WebM** (convert to GIF only if needed) |
| UI motion, vector illustration | **Lottie / Rive** |

---

## 7 · References

- Mozilla APNG Specification: <https://wiki.mozilla.org/APNG_Specification>
- MDN Image file type and format guide: <https://developer.mozilla.org/en-US/docs/Web/Media/Guides/Formats/Image_types>
- GIF89a Specification (Graphic Control Extension, 1/100 s delay): <https://www.w3.org/Graphics/GIF/spec-gif89a.txt>
- Live2D (Wikipedia): <https://en.wikipedia.org/wiki/Live2D>
- Live2D official: <https://www.live2d.com/en/>
- ComfyUI `comfy/samplers.py`: `KSampler.set_steps()` denoise handling
- This repository: [APNG, GIF and video-to-GIF](formats.md)
