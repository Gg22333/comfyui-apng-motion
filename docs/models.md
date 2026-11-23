# 模型与架构

一句话：**DiT 是架构，MOSS 是模型。** 把两者并列写成「Moss / DiT」，等于把「汽车」和「卡罗拉」写成两类交通工具。
早期版本本文档就是这么写的，已经改掉。

## 先分清三层

选模型时，真正影响你操作的只有三件事。它们互相独立，不要混着记。

| 层 | 决定什么 | 取值 |
| --- | --- | --- |
| **架构** | 关键帧 `denoise` 能开多大、会不会换脸 | UNet · DiT |
| **文本编码器** | 提示词怎么写、要不要堆标签 | CLIP · T5 · Qwen-VL 系 |
| **步数范式** | `steps` 与 `cfg` 填多少 | 常规 20–30 步 · DMD / Turbo 蒸馏 |

同一层里的东西可以互换，跨层的不能。比如「FLUX 用标签写法」是错的——它是 DiT 架构没错，但文本编码器是 T5，不吃逗号标签权重。

## 什么是 DiT

DiT = **Diffusion Transformer**，出自 Peebles & Xie, *Scalable Diffusion Models with Transformers*（arXiv:2212.09748，ICCV 2023）。
核心改动只有一句话：**把 U-Net 主干换成 transformer**，在 latent 的 patch 序列上做去噪。
U-Net 靠卷积 + 下采样堆感受野，DiT 靠自注意力，序列越长越吃显存，但扩展性更好。

所以：

- **UNet 系**：SD 1.5、SD 2.x、SDXL、Illustrious、NoobAI、Pony —— 不是 DiT。
- **DiT 系**：FLUX、SD3 / SD3.5（MMDiT）、PixArt-α、HunyuanDiT、MOSS-Image、Qwen-Image、Krea 2、Anima。

MMDiT = Multi-Modal Diffusion Transformer，是 DiT 的一个变体：图像和文本各走一条流，在注意力层里交互。SD3 与 Qwen-Image 用的是它。

## 总表

| 模型 | 架构 | 文本编码器 | 步数 | 关键帧 denoise | 本仓库加载器 |
| --- | --- | --- | --- | --- | --- |
| SD 1.5 | UNet | CLIP | 20–30 | 0.45–0.55 | `CheckpointLoaderSimple` |
| SDXL / Illustrious / NoobAI / Pony | UNet | CLIP-L + CLIP-G | 20–30 | 0.35–0.45 | `CheckpointLoaderSimple` |
| FLUX.1 dev / schnell | DiT（MMDiT + 并行块） | CLIP-L + T5-XXL | 20–28 / 4 | 0.45–0.55 | `UNETLoader` + `DualCLIPLoader` + `VAELoader` + `FluxGuidance` |
| SD3 / SD3.5 | MMDiT | CLIP-L + CLIP-G + T5-XXL | 20–30 | 0.40–0.50 | `CheckpointLoaderSimple`（或三件套） |
| **MOSS-Image** | **DiT** | **Qwen3.5-9B** | **8（DMD）** | **0.82–0.90** | `UNETLoader` + `CLIPLoader(type=moss_image)` + `VAELoader` |
| Krea 2 | DiT | Qwen3-VL 4B | Raw 20–30 / Turbo 4–8 | 0.45–0.55 | `UNETLoader` + `CLIPLoader` + `VAELoader` |
| Anima 2B | DiT | Qwen3-0.6B | Base 30–50 / Turbo 8–12 | 0.45–0.55 | `UNETLoader` + `CLIPLoader` + `VAELoader` |
| Qwen-Image | MMDiT 20B | Qwen2.5-VL | 20–30 | 0.45–0.55 | `UNETLoader` + `CLIPLoader` + `VAELoader` |

