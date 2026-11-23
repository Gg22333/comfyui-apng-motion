---
name: comfyui-apng-motion
description: >
  ComfyUI 里用「首帧 + 2–4 个关键帧 latent 插值」做 8–60 帧连贯 APNG/WebP/GIF 动图（表情包/微故事）的完整方法：
  双环境配置（UNet 系 / DiT 系）、工作流结构、任意帧数扩缩、提示词写法、17 组动作库、只存成品的输出规范、
  兼容性与排错。Use when 用户提到 ComfyUI、APNG、动图、表情包、8/24/30/60 帧、帧间闪烁、不连贯、LatentInterpolate、
  SaveAnimatedPNG、SaveAnimatedWEBP、VHS_VideoCombine、SDXL、MOSS-Image、DiT 架构、FLUX、剧情分镜、多角色、
  表情包定义、画风锁定、瞳色漂移、换机器、移植、profile、环境探测。
---

# ComfyUI 连贯动图（8–60 帧）· APNG / WebP / GIF

一句话：**三张关键帧（中性 → A → B）→ N 个 LatentInterpolate 比例 → N 次 VAE 解码 → ImageBatchMulti → 三个保存节点。**
N 由 `--frames` 决定（默认 24，支持 8–60 任意值），插值/解码/batch 节点自动扩缩。
不靠 `batch_size` 堆帧，不靠外部脚本合成，不在中间落盘，一次 Queue 出一个成品文件。

---

## 0 · 先看这张表

| 项 | UNet 系环境（`-xl`） | DiT 系环境（`-Dit`） |
| --- | --- | --- |
| ComfyUI 根 | `D:\ComfyUI-aki-v3.2-xl\ComfyUI` | `D:\ComfyUI-aki-v3.2-Dit\ComfyUI` |
| Python | `D:\ComfyUI-aki-v3.2-xl\python\python.exe` | `D:\ComfyUI-aki-v3.2-Dit\python\python.exe` |
| 版本 | ComfyUI 0.46.2 / torch 2.13.0+cu130 | ComfyUI 0.46.0 / torch 2.13.0+cu132 |
| 共用 | Python 3.13.11 / Pillow 12.1.0 / RTX 5070 Ti Laptop 12GB | 同左 |

> **下表是本机实例，不是规格。** 换机器先跑 `python scripts/detect_env.py`，路径、端口、模型名、版本全部落进 `profiles/*.json`；正文里的 `D:\...` 一律当示例读，脚本不依赖它们。
| 模型 | `checkpoints\NovaAnimeILV190.safetensors` | `diffusion_models\moss_image_base_8stepdmd_int8_convrot.safetensors` + `text_encoders\qwen3.5_9b_moss_image_sft_w4a8_gptq.safetensors`（type=`moss_image`）+ `vae\moss_image_vae_bf16.safetensors` |
| 工作流 | `user\default\workflows\APNG多帧合成-SDXL.json` | `user\default\workflows\APNG多帧合成-Moss.json` |
| 默认端口 | 8188（验证用 8190） | 8189（验证用 8191） |
| 关键帧 denoise | 0.4 | 0.85（0.82–0.90） |
| 采样 | 20 步 / cfg 6.0 / euler_ancestral / normal | 8 步 / cfg 1.0 / euler / simple |

两套工作流**不是同一份**：加载器和采样参数不同，但节点结构一致；帧数由 `--frames` 决定，曲线长度跟着帧数走。
依赖插件：`comfyui-kjnodes`（ImageBatchMulti）、`ComfyUI-VideoHelperSuite`（Video Combine 出 GIF），两个环境都已装。

启动验证（不要占用绘世的默认端口）：

```powershell
& 'D:\ComfyUI-aki-v3.2-xl\python\python.exe' -s 'D:\ComfyUI-aki-v3.2-xl\ComfyUI\main.py' --port 8190 --listen 127.0.0.1
& 'D:\ComfyUI-aki-v3.2-Dit\python\python.exe' -s 'D:\ComfyUI-aki-v3.2-Dit\ComfyUI\main.py' --port 8191 --listen 127.0.0.1
netstat -ano | findstr ":8190 :8191"
```

收尾必须 `Stop-Process -Id <PID>` 并确认端口释放，否则绘世启动器会报端口占用。

### 0.1 当前状态（2026-11-23 实测成片）

| 版本 | 环境 | 相邻帧差异 | 颜色漂移 | 结论 |
| --- | --- | --- | --- | --- |
| 新（denoise 0.35 + linear + 全局动作） | xl | 0.12 – 2.35，平均 1.08 | 2.63 | 当前默认，已不闪 |
| 旧（denoise 0.55 + 幂曲线） | xl | 0.95 – 5.42，平均 2.34 | 3.07 | 中段出现色斑，已弃用 |
| 历史 | Dit | 0.06 – 3.04，平均 1.43 | — | 结构同步到新默认，未重测成片 |
| 60 帧展示图（MOSS-Image，DiT，denoise 0.85，20fps，十一拍） | Dit | 1.72 – 5.00，平均 2.78 | 14.75 | 当前仓库预览；接缝无停顿，桌子与白碗全程在画面里；漂移来自手机冷光和闭眼拍 |

xl 的稳定上限约 **denoise 0.35**：0.42 时颜色漂移升到 8 左右，衣服和背景开始被重绘；0.45 时衣服变蓝。
要更大表情，优先加帧数或做面部局部重绘，不要直接抬 denoise。

### 0.2 用这个 skill 的顺序

1. 先读线上工作流文件（`user/default/workflows/APNG多帧合成-*.json`），`assets/` 里的只是抓取当时的快照，用户可能已经改过。
2. 改任何东西都要**两个环境同时改**：xl 和 Dit 节点结构一致，只有加载器、采样参数、denoise 不同。
3. 改完让用户刷新浏览器页面再 Queue，否则前端还持着旧节点和旧 prefix。
4. 验证一律用 8190 / 8191，结束清端口。

### 0.3 启动与离线配置（归档会话结论）

- 两个环境的 `ComfyUI\user\__manager\config.ini` 都已是 `network_mode = offline`、`security_level = normal`。启动时不再刷 `FETCH ComfyRegistry Data`、`Cannot connect to raw.githubusercontent.com`。剩下的 `WinError 10022` 来自别的插件联网被重置，不影响出图。
- 只验证工作流时用白名单启动，别把几十个自定义节点全加载（实测可用）：

```powershell
& 'D:\ComfyUI-aki-v3.2-xl\python\python.exe' -s 'D:\ComfyUI-aki-v3.2-xl\ComfyUI\main.py' --port 8190 --listen 127.0.0.1 --disable-all-custom-nodes --whitelist-custom-nodes comfyui-kjnodes ComfyUI-VideoHelperSuite --disable-manager-ui --disable-product-tips --disable-auto-launch
```

- 结束必须 `Stop-Process -Id <PID>`，再 `netstat -ano | findstr ":8190"` 确认端口空。绘世默认占用 8188（xl）/ 8189（Dit），验证别用这两个。
- 归档里踩过两次：验证实例没退，绘世启动器报端口占用（一次 8188、一次 8189）。

### 0.4 本 skill 的来源（三份归档会话）

| 会话 | 时间 | 贡献 |
| --- | --- | --- |
| 原始搭建 | 2026-11-22 15:35 → 11-23 00:53 | `batch_size` 失败 → 8 帧同源重绘 → 三关键帧插值 → 24 帧三格式；目录分层；只存成品 |
| 续修 | 2026-11-23 08:54 → 11:41 | xl 闭眼导致虹膜变色 → `eyes half closed`、denoise 0.4；两环境统一"不闪" |
| 交接 | 2026-11-23 11:38 → 11:49 | SKILL.md 成稿、脚本落盘、外部资料核对 |

前两份会话里未落地的需求（本版补进第 5 节）：剧情动作指导模块、表情包的故事内核、多角色与任意动作、画风/发色/瞳色锁定。

---

### 0.5 换一台机器：三步

