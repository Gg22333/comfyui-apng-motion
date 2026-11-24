# -*- coding: utf-8 -*-
"""make_camera_preview.py — 一张静图，预览整段镜头运动，不跑生成。

用法:
    python make_camera_preview.py still.png --preset dolly_in --out preview.gif
    python make_camera_preview.py still.png --x 24 --zoom 1.12 --frames 24 --fps 10
    python make_camera_preview.py still.png --preset pan_left --no-loop --border repeat

产物按扩展名决定：.gif / .png(APNG) / .webp。纯 Pillow，不依赖 torch。
"""
import argparse
import math
import os
import sys

from PIL import Image, ImageChops

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import camera_presets as CP  # noqa: E402


def warp(img, scale, deg, tx, ty, border="zeros"):
    """与 APNG Camera Move 同一套仿射：output -> input 采样。"""
    w, h = img.size
    r = math.radians(deg)
    a = scale * math.cos(r)
    b = -scale * math.sin(r)
    d = scale * math.sin(r)
    e = scale * math.cos(r)
    if border == "repeat":
        canvas = Image.new("RGB", (w * 3, h * 3))
        for ox in range(3):
            for oy in range(3):
                canvas.paste(img, (ox * w, oy * h))
        return canvas.transform((w, h), Image.AFFINE,
                                (a, b, tx + w, d, e, ty + h), Image.BICUBIC)
    return img.transform((w, h), Image.AFFINE, (a, b, tx, d, e, ty),
                         Image.BICUBIC, fillcolor=(0, 0, 0))


def build(img, frames, x=0.0, y=0.0, zoom=1.0, angle=0.0,
          easing="sine", loop=True, border="zeros"):
    ps = CP.camera_progress(frames, easing, loop)
    out = []
    for p in ps:
        scale = 1.0 / (1.0 + (float(zoom) - 1.0) * p)
        out.append(warp(img, scale, float(angle) * p, -float(x) * p, -float(y) * p, border))
    return out


def _unmerge(frames):
    """PIL 写 GIF 会把完全相同的相邻帧合并、时长相加；给重复帧改 1 个像素位避免丢帧。"""
    out = list(frames)
    for i in range(1, len(out)):
        if ImageChops.difference(out[i - 1], out[i]).getbbox() is None:
            f = out[i].copy()
            px = f.load()
            r, g, b = px[f.width - 1, f.height - 1]
            px[f.width - 1, f.height - 1] = ((r + 1) % 256, g, b)
            out[i] = f
    return out


def save(frames, path, fps=10):
    ext = os.path.splitext(path)[1].lower()
    frames = _unmerge(frames)
    kw = dict(save_all=True, append_images=frames[1:], duration=int(round(1000.0 / max(fps, 1))), loop=0)
    if ext == ".gif":
        frames[0].save(path, format="GIF", disposal=2, optimize=False, **kw)
    elif ext == ".webp":
        frames[0].save(path, format="WEBP", quality=90, **kw)
    else:
        frames[0].save(path, format="PNG", **kw)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("--out", default="camera-preview.gif")
    ap.add_argument("--preset", default="")
    ap.add_argument("--speed", type=float, default=1.0, help="预设倍速")
    ap.add_argument("--amp", type=float, default=1.0, help="预设幅度倍率")
    ap.add_argument("--x", type=float, default=0.0, help="整段横向总位移（像素）")
    ap.add_argument("--y", type=float, default=0.0, help="整段纵向总位移（像素）")
    ap.add_argument("--zoom", type=float, default=1.0, help="末帧倍率")
    ap.add_argument("--angle", type=float, default=0.0, help="整段总角度")
    ap.add_argument("--frames", type=int, default=24)
    ap.add_argument("--fps", type=int, default=10)
    ap.add_argument("--easing", default="sine", choices=CP.CAMERA_EASINGS)
    ap.add_argument("--no-loop", action="store_true", help="单向推进（默认 0->1->0 往返）")
    ap.add_argument("--border", default="zeros", choices=["zeros", "repeat"])
    ap.add_argument("--size", type=int, default=0, help="可选：先把静图缩成正方形")
    args = ap.parse_args()

    img = Image.open(args.image).convert("RGB")
    if args.size:
        img = img.resize((args.size, args.size), Image.LANCZOS)

    x, y, zoom, angle = args.x, args.y, args.zoom, args.angle
    if args.preset:
        vals = CP.resolve(args.preset, img.width, img.height, args.speed, args.amp)
        x, y, zoom, angle = vals["x"], vals["y"], vals["zoom"], vals["angle"]
        print("preset  : %s -> x=%.1f y=%.1f zoom=%.3f angle=%.1f" % (args.preset, x, y, zoom, angle))

    frames = build(img, args.frames, x, y, zoom, angle, args.easing, not args.no_loop, args.border)
    save(frames, args.out, args.fps)
    print("out     : %s  frames=%d  size=%dx%d  fps=%d" % (args.out, len(frames), img.width, img.height, args.fps))
    return 0


if __name__ == "__main__":
    sys.exit(main())
