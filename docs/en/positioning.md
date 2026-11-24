# What this is, and what it is not

In one line: **a motion-layout tool that turns keyframes into animation, not an AI video generator.**

It sits closer to PowerPoint animation or a stripped-down After Effects: the model draws
3–8 keyframes, and the motion between them is math. Every trade-off below follows from that.

## Three design decisions

**1. The unit is a beat, not a frame.**
You author 3–8 keyframes, not 24/60 continuous images. That is where the cost comes from:
24 frames cost 3 samples — not an optimisation, a definition.

**2. Interpolation, not per-frame redraw.**
Per-frame img2img can add detail, but every frame is re-encoded and error accumulates.
Measured at 512², 8 steps, 24 frames:

| | Per-frame redraw | Keyframe interpolation |
| --- | --- | --- |
| Samples | 24 | 3 |
| Wall clock | 40.1 s | 15.5 s |
| Drift curve | 0 → 38, monotone | peak 16 → last frame 1.5, closed |

One is a random walk, the other a closed loop. Stickers and short loops want the second.

**3. APNG is the primary output; GIF is compatibility.**
APNG is lossless with true colour and alpha. GIF is 256 colours, merges identical frames,
and rounds durations to 10 ms. Check the APNG first; only confirm the GIF plays.

## What it is good at

Not cinematic shots — **rhythmic short loops**: stickers, emoji packs, three-beat micro-stories,
product showcases, UI motion. The audience watches *change*, not *movement*.

## Its ceiling

- In-between frames are **morphs**, not performance: a hand does not rise, it blends from A to B.
- The camera is a 2D affine transform: no parallax, a push-in never enters the scene.
- Quality is capped by the keyframes; interpolation smooths, it does not improve.
- It does not replace video models and should not compete with them.

## When not to use it

| What you need | What to use |
| --- | --- |
| Real body motion, lip sync, walking | A video model (Wan / MiniMax H3, …) |
| 3D parallax, orbit, dolly | 3D previz + a video model |
| Morphs that need new detail every frame | Per-frame img2img / Deforum-style |
| Long takes, multi-scene editing | A timeline tool + a video model |
| **A still that moves, loops, and can be re-checked** | **This project** |

## Why lightweight is not a compromise

It runs on a 12 GB laptop GPU, adds no new models or dependencies, and every move is
reproducible (same seed, same parameters, same result) and explainable (how many pixels,
what zoom, which easing).

The cost is coarse control: 3–8 beats, one 2D camera, one curve. At that granularity it can
promise something heavier pipelines struggle with — change one number, re-render, and it still
does not drift.

---

> This route is not well documented in public. If you see a similar approach elsewhere, bring
> the link; we take ideas, not implementations.