```powershell
python scripts/detect_env.py                     # 1 扫描本机 ComfyUI，写 profiles/*.json
python scripts/doctor.py                         # 2 逐项体检（模型/插件/节点/输出目录/端口）
python scripts/emit_workflow.py --base workflows/workflow-sdxl.json --story assets/story.4beat.json --out my-4beat.json
```

`emit_workflow.py` 认的是**结构**，不是模型名：只要 base 里有「1 个 denoise=1 的 KSampler + ≥2 个关键帧 KSampler + 24 个 LatentInterpolate + 24 个 VAEDecode + ImageBatchMulti(24) + 三个输出」，就能扩成 3–5 拍。换模型只需要把 base 里的 loader 换成你自己的（`CheckpointLoaderSimple` 或 `UNETLoader`+`CLIPLoader`+`VAELoader` 都行），其余别动。

模型与 denoise 的对应（经验值，同 seed 下测出来的稳定上限）。

**先记住分类：DiT 是架构，MOSS 是模型。** DiT（Diffusion Transformer，arXiv:2212.09748）是把 U-Net 主干
换成 transformer 的那一族。SDXL 是 UNet，不是 DiT；MOSS-Image / FLUX / SD3 / Krea / Anima 是 DiT。
配置时真正独立的是三层：**架构**（决定 denoise 区间）、**文本编码器**（决定提示词方言）、
**步数范式**（常规 20–30 步 vs DMD/Turbo 蒸馏）。

| 模型族 | 架构 | 文本编码器 | 加载器 | 关键帧 denoise |
| --- | --- | --- | --- | --- |
| SD 1.5 | UNet | CLIP | `CheckpointLoaderSimple` | 0.45–0.55 |
| SDXL / Illustrious / NoobAI | UNet | CLIP-L + CLIP-G | `CheckpointLoaderSimple` | 0.35–0.45 |
| FLUX.1 | DiT | CLIP-L + T5-XXL | `UNETLoader` + `DualCLIPLoader` + `VAELoader` | 0.45–0.55（前面加 `FluxGuidance` 3.5，cfg 1.0） |
| SD3 / SD3.5 | MMDiT | CLIP-L + CLIP-G + T5-XXL | `CheckpointLoaderSimple` 或三件套 | 0.40–0.50（cfg 4–7） |
| MOSS-Image | DiT + 8 步 DMD | Qwen3.5-9B | `UNETLoader` + `CLIPLoader`（`type=moss_image`）+ `VAELoader` | 0.82–0.90 |
| Krea 2 | DiT | Qwen3-VL 4B | `UNETLoader` + `CLIPLoader` + `VAELoader` | 0.45–0.55 |
| Anima 2B | DiT | Qwen3-0.6B | `UNETLoader` + `CLIPLoader` + `VAELoader` | 0.45–0.55 |

### 0.5.1 工作流里能改什么

生成出来的每个工作流都自带这三层，打开就能调：

| 范围 | 节点 | 改什么 |
| --- | --- | --- |
| 全片 | `CLIPTextEncode`「全局动作指导（所有关键帧共享）」 | 动作、镜头、光照、风格；改一处，所有关键帧生效 |
| 每帧 | `CLIPTextEncode`「K0 / K1 / … 提示」 | 表情、姿态、视线 |
| 每帧采样 | 每个 `KSampler` | seed、steps、cfg、采样器、调度器、denoise |
| 节奏 | N 个 `LatentInterpolate` 的 ratio（N = frames） | `linear` 最均匀，`ease` 两端慢，`snap` 旧行为 |
| 速度 | 三个保存节点的 `fps` | 三处必须一致（fps × N = 时长；24 @10fps = 2.4 秒） |
| 画质 | APNG `compress_level`、WebP `lossless`/`quality`、VHS `loop`/`pingpong` | 体积与播放 |

CLI 对应参数：`--motion` `--curve` `--seed` `--denoise` `--steps` `--cfg`。画布里还有一个 `Note` 节点把这张表写在旁边。

跑之前想确认能不能落地，加 `--run`：

```powershell
python scripts/emit_workflow.py --validate my-4beat.json --run --profile profiles/xl.json
```

它会调 `/object_info` 校验节点、把工作流转成 API 格式提交、轮询 `/history`、把成品路径打出来并自动跑 `check_anim.py`。

### 0.6 脚本矩阵

| 脚本 | 干什么 | 依赖 |
| --- | --- | --- |
| `detect_env.py` | 扫本机 ComfyUI：版本、Python、模型清单、插件、运行端口、可用工作流 → `profiles/*.json` | 无 |
| `doctor.py` | 按 profile 体检：文件、模型、插件、节点类型、输出目录可写、端口是否活 | 无（探活要网络） |
| `emit_workflow.py` | 3 关键帧 → K 拍（3–5）+ 任意帧数（8–60）；编译剧情卡提示词；重算曲线；校验连线；可选 `--run` 直接出片 | 无 |
| `make_story.py` | 从 17 组动作库生成剧情卡；校验 frames/segs/beats；自动追加场景提示 | 无 |
| `check_anim.py` | 帧数、时长、循环、相邻帧差异、重复帧、颜色漂移 | Pillow |
| `make_curve.py` | 单独出 ratio 曲线，改节奏用 | 无 |
| `make_preview.py` | 把成品 APNG 重编码成网页预览：全局调色板 + 关抖动 GIF、真彩 WebP；`--story` 时写逐帧延时 | Pillow |
| `retime.py` | 出片后重写 APNG 的逐帧延时（`fps` / `dwell` / `ease`）：像素不动、不重跑采样 | Pillow |
| `timing.py` | 帧延时计算唯一真相源：`frame_delays()` 保证总时长恒等于 `frames / fps` | 无 |
| `comfy_lib.py` | 共用库：profile、HTTP、曲线、UI→API 转换 | 无 |

本机实测（2026-11-24，新默认）：UNet 系 3 拍 67 节点、4 拍 70 节点；DiT 系 3 拍 69 节点、4 拍 72 节点。
`--run` 交出三格式成品并自动验片；8 / 24 / 60 帧都实测过，`check_anim` 全部 `loop=0 / EXIT=0`。
denoise 0.35 的 24 帧预览相邻帧差异 0.12–2.35（avg 1.08）、漂移 2.63；
60 帧 MOSS-Image 展示片：1.72–5.00（avg 2.78），漂移 14.75，60 帧 @20fps = 3.00 s。

### 0.7 依赖与分发

依赖自检（不联网、不出图）：

```powershell
python scripts/check_deps.py
```

| 依赖 | 版本 | 必需 | 缺了会怎样 |
| --- | --- | --- | --- |
| Python | ≥ 3.9 | 是 | 脚本跑不起来 |
| Pillow | ≥ 9.0 | 仅校验 | `check_anim.py` 不可用；出片不受影响 |
| ComfyUI | ≥ 0.3（带 `SaveAnimatedPNG` / `SaveAnimatedWEBP`） | 是 | 保存节点不存在 |
| `comfyui-kjnodes` | 任意 | 是 | `ImageBatchMulti` 爆红 |
| `ComfyUI-VideoHelperSuite` | 任意 | 否 | 只少 GIF，APNG/WebP 正常 |
| `curl` | 任意 | 否 | `--run` 的 HTTP 兜底通道失效（正常网络用不到） |

Pillow 装在哪儿有讲究：`check_deps.py` 会顺便列出 profiles 里各环境的 python 有没有 Pillow。**直接用 ComfyUI 自带的解释器**跑校验，比给自己系统 Python 装包省事。

三种分发形态：

| 形态 | 命令 | 适用 |
| --- | --- | --- |
| 目录拷贝 | `python scripts/install.py --dest <skills 目录>` | 本机多处安装（Codex / magpie） |
| zip 包 | `python scripts/package.py` → `dist/comfyui-apng-motion-<ver>.zip` + `.sha256` | 离线分发、丢给别人 |
| git 仓库 | 整个目录进仓库即可（`.gitignore` 已排除 dist / profiles / 备份） | 团队协作、版本追踪 |

`install.py` 覆盖前会把旧 `SKILL.md` 备份成 `SKILL.md.bak-<时间戳>`；默认不拷 `profiles/`（那是本机产物），要拷加 `--with-profiles`。

### 0.8 只有一个 skill，两处入口

