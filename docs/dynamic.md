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
目录复制进去并改名 `apng_motion_nodes`。**装完重启 ComfyUI**，三个节点出现在 `APNG Motion` 分类下。

## 2 · 生成动态工作流

```bash
python scripts/emit_workflow.py \
    --base workflows/workflow-sdxl.json \
    --story assets/story.example.json \
    --dynamic \
    --out my-dynamic.json
```

3 拍 24 帧输出 **26 个节点 / 39 条连线**（同样内容的静态图是 67 个节点）。关键帧链完全不动，
只替换插值/解码/合批层。

```
K 个关键帧 KSampler（同 seed，首帧 latent）
  → 每拍 1 个 APNGLatentInterpolateN（frames = 这一拍的帧数）
  → N-1 个 APNGLatentConcat（按拍序拼 batch）
  → 1 个 VAEDecode（一次解码全部帧）
  → SaveAnimatedPNG + SaveAnimatedWEBP + VHS_VideoCombine
  → APNGFrameStats（打印帧数 / 时长 / 帧差 / 接缝）
```

## 3 · 五个维度分别在哪控制

| 维度 | 工作流里的位置 | 怎么用 |
| --- | --- | --- |
| **帧数** | 每个 `APNG Latent Interpolate N` 的 `frames` widget | 改数字即可。总帧数 = 各拍 `frames` 之和，1–240 |
| **时长** | 三个保存节点的 `fps`，以及 `APNGFrameStats` 的 `fps` | 总时长 = 总帧数 / fps；报告节点直接打印 `duration=2.40s` |
| **相邻帧差** | `APNGFrameStats` 输出 | 打印 `diff min/max/avg` 与 `identical_pairs`；相同帧会警告 APNG 合并帧 |
| **接缝唯一性** | `APNGFrameStats` 的 `segs` widget | 填各拍帧数逗号串（如 `8,8,8`），逐拍打印 `full/lower` 判定 OK/FAIL，并检查循环 `K_N→K0` |
| **分镜 / 故事板** | K 个 `KSampler` + 各自的 `CLIPTextEncode` | 一个关键帧就是一拍，和静态模式完全一致；加拍仍是复制一对节点 |

`APNGFrameStats` 的阈值与 `scripts/check_anim.py` 一致：拍内 `full >= 2.0 && lower >= 1.0`，
循环接缝 `0.3 <= full <= 6.0`。

## 4 · 节点参考

| 节点 | 输入 | 输出 | 说明 |
| --- | --- | --- | --- |
| `APNG Latent Interpolate N` | `samples1`, `samples2`, `frames`, `role`, `curve` | `LATENT`（batch=frames） | 插值公式与 ComfyUI 原生 `LatentInterpolate` 相同；`role` 按拍序 first/middle/last |
| `APNG Latent Concat` | `samples1`, `samples2` | `LATENT` | 只在 batch 维拼接，不改宽高 |
| `APNG Frame Stats` | `images`, `fps`, `segs` | `STRING` + UI 文本 | `OUTPUT_NODE`，不需要下游接线也能执行 |

`segs` 必须与各拍 `frames` 之和一致，否则 `--validate` 直接报错：

```
帧报告 segs 之和 24 与各拍 frames 之和 20 不一致
```

## 5 · 改帧数的完整动作

以 3 拍 24 帧（`8,8,8`）为例，想改成 12 帧：

1. 三个插值节点的 `frames` 都改成 `4`。
2. `APNGFrameStats` 的 `segs` 改成 `4,4,4`。
3. 三个保存节点的 `fps` 保持 10，则时长自动变成 1.20s。
4. 队列执行；帧报告打印 `frames=12`、`duration=1.20s`、帧差与接缝判定。

只改 `frames` 不改 `segs`，`--validate` 会拦下来；在 ComfyUI 里直接跑则帧报告仍会打印实际帧数，
但接缝检查会跳过（因为 `segs` 之和对不上）。

## 6 · 边界

- **逐帧停留（dwell）与拍内缓动（ease）仍然不在工作流里。** ComfyUI 的保存节点只有一个全局
  `fps`，表达不了逐帧不同 delay。要变速仍用 `scripts/retime.py`，它只改 APNG 的 `fcTL` delay，像素不动。
- **动态模式不需要 KJNodes 的 `ImageBatchMulti`**，但静态模式仍需要。
- `APNGLatentInterpolateN` 要求每个关键帧 latent 的 batch=1；关键帧 KSampler 本来就是 1。
- 节点是普通 Python 张量运算，CPU/GPU 都行；显存峰值取决于一次解码的总帧数，60 帧比 24 帧高。

## 7 · 排错

| 现象 | 原因 | 处理 |
| --- | --- | --- |
| 节点列表里没有 APNG Motion | 没装或没重启 ComfyUI | 跑 `install_nodes.py --check`，然后重启 |
| `--validate` 报 role 非法 | 手改成了别的字符串 | 只能是 `first` / `middle` / `last` |
| 帧数改了但总帧数没变 | 只改了一个插值节点 | 每拍一个 `frames`，全部要改 |
| 帧报告不打印接缝 | `segs` 之和 ≠ 实际帧数 | 把 `segs` 改成新的逗号串 |
| 出片帧数比设置少 | 相邻帧像素完全相同，APNG 合并 | 看 `identical_pairs`，调整 ratio 或曲线 |
