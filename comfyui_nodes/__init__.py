# -*- coding: utf-8 -*-
"""APNG Motion · 动态帧数节点（可选安装）

把「N 个 LatentInterpolate + N 个 VAEDecode」压成「每拍一个插值节点 + 一次解码」：
帧数从图里的节点数量变成节点上的一个 widget，改数字就能改总帧数。

节点
  APNG Latent Interpolate N  两个关键帧 -> 指定帧数的 latent batch
  APNG Latent Concat         把多拍 batch 按顺序拼起来
  APNG Frame Stats           出图前报帧数 / 时长 / 相邻帧差 / 接缝差（阈值同 check_anim.py）
  APNG One Shot              一个节点走完「K 个关键帧 -> 插值 -> 解码 -> 镜头」，适合单条动图

安装
  把整个 comfyui_nodes 目录复制进 ComfyUI/custom_nodes/，或
  python scripts/install_nodes.py --profile profiles/xl.json

插值公式与 ComfyUI 原生 LatentInterpolate 完全一致（单位化方向 + 幅度线性插值），
比例序列与 scripts/comfy_lib.py 的 build_curve 逐值相同，所以静态图和动态图出帧一致。
"""
import math

import torch
import torch.nn.functional as F

CATEGORY = "APNG Motion"
LUM = (0.299, 0.587, 0.114)


def segment_ratios(cnt, role="middle", curve="linear"):
    """单拍的 ratio 序列，逐值与 comfy_lib.build_curve 的单段结果对齐。"""
    cnt = int(cnt)
    vals = []
    for j in range(cnt):
        if role == "first":
            u = j / (cnt - 1) if cnt > 1 else 1.0
        elif role == "last":
            u = (j + 1) / (cnt + 1) if cnt else 0.0
        else:
            u = (j + 1) / cnt if cnt else 1.0
        if curve == "ease":
            t = u * u * u * (u * (u * 6 - 15) + 10)
        elif curve == "snap":
            t = u ** 1.8
        else:
            t = u
        v = round(min(max(1.0 - t, 0.0), 1.0), 3)
        if vals and v >= vals[-1]:
            v = round(max(0.0, vals[-1] - 0.001), 3)
        vals.append(v)
    return vals


def blend_latent(s1, s2, ratio):
    """与 ComfyUI 原生 LatentInterpolate.execute 同一套算式（逐样本，B=1）。"""
    m1 = torch.linalg.vector_norm(s1, dim=(1))
    m2 = torch.linalg.vector_norm(s2, dim=(1))
    a = torch.nan_to_num(s1 / m1)
    b = torch.nan_to_num(s2 / m2)
    t = a * ratio + b * (1.0 - ratio)
    mt = torch.linalg.vector_norm(t, dim=(1))
    st = torch.nan_to_num(t / mt)
    return st * (m1 * ratio + m2 * (1.0 - ratio))


def _one(samples):
    s = samples["samples"]
    if s.shape[0] != 1:
        raise ValueError("APNG 节点要求每个关键帧 latent 的 batch=1，当前 %d" % s.shape[0])
    return s


class APNGLatentInterpolateN:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "samples1": ("LATENT",),
                "samples2": ("LATENT",),
                "frames": ("INT", {"default": 8, "min": 1, "max": 240, "step": 1}),
                "role": (["middle", "first", "last"], {"default": "middle"}),
                "curve": (["linear", "ease", "snap"], {"default": "linear"}),
            }
        }

    RETURN_TYPES = ("LATENT",)
    FUNCTION = "interpolate"
    CATEGORY = "APNG Motion"

    def interpolate(self, samples1, samples2, frames, role, curve):
        s1 = _one(samples1)
        s2 = _one(samples2)
        if s1.shape[1:] != s2.shape[1:]:
            raise ValueError("两个关键帧形状不一致：%s vs %s" % (tuple(s1.shape), tuple(s2.shape)))
        ratios = segment_ratios(frames, role, curve)
        out = [blend_latent(s1, s2, r) for r in ratios]
        return ({"samples": torch.cat(out, dim=0),
                 "batch_index": list(range(len(out)))},)