不是两个 skill。唯一源是 `E:\Documents\zezeze\tools\comfyui-apng\skill`，两处安装只是两个加载器的入口：

| 路径 | 谁读 |
| --- | --- |
| `~/.codex/skills/comfyui-apng-motion` | Codex 原生 skills |
| `~/.config/magpie/library/skills/comfyui-apng-motion` | magpie 的 library |

防漂移：

```powershell
python scripts/install.py --check    # 逐文件哈希比对，输出 SAME / DRIFT
```

要让物理上真的只有一份，可以改成 junction（Windows）/软链：

```powershell
python scripts/install.py --link
```

代价：安装位置依赖源目录存在，源目录一挪就断。默认仍是**拷贝**（抗挪动），用 `--check` 兜漂移。

## 1 · 为什么这么搭（每个决定都有原因）

| 做法 | 原因 |
| --- | --- |
| 不用 `batch_size=24` | `batch_size=N` 是**N 个互相独立的噪声样本**。固定 seed 只保证可复现，不会让它们变成连续帧，播放必然闪。 |
| 所有帧都从「首帧 latent」出发 | 逐帧继承上一帧会累积漂移：实测黑发几帧后变青蓝。锚死同一张首帧 latent，脸、发色、构图都不跑。 |
| 关键帧用 img2img（denoise 0.4 / 0.5） | 小于 1.0 等于「在首帧上按新提示词局部重绘」，只改表情区，不改画风。 |
| 中间帧用 LatentInterpolate | 在 latent 空间插值比在像素空间交叉淡化干净，不会出现半透明重影。 |
| 默认 24 帧，而不是写死 24 | 24 帧 @10fps = 2.4 秒，够放「起 → 高潮 → 收」；8 帧只够轮播，30/60 帧给五拍故事和网页预览。帧数是预算，用 `--frames` 改。 |
| 三角形曲线 + 关键帧停顿 | 首帧 → A → B → 首帧，关键帧处停留 2 帧，动作才有「呼吸感」。 |
| 只保存成品 | 每帧都 SaveImage 会把输出目录塞满，用户根本不用单帧。 |

### 1.1 LatentInterpolate 到底怎么算

本机源码 `comfy_extras/nodes_latent.py`：先各自做范数归一化，线性混合，再按 `m1*ratio + m2*(1-ratio)` 还原模长：

```python
s1 = s1 / ||s1||;  s2 = s2 / ||s2||
t  = s1 * ratio + s2 * (1.0 - ratio)
t  = t / ||t||
out = t * (m1 * ratio + m2 * (1.0 - ratio))
```

结论：**`ratio` 是 samples1 的权重。`ratio=1.0` 输出就是 samples1，`0.0` 输出就是 samples2。**
所以曲线从 1.0 往 0 走 = 从 samples1 走向 samples2；同一对 latent 里 `0.08` 和 `0.92` 表示「分别从两端逼近同一个关键帧」。

---

## 2 · 工作流结构（逐节点）

```
EmptyLatent 512×512×1
        │
   KSampler 首帧（denoise 1.0，seed 123456789 fixed）
        │
        ├──────────────► CLIPTextEncode A ─► KSampler A（denoise 0.4/0.5，同 seed，latent=首帧）
        ├──────────────► CLIPTextEncode B ─► KSampler B（denoise 0.4/0.5，同 seed，latent=首帧）
        │
   N × LatentInterpolate（N = frames，8–60；每帧一个 ratio）
        │
   N × VAEDecode
        │
   ImageBatchMulti（inputcount = N，image_1 … image_N）
        ├──► SaveAnimatedPNG   → output\APNG\final\apng\anim24_00001_.png
        ├──► SaveAnimatedWEBP  → output\APNG\final\webp\anim24_00001_.webp
        └──► VHS_VideoCombine  → output\APNG\final\gif\anim24_00001.gif
```

节点数随拍数和帧数变：3 拍 xl 66 / Dit 68，4 拍 69 / 71，5 拍 72 / 74（含全局动作层与 Note）。

**三路输出必须接在同一个 ImageBatchMulti 输出上**，否则三份文件的帧序会不一致。

### 2.1 比例表（以 24 帧为例，直接抄）

| 帧 | samples1 | samples2 | ratio | 段 |
| --- | --- | --- | --- | --- |
| 1 | 首帧 | A | 1.0 | 首帧 → A |
| 2 | 首帧 | A | 0.995 | |
| 3 | 首帧 | A | 0.975 | |
| 4 | 首帧 | A | 0.92 | |
| 5 | 首帧 | A | 0.80 | |
| 6 | 首帧 | A | 0.58 | |
| 7 | 首帧 | A | 0.30 | |
| 8 | 首帧 | A | 0.08 | 逼近 A |
| 9 | A | B | 0.92 | A → B（起点仍在 A 附近，形成停顿） |
| 10 | A | B | 0.80 | |
| 11 | A | B | 0.62 | |
| 12 | A | B | 0.42 | |
| 13 | A | B | 0.22 | |
| 14 | A | B | 0.09 | |
| 15 | A | B | 0.03 | |
| 16 | A | B | 0.0 | 正好 B |
| 17 | B | 首帧 | 0.88 | B → 首帧（起点在 B 附近，形成停顿） |
| 18 | B | 首帧 | 0.72 | |
| 19 | B | 首帧 | 0.52 | |
| 20 | B | 首帧 | 0.32 | |
| 21 | B | 首帧 | 0.16 | |
| 22 | B | 首帧 | 0.06 | |
| 23 | B | 首帧 | 0.02 | |
| 24 | B | 首帧 | 0.01 | 几乎回到首帧，接第 1 帧无缝 |

其它帧数不要手抄这张表：用 `python scripts/make_curve.py --segs 8,8,7,7`（30 帧 4 拍）生成 N 个值，
或直接给 `emit_workflow.py --frames 30`，它会按拍平均分并重算曲线。

要点：

1. **同一对 latent 上 ratio 不重复**。不同段之间同值安全（样本对不同，画面必然不同）；同一段里撞值才会产生像素相同的相邻帧。
2. 停顿靠「两端靠近同一个关键帧」实现（8 帧 0.08 → 9 帧 0.92；16 帧 0.0 → 17 帧 0.88），不是靠减帧。这两处 0.92 / 0.0 落在不同段，属于安全复用。
3. 首尾都在首帧附近（1.0 与 0.01），循环播放不跳。

### 2.2 相同帧会被吃掉（必须知道）

Pillow 写 APNG 时，如果两帧像素完全相同，会**丢掉这一帧并把 duration 累加到上一帧**
（`PIL/PngImagePlugin.py` 的 `_write_multiple_frames`，`bbox` 为空就 `previous.encoderinfo["duration"] += ...; continue`）。
实测排了 24 帧导出只剩 19 帧，就是这个原因。**同一对 samples1/samples2 上不要出现重复 ratio**；不同段同值是安全的，但首尾帧也不要像素级完全相同。

---

### 2.3 从 3 关键帧扩到 K 关键帧（做剧情，不改结构）

3 个关键帧只有三段时，能演的只有"起 → 一个动作 → 回落"。要演完整故事，把关键帧从 3 个加到 4–5 个，段数跟着加，每加一个关键帧只多 3 个节点（`CLIPTextEncode` + `KSampler` + `ConditioningCombine`）：

| 拍数 | 关键帧链 | 段数 | 24 帧分配（其它帧数按拍平均分） |
| --- | --- | --- | --- |
| 3 | 首帧 → A → B | 3 | 8 / 8 / 8 |
| 4 | 首帧 → A → B → C | 4 | 6 / 7 / 6 / 5 |
| 5 | 首帧 → A → B → C → D | 5 | 5 / 6 / 5 / 4 / 4 |

加一个关键帧（以 xl 为例，Dit 同构）：

