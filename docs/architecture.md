# 架构

## 数据流

```
EmptyLatentImage(512,512,1)
        │
   KSampler K0   denoise 1.0, seed 123456789
        │  LATENT ─────────────────────────┐
        ├──────────────► CLIPTextEncode K1 ─┐
        ├──────────────► CLIPTextEncode K2 ─┤
        ├──────────────► CLIPTextEncode K3 ─┤
        │                                   │
   CLIPTextEncode「全局动作指导」──► ConditioningCombine（每帧一个）
                                          │
                     KSampler K1/K2/K3  positive 走合并后的条件
                     denoise 0.35-0.4，与 K0 同 seed、同首帧 latent
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
   同时所有 KSampler 共用同一个 seed：seed 不同会带来不同噪声路径，插值时表现为色斑。
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
| `make_preview.py` | 成品 APNG | 全局调色板 GIF + WebP 网页预览 |
| `package.py` | 仓库目录 | 确定性 zip + SHA256 |

## 曲线

默认 `linear`：每段从 1.0 均匀降到 0.0，每帧步长恒定。

```
段1: 1.0 0.857 0.714 0.571 0.429 0.286 0.143 0.0
段2: 0.996 0.861 ... 0.004        （段首与上一段末几乎相接）
段3: 0.992 0.853 ... 0.008
```

`ease` 用 smootherstep，两端慢、中间快，单帧最大位移约为线性版的 1.9 倍；
`snap` 是旧版幂曲线，前段几乎静止、末段猛冲，容易看成跳帧，只在对比时用。

段与段之间留 0.004 的微差，避免 Pillow 把相邻的完全同值帧合并。

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


