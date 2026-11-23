# 架构

## 数据流

```
EmptyLatentImage(512,512,1)
        │
   KSampler K0   denoise 1.0, seed 123456789
        │  LATENT ─────────────────────────┐
        ├──────────────► CLIPTextEncode K1 ─► KSampler K1  denoise 0.4, seed +1
        ├──────────────► CLIPTextEncode K2 ─► KSampler K2  denoise 0.4, seed +2
        └──────────────► CLIPTextEncode K3 ─► KSampler K3  denoise 0.4, seed +3（4 拍时）
                                          │
        24 × LatentInterpolate（每帧一个 ratio；同一对 latent 内不重复）
                                          │
        24 × VAEDecode ◄── VAE
                                          │
        ImageBatchMulti(inputcount=24)
                ├──► SaveAnimatedPNG   → output/APNG/final/apng/
                ├──► SaveAnimatedWEBP  → output/APNG/final/webp/
                └──► VHS_VideoCombine  → output/APNG/final/gif/
```

关键约束：

1. **所有关键帧的 `latent_image` 都指向 K0 的 LATENT**，不链式继承上一帧，否则颜色会累积漂移。
2. **同一对 latent 上的 ratio 唯一**。不同段（K0→K1 与 K1→K2）可以同值，样本对不同画面就不同；同一段里撞值才会被 Pillow 合并。
3. **三个输出接同一个 batch**，否则三种格式的帧序会不一致。

## 脚本分工

| 脚本 | 输入 | 输出 |
| --- | --- | --- |
| `detect_env.py` | 磁盘上的 ComfyUI | `profiles/*.json` |
| `doctor.py` | profile + 工作流 | PASS/WARN/FAIL 清单 |
| `emit_workflow.py` | base 工作流 + 剧情卡 | K 拍工作流 JSON（含校验） |
| `emit_workflow.py --run` | 上述 + profile | 提交 API、轮询、成品路径、自动校验 |
| `check_anim.py` | 成品文件 | 帧数/时长/循环/差异/颜色漂移 |
| `make_curve.py` | 段数 | 24 个 ratio |
| `package.py` | 仓库目录 | 确定性 zip + SHA256 |

## 曲线

每段从「贴着上一个关键帧」走到「贴着下一个关键帧」：

```
段1: 1.0 → 0.05   段2: 0.94 → 0.04   段3: 0.92 → 0.03   段4: 0.90 → 0.01
```

相邻两段在关节处一个收、一个起，播放时形成 1–2 帧停顿。
3 段时保留旧默认值（`1.0/0.92/0.88` → `0.08/0.0/0.01`），与历史成品一致。

## UI → API

`--run` 需要把 UI 工作流转成 API prompt。`comfy_lib.ui_to_api` 的做法：

1. 用 `/object_info/<type>` 取节点的 required/optional 定义；
2. 按 `input_order` 遍历，链接类型（MODEL/LATENT/...）走连线，其余取 `widgets_values`；
3. 遇到 `control_after_generate`（如 KSampler 的 seed）多跳一格；
4. 每个输入写成 `[origin_node_id, origin_slot]`。

## 为什么不用脚本逐帧生成

逐帧 img2img 需要每帧一次采样，24 帧就是 24 次采样；插值只需要 3–5 次采样 + 24 次解码，
显存不变、耗时线性下降，而且中间帧由数学过渡，差异更均匀。
代价是没有真实运动轨迹，所以只适合微表演。