1. 复制 `CLIPTextEncode`(6) 与 `KSampler`(7) 一整对成新节点；`KSampler` 的 `latent_image` 仍接首帧 `VAEEncode`，`positive` 接新 `CLIPTextEncode`，seed 改 `123456792`、mode 仍 `fixed`。
2. 把原来 `A→B` 那段 8 个 `LatentInterpolate` 拆成 `A→B` 与 `B→C` 两组，`samples1` / `samples2` 按段改接。
3. 用 `make_curve.py --segs 6,7,6,5` 重算 24 个 ratio，逐个粘贴。
4. 单段帧数不要低于 4：低于 4 帧的那段看不出动作，只算一次跳。拍数上去了就减段数，或把总帧数加到 30/60（`--frames 30 --segs 6,6,6,6,6`）。

## 3 · 保存节点参数

| 节点 | 参数 | xl | Dit | 说明 |
| --- | --- | --- | --- | --- |
| SaveAnimatedPNG | filename_prefix | `APNG/final/apng/anim24` | 同 | 前缀里的 `/` 会建子目录 |
| | fps | 10 | 10 | 每帧 `int(1000/fps)` 毫秒；24 帧 @10fps = 2.4s，60 帧 @30fps = 2s |
| | compress_level | 4 | 4 | 0–9，越高越小越慢 |
| SaveAnimatedWEBP | filename_prefix | `APNG/final/webp/anim24` | 同 | |
| | fps | 10 | 10 | |
| | lossless | True | True | **要体积就改 False** |
| | quality | 90 | 90 | lossless=True 时不生效 |
| | method | default | default | default=4 / fastest=0 / slowest=6 |
| VHS_VideoCombine | frame_rate | 10 | 10 | |
| | loop_count | 0 | 0 | 0 = 无限循环 |
| | filename_prefix | `APNG/final/gif/anim24` | 同 | |
| | format | image/gif | 同 | |
| | pingpong | False | False | 开着会正放+倒放，帧数翻倍 |
| | save_output | True | True | |

输出实测（24 帧 512²，2026-11-23 成片）：

| 环境 / 内容 | 帧数 | APNG | GIF | WebP（lossless=True） |
| --- | --- | --- | --- | --- |
| xl / 银发校服 | 24 | 6.61 MB | 2.41 MB | 0.80 MB |
| Dit / 银发校服 | 24 | 4.15 MB | 2.72 MB | 2.88 MB |
| Dit / 雨夜霓虹 | 60 | 17.23 MB | 7.21 MB | 12.76 MB |

体积随画面复杂度波动，不是固定比例。**WebP 开了 lossless 不一定比 GIF 小**；要小就关掉 lossless，quality 80–90。

---

## 4 · 节奏怎么调（不要靠减帧）

节奏分三层，**互不干扰**，调的时候一次只动一层：

| 层 | 在哪改 | 影响 |
| --- | --- | --- |
| 总时长 | 三个保存节点的 `fps`（剧情卡 `fps`） | `frames / fps`。60 帧 @20fps = 3 秒 |
| 每拍停留 | 剧情卡 `dwell`（每拍一个权重） | 关键帧多停、过渡快过；总时长不变 |
| 拍内缓动 | 剧情卡 `ease`（0–0.8，默认 0.3） | 每拍首尾帧延时加长，中段加速 |

**ComfyUI 的保存节点只接受一个全局 fps**，逐帧停留表达不出来。所以 `dwell` / `ease` 是
**导出后重定时**，不是采样参数：

```bash
python scripts/retime.py <apng> --story <剧情卡>        # 只改 fcTL 的 delay，像素一个不动
python scripts/make_preview.py <apng> --story <剧情卡> --out-dir docs/assets
```

三步顺序固定：`emit_workflow.py` 出图 → `retime.py` 改节奏 → `make_preview.py` 出网页预览。

### 4.1 帧数 × 帧率

| 帧数 | 慢（叙事） | 标准 | 快（弹幕感） |
| --- | --- | --- | --- |
| 8 | 6fps / 1.33s | 8fps / 1.00s | 10fps / 0.80s |
| 24 | 8fps / 3.00s | 10fps / 2.40s | 12fps / 2.00s |
| 30 | 10fps / 3.00s | 15fps / 2.00s | 20fps / 1.50s |
| 60 | **20fps / 3.00s（默认）** | 25fps / 2.40s | 30fps / 2.00s |

**GIF 的帧延时只能量化到 10ms（1 厘秒）**。这是硬限制，不是可选优化：

| fps | 每帧 | GIF 实际写入 | 60 帧实际时长 |
| --- | --- | --- | --- |
| 8 | 125ms | 120ms | 7.2s（24 帧时 2.9s） |
| 10 | 100ms | 100ms ✓ | 6.0s（24 帧时 2.4s） |
| 20 | 50ms | 50ms ✓ | 3.00s |
| 25 | 40ms | 40ms ✓ | 2.40s |
| 24 | 41.7ms | 40ms | **2.40s，不是 2.5s** |
| 30 | 33.3ms | 30ms | **1.80s，不是 2.0s** |

打 ✓ 的整除档 GIF 不会悄悄改速。APNG / WebP 是毫秒精度，任何 fps 都准。
要 GIF 干净就把 fps 限定在 8 / 10 / 20 / 25。

### 4.2 每拍至少 0.20 秒

十一拍 60 帧 @20fps，平均每拍 0.27 秒。只动肩头的拍可以给 4 帧（0.20 秒），再少就是一闪而过。
`retime.py` 和 `check_anim.py --story` 都会把低于 200ms 的拍标成 WARN。

### 4.3 优先级

1. **整体太快 → 先降 fps**。帧数不动，插值步长不变，只是整体变慢，最省事。
2. **某几拍要看清楚 → 调 `dwell`**。动作跨度大的拍给 1.3，只动肩头的给 0.9。
3. **每拍内部要"起—停" → 调 `ease`**。0.3 够用，超过 0.5 会显得黏。
4. **动作幅度不够 → 先加 A/B 提示词差异，再加 denoise**（UNet 0.4→0.45；MOSS-Image 0.85→0.90 上限）。
5. **不要用加帧数换"慢"**。加帧只会让过渡更细，不会让每一拍停留更久。

手感基准（实测可接受区间）：

| 指标 | 合适范围 | 说明 |
| --- | --- | --- |
| 相邻帧平均像素差 | 0.3–3.0 | xl 偏小（0.4 左右）属正常，超过 0 就行 |
| 总时长 | 表情包 1.6–3.0 s；故事片 3–4 s | 单表情超过 3s 会显得拖 |
| 单拍时长 | ≥ 0.20 s | 再短就是一闪而过 |
| 停顿帧 | 每个关键帧 1–2 帧 | 再多就像卡住 |

xl 现在偏"细腻"，想要更明显：A 的 `blush` 保留、加 `mouth open` 或 `closed eyes`→`squint`，denoise 提到 0.45。
DiT 侧 MOSS-Image 的差异已到 1.72–5.00（v1.3.2 实测），动作幅度够，不要再加大。

---

## 5 · 提示词写法（决定连贯度的一半）

### 5.0 两套方言：`tags` 与 `moss_zh`

`emit_workflow.py --prompt-mode`（或剧情卡 `"prompt_mode"`）决定三段怎么拼：

| 模式 | 拼接结果 | 给谁用 |
| --- | --- | --- |
| `tags`（默认） | `lock, 动作, style` 英文逗号 | SDXL / 传统 CLIP |
| `moss_zh` | `lock。\n 动作。\n style。` 中文散文 | MOSS-Image / Krea 2 / Qwen-Image / Anima（Qwen-VL 系） |

方言跟**文本编码器**走，不跟模型名走。第三种方言是 T5（FLUX / SD3）：完整英文句子，不用 `(word:1.3)`
权重括号。三种方言的完整规则在仓库 `docs/prompting.md`，画布上的 Note 也写了一份。

MOSS-Image 读的是自然语言语义，不读逗号标签权重。堆 `masterpiece, best quality` 只会让它退回通用图库风格。
用**可测量的身体描述**代替形容词：

- 震惊 = 双眼睁大、瞳孔缩小、嘴张开
- 疲惫嫌弃 = 眼半闭、瞳孔偏低、唇压成直线
- 破功 = 肩膀塌下、头低到接近碗口、嘴角拉成直线

构图必须写死：固定机位、平视、全身镜头、从头到脚完整入画、双手双脚留在画框内。
负向也用中文，放在单独的 `CLIPTextEncode`。

