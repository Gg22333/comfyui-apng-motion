# 动态帧数模式（工作流内控制）

这一页解决一个具体问题：**帧数、时长、相邻帧差、接缝、分镜，不能只靠 skill 脚本事后算，得在 ComfyUI 图上直接调、直接看。**

静态工作流把「N 帧」展开成 N 个 `LatentInterpolate` + N 个 `VAEDecode`；改帧数就得重跑 `emit_workflow.py`。
动态模式把这一层压成：**每拍一个插值节点，帧数是节点上的一个数字**。

## 1 · 装节点

节点随仓库发布，在 `comfyui_nodes/`。

```bash
python scripts/install_nodes.py --profile xl      # 读 profiles/xl.json 的 comfy_root
python scripts/install_nodes.py --all             # profiles 里所有机器
python scripts/install_nodes.py --check           # 只比对，不写
```

目标固定为 `<comfy_root>/custom_nodes/apng_motion_nodes/`。也可以手动把整个 `comfyui_nodes`
目录复制进去并改名 `apng_motion_nodes`。**装完重启 ComfyUI**，四个节点出现在 `APNG Motion` 分类下。

## 2 · 生成动态工作流

```bash
python scripts/emit_workflow.py \
    --base workflows/workflow-sdxl.json \
    --story assets/story.example.json \
    --dynamic \
    --out my-dynamic.json
```

加整段镜头运动（平移 / 缩放 / 旋转，默认中立值，出图后在图上调）：

```bash
python scripts/emit_workflow.py \
    --base workflows/workflow-sdxl.json \
    --story assets/story.example.json \
    --dynamic --camera \
    --out my-dynamic-camera.json
```

3 拍 24 帧输出 **26 个节点 / 39 条连线**，加 `--camera` 是 27 个节点（同样内容的静态图是 67 个节点）。关键帧链完全不动，
只替换插值/解码/合批层。

```
K 个关键帧 KSampler（同 seed，首帧 latent）
  → 每拍 1 个 APNGLatentInterpolateN（frames = 这一拍的帧数）
  → N-1 个 APNGLatentConcat（按拍序拼 batch）
  → 1 个 VAEDecode（一次解码全部帧）
  → [可选] 1 个 APNG Camera Move（--camera：整段平移 / 缩放 / 旋转）
  → SaveAnimatedPNG + SaveAnimatedWEBP + VHS_VideoCombine
  → APNGFrameStats（打印帧数 / 时长 / 帧差 / 接缝）
```

## 3 · 六个维度分别在哪控制

| 维度 | 工作流里的位置 | 怎么用 |
| --- | --- | --- |
| **帧数** | 每个 `APNG Latent Interpolate N` 的 `frames` widget | 改数字即可。总帧数 = 各拍 `frames` 之和，1–240 |
| **时长** | 三个保存节点的 `fps`，以及 `APNGFrameStats` 的 `fps` | 总时长 = 总帧数 / fps；报告节点直接打印 `duration=2.40s` |
| **相邻帧差** | `APNGFrameStats` 输出 | 打印 `diff min/max/avg` 与 `identical_pairs`；相同帧会警告 APNG 合并帧 |
| **接缝唯一性** | `APNGFrameStats` 的 `segs` widget | 填各拍帧数逗号串（如 `8,8,8`），逐拍打印 `full/lower` 判定 OK/FAIL，并检查循环 `K_N→K0` |
| **分镜 / 故事板** | K 个 `KSampler` + 各自的 `CLIPTextEncode` | 一个关键帧就是一拍，和静态模式完全一致；加拍仍是复制一对节点 |
| **镜头运动** | `APNG Camera Move` 的 `x`/`y`/`zoom`/`angle`/`easing`/`loop` | 整段统一运动；与分镜正交，可叠加（见下一节） |

`APNGFrameStats` 的阈值与 `scripts/check_anim.py` 一致：拍内 `full >= 2.0 && lower >= 1.0`，
循环接缝 `0.3 <= full <= 6.0`。

## 4 · 镜头运动（整段平移 / 缩放 / 旋转）

`--camera` 在 `VAEDecode` 后插一个 `APNG Camera Move`：**对整段所有帧施加同一条相机路径**，
纯像素仿射变换，不重新采样、不加依赖、不碰采样器。默认参数是中立值，出图后在图上调。

| widget | 含义 | 范围 / 取值 |
| --- | --- | --- |
| `x` | 整段总横向位移（像素），正数向右 | -2048…2048 |
| `y` | 整段总纵向位移（像素），正数向下 | -2048…2048 |
| `zoom` | **末帧**倍率，`>1` 推近，`<1` 拉远 | 0.5…4.0 |
| `angle` | 整段总旋转角度（度），正数逆时针 | -360…360 |
| `easing` | 进度曲线：`linear` `sine` `cubic` `quint` `back` `elastic` `bounce` | 默认 `sine` |
| `loop` | `True` 走 0→1→0 往返，首尾帧完全一致 | 默认 `True` |
| `border` | 越界取样：`reflection` 镜像 / `border` 拉伸边缘 / `zeros` 黑边 | 默认 `reflection` |

