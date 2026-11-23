# Models and architectures

One sentence: **DiT is an architecture; MOSS is a model.** Writing "Moss / DiT" as if they were two
alternatives is like writing "cars / Corolla" as two kinds of vehicle. Earlier versions of this
documentation did exactly that; that is fixed now.

## Three independent layers

Only three things actually change what you do. They are independent — do not memorise them as one blob.

| Layer | What it decides | Values |
| --- | --- | --- |
| **Architecture** | how far keyframe `denoise` can go before the face changes | UNet · DiT |
| **Text encoder** | how you write the prompt, and whether tags matter | CLIP · T5 · Qwen-VL family |
| **Step paradigm** | what to put in `steps` and `cfg` | regular 20–30 · DMD / Turbo distilled |

Things inside a layer are interchangeable; things across layers are not. "Write tags for FLUX" is
wrong not because of the architecture but because FLUX's text encoder is T5, which ignores comma-tag
weighting.

## What DiT is

DiT = **Diffusion Transformer**, from Peebles & Xie, *Scalable Diffusion Models with Transformers*
(arXiv:2212.09748, ICCV 2023). The change is one sentence long: **swap the U-Net backbone for a
transformer** that denoises a sequence of latent patches. A U-Net builds receptive field with
convolutions and downsampling; a DiT builds it with self-attention, which costs more VRAM on long
sequences but scales better.

Therefore:

- **UNet family**: SD 1.5, SD 2.x, SDXL, Illustrious, NoobAI, Pony — not DiT.
- **DiT family**: FLUX, SD3 / SD3.5 (MMDiT), PixArt-α, HunyuanDiT, MOSS-Image, Qwen-Image, Krea 2, Anima.

MMDiT = Multi-Modal Diffusion Transformer, a DiT variant where image and text run as two streams that
interact inside the attention layers. SD3 and Qwen-Image use it.

## Overview

| Model | Architecture | Text encoder | Steps | Keyframe denoise | Loaders in this repo |
| --- | --- | --- | --- | --- | --- |
| SD 1.5 | UNet | CLIP | 20–30 | 0.45–0.55 | `CheckpointLoaderSimple` |
| SDXL / Illustrious / NoobAI / Pony | UNet | CLIP-L + CLIP-G | 20–30 | 0.35–0.45 | `CheckpointLoaderSimple` |
| FLUX.1 dev / schnell | DiT (MMDiT + parallel blocks) | CLIP-L + T5-XXL | 20–28 / 4 | 0.45–0.55 | `UNETLoader` + `DualCLIPLoader` + `VAELoader` + `FluxGuidance` |
| SD3 / SD3.5 | MMDiT | CLIP-L + CLIP-G + T5-XXL | 20–30 | 0.40–0.50 | `CheckpointLoaderSimple` (or the three-piece stack) |
| **MOSS-Image** | **DiT** | **Qwen3.5-9B** | **8 (DMD)** | **0.82–0.90** | `UNETLoader` + `CLIPLoader(type=moss_image)` + `VAELoader` |
| Krea 2 | DiT | Qwen3-VL 4B | Raw 20–30 / Turbo 4–8 | 0.45–0.55 | `UNETLoader` + `CLIPLoader` + `VAELoader` |
| Anima 2B | DiT | Qwen3-0.6B | Base 30–50 / Turbo 8–12 | 0.45–0.55 | `UNETLoader` + `CLIPLoader` + `VAELoader` |
| Qwen-Image | MMDiT 20B | Qwen2.5-VL | 20–30 | 0.45–0.55 | `UNETLoader` + `CLIPLoader` + `VAELoader` |

