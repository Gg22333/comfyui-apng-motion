# -*- coding: utf-8 -*-
"""APNG Motion · 动态帧数节点（可选安装）

把「N 个 LatentInterpolate + N 个 VAEDecode」压成「每拍一个插值节点 + 一次解码」：
帧数从图里的节点数量变成节点上的一个 widget，改数字就能改总帧数。

节点
  APNG Latent Interpolate N  两个关键帧 -> 指定帧数的 latent batch
  APNG Latent Concat         把多拍 batch 按顺序拼起来
  APNG Frame Stats           出图前报帧数 / 时长 / 相邻帧差 / 接缝差（阈值同 check_anim.py）

安装
  把整个 comfyui_nodes 目录复制进 ComfyUI/custom_nodes/，或
  python scripts/install_nodes.py --profile profiles/xl.json

插值公式与 ComfyUI 原生 LatentInterpolate 完全一致（单位化方向 + 幅度线性插值），
比例序列与 scripts/comfy_lib.py 的 build_curve 逐值相同，所以静态图和动态图出帧一致。
"""
import torch

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
        txt = "\n".join(lines)
        print("[APNG] " + txt.replace("\n", "\n[APNG] "))
        return {"ui": {"text": [txt]}, "result": (txt,)}


NODE_CLASS_MAPPINGS = {
    "APNGLatentInterpolateN": APNGLatentInterpolateN,
    "APNGLatentConcat": APNGLatentConcat,
    "APNGFrameStats": APNGFrameStats,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "APNGLatentInterpolateN": "APNG Latent Interpolate N",
    "APNGLatentConcat": "APNG Latent Concat",
    "APNGFrameStats": "APNG Frame Stats",
}