denoise 一列是**关键帧重绘幅度**，不是文生图参数。它的作用见 [工作流](workflows.md#两个环境的参数差异)。

## 逐个模型

### SD 1.5 · UNet

最老的一档，512×512 原生。关键帧 `denoise` 给 0.45–0.55，再高就开始换衣服。
文本编码器只有 CLIP，写标签，不写散文。显存 6 GB 就能跑。

### SDXL · Illustrious · NoobAI · Pony · UNet

构图能力比 SD1.5 强一档，1024×1024 原生，512 也稳。**关键帧 denoise 上限约 0.45**——
超过 0.42 五官就开始漂，这是本项目实测最容易翻车的地方。闭眼（`eyes closed`）在 SDXL 上尤其容易糊成一团。

写标签，画风放最后。CLIP 对末尾 token 权重最高。

### FLUX.1 · DiT

12B 的 DiT 混合架构。文本编码器是 CLIP-L + T5-XXL，**T5 占大头**。
所以写法要从「逗号标签」切到「完整英文句子」——`(word:1.3)` 这种权重括号对 T5 基本无效。

`cfg` 固定 1.0，强度靠 `FluxGuidance` 节点调，dev 版 3.5 起。schnell 是 4 步蒸馏版，别再往上加。
关键帧 denoise 0.45–0.55。

### SD3 / SD3.5 · MMDiT

图像流和文本流各走一条 transformer，在注意力层交互。编码器是 CLIP-L + CLIP-G + T5-XXL 三路。
写法介于 FLUX 和 SDXL 之间：可以写完整句子，标签也不完全失效，但别指望权重语法。

`cfg` 4–7，不要像 FLUX 那样压到 1.0。关键帧 denoise 0.40–0.50。

### MOSS-Image · DiT + DMD

本项目默认的 DiT 侧环境。**它是 DiT，不是 DiT 的对立面。**

- 主干：DiT transformer（官方技术报告 arXiv:2610.23374）
- 文本编码器：Qwen3.5-9B，读**中文散文**，不读逗号标签
- 采样：8 步 DMD 蒸馏。`steps` 写 8，`cfg` 写 1.0，往上加只会更糊
- 关键帧 denoise：**0.82–0.90**。低于 0.80 关键帧几乎不动（整片相邻帧差 0.03），
  0.85 起动作才出得来。这是它和 UNet 系差得最远的一个参数

配 512 或 640 边长。提示词写法见 [提示词写法](prompting.md)。

### Krea 2 · DiT

发布包里的文件布局是 `diffusion_models/krea2_*.safetensors` + `text_encoders/qwen3vl_4b_*` + `vae/qwen_image_vae`，
按这个判定它和 Qwen-Image 同系，属 DiT 家族（厂商没有单独公布架构论文，此条按发布文件推断）。
文本编码器是 Qwen3-VL 4B，所以用**中文/英文散文**写法，不是标签。

Raw 版 20–30 步；Turbo 是蒸馏版，4–8 步、`cfg` 1.0。

### Anima 2B · DiT

CircleStone Labs × Comfy Org 的 2B 动漫模型。模型卡写明底座是 `nvidia/Cosmos-Predict2-2B-Text2Image`，
Cosmos-Predict2 是 DiT 系流模型，所以 Anima 也是 DiT。
文本编码器 `qwen_3_06b_base`（Qwen3-0.6B），VAE 直接用 `qwen_image_vae`。

模型卡给的参数：30–50 步、`cfg` 4–5；Turbo 版 8–12 步、`cfg` 1.0。
写法用散文，别堆 `masterpiece`。

### Qwen-Image · MMDiT

20B 的 MMDiT，文本编码器 Qwen2.5-VL。中文原生支持最好的一档。
`cfg` 2.5–4，20–30 步；蒸馏版另算。写法同样是散文。

## 本机两个目录叫什么

`profiles/*.json` 里的目录名是本机安装路径，不是分类标准：

| 目录 | 实际含义 |
| --- | --- |
| `ComfyUI-aki-v3.2-xl` | 跑 **UNet 系**（SDXL）的那套 |
| `ComfyUI-aki-v3.2-Dit` | 跑 **DiT 系**（默认 MOSS-Image）的那套 |

目录叫 `-Dit` 只是因为它是装 DiT 模型的那一份。它不代表「MOSS 之外的另一类」。
你完全可以在这套环境里换成 FLUX、SD3、Krea 或 Anima，节点结构一样，只换加载器和步数。

## 换模型要改什么

1. **加载器**：`CheckpointLoaderSimple` ↔ `UNETLoader` + `CLIPLoader` + `VAELoader`
2. **`steps` / `cfg`**：按上表
3. **关键帧 `denoise`**：UNet 0.35–0.55，DiT 0.45–0.55，DiT+DMD 0.82–0.90
4. **提示词方言**：CLIP 写标签，T5 写句子，Qwen-VL 写散文

节点数量、连线、保存路径都不用动——这是本项目「换模型不换结构」的前提。

## 来源

- DiT：Peebles & Xie, *Scalable Diffusion Models with Transformers* — <https://arxiv.org/abs/2212.09748>
- SD3 / MMDiT：Esser et al., *Scaling Rectified Flow Transformers for High-Resolution Image Synthesis* — <https://arxiv.org/abs/2403.03206>
- MOSS-Image 技术报告 — <https://arxiv.org/abs/2610.23374>
- MOSS-Image 模型卡 — <https://huggingface.co/OpenMOSS-Team/MOSS-Image-Base>
- Krea 2 ComfyUI 重打包 — <https://huggingface.co/Comfy-Org/Krea-2>
- Anima 模型卡 — <https://huggingface.co/circlestone-labs/Anima>
- FLUX.1 — <https://github.com/black-forest-labs/flux>

表格里标「按发布文件推断」的条目没有官方架构声明，只按权重与编码器文件反推，换版本时请重新核对。