完整范例 `assets/story.diet.json`：十一拍 / 60 帧 / 20fps / 3.0 秒 / 640×640，节拍 `5,5,4,7,6,7,5,6,5,5,5`，
denoise 0.85，每拍停留 `dwell = 0.95, 0.95, 1.1, 1.3, 1.0, 1.3, 0.95, 1.0, 0.9, 0.95, 0.95`。生成命令：

```bash
python scripts/emit_workflow.py --base workflows/workflow-moss.json \
  --story assets/story.diet.json --size 640 --out diet60.json
```

三个正向框必须共享同一句"主体锁定句"，只改表情尾巴：

```
主体锁定（三个框都一样）
masterpiece, best quality, 1girl, solo, upper body, looking at viewer, simple background

首帧：… , neutral expression, mouth closed
关键帧 A：… , big smile, eyes half closed, blush
关键帧 B：… , laughing, mouth open, blush
负向：worst quality, low quality, blurry, watermark, text, signature, bad anatomy, extra fingers
```

规则：

1. **只改 1–2 个动作标签**。加 `arms up`、`turn head`、`from side` 会连构图一起变，帧间就割裂。
2. **A 和 B 要有梯度**：A 是"小笑"，B 是"大笑张嘴"。两帧太像就看不出动。
3. **SDXL 不要用 `eyes closed`**。实测虹膜从灰蓝渐变到青绿，播放像闪；用 `eyes half closed` 或 `squint`。
4. MOSS-Image 对表情控制弱一些，A/B 用词差异可以更大（`eyes closed` 在 DiT 上是稳的）。
5. 负向保持固定，不要逐帧改。
6. 换角色只改主体句里的角色描述，A/B 的表情词原样保留。

### 5.1 现成表情模板（A / B 直接替换）

| 效果 | A | B | 备注 |
| --- | --- | --- | --- |
| 微笑 → 大笑 | `big smile, eyes half closed` | `laughing, mouth open` | 当前默认，最稳 |
| 眨眼 | `one eye closed, wink` | `eyes closed, smile` | 眨眼帧少一点更好看 |
| 惊讶 | `surprised, mouth open, wide eyes` | `shocked, gasp` | 动作幅度大，denoise 降 0.05 |
| 害羞 | `blush, looking away` | `blush, eyes closed, shy smile` | 眼神偏移容易漂，先小步试 |
| 生气 | `pout, angry` | `angry, mouth open, frown` | 眉毛变化明显，注意别换脸 |
| 哭 | `teary eyes, sad` | `crying, tears` | 眼泪容易变成噪点，512 下慎用 |

---

### 5.2 表情包不是"动了一下"（定义与故事内核）

维基定义（2026-11-23 抓取）：表情包是以图片为媒介、在社交软件或社交网站兴起后形成的流行文化，通常以名人、语录、漫画、影视截图等素材，配上传达主旨或解释图片的文字，用来表达特定情感或观点，属于迷因的一种。**关键词是"表达"和"观点"，不是"画面在动"。**

判断一版动图合不合格，不看 diff 数值，看三条：

| 判据 | 合格 | 不合格 |
| --- | --- | --- |
| 读得懂 | 不看文字也知道这人在"得意 / 无语 / 崩溃" | 只是眼睛眨了、嘴动了两下 |
| 有转折 | 铺垫 → 变化 → 收住，三拍完整 | 从头到尾一个表情匀速过渡 |
| 可复用 | 抽掉具体角色，这个梗还能用 | 只有这张脸好看，换人就没意义 |

最小故事结构（3 拍，正好对 3 关键帧）：

```
铺垫（首帧）：常态，情绪中立，别做怪表情
转折（A）  ：一个明确的态度变化，幅度要够，第一眼能看出来
强化（B）  ：比 A 再推一步（张嘴、垮脸、翻白眼、后仰），然后回落到首帧
```

4–5 拍版本：`常态 → 察觉 → 反应 → 强化 → 收`。

### 5.3 剧情动作指导模块（剧情卡）

不要边想边改提示词。先填一张剧情卡，再编译成 3–5 个关键帧提示词。六栏：

| 栏 | 写什么 | 例 |
| --- | --- | --- |
| 1 主体锁定句 | 逐字复制进每个关键帧，一个字不改 | `masterpiece, best quality, 1girl, solo, upper body, looking at viewer, simple background, silver hair, blue eyes, school uniform` |
| 2 画风锁定 | 画风/渲染词，同样逐字复制 | `anime screencap, clean lineart, flat cel shading` |
| 3 情绪曲线 | 按拍写 3–5 个情绪 | `neutral → annoyed → exasperated → done` |
| 4 动作轨迹 | 每拍只给 1 个身体动作 + 1 个表情 | `head tilted 8 degrees` / `one eyebrow raised` |
| 5 停顿点 | 哪几拍要停 | 转折拍停 2 帧，收尾拍停 2 帧 |
| 6 禁止项 | 负向 + 本片禁改项 | `different hair color, different eye color, color shift, style change` |

编译规则（硬性）：

1. `关键帧_i = 主体锁定句 + 画风锁定 + 第 i 拍动作 + 第 i 拍表情`，字段顺序固定。
2. 每帧只许改第 3、4 栏的 1–2 个标签；机位、景别、光照、背景、服装一律不动。
3. 情绪词要能落到身体上（借 prompt-forge 的"可测量替代形容词"）：不写 `smug`，写 `the corner of her mouth pulled up, one eyebrow raised`；不写 `annoyed`，写 `eyes half lidded, lips pressed together`。
4. 不写 `更有张力 / 更华丽 / 更可爱` 这类效果词，模型只会往极端推。
5. 首帧必须中性，首帧就做表情，整条曲线没有起点。

剧情卡 → 提示词（4 拍，24 帧 6/7/6/5）：

```
主体锁定：masterpiece, best quality, 1girl, solo, upper body, looking at viewer, simple background, silver hair, blue eyes, school uniform
画风锁定：anime screencap, clean lineart, flat cel shading

K0 首帧：… , neutral expression, mouth closed, head straight
K1 察觉：… , eyes widened, eyebrows raised, head tilted 8 degrees
K2 反应：… , eyes half closed, mouth open, head tilted back 12 degrees
K3 收：  … , flat expression, eyes half lidded, mouth closed, head straight

负向：worst quality, low quality, blurry, watermark, text, signature, bad anatomy, extra fingers,
      different hair color, different eye color, color shift, style change, multiple views
```

### 5.3.1 动作库：17 组现成节拍

`assets/motion-presets.json` 把常见表情包动作写成了可复用的节拍卡，`scripts/make_story.py` 直接生成剧情卡：

```bash
python scripts/make_story.py --list
python scripts/make_story.py --preset laugh --lock "masterpiece, 1girl, silver hair, blue eyes" --out story.laugh.json
python scripts/make_story.py --preset rainy-walk --lock "masterpiece, 1girl" --frames 60 --fps 30 --out story.rain.json
```

| 组 | id |
| --- | --- |
| 情绪 | `laugh` `cry` `shock` `angry` `smug` `sigh` `panic` `sleepy` `love` |
| 动作 | `wave` `nod` `shake` `thumbsup` `think` |
| 五拍故事 | `rainy-walk` `morning-coffee` |
| 十一拍全身故事 | `diet-betrayal`（`moss_zh` 中文散文，60 帧） |

表情/动作卡固定为五拍：**K0 静息（循环接点 + 封面）→ K1 预备（反方向蓄力）→ K2 主动作（最大剪影变化）→ K3 余震（回落）→ 回到 K0**。
故事卡不受五拍限制：`diet-betrayal` 是 11 拍 60 帧，每一拍只推进一步，大动作多给帧。
每拍只改 1–2 个部位；`style` 必须放在提示词末尾。完整说明与平台规格（Telegram 512/≤3s/60fps、LINE APNG 5–20 帧/≤4s/≤1MB、微信 GIF 240²/≤500KB）
见 [docs/motion-presets.md](docs/motion-presets.md)。

### 5.4 不换脸、不换发色、不换瞳色