The denoise column is **how far a keyframe is redrawn**, not a text-to-image setting. Its role is
explained in [Workflows](workflows.md#environment-differences).

## Model by model

### SD 1.5 · UNet

The oldest tier, 512×512 native. Keyframe `denoise` 0.45–0.55; higher starts changing clothes.
CLIP-only text encoder: write tags, not prose. Runs in 6 GB of VRAM.

### SDXL · Illustrious · NoobAI · Pony · UNet

A tier above SD1.5, 1024×1024 native, 512 also stable. **Keyframe denoise ceiling is about 0.45** —
above 0.42 the face starts drifting, which is the most common failure this project measured.
Closed eyes (`eyes closed`) are especially prone to smearing on SDXL.

Write tags; put the style last. CLIP weights trailing tokens most heavily.

### FLUX.1 · DiT

A 12B hybrid DiT. Text encoders are CLIP-L + T5-XXL, with **T5 carrying most of the weight**. So the
writing style flips from "comma tags" to "complete English sentences" — `(word:1.3)` weighting barely
works on T5.

`cfg` stays at 1.0; intensity is controlled by the `FluxGuidance` node, starting at 3.5 for dev.
schnell is a 4-step distilled variant; do not add steps. Keyframe denoise 0.45–0.55.

### SD3 / SD3.5 · MMDiT

Image and text run as two transformer streams that interact in the attention layers. Encoders are
CLIP-L + CLIP-G + T5-XXL. Writing sits between FLUX and SDXL: full sentences work, tags are not
useless, but weight syntax is not reliable.

`cfg` 4–7 — do not push it to 1.0 like FLUX. Keyframe denoise 0.40–0.50.

### MOSS-Image · DiT + DMD

The DiT-side environment this project defaults to. **It is a DiT, not the opposite of DiT.**

- Backbone: DiT transformer (technical report arXiv:2610.23374)
- Text encoder: Qwen3.5-9B, reads **Chinese prose**, not comma tags
- Sampling: 8-step DMD distillation. `steps` 8, `cfg` 1.0; raising either only makes it blurrier
- Keyframe denoise: **0.82–0.90**. Below 0.80 keyframes barely move (adjacent-frame diff 0.03 over
  the whole clip); from 0.85 the motion appears. This is the parameter that differs most from the
  UNet family

Use 512 or 640 square. Prompt writing: [Prompting](prompting.md).

### Krea 2 · DiT

The release layout is `diffusion_models/krea2_*.safetensors` + `text_encoders/qwen3vl_4b_*` +
`vae/qwen_image_vae`, which places it in the same family as Qwen-Image, i.e. the DiT family
(the vendor published no separate architecture paper — this row is inferred from the released file
layout). Text encoder is Qwen3-VL 4B, so write **prose**, not tags.

Raw runs 20–30 steps; Turbo is distilled, 4–8 steps at `cfg` 1.0.

### Anima 2B · DiT

A 2B anime model by CircleStone Labs × Comfy Org. The model card lists
`nvidia/Cosmos-Predict2-2B-Text2Image` as its base, and Cosmos-Predict2 is a DiT flow model, so Anima
is DiT too. Text encoder `qwen_3_06b_base` (Qwen3-0.6B), VAE `qwen_image_vae`.

Card settings: 30–50 steps at `cfg` 4–5; Turbo 8–12 steps at `cfg` 1.0. Write prose, do not stack
`masterpiece`.

### Qwen-Image · MMDiT

A 20B MMDiT with a Qwen2.5-VL text encoder. The strongest native Chinese support of the set.
`cfg` 2.5–4 at 20–30 steps; distilled variants differ. Prose again.

## What the two local folders are called

The folder names in `profiles/*.json` are local install paths, not a taxonomy:

| Folder | What it actually is |
| --- | --- |
| `ComfyUI-aki-v3.2-xl` | the one running the **UNet family** (SDXL) |
| `ComfyUI-aki-v3.2-Dit` | the one running the **DiT family** (MOSS-Image by default) |

It is called `-Dit` only because that copy holds the DiT models. It does not mean "the other class
next to MOSS". You can swap in FLUX, SD3, Krea or Anima in that same environment — same node graph,
different loaders and step settings.

## What to change when you swap models

1. **Loaders**: `CheckpointLoaderSimple` ↔ `UNETLoader` + `CLIPLoader` + `VAELoader`
2. **`steps` / `cfg`**: from the table above
3. **Keyframe `denoise`**: UNet 0.35–0.55, DiT 0.45–0.55, DiT+DMD 0.82–0.90
4. **Prompt dialect**: tags for CLIP, sentences for T5, prose for Qwen-VL

Node count, wiring and output paths stay untouched — that is the premise of "swap the model, not the
graph".

## Sources

- DiT: Peebles & Xie, *Scalable Diffusion Models with Transformers* — <https://arxiv.org/abs/2212.09748>
- SD3 / MMDiT: Esser et al., *Scaling Rectified Flow Transformers for High-Resolution Image Synthesis* — <https://arxiv.org/abs/2403.03206>
- MOSS-Image technical report — <https://arxiv.org/abs/2610.23374>
- MOSS-Image model card — <https://huggingface.co/OpenMOSS-Team/MOSS-Image-Base>
- Krea 2 ComfyUI repack — <https://huggingface.co/Comfy-Org/Krea-2>
- Anima model card — <https://huggingface.co/circlestone-labs/Anima>
- FLUX.1 — <https://github.com/black-forest-labs/flux>

Rows marked "inferred from released files" have no official architecture statement; they were
derived from weights and encoder files. Re-check when versions change.