# APNG vs GIF vs video-to-GIF

This page explains three things: why APNG suits sticker-style animations, how it differs from
"turn a video into a GIF", and what is lost when an APNG is re-encoded as a GIF.

---

## 1 · How APNG is stored

APNG is not a new format; it is an **extension of PNG** that inserts three chunk types into an ordinary PNG.

| Chunk | Purpose |
| --- | --- |
| `acTL` | Animation control: `num_frames`, `num_plays` (0 = infinite) |
| `fcTL` | Per-frame control: size, offset, `delay_num` / `delay_den`, `dispose_op`, `blend_op` |
| `fdAT` | Image data for frame 2 and later |

Key points from the specification:

- **`num_plays = 0` means loop forever**; `num_frames` must equal the number of `fcTL` chunks.
- Frame duration = `delay_num / delay_den` seconds; **`delay_den = 0` is treated as 100**, so the unit becomes 1/100 s.
- Frame 1 is an ordinary PNG `IDAT`, so **decoders without APNG support fall back to a static PNG**. That is APNG's most important property: it degrades gracefully instead of showing a broken image.

Two direct benefits:

1. One `.png` is both an animation and a still; chat previews, image hosts and CDNs do not break.
2. True colour plus true alpha (RGBA); soft edges stay soft.

The cost is size: every APNG frame is a full PNG image, with **no inter-frame prediction** (no P/B frames, no motion compensation).
For the same content, APNG is usually larger than GIF and an order of magnitude larger than MP4/WebM.