class APNGLatentConcat:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"samples1": ("LATENT",), "samples2": ("LATENT",)}}

    RETURN_TYPES = ("LATENT",)
    FUNCTION = "concat"
    CATEGORY = "APNG Motion"

    def concat(self, samples1, samples2):
        a = samples1["samples"]
        b = samples2["samples"]
        if a.shape[1:] != b.shape[1:]:
            raise ValueError("两段 latent 形状不一致：%s vs %s" % (tuple(a.shape), tuple(b.shape)))
        out = samples1.copy()
        out["samples"] = torch.cat((a, b), dim=0)
        out["batch_index"] = list(range(out["samples"].shape[0]))
        return (out,)


def _lum(img):
    w = torch.tensor(LUM, dtype=img.dtype, device=img.device)
    return (img[..., :3] * w).sum(dim=-1)


def _mad(a, b):
    """0-255 尺度的平均绝对差，与 check_anim.py 的 mean_abs_diff 同量纲。"""
    return float((_lum(a) - _lum(b)).abs().mean().item()) * 255.0


def _color_drift(a, b):
    """RGB 三通道均值相对第 1 帧的最大偏移，与 check_anim.py 的 color drift 同量纲。"""
    am = a[..., :3].mean(dim=(0, 1))
    bm = b[..., :3].mean(dim=(0, 1))
    return float((am - bm).abs().max().item()) * 255.0


