# -*- coding: utf-8 -*-
"""make_loop.py — 后处理：ping-pong、首尾停留、整段重复。

用法:
    python make_loop.py anim.png --ping-pong --out looped.png
    python make_loop.py anim.gif --hold-first 2 --hold-last 2 --out held.gif
    python make_loop.py anim.png --repeat 2 --fps 10 --out x2.png
"""
import argparse
import os
import sys

from PIL import Image, ImageChops

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def load(path):
    im = Image.open(path)
    frames, durations, loop = [], [], im.info.get("loop")
    for i in range(getattr(im, "n_frames", 1)):
        im.seek(i)
        frames.append(im.convert("RGB"))
        durations.append(im.info.get("duration") or 100)
    return frames, durations, loop


def unmerge(frames):
    """Pillow 会把完全相同的相邻帧合并、时长相加；改 1 个像素位保住帧数。"""
    out = list(frames)
    for i in range(1, len(out)):
        if ImageChops.difference(out[i - 1], out[i]).getbbox() is None:
            f = out[i].copy()
            px = f.load()
            r, g, b = px[f.width - 1, f.height - 1]
            px[f.width - 1, f.height - 1] = ((r + 1) % 256, g, b)
            out[i] = f
    return out


def transform(frames, durations, ping_pong=False, hold_first=0, hold_last=0, repeat=1):
    seq = list(zip(frames, durations))
    if ping_pong and len(seq) > 2:
        seq = seq + seq[-2:0:-1]          # 去掉首尾，避免接缝处重复两帧
    if hold_first > 0:
        seq = [seq[0]] * int(hold_first) + seq
    if hold_last > 0:
        seq = seq + [seq[-1]] * int(hold_last)
    if repeat > 1:
        seq = seq * int(repeat)
    return [s[0] for s in seq], [s[1] for s in seq]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--out", required=True)
    ap.add_argument("--ping-pong", action="store_true", help="正放 + 倒放，接缝不重复端点")
    ap.add_argument("--hold-first", type=int, default=0, help="开头多停 N 帧")
    ap.add_argument("--hold-last", type=int, default=0, help="结尾多停 N 帧")
    ap.add_argument("--repeat", type=int, default=1, help="整段重复 N 次")
    ap.add_argument("--fps", type=float, default=0, help="统一改帧率；0 = 沿用原文件时长")
    ap.add_argument("--loop", type=int, default=0)
    ap.add_argument("--allow-merge", action="store_true",
                    help="允许 Pillow 合并相同相邻帧（默认保住帧数）")
    args = ap.parse_args()

    if not os.path.isfile(args.path):
        print("MISSING:", args.path)
        return 2
    if args.repeat < 1:
        print("--repeat 至少 1")
        return 2

    frames, durations, _ = load(args.path)
    out, durs = transform(frames, durations, args.ping_pong, args.hold_first, args.hold_last, args.repeat)
    if args.fps > 0:
        durs = [int(round(1000.0 / args.fps))] * len(out)

    if not args.allow_merge:
        out = unmerge(out)

    ext = os.path.splitext(args.out)[1].lower()
    kw = dict(save_all=True, append_images=out[1:], duration=durs, loop=args.loop)
    if ext == ".gif":
        out[0].save(args.out, format="GIF", disposal=2, optimize=False, **kw)
    elif ext == ".webp":
        out[0].save(args.out, format="WEBP", quality=90, **kw)
    else:
        out[0].save(args.out, format="PNG", **kw)

    total = sum(durs) / 1000.0
    print("in      : %d frames -> out %d frames" % (len(frames), len(out)))
    print("duration: %.2fs  (%s)" % (total, args.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