| 现象 | 根因 | 处理 |
| --- | --- | --- |
| 眼睛颜色逐帧渐变（灰蓝 → 青绿） | 关键帧写了 `eyes closed` / `crying` / `glowing eyes`，SDXL 重算虹膜 | 改 `eyes half closed` / `squint`；负向加 `color shift, different eye color` |
| 头发颜色漂 | 关键帧带了光照/环境词（`night`, `rim light`, `sunset`） | 光照词只写在主体锁定句里，所有帧共用一套 |
| 脸型变了 | denoise 太高，或 A/B 带了机位、姿势、场景词 | denoise 降 0.05；删机位、姿势、场景词 |
| 画风变了 | 每个框各写一套画风 | 画风锁定句逐字复制，不许同义替换（`anime` ≠ `anime style`） |
| 服装细节变了 | 动作词带了 `arms up` / `turn around` | 大动作走 5.5 的 B/C 档，别靠加 denoise 硬顶 |

实测口径：xl 关键帧 denoise ≤ 0.45 主体稳定，0.55 起五官漂；闭眼是 xl 最典型的翻车点，DiT 的 MOSS-Image 对闭眼宽容（可用 `eyes closed`）。

### 5.5 多角色与任意动作：三档能力

现工作流只擅长"同构图下的微动"：表情、呼吸、轻微头部动作。老板明确要求不能只限单人上半身，按能力分档，别用一档硬做另一档的活：

| 档 | 能做什么 | 做法 | 依赖 |
| --- | --- | --- | --- |
| A 微动（现工作流） | 单人/双人同构图，表情与头部微动 | 三关键帧 + `LatentInterpolate` | 无 |
| B 中动 | 转头、抬手、转身、双人互动 | 每个关键帧挂一张 ControlNet OpenPose/Depth 图 + IPAdapter 锁脸，denoise 0.55–0.7 | 两环境都有 `comfyui_controlnet_aux`、`ComfyUI-IPAdapter_plus`；xl 另有 `ComfyUI-Advanced-ControlNet` |
| C 大动 | 走位、打斗、镜头运动 | Wan / LTX 视频模型出片再转 GIF | 两环境都有 `ComfyUI-WanVideoWrapper`、`ComfyUI-LTXVideo`，需另下视频模型；本 skill 未实测 |

多角色注意：

1. 所有角色都要出现在首帧，左右/前后关系写死；插值不会凭空生人。
2. 互动（推、抱、对视）走 B 档：接触点的几何变化，latent 插值做不出来，只会糊。
3. 双人 denoise 比单人低 0.05–0.1，否则两张脸一起漂。
4. 主体锁定句里每个角色独立描述，顺序固定：`1girl ... , 1boy ...`，别写 `two people`。

## 6 · 只存成品：目录与命名

### 6.0 落盘细则（归档会话里踩过的坑）

- 只接三个保存节点，全部接**同一个** `ImageBatchMulti` 输出；中间不接 `SaveImage` / `PreviewImage`。xl 66 节点、Dit 68 节点 = 3 关键帧 + 3 个条件合并 + 1 个全局动作编码 + 1 个 Note + N 插值 + N 解码 + 三输出，没有隐藏的落盘节点。
- 目录分层（两环境一致）：

```
output\APNG\
├─ final\apng\anim24_00001_.png
├─ final\webp\anim24_00001_.webp
├─ final\gif\anim24_00001.gif
└─ archive\frames\     archive\tests\
```

- `filename_prefix` 里的 `/` 会建子目录；改完前缀必须 **F5 刷新页面**再 Queue，否则前端还持旧 prefix，成品落到 `output\APNG\anim24_00001_.png`（踩过两次）。
- VHS 出 GIF 时会在同目录多写一张同名 `.png`（首帧预览），插件行为，不是每帧保存，可以删。
- 计数器每次 Queue 自增；要固定名就把 prefix 改成 `APNG/final/apng/我的表情`。
- 工作流本身不落单帧。看到 `anim24_1_00002_.png` 这种带 `_1_`、`_2_` 的是历史脚本的中间帧，不是成品；BandiView 要打开 `anim24_*.png` 才是动图。
- 备份工作流不要留在 `user\default\workflows`，会和工作流同名混淆（踩过：`-v1.json` 被当成第二套工作流）。备份放 `archive`。

```
<ComfyUI>\output\APNG\
├─ final\
│  ├─ apng\anim24_00001_.png      ← 成品 APNG
│  ├─ webp\anim24_00001_.webp     ← 成品 WebP
│  └─ gif\anim24_00001.gif        ← 成品 GIF
└─ archive\
   ├─ frames\                     ← 需要留档的单帧（默认不产生）
   └─ tests\                      ← 调参期的试片
```

- 三个保存节点都指向同一个 batch，**不再接 SaveImage / PreviewImage**。
- 计数器每次 Queue 自增，取最新一个看 mtime 就行；想固定名字就把 prefix 改成 `APNG/final/apng/我的表情`。
- VHS 会在 gif 同目录多写一张同名 `.png`（首帧预览），属插件行为，可以删。
- 前缀被旧值覆盖过会导致成品落到 `output\APNG\anim24_00001_.png`；改完 prefix 记得**刷新浏览器页面**再 Queue。
- 结构自查：`python scripts/check_output.py --profile profiles/xl.json`；加 `--fix` 把 `APNG` 根目录和 `output` 根目录的游离文件移进 `APNG/archive/stray-<时间戳>/`。完整规则见 `docs/output.md`。

校验（脚本在 `scripts/check_anim.py`，**必须用 ComfyUI 自带的 Python**，`C:\Python315` 没装 Pillow）：

```powershell
& 'D:\ComfyUI-aki-v3.2-xl\python\python.exe' 'scripts\check_anim.py' 'D:\ComfyUI-aki-v3.2-xl\ComfyUI\output\APNG\final\apng\anim24_00001_.png' --expect 24
```

输出 `frames=24`、`loop=0`、`identical_pairs=0` 才算过关；退出码 1 表示帧数不对。

---

## 7 · 表情包控制

| 维度 | 建议 | 原因 |
| --- | --- | --- |
| 尺寸 | 512×512；要更小就 384 或 320 | 每帧仍是 512²，显存基本不随帧数涨 |
| 主体 | 默认单人上半身、居中、留边；双人/全身见 5.5 | 小窗里要看得清；但别把它当硬限制 |
| 背景 | `simple background` / 纯色 | 背景一动就抢戏，还会让文件变大 |
| 帧数 | 16–24 | 少于 12 像幻灯片，多于 32 收益低 |
| 时长 | 1.6–3.0 s | 24 帧 @10fps = 2.4s |
| 停顿 | 每个关键帧 1–2 帧 | 让动作有节奏，不是匀速平移 |
| 循环 | 首尾都在首帧附近 | 否则每次循环会"跳一下" |
| 动作幅度 | 小 | 大幅动作必然换构图，割裂感来自这里 |
| 文字 | 不要放进图里 | 512 下会糊，后期加字更清楚 |

分发建议：

| 场景 | 用哪个 | 说明 |
| --- | --- | --- |
| 微信 / QQ 聊天 | GIF | 兼容性最好，256 色够用 |
| 网页 / Discord / 文档 | WebP | 支持透明、体积小（关掉 lossless 更小） |
| 本地高清回看 | APNG | 无损、24 位色，浏览器和 BandiView 能播 |
| 微信自定义表情 | GIF，控制在 5MB 内 | 平台规则会变，上传前以客户端提示为准（未逐一验证） |

---

## 8 · 兼容性事实

- APNG 浏览器支持率 **97.39%**（caniuse `apng`，2026-11-23 抓取），Chrome / Edge / Firefox / Safari / Android 全绿。
- WebP 支持率 **97.24%**（caniuse `webp`，同日）。
- **Windows 自带照片查看器据报不播 APNG**（本机未复测；用户实际用的是 BandiView，能正常播）；浏览器拖进去也能看。
- 网页里看到的动图是**已经合成好的单个 APNG 文件**，不是前端逐帧切换。
- APNG 用 Pillow 编码，`loop=0`（无限循环），每帧时长固定为 `int(1000/fps)`。