class APNGFrameStats:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "images": ("IMAGE",),
                "fps": ("INT", {"default": 10, "min": 1, "max": 120, "step": 1}),
                "segs": ("STRING", {"default": "", "multiline": False}),
            }
        }

    RETURN_TYPES = ("STRING",)
    OUTPUT_NODE = True
    FUNCTION = "report"
    CATEGORY = "APNG Motion"

    def report(self, images, fps, segs):
        img = images
        n = int(img.shape[0])
        h = int(img.shape[1])
        diffs, identical = [], 0
        for i in range(1, n):
            d = _mad(img[i - 1], img[i])
            if img[i - 1].equal(img[i]):
                identical += 1
            diffs.append(round(d, 2))
        lines = [
            "frames=%d  fps=%d  duration=%.2fs" % (n, fps, n / float(max(fps, 1))),
            "diff   : min=%s max=%s avg=%s" % (
                min(diffs) if diffs else None,
                max(diffs) if diffs else None,
                round(sum(diffs) / len(diffs), 2) if diffs else None),
            "identical_pairs=%d" % identical,
        ]
        if n > 1:
            idx = sorted(set([0] + [round((n - 1) * k / 10.0) for k in range(1, 10)] + [n - 1]))
            curve = [round(_mad(img[0], img[i]), 2) for i in idx]
            lines.append("curve   : " + "  ".join("f%d=%.2f" % (i, v) for i, v in zip(idx, curve)))
            peak, last = max(curve), curve[-1]
            if peak > 6.0 and last < peak * 0.4:
                lines.append("shape   : 闭合（峰值 %.2f -> 末帧 %.2f，回到起点附近）" % (peak, last))
            elif peak > 6.0:
                lines.append("shape   : 累积（峰值 %.2f -> 末帧 %.2f，没有回落）" % (peak, last))
        if identical:
            lines.append("WARN   : 有相邻帧完全相同，APNG 会合并帧、时长相加")
        seg_list = [int(x) for x in str(segs).replace("，", ",").split(",") if x.strip()]
        if seg_list and sum(seg_list) == n:
            starts, acc = [], 0
            for s in seg_list:
                starts.append(acc)
                acc += s
            for i, st in enumerate(starts):
                en = min(st + seg_list[i], n) - 1
                if en <= st:
                    continue
                full = _mad(img[st], img[en])
                low = _mad(img[st, h // 2:], img[en, h // 2:])
                ok = full >= 2.0 and low >= 1.0
                lines.append("%s beat K%d->K%d @f%-3d full=%-6.2f lower=%-6.2f" % (
                    "OK  " if ok else "FAIL", i, (i + 1) % len(seg_list), st, full, low))
            loop_full = _mad(img[-1], img[0])
            loop_ok = 0.3 <= loop_full <= 6.0
            lines.append("%s loop K%d->K0 full=%.2f (0.3..6.0)" % (
                "OK  " if loop_ok else "FAIL", len(seg_list), loop_full))
            for i, st in enumerate(starts[1:], start=1):
                d = _color_drift(img[st], img[0])
                lines.append("%s K%d color drift=%.2f vs K0" % (
                    "WARN" if d > 20.0 else "OK  ", i, d))
        txt = "\n".join(lines)
        print("[APNG] " + txt.replace("\n", "\n[APNG] "))
        return {"ui": {"text": [txt]}, "result": (txt,)}


CAMERA_EASINGS = [
    "linear",
    "sine", "sine_in", "sine_out",
    "cubic", "cubic_in", "cubic_out",
    "quint", "quint_in", "quint_out",
    "back", "back_in", "back_out",
    "elastic", "elastic_in", "elastic_out",
    "bounce", "bounce_in", "bounce_out",
]

# 裸名保持历史行为，不重定义已有工作流的出帧：
#   sine = 缓入缓出；cubic / quint / back / elastic = 缓入；bounce = 缓出
_EASE_ALIAS = {"sine": "sine_inout", "cubic": "cubic_in", "quint": "quint_in",
               "back": "back_in", "elastic": "elastic_in", "bounce": "bounce_out"}


def _ease_in(name, t):
    """缓入：慢起快收。"""
    if name == "sine":
        return 1.0 - math.cos(math.pi * t / 2.0)
    if name == "cubic":
        return t * t * t
    if name == "quint":
        return t ** 5
    if name == "back":
        s = 1.70158
        return t * t * ((s + 1.0) * t - s)
    if name == "bounce":
        return 1.0 - _ease_out("bounce", 1.0 - t)
    if name == "elastic":
        if t in (0.0, 1.0):
            return t
        p = 0.3
        return -(2.0 ** (10.0 * (t - 1.0))) * math.sin((t - 1.0 - p / 4.0) * (2.0 * math.pi) / p)
    raise ValueError("未知缓动族: %s" % name)


def _ease_out(name, t):
    """缓出：快起慢收。bounce 用原生公式，其余用 in 的镜像。"""
    if name == "bounce":
        n1, d1 = 7.5625, 2.75
        if t < 1.0 / d1:
            return n1 * t * t
        if t < 2.0 / d1:
            t -= 1.5 / d1
            return n1 * t * t + 0.75
        if t < 2.5 / d1:
            t -= 2.25 / d1
            return n1 * t * t + 0.9375
        t -= 2.625 / d1
        return n1 * t * t + 0.984375
    return 1.0 - _ease_in(name, 1.0 - t)


def _ease_inout(name, t):
    """缓入缓出：前半段缓入、后半段缓出，两端都平滑。"""
    if t < 0.5:
        return 0.5 * _ease_in(name, 2.0 * t)
    return 1.0 - 0.5 * _ease_in(name, 2.0 - 2.0 * t)


def _ease(name, t):
    """0..1 的缓动。公式是公开的标准 easing，不依赖第三方库。"""
    t = min(max(float(t), 0.0), 1.0)
    if t <= 0.0:
        return 0.0
    if t >= 1.0:
        return 1.0
    if name == "linear":
        return t
    name = _EASE_ALIAS.get(name, name)
    if name.endswith("_inout"):
        return _ease_inout(name[:-6], t)
    if name.endswith("_out"):
        return _ease_out(name[:-4], t)
    if name.endswith("_in"):
        return _ease_in(name[:-3], t)
    raise ValueError("未知 easing: %s" % name)


def camera_progress(frames, easing="sine", loop=True):
    """整段镜头的推进量。loop=True 时 0→1→0，首尾回到原位。"""
    n = int(frames)
    if n <= 1:
        return [0.0]
    out = []
    for i in range(n):
        t = i / float(n - 1)
        p = (1.0 - math.cos(2.0 * math.pi * t)) / 2.0 if loop else t
        out.append(_ease(easing, p))
    return out


def camera_is_neutral(x, y, zoom, angle):
    return (abs(float(x)) < 1e-9 and abs(float(y)) < 1e-9
            and abs(float(zoom) - 1.0) < 1e-9 and abs(float(angle)) < 1e-9)


def apply_camera(images, x, y, zoom, angle, easing, loop, border):
    """对整段 IMAGE 施加同一条相机路径。纯像素仿射，不重新采样。"""
    n, h, w, c = images.shape
    if n == 0 or camera_is_neutral(x, y, zoom, angle):
        return images
    ps = camera_progress(n, easing, loop)
    p = torch.tensor(ps, dtype=images.dtype, device=images.device).view(n, 1, 1)
    scale = 1.0 / (1.0 + (float(zoom) - 1.0) * p)
    rad = math.radians(float(angle)) * p
    cos, sin = torch.cos(rad), torch.sin(rad)
    # affine_grid 的 theta 是 output->input；平移取负号，画面才向参数方向移动。
    tx = (-2.0 * float(x) * p) / float(w)
    ty = (-2.0 * float(y) * p) / float(h)
    theta = torch.zeros((n, 2, 3), dtype=images.dtype, device=images.device)
    theta[:, 0, 0] = (scale * cos).view(-1)
    theta[:, 0, 1] = (-scale * sin).view(-1)
    theta[:, 0, 2] = tx.view(-1)
    theta[:, 1, 0] = (scale * sin).view(-1)
    theta[:, 1, 1] = (scale * cos).view(-1)
    theta[:, 1, 2] = ty.view(-1)
    grid = F.affine_grid(theta, (n, c, h, w), align_corners=False)
    src = images.permute(0, 3, 1, 2)
    out = F.grid_sample(src, grid, mode="bilinear", padding_mode=border, align_corners=False)
    return out.permute(0, 2, 3, 1).clamp(0.0, 1.0)


class APNGCameraMove:
    """整段镜头运动：平移 / 缩放 / 旋转，纯像素变换，不重新采样。

    正 x 向右、正 y 向下、正 angle 逆时针（屏幕坐标）。zoom>1 推近，<1 拉远。
    loop=True 时使用 0→1→0 的往返路径，首尾帧回到原位，适合循环动图。
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "images": ("IMAGE",),
                "x": ("FLOAT", {"default": 0.0, "min": -2048.0, "max": 2048.0, "step": 1.0}),
                "y": ("FLOAT", {"default": 0.0, "min": -2048.0, "max": 2048.0, "step": 1.0}),
                "zoom": ("FLOAT", {"default": 1.0, "min": 0.5, "max": 4.0, "step": 0.01}),
                "angle": ("FLOAT", {"default": 0.0, "min": -360.0, "max": 360.0, "step": 1.0}),
                "easing": (CAMERA_EASINGS, {"default": "sine"}),
                "loop": ("BOOLEAN", {"default": True}),
                "border": (["reflection", "border", "zeros"], {"default": "reflection"}),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "move"
    CATEGORY = "APNG Motion"

    def move(self, images, x, y, zoom, angle, easing, loop, border):
        return (apply_camera(images, x, y, zoom, angle, easing, loop, border),)


def split_actions(text):
    parts = str(text).replace("｜", "|").replace("\n", "|").split("|")
    return [p.strip() for p in parts if p.strip()]


def parse_segs(text):
    """'8,8,8' -> [8, 8, 8]；空或 None -> []。"""
    t = "" if text is None else str(text).replace("，", ",").strip()
    if not t:
        return []
    out = []
    for part in t.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            out.append(int(part))
        except ValueError:
            raise ValueError("segs 只能是逗号分隔的整数，例如 8,8,8；收到 %r" % text)
    return out


def split_segments(total, k):
    """把总帧数平均分给 k 拍，余数给最后一拍。"""
    total, k = int(total), int(k)
    base = total // k
    segs = [base] * k
    segs[-1] += total - base * k
    return segs


class APNGOneShot:
    """一个节点出整段：K 个关键帧各采样一次 -> latent 插值 -> 一次解码 -> 镜头。

    与 --dynamic 工作流等价（同样的 K 次采样、同样的插值公式），只是不用搭图。
    每个动作本身是完整提示词片段，用 | 分隔；base positive 放不变的锁定词和画风。
    """

    @classmethod
    def INPUT_TYPES(cls):
        import comfy.samplers
        return {
            "required": {
                "model": ("MODEL",),
                "clip": ("CLIP",),
                "vae": ("VAE",),
                "positive": ("CONDITIONING",),
                "negative": ("CONDITIONING",),
                "width": ("INT", {"default": 512, "min": 64, "max": 4096, "step": 8}),
                "height": ("INT", {"default": 512, "min": 64, "max": 4096, "step": 8}),
                "frames": ("INT", {"default": 24, "min": 2, "max": 240, "step": 1}),
                "actions": ("STRING", {"default": "neutral|notice|react", "multiline": True}),
                "steps": ("INT", {"default": 20, "min": 1, "max": 200}),
                "cfg": ("FLOAT", {"default": 6.0, "min": 0.0, "max": 100.0, "step": 0.1}),
                "sampler_name": (comfy.samplers.KSampler.SAMPLERS, {"default": "euler"}),
                "scheduler": (comfy.samplers.KSampler.SCHEDULERS, {"default": "normal"}),
                "seed": ("INT", {"default": 0, "min": 0, "max": 0xffffffffffffffff}),
                "refine": ("FLOAT", {"default": 0.4, "min": 0.0, "max": 0.95, "step": 0.01}),
                "curve": (["linear", "ease", "snap"], {"default": "linear"}),
                "x": ("FLOAT", {"default": 0.0, "min": -2048.0, "max": 2048.0, "step": 1.0}),
                "y": ("FLOAT", {"default": 0.0, "min": -2048.0, "max": 2048.0, "step": 1.0}),
                "zoom": ("FLOAT", {"default": 1.0, "min": 0.5, "max": 4.0, "step": 0.01}),
                "angle": ("FLOAT", {"default": 0.0, "min": -360.0, "max": 360.0, "step": 1.0}),
                "easing": (CAMERA_EASINGS, {"default": "sine"}),
                "loop": ("BOOLEAN", {"default": True}),
                "border": (["reflection", "border", "zeros"], {"default": "reflection"}),
                "segs": ("STRING", {"default": "", "multiline": False}),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "animate"
    CATEGORY = "APNG Motion"

    def animate(self, model, clip, vae, positive, negative, width, height, frames, actions,
                steps, cfg, sampler_name, scheduler, seed, refine, curve,
                x, y, zoom, angle, easing, loop, border, segs=""):
        acts = split_actions(actions)
        if len(acts) < 2:
            raise ValueError("actions 至少两拍，用 | 分隔，例如 neutral|notice|react")
        k = len(acts)
        frames = int(frames)
        if frames < k:
            raise ValueError("frames=%d 小于拍数 %d，每一拍至少一帧" % (frames, k))

        counts = parse_segs(segs)
        if counts:
            if len(counts) != k:
                raise ValueError("segs 有 %d 段，但 actions 有 %d 拍" % (len(counts), k))
            if any(c < 1 for c in counts):
                raise ValueError("segs 每一段至少 1 帧")
            if sum(counts) != frames:
                raise ValueError("segs 之和 %d 与 frames=%d 不一致" % (sum(counts), frames))
        else:
            counts = split_segments(frames, k)

        import nodes as comfy_nodes

        latent = comfy_nodes.EmptyLatentImage().generate(int(width), int(height), 1)[0]
        keys = []
        for i, act in enumerate(acts):
            cond = positive
            if act:
                extra = comfy_nodes.CLIPTextEncode().encode(clip, act)[0]
                cond = comfy_nodes.ConditioningCombine().combine(positive, extra)[0]
            (out,) = comfy_nodes.common_ksampler(
                model, int(seed), int(steps), float(cfg), sampler_name, scheduler,
                cond, negative, latent, denoise=1.0 if i == 0 else float(refine))
            keys.append(out)
            latent = out

        seq = []
        for i, cnt in enumerate(counts):
            if cnt <= 0:
                continue
            role = "first" if i == 0 else ("last" if i == k - 1 else "middle")
            a, b = keys[i], keys[(i + 1) % k]
            for r in segment_ratios(cnt, role, curve):
                seq.append(blend_latent(a["samples"], b["samples"], r))

        batch = torch.cat(seq, dim=0)
        images = comfy_nodes.VAEDecode().decode(vae, {"samples": batch})[0]
        images = apply_camera(images, x, y, zoom, angle, easing, loop, border)
        return (images,)


NODE_CLASS_MAPPINGS = {
    "APNGLatentInterpolateN": APNGLatentInterpolateN,
    "APNGLatentConcat": APNGLatentConcat,
    "APNGFrameStats": APNGFrameStats,
    "APNGCameraMove": APNGCameraMove,
    "APNGOneShot": APNGOneShot,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "APNGLatentInterpolateN": "APNG Latent Interpolate N",
    "APNGLatentConcat": "APNG Latent Concat",
    "APNGFrameStats": "APNG Frame Stats",
    "APNGCameraMove": "APNG Camera Move",
    "APNGOneShot": "APNG One Shot",
}