> Note: the spec allows `x_offset` / `y_offset` plus `dispose_op` to update only part of a frame, but Pillow
> (what ComfyUI's `SaveAnimatedPNG` uses) writes full frames and **merges adjacent pixel-identical frames**,
> adding their duration to the previous frame. That is the root cause of "24 frames scheduled, 19 exported",
> and why this project forbids duplicate ratios within one latent pair.

---

## 2 · The real difference from video-to-GIF

Two completely different pipelines:

```
Video to GIF:
  capture/generate video → H.264/H.265 (inter-frame prediction, YUV, lossy)
      → frame extraction → palette quantization (≤256 colours) → GIF (LZW, 1-bit alpha)

This project (APNG route):
  first-frame sample → 3–5 keyframes (redrawn from the same latent)
      → LatentInterpolate to 24 frames → VAE decode (full RGBA per frame)
      → three independent encoders: APNG / WebP / GIF
```

| Dimension | Video to GIF | This project |
| --- | --- | --- |
| Motion source | Real sampling with motion blur and physical trajectories | Mathematical interpolation between keyframes, **no real trajectory** |
| What it can act | Walking, turning, camera moves, complex interaction | Expressions, breathing, small head moves; big motion needs ControlNet or a video model |
| Quality | Limited by video bitrate and quantization | Every frame is full quality, no compression artifacts |
| Size | Video is small; the GIF explodes | APNG is large, GIF moderate |
| Control | Reshoot or re-edit | Change one prompt line to change the performance |

**In one sentence**: video-to-GIF records motion that already happened; this project interpolates between two states.
The former suits real action, the latter suits **sticker-style micro-performance**, and it is reproducible and parameterized.

---

## 3 · APNG characteristics

| Characteristic | Detail |
| --- | --- |
| Backward compatible | Unsupported software shows frame 1, not a broken image |
| 24-bit colour + alpha | Gradients, hair strands and translucent glows survive |
| Lossless | DEFLATE compression, no banding |
| Browser support 97.39% | Chrome / Edge / Firefox / Safari / Android all pass (caniuse, 2026-11-23) |
| Desktop viewers vary | Windows Photos does **not** play APNG; BandiView and browsers do |
| Large | Full PNG per frame; 512² × 24 frames is 4–7 MB, 60 frames is 10–18 MB depending on detail |
| No audio | Image sequence only |

Good for: web pages, documents, Discord (alpha preserved), local high-quality review, anything that needs a still-image fallback.

---

## 4 · What APNG to GIF loses

APNG to GIF is not a container swap; it is **dimensionality reduction**. Four things always happen.

### 4.1 Colour: 24-bit to an 8-bit palette

GIF allows at most 256 colours per frame. Two approaches:

| Approach | Result |
| --- | --- |
| Per-frame quantization | The palette jumps between frames; colours "breathe" and flicker |
| One global palette | No flicker, but the whole clip is limited to 256 colours; gradients and skin tones band |

This project's GIF uses VHS `image/gif`: one `palettegen` pass plus `paletteuse`, with `sierra2_4a` dithering.
No flicker, but **banding and dither noise are unavoidable**.

### 4.2 Alpha: true alpha to 1-bit transparency

Semi-transparent regions (hair tips, glows) become either fully opaque or fully transparent,
producing hard or white edges. For transparency, prefer WebP or APNG.

### 4.3 Time: milliseconds to 1/100 s

GIF frame delay is measured in **1/100 s** (GIF89a GCE), so the real frame rate can only be `100/n`:

| Target fps | GIF delay | Actual fps |
| --- | --- | --- |
| 10 | 10cs | 10.00 |
| 12 | 8cs | 12.50 |
| 9 | 11cs | 9.09 |
| 8 | 12cs | 8.33 |

Browsers also clamp very short delays, so **8–12 fps** is the practical range for stickers.

### 4.4 Size: not necessarily larger

GIF is worse in quality, so it feels like it should be bigger, but the opposite is common: LZW plus 256 colours is very kind to flat anime shading.
Measured here (512², straight from ComfyUI):

| Stack / content | Frames | APNG | GIF | WebP (lossless) |
| --- | --- | --- | --- | --- |
| SDXL / silver hair | 24 | 6.61 MB | 2.41 MB | 0.80 MB |
| Moss / silver hair | 24 | 4.15 MB | 2.72 MB | 2.88 MB |
| Moss / rainy neon | 60 | 17.23 MB | 7.21 MB | 12.76 MB |

Size is roughly linear for the same content (60 frames ≈ 2.5× of 24); across different content it is not comparable.

Conclusion: **GIF is usually smaller than lossless APNG, but lossless WebP is not always smaller than GIF**; for size, turn lossless off and use quality 80–90.

### 4.5 Two more details

- **Identical frames get merged**: when Pillow writes APNG, adjacent pixel-identical frames are dropped and their duration is added to the previous frame. GIF encoders differ, so ratios within one latent pair must be unique (equal values across different segments are safe).
- **Loop count**: APNG `num_plays=0` and the GIF NETSCAPE2.0 `loop=0` both mean infinite, semantically identical.

### 4.6 Why the web preview is WebP

`docs/assets/preview.webp` is the primary preview; `preview.gif` is a compatibility copy.

| File | Size | Frames | Bytes | Adjacent-frame diff (avg) |
| --- | --- | --- | --- | --- |
| Old GIF (VHS direct, 512, `sierra2_4a`) | 512x512 | 24 | 3.45 MB | 2.49 |
| New GIF (global palette + `dither=none`) | 384x384 | 60 | 2.13 MB | 1.94 |
| New WebP (quality 100, keeps all 60 frames) | 384x384 | 60 | 1.46 MB | 1.82 |

The current preview is 60 frames / 30 fps / Moss-DiT, recipe in `assets/story.preview.json`.

WebP has a frame-count trap: libwebp's animation encoder merges adjacent frames that are nearly identical after compression.
At quality 90, 60 frames become 58 (same duration, wrong metadata); quality 100 keeps all 60, at the cost of
growing from ~0.6 MB to 1.5 MB. `make_preview.py` defaults to 100 and verifies the frame count after saving,
falling back to lossless if needed.

GIF has 256 colours. VHS runs `palettegen` + `paletteuse` per frame with `sierra2_4a` dithering:
every frame gets its own palette and its own dither grain. On playback that reads as **blocks
flickering**, independent of whether the artwork moves.

`scripts/make_preview.py` fixes it by sharing one palette across all frames, disabling dither,
and downscaling to 384 px. The per-frame quantisation error stays around 2.3/255, but the
**error becomes consistent between frames**, so the flicker disappears.

## 5 · Two sources of colour flicker

Check the APNG first, then the GIF.

| Source | How to recognise | Fix |
| --- | --- | --- |
| Generation: keyframe denoise too high | APNG adjacent diff avg > 2, patchy blotches on face/clothes | drop keyframe denoise to 0.35-0.40; same seed; same first latent |
| Generation: uneven curve | diff series has 4-5 spikes in the middle | `--curve linear`; avoid `snap` |
| Encoding: per-frame GIF palette | APNG clean, GIF shows blocky noise | global palette + no dither; or use WebP |
| Loop seam | last frame to first frame diff is large | bring the last beat back to the first pose |

Measured on the same content: denoise 0.55 gave APNG diff 2.34 and drift 8+; 0.35 gives
diff 1.08 and drift 2.63. Re-encoding the GIF removes another ~0.05.

---

> For how this route compares with Live2D, frame-by-frame AI and video generation, including the
> compute bill, see [Animation approaches compared](synthesis-comparison.md).

## 6 · Which format to ship

| Scenario | Use | Why |
| --- | --- | --- |
| WeChat / QQ chat, custom stickers | **GIF** | Best compatibility, controllable size |
| Web, Discord, transparency | **WebP** | Small, supports alpha |
| Documents, still-image fallback, lossless | **APNG** | Shows frame 1 when unsupported, never breaks |
| Real motion (walking, turning) | Video model → MP4/WebM | Out of scope for this route |

---

## 7 · References

- APNG specification: <https://wiki.mozilla.org/APNG_Specification>
- GIF89a Graphic Control Extension (1/100 s delay)
- caniuse: `apng` 97.39%, `webp` 97.24% (retrieved 2026-11-23)
- Pillow `PngImagePlugin._write_multiple_frames` (identical-frame merging)
- ComfyUI `comfy_api/latest/_ui.py`: `duration = int(1000.0 / fps)`
- VHS `video_formats/ffmpeg-gif.json`: single-pass `palettegen` + `paletteuse`, `sierra2_4a`