---

### 8.1 规格事实（本轮核对）

| 事实 | 来源 |
| --- | --- |
| APNG `acTL.num_plays = 0` 表示无限循环；`num_frames` 必须等于 `fcTL` 数量 | APNG 规范 |
| APNG 帧时长 = `delay_num / delay_den` 秒；`delay_den = 0` 按 100 处理，即 1/100 秒 | APNG 规范 |
| ComfyUI `SaveAnimatedPNG/WEBP` 的 `duration = int(1000.0 / fps)`，整数毫秒 | `comfy_api/latest/_ui.py` |
| GIF 帧延迟单位是 1/100 秒（GCE），实际 fps 只能取 100/n：10fps = 10cs 精确；12fps → 8cs ≈ 12.5fps；9fps → 11cs ≈ 9.1fps | GIF89a |
| VHS 的 GIF 是单遍 `palettegen` + `paletteuse`，全片统一调色板，`sierra2_4a` 抖动 | `video_formats/ffmpeg-gif.json` |
| Pillow 写 APNG 时相邻帧像素完全相同就丢这帧，把 duration 累加到上一帧 | `PIL/PngImagePlugin.py` |
| caniuse：APNG 97.39%，WebP 97.24%（2026-11-23 抓取） | caniuse |

## 9 · 故障排查

