# -*- coding: utf-8 -*-
"""camera_presets.py — 镜头预设 + 纯 Python 进度曲线。

把「推近 / 左移 / 螺旋」这类口头指令翻成 APNG Camera Move 的**整段总量**
（x 像素、y 像素、zoom 倍率、angle 度），同时给预览脚本提供与节点同口径的
camera_progress。

命名与别名参考了 Difforum 的预设表（MIT）；数值和公式按本项目的「整段总量」
模型重写，不是逐帧增量。3D-only 的运镜（orbit / tilt / crane / 真 dolly）
在这里直接报错，避免「静默不动」——那是 Difforum 在无深度图时的已知坑。
"""
import math

# (x 比例, y 比例, zoom 增量, angle 总量)
PRESETS = {
    "still":     (0.0, 0.0, 0.0, 0.0),
    "zoom_in":   (0.0, 0.0, 0.12, 0.0),
    "zoom_out":  (0.0, 0.0, -0.10, 0.0),
    "dolly_in":  (0.0, 0.0, 0.18, 0.0),   # 2D 代理：用 zoom 模拟推近，不产生视差
    "dolly_out": (0.0, 0.0, -0.15, 0.0),
    "pan_left":  (-0.12, 0.0, 0.0, 0.0),
    "pan_right": (0.12, 0.0, 0.0, 0.0),
    "pan_up":    (0.0, -0.10, 0.0, 0.0),
    "pan_down":  (0.0, 0.10, 0.0, 0.0),
    "roll_cw":   (0.0, 0.0, 0.0, 6.0),
    "roll_ccw":  (0.0, 0.0, 0.0, -6.0),
    "spiral":    (0.0, 0.0, 0.12, 6.0),
    "breathe":   (0.0, 0.0, 0.06, 0.0),
    "rise":      (0.0, -0.08, 0.10, 0.0),
}

ALIASES = {
    "push_in": "dolly_in", "push": "dolly_in", "pull_out": "dolly_out", "pull_back": "dolly_out",
    "truck_left": "pan_left", "truck_right": "pan_right",
    "pedestal_up": "pan_up", "pedestal_down": "pan_down",
    "track_left": "pan_left", "track_right": "pan_right",
    "slide_left": "pan_left", "slide_right": "pan_right",
    "static": "still", "hold": "still", "locked": "still",
    "vertigo": "dolly_zoom", "zoom_dentro": "zoom_in", "zoom_fora": "zoom_out",
}

# 需要深度图 / 3D 轴的运镜：2D 仿射表达不了，明确拒绝而不是悄悄不动
NEEDS_3D = {
    "orbit_left", "orbit_right", "tilt_up", "tilt_down", "crane_up",
    "handheld", "shake", "sway", "drift", "vortex", "dolly_zoom",
}


def names():
    return sorted(PRESETS)


def resolve(name, width=512, height=512, speed=1.0, amp=1.0):
    """预设 -> {'x','y','zoom','angle'}，单位与节点 widget 一致。"""
    key = str(name).strip().lower().replace(" ", "_").replace("-", "_")
    key = ALIASES.get(key, key)
    if key in NEEDS_3D:
        raise ValueError(
            "预设 %r 需要 3D / 深度图，2D 仿射镜头做不了；可选：%s"
            % (name, ", ".join(names())))
    if key not in PRESETS:
        raise ValueError("未知镜头预设 %r；可选：%s" % (name, ", ".join(names())))

    fx, fy, dz, ang = PRESETS[key]
    s = float(speed) * float(amp)
    x = fx * float(width) * s
    y = fy * float(height) * s
    zoom = 1.0 + dz * s
    angle = ang * s
    x = max(-2048.0, min(2048.0, x))
    y = max(-2048.0, min(2048.0, y))
    zoom = max(0.5, min(4.0, zoom))
    angle = max(-360.0, min(360.0, angle))
    return {"x": round(x, 3), "y": round(y, 3), "zoom": round(zoom, 4), "angle": round(angle, 3)}


# ---- 与 comfyui_nodes 同口径的缓动（纯 Python，预览脚本不依赖 torch）----
CAMERA_EASINGS = [
    "linear",
    "sine", "sine_in", "sine_out",
    "cubic", "cubic_in", "cubic_out",
    "quint", "quint_in", "quint_out",
    "back", "back_in", "back_out",
    "elastic", "elastic_in", "elastic_out",
    "bounce", "bounce_in", "bounce_out",
]
_ALIAS = {"sine": "sine_inout", "cubic": "cubic_in", "quint": "quint_in",
          "back": "back_in", "elastic": "elastic_in", "bounce": "bounce_out"}


def _ease_in(fam, t):
    if fam == "sine":
        return 1.0 - math.cos(math.pi * t / 2.0)
    if fam == "cubic":
        return t * t * t
    if fam == "quint":
        return t ** 5
    if fam == "back":
        s = 1.70158
        return t * t * ((s + 1.0) * t - s)
    if fam == "elastic":
        if t in (0.0, 1.0):
            return t
        p = 0.3
        return -(2.0 ** (10.0 * (t - 1.0))) * math.sin((t - 1.0 - p / 4.0) * (2.0 * math.pi) / p)
    if fam == "bounce":
        return 1.0 - _ease_out("bounce", 1.0 - t)
    raise ValueError(fam)


def _ease_out(fam, t):
    if fam == "bounce":
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
    return 1.0 - _ease_in(fam, 1.0 - t)


def _ease(name, t):
    t = min(max(float(t), 0.0), 1.0)
    if t <= 0.0:
        return 0.0
    if t >= 1.0:
        return 1.0
    if name == "linear":
        return t
    name = _ALIAS.get(name, name)
    if name.endswith("_inout"):
        fam = name[:-6]
        return 0.5 * _ease_in(fam, 2.0 * t) if t < 0.5 else 1.0 - 0.5 * _ease_in(fam, 2.0 - 2.0 * t)
    if name.endswith("_out"):
        return _ease_out(name[:-4], t)
    if name.endswith("_in"):
        return _ease_in(name[:-3], t)
    raise ValueError("未知 easing: %s" % name)


def camera_progress(frames, easing="sine", loop=True):
    n = int(frames)
    if n <= 1:
        return [0.0]
    out = []
    for i in range(n):
        t = i / float(n - 1)
        p = (1.0 - math.cos(2.0 * math.pi * t)) / 2.0 if loop else t
        out.append(_ease(easing, p))
    return out
