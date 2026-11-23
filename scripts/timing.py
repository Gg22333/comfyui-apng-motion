# -*- coding: utf-8 -*-
"""timing.py — 帧延时计算，全仓唯一真相源。

ComfyUI 的三个保存节点（SaveAnimatedPNG / SaveAnimatedWEBP /
VHS_VideoCombine）只接受**一个全局 fps**，逐帧停留表达不出来。
所以节奏分三层：

    fps    总时长 = frames / fps
    dwell  每拍停留权重，决定时间怎么分配（1.4 = 多停 40%）
    ease   拍内缓动，关键帧附近多停、中段加速（0 = 等速）

三条不变量，由 tests/test_timing.py 守住：

    1. 列表长度恒等于 frames
    2. 总延时恒等于 frames * 1000 / fps（量化后误差 < quantum）
    3. dwell 长度必须等于段数，segs 之和必须等于 frames

GIF 的帧延时单位是厘秒（10 ms），非整除的 fps 会被悄悄改快。
所以 quantize=10 时，24 fps（41.67 ms）会变成 40 ms，整片 2.4 s 不是 2.5 s。
APNG / WebP 支持毫秒精度，用 quantize=1。
"""


def frame_delays(frames, segs, fps, dwell=None, ease=0.3, quantum=1):
    """返回每帧毫秒延时列表，长度 == frames。

    frames  总帧数
    segs    每段帧数，sum(segs) 必须等于 frames
    fps     基准帧率；总时长 = frames / fps
    dwell   每段停留权重，缺省全 1.0
    ease    拍内缓动 0..0.8；0 = 等速，0.3 = 关键帧附近约慢 30%
    quantum 量化步长（毫秒）；GIF 用 10，APNG / WebP 用 1
    """
    frames = int(frames)
    segs = [int(x) for x in segs]
    if frames <= 0:
        raise ValueError("frames 必须 > 0")
    if fps is None or float(fps) <= 0:
        raise ValueError("fps 必须 > 0")
    if not segs:
        raise ValueError("segs 不能为空")
    if any(c <= 0 for c in segs):
        raise ValueError("segs 每段至少 1 帧")
    if sum(segs) != frames:
        raise ValueError("segs 之和 %d != frames %d" % (sum(segs), frames))

    if dwell is None:
        dwell = [1.0] * len(segs)
    dwell = [float(x) for x in dwell]
    if len(dwell) != len(segs):
        raise ValueError("dwell 长度 %d != 段数 %d" % (len(dwell), len(segs)))
    if any(x <= 0 for x in dwell):
        raise ValueError("dwell 必须全为正数")

    ease = max(0.0, min(0.8, float(ease)))
    quantum = max(1, int(quantum))
    base = 1000.0 / float(fps)
    total = frames * base

    # 拍内缓动：(2u-1)^2 在 [0,1] 上的均值是 1/3，除掉它才不改变总时长
    norm = 1.0 + ease / 3.0
    raw = []
    for cnt, w in zip(segs, dwell):
        for j in range(cnt):
            u = (j + 0.5) / cnt
            f = 1.0 + ease * (2.0 * u - 1.0) ** 2
            raw.append(base * w * f / norm)

    scale = total / sum(raw)
    raw = [v * scale for v in raw]

    q = [max(quantum, int(round(v / quantum)) * quantum) for v in raw]
    _rebalance(q, int(round(total)), quantum)
    return q


def _rebalance(q, target, quantum):
    """把取整误差摊回各帧，保住总时长。"""
    diff = target - sum(q)
    if diff == 0:
        return
    order = sorted(range(len(q)), key=lambda i: q[i], reverse=True)
    guard = 0
    while diff and guard < 10000:
        guard += 1
        moved = False
        for k in order:
            if diff == 0:
                break
            if diff > 0:
                q[k] += quantum
                diff -= quantum
                moved = True
            elif q[k] > quantum:
                q[k] -= quantum
                diff += quantum
                moved = True
        if not moved:
            break


def seg_ranges(segs):
    """[(start, end), ...]，end 不含。"""
    out, i = [], 0
    for c in segs:
        out.append((i, i + int(c)))
        i += int(c)
    return out


def beat_totals(delays, segs):
    """每一拍的总毫秒数。"""
    return [sum(delays[a:b]) for a, b in seg_ranges(segs)]


def summary(frames, segs, fps, dwell=None, ease=0.3, quantum=1):
    """给命令行打印用的一行摘要。"""
    d = frame_delays(frames, segs, fps, dwell=dwell, ease=ease, quantum=quantum)
    bt = beat_totals(d, segs)
    total = sum(d)
    return {
        "frames": frames,
        "fps": float(fps),
        "target_s": round(frames / float(fps), 3),
        "total_s": round(total / 1000.0, 3),
        "frame_ms_min": min(d),
        "frame_ms_max": max(d),
        "beats_ms": bt,
        "beats_s_min": round(min(bt) / 1000.0, 3),
        "beats_s_max": round(max(bt) / 1000.0, 3),
        "delays": d,
    }