| 症状 | 根因 | 处理 |
| --- | --- | --- |
| N 张互不相干、一直闪 | 把帧数塞进 `batch_size` | 改成「首帧 latent + 关键帧重绘 + 插值」结构 |
| 颜色越播越跑（黑发变青） | 逐帧继承上一帧 | 所有关键帧的 latent 都接首帧 |
| 排了 N 帧，导出明显变少（24 → 19） | 有像素完全相同的相邻帧，Pillow 合并 | 曲线不要有重复 ratio；首尾别做成一模一样 |
| 输出只有一张静态 PNG | `images` 只有 1 张 | 确认 ImageBatchMulti 的 N 个输入都接上 |
| 照片查看器不动 | 它不支持 APNG | 看 GIF/WebP，或用 BandiView / 浏览器 |
| 只有 APNG，没有 GIF/WebP | 缺 VHS 插件 / 节点爆红 | `custom_nodes` 装 `ComfyUI-VideoHelperSuite`，重启 |
| 文件落在 `output\APNG\` 根目录 | prefix 被旧值覆盖 | 三个保存节点逐个改前缀，刷新页面重跑 |
| 启动报端口占用 | 上次验证实例没退 | `netstat -ano \| findstr :8189` → `Stop-Process -Id` |
| 动作太快 | fps 偏高 / 曲线中段太陡 | fps 10→9，或把中段比例拆细 |
| 动作太慢、像卡住 | 停顿帧太多 | 每段保留 1 个停顿帧即可 |
| 表情变了但脸也变了 | denoise 太高 / A、B 提示词带了构图词 | denoise -0.05，删掉机位、姿势、场景词 |
| 看不出动作 | A、B 太像 | 加大表情差异（张嘴、挑眉、闭眼） |
| 画面掉成写实拼贴、脸糊 | 空 `motion` 仍参与 `ConditioningCombine`，稀释了本帧提示 | 1.3.0 起留空会自动旁路；旧工作流删掉合并节点或填一句 `same framing, stable lighting` |
| 风格被动作词吃掉 | `style` 写在 `action` 前面 | 固定顺序 `lock + action + style`，风格词放末尾 |
| 前端改了不生效 | 页面还持着旧节点 | F5 刷新后再 Queue |

---

### 9.1 补充症状

| 症状 | 根因 | 处理 |
| --- | --- | --- |
| 启动刷 ComfyRegistry / GitHub 报错 | Manager 联网 | `user\__manager\config.ini` 里 `network_mode = offline`（两环境已改） |
| 工作流改了不生效、还落旧目录 | 页面持旧节点 | F5 刷新后重开工作流 |
| 只有一张静态 png | `images` 只有 1 张 | `ImageBatchMulti` 的 inputcount 必须等于 frames，输入全接 |
| 眼睛颜色渐变、像在闪 | `eyes closed` 或光照词变动 | 见 5.4 |
| 双人一互动就糊 | 用 A 档做 B 档的活 | 见 5.5，上 ControlNet |
| N 帧只剩更少（24 → 19） | 曲线里有重复 ratio | 见 2.2 |
| 动作幅度够了但读不出情绪 | 只改了表情词，没给身体动作 | 见 5.3 剧情卡第 3、4 栏 |

## 10 · 从零复刻 / 换题材的操作顺序

1. 打开对应环境的工作流（xl：`APNG多帧合成-SDXL.json`；Dit：`APNG多帧合成-Moss.json`）。
2. 改 4 个文本框：首帧、A、B、负向。三句正向共享主体锁定句。
3. 确认 3 个 KSampler 的 seed 都是 `fixed`（123456789 / +1 / +2），denoise 分别 1.0 / 0.4 或 0.5。
4. 确认 N 个 ratio 与第 2.1 节一致（或用 `make_curve.py` / `--frames` 重算），且**没有重复值**。
5. 确认 ImageBatchMulti `inputcount = frames`，N 个输入全接上。
6. 确认三个保存节点的 prefix 分别是 `APNG/final/apng|webp|gif/anim24`。
7. Queue，等结束，去 `output\APNG\final\` 取成品。
8. 跑 `check_anim.py --expect 24` 验证。
9. 不满意先调 fps，再调曲线密度，最后才动 denoise。

---

## 11 · 已知限制

- 没有真正的"运动轨迹"：这是三关键帧之间的 latent 插值，适合表情、呼吸、轻微头部动作，不适合走路、转身、镜头运动。
- 帧数多了耗时线性增加（每帧一次 VAE 解码；采样只跑 3 次）。
- 512 以下 APNG 体积仍然偏大（每帧全尺寸 PNG），发聊天软件优先 GIF。
- DiT 的 MOSS-Image 对表情服从度弱于 SDXL，极限表情需要更大 denoise；DMD 模型的上限在 0.90，超过就开始漂。
- 工作流是 24 个独立插值节点，改曲线要逐个数；这是"一体化、不依赖脚本"的代价。批量改曲线可以用 `scripts/make_curve.py` 生成值再粘贴。

---

## 12 · 来自前几轮会话的教训（血泪版）

1. 第一版用 `batch_size=8`，8 张是 8 个独立噪声，播放就是闪烁——固定 seed 救不了。
2. 第二版逐帧继承上一帧，动作顺了但黑发漂成青蓝。
3. 第三版改成"首帧 + 7 帧同源重绘"，差异均匀，方向才正确。
4. 中途留了 `-v1.json` 备份，用户看到两个工作流以为出错——备份要放 `archive`，不要留在 workflows 目录。
5. 用 8189 验证完没清进程，绘世启动器报端口占用——验证一律 8190/8191，结束必须确认端口空。
6. 早期每帧都 SaveImage，输出目录几百张 PNG——改成只保存成品。
7. 前缀被旧值覆盖，成品落到 `output\APNG\` 根目录——改完 prefix 要刷新页面。
8. 24 帧导出 19 帧——Pillow 合并相同帧，见 2.2。
9. xl 用 `eyes closed` 导致虹膜变色像闪——换 `eyes half closed`。
10. Windows 照片不播 APNG，用户以为没合成——同时输出 GIF + WebP。
11. GIF 若逐帧各自量化会颜色跳，VHS 的 `image/gif` 用的是全片统一调色板 + `sierra2_4a` 抖动（`video_formats\ffmpeg-gif.json`），比逐帧量化稳。
12. WebP 开 `lossless=True` 体积可能比 GIF 还大，要小就关。
13. xl 关键帧 denoise 的演进 0.55 → 0.45 → 0.4：0.55 五官开始漂，0.4–0.45 是幅度与稳定的平衡点。
14. 三格式输出必须接同一个 `ImageBatchMulti`，各接各的 batch 会让 APNG/WebP/GIF 帧序不一致。
15. 只加提示词、不加拍数，做不出剧情：三关键帧最多演"起 → 一个动作 → 回落"。
16. 瞳色/发色漂移不只 `eyes closed`：任何改变光照或材质的词（`night`、`rim light`、`wet`、`glowing`）都会在插值里变成逐帧渐变。
17. 60 帧十一拍按 30fps 播完只要 2 秒，11 拍挤在 2 秒里根本没有衔接——节奏要靠 `fps` + `dwell` 显式写出来，不能只写在文档里一句话。
18. GIF 的帧延时是厘秒：24fps 会被悄悄写成 40ms，整片变 2.4 秒。要 GIF 干净就选 20 / 25fps。
19. 把「MOSS」和「DiT」并列写成两类，是把模型当架构。**DiT 是架构，MOSS 是模型**；这个错曾扩散到 README、SKILL 和九个文档页。

## 13 · 文件清单

| 路径 | 用途 |
| --- | --- |
| `workflows/workflow-sdxl.json` | xl 环境工作流副本（与线上一致） |
| `workflows/workflow-moss.json` | DiT 系环境工作流副本（装任何 DiT 模型，换三个加载器即可） |
| `scripts/check_anim.py` | 帧数 / 时长 / 相邻帧差异 / 颜色漂移校验 |
| `scripts/make_preview.py` | 成品 APNG → 全局调色板 GIF + WebP 网页预览；`--story` 写逐帧延时 |
| `scripts/retime.py` | 出片后重写逐帧停留（fps / dwell / ease），像素不动 |
| `scripts/timing.py` | 帧延时计算唯一真相源（被 retime / make_preview / check_anim / emit 共用） |
| `scripts/make_storyboard.py` | 按 segs 抽关键拍拼联系表 → `docs/assets/storyboard-*.webp` |
| `scripts/sync_workflows.py` | `workflows/` 与 `assets/` → `docs/assets/` 同步，`--check` 查漂移 |
| `scripts/make_story.py` | 从 `assets/motion-presets.json` 生成剧情卡；校验 frames/segs/beats |
| `assets/motion-presets.json` | 17 组动作节拍（情绪 / 动作 / 五拍故事 / 十一拍 moss_zh 故事） |
| `scripts/make_curve.py` | 生成 ratio 曲线，支持 3–6 段：`--segs 6,7,6,5` 出 24 值 |
| `scripts/detect_env.py` | 扫本机 ComfyUI → `profiles/*.json`（换机器第一步） |
| `scripts/doctor.py` | profile 体检：模型、插件、节点、端口、输出目录 |
| `scripts/emit_workflow.py` | 3 关键帧 → 3–8 拍剧情工作流；`--prompt-mode`、`--size`、编译提示词、重算曲线、校验、可选 `--run`、`--notes-only` |
| `scripts/comfy_lib.py` | 共用库（profile / HTTP / 曲线 / UI→API） |
| `profiles/xl.json` `profiles/dit.json` | 本机探测结果，换机器重新生成 |
| `assets/story.example.json` `assets/story.4beat.json` | 剧情卡样例（3 拍 / 4 拍，tags 模式） |
| `assets/story.diet.json` | 十一拍全身故事（`moss_zh` 中文散文，60 帧 / 20fps / 带 dwell） |
| `workflows/workflow-sdxl-4beat.json` `workflows/workflow-moss-4beat.json` | 已扩好的 4 拍工作流 |
| `assets/node_schema.json` | 节点定义兜底（服务器 `/object_info` 取不到时用） |
| `scripts/check_deps.py` | 依赖自检：Python / Pillow / curl / profiles 里的 ComfyUI 与插件 |
| `scripts/install.py` | 装到 Codex / magpie 的 skills 目录，覆盖前自动备份 |
| `scripts/package.py` | 打确定性 zip（固定时间戳）+ SHA256，默认不含 profiles |
| `skill.json` | 版本、依赖、入口、安装目标、排除项 |
| `requirements.txt` | 脚本侧依赖（仅 Pillow） |
| `CHANGELOG.md` `LICENSE` `.gitignore` | 分发用元数据 |


| `C:\Users\泽山居士\.codex\archived_sessions\rollout-2026-11-22T15-35-59-*.jsonl` | 原始搭建会话，40 条用户消息 / 18 条助手消息 |
| `C:\Users\泽山居士\.codex\archived_sessions\rollout-2026-11-23T08-54-56-*.jsonl` | 续修会话，剧情模块需求提出处 |
| `C:\Users\泽山居士\.codex\archived_sessions\rollout-2026-11-23T11-38-23-*.jsonl` | 交接会话，skill 成稿记录 |
| `E:\Documents\zezeze\tools\comfyui-apng\anim24.py` | 旧的脚本路线（API 驱动），保留但非首选 |

## 附录 A · profile 字段

```json
{
  "name": "xl",
  "comfy_root": "<ComfyUI 根目录，含 main.py>",
  "python": "<该环境的 python 可执行文件，可空>",
  "host": "127.0.0.1",
  "port": 8188,
  "stack": "sdxl | moss | dit-other | unknown",
  "version": "ComfyUI 版本",
  "models": { "checkpoints": [], "diffusion_models": [], "text_encoders": [], "vae": [] },
  "custom_nodes_present": { "comfyui-kjnodes": true, "ComfyUI-VideoHelperSuite": true },
  "workflow": "<默认打开的工作流（帧数由剧情卡决定）>",
  "fps": 10,
  "prefix_root": "APNG/final"
}
```

只跑 `detect_env.py` 就能生成；手改也只需要这几项。`port` 只影响 `doctor --probe` 和 `emit --run`，跟出图无关。

## 附录 B · 新机器移植清单

| 步骤 | 做什么 | 不做的后果 |
| --- | --- | --- |
| 1 | 装 `comfyui-kjnodes`（`ImageBatchMulti`） | 工作流里合并节点爆红 |
| 2 | 装 `ComfyUI-VideoHelperSuite`（GIF） | 只有 APNG/WebP，没有 GIF |
| 3 | ComfyUI ≥ 0.3（有 `SaveAnimatedPNG` / `SaveAnimatedWEBP`） | 保存节点不存在 |
| 4 | Pillow ≥ 9（`check_anim.py` 要用） | 校验脚本跑不起来 |
| 5 | 模型放对目录：SDXL 进 `models/checkpoints`；MOSS-Image 三件套进 `diffusion_models` / `text_encoders` / `vae` | loader 报找不到文件 |
| 6 | 跑 `detect_env.py` + `doctor.py` | 不知道自己缺什么 |
| 7 | 用 `emit_workflow.py` 生成自己的 K 拍工作流 | 只能用 3 拍 |

不装任何插件也能出 APNG —— `SaveAnimatedPNG` 是 ComfyUI 原生的；缺的只是 24 路合批（KJNodes）和 GIF（VHS）。

## 附录 C · 与本机路径解耦的边界

| 现状 | 说明 |
| --- | --- |
| 正文里的 `D:\ComfyUI-aki-v3.2-xl` | 示例。脚本只从 profile 读路径 |
| 正文里的 8190/8191 | 示例。`doctor`/`emit --run` 用 profile 的 `port` |
| `workflows/workflow-*.json` | 结构模板，模型名要换成你自己的 |
| `profiles/*.json` | 本机探测产物，别拷到别的机器直接用，重新跑 `detect_env.py` |

## 附录 D · 安装、升级、卸载

```powershell
# 装到本机已有的 skills 目录（两个目标都会装）
python scripts/install.py

# 只装一个位置
python scripts/install.py --dest C:\Users\me\.codex\skills\comfyui-apng-motion

# 连本机 profiles 一起装（换机器别用）
python scripts/install.py --with-profiles

# 先看会写哪里
python scripts/install.py --dry-run

# 分发
python scripts/package.py
```

升级就是重新跑一次 `install.py`：旧 `SKILL.md` 自动备份，`profiles/` 不会被删。卸载直接删目标目录。

常查漂移：

```powershell
python scripts/install.py --check
```

确认过要单物理副本再动 `--link`（会把旧目录改名成 `.bak-<时间戳>` 再建 junction）。

版本号在 `skill.json`；改完功能记得同步 `CHANGELOG.md`，再跑 `package.py` 出新 zip。