语义要点：

- **参数是整段总量，不是每帧增量。** 第 i 帧的推进量 `p = ease(i / (N-1))`，位移、缩放、旋转都按 `p` 插值，
  所以 `x=20` 表示「从头到尾一共右移 20 像素」。
- `loop=True` 时 `p = ease((1 - cos(2πt)) / 2)`，首尾两帧都回到 0，循环播放不跳；`loop=False` 是单向推进。
- `zoom` 是**末帧**的倍率（`loop=True` 时是中点最大）；「推近再回来」用 `loop=True` + `zoom=1.2`。
- `loop=True` 且总帧数 N=2 时，首尾都是原位，等于没有运动；要动就关 `loop` 或加帧。
- 镜头和分镜是两件事：**分镜**改的是关键帧内容（K 个 KSampler + 各自的提示词），
  **镜头**只对已经解码好的像素做统一变换。两者可以叠加。
- 只存成品：`--camera` 的图里三个保存节点和 `APNGFrameStats` 都接在镜头节点之后，
  帧差 / 接缝检查看的就是最终像素。

- 出图自检：`python scripts/check_anim.py <文件> --expect 24 --camera`。镜头位移会让整幅画面的
  RGB 均值一起平移，`--camera` 把漂移阈值从 20 放宽到 45，避免把正常位移误判成闪色；
  `emit_workflow.py --run` 检测到非中立镜头参数时会自动带上这个开关。

> 整段镜头 + 缓动的思路参考 [ShmuelRonen/ComfyUI-AstralAnimator](https://github.com/ShmuelRonen/ComfyUI-AstralAnimator)。
> 该仓库没有许可证文件，**未复用任何代码**；本节点是 `torch.nn.functional.affine_grid` + `grid_sample` 的独立实现。

## 5 · 节点参考

| 节点 | 输入 | 输出 | 说明 |
| --- | --- | --- | --- |
| `APNG Latent Interpolate N` | `samples1`, `samples2`, `frames`, `role`, `curve` | `LATENT`（batch=frames） | 插值公式与 ComfyUI 原生 `LatentInterpolate` 相同；`role` 按拍序 first/middle/last |
| `APNG Latent Concat` | `samples1`, `samples2` | `LATENT` | 只在 batch 维拼接，不改宽高 |
| `APNG Frame Stats` | `images`, `fps`, `segs` | `STRING` + UI 文本 | `OUTPUT_NODE`，不需要下游接线也能执行 |

`segs` 必须与各拍 `frames` 之和一致，否则 `--validate` 直接报错：

```
帧报告 segs 之和 24 与各拍 frames 之和 20 不一致
```

## 6 · 改帧数的完整动作

以 3 拍 24 帧（`8,8,8`）为例，想改成 12 帧：

1. 三个插值节点的 `frames` 都改成 `4`。
2. `APNGFrameStats` 的 `segs` 改成 `4,4,4`。
3. 三个保存节点的 `fps` 保持 10，则时长自动变成 1.20s。
4. 队列执行；帧报告打印 `frames=12`、`duration=1.20s`、帧差与接缝判定。

只改 `frames` 不改 `segs`，`--validate` 会拦下来；在 ComfyUI 里直接跑则帧报告仍会打印实际帧数，
但接缝检查会跳过（因为 `segs` 之和对不上）。

## 7 · 边界

- **逐帧停留（dwell）与拍内缓动（ease）仍然不在工作流里。** ComfyUI 的保存节点只有一个全局
  `fps`，表达不了逐帧不同 delay。要变速仍用 `scripts/retime.py`，它只改 APNG 的 `fcTL` delay，像素不动。
- **动态模式不需要 KJNodes 的 `ImageBatchMulti`**，但静态模式仍需要。
- `APNGLatentInterpolateN` 要求每个关键帧 latent 的 batch=1；关键帧 KSampler 本来就是 1。
- 节点是普通 Python 张量运算，CPU/GPU 都行；显存峰值取决于一次解码的总帧数，60 帧比 24 帧高。

## 8 · 排错

| 现象 | 原因 | 处理 |
| --- | --- | --- |
| 节点列表里没有 APNG Motion | 没装或没重启 ComfyUI | 跑 `install_nodes.py --check`，然后重启 |
| `--validate` 报 role 非法 | 手改成了别的字符串 | 只能是 `first` / `middle` / `last` |
| 帧数改了但总帧数没变 | 只改了一个插值节点 | 每拍一个 `frames`，全部要改 |
| 帧报告不打印接缝 | `segs` 之和 ≠ 实际帧数 | 把 `segs` 改成新的逗号串 |
| 出片帧数比设置少 | 相邻帧像素完全相同，APNG 合并 | 看 `identical_pairs`，调整 ratio 或曲线 |
| 镜头方向反了 | 把总量当成了每帧增量 | `x`/`y` 是整段总位移，正 x 向右、正 y 向下 |
| 循环播放首尾跳一下 | `loop=False` | 打开 `loop=True`，首尾帧像素一致 |
| 画面边缘出现黑边 | `border=zeros` | 改 `reflection` 或 `border` |
