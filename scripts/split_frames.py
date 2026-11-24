# -*- coding: utf-8 -*-
"""split_frames.py — 把 APNG / WebP / GIF 拆回 PNG 序列，可顺手挑关键帧。

用法:
    python split_frames.py anim.png --out frames/
    python split_frames.py anim.png --out frames/ --pick 4
    python split_frames.py anim.png --out frames/ --json
"""
import argparse
import json
import os
import sys

from PIL import Image, ImageChops, ImageStat

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def mad(a, b):
    return ImageStat.Stat(ImageChops.difference(a, b)).mean[0]


def load(path):
    im = Image.open(path)
    frames, durations = [], []
    for i in range(getattr(im, "n_frames", 1)):
        im.seek(i)
        durations.append(im.info.get("duration"))
        frames.append(im.convert("RGB"))
    return frames, durations


def pick_keyframes(frames, n):
    """把序列按 n 段切开，每段取与上一帧差最大的那帧（第一段固定取首帧）。"""
    if n <= 1 or len(frames) <= n:
        return list(range(min(n, len(frames))))
    picks = [0]
    rest = len(frames) - 1
    per = rest / float(n - 1)
    for k in range(1, n):
        lo = 1 + int(round((k - 1) * per))
        hi = 1 + int(round(k * per))
        hi = min(hi, len(frames) - 1)
        if hi < lo:
            hi = lo
        best, best_d = lo, -1.0
        for i in range(lo, hi + 1):
            d = mad(frames[i - 1], frames[i])
            if d > best_d:
                best, best_d = i, d
        picks.append(best)
    return picks


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--out", required=True)
    ap.add_argument("--pick", type=int, default=0, help="额外挑 N 个关键帧，命名 key_XX.png")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    if not os.path.isfile(args.path):
        print("MISSING:", args.path)
        return 2
    frames, durations = load(args.path)
    os.makedirs(args.out, exist_ok=True)

    paths = []
    for i, f in enumerate(frames):
        p = os.path.join(args.out, "frame_%03d.png" % i)
        f.save(p)
        paths.append(p)

    diffs = [round(mad(frames[i - 1], frames[i]), 2) for i in range(1, len(frames))]
    keys = []
    if args.pick:
        idx = pick_keyframes(frames, args.pick)
        for j, i in enumerate(idx):
            p = os.path.join(args.out, "key_%02d.png" % j)
            frames[i].save(p)
            keys.append({"index": i, "path": p})

    res = {
        "file": args.path,
        "frames": len(frames),
        "size": list(frames[0].size) if frames else None,
        "diff_avg": round(sum(diffs) / len(diffs), 2) if diffs else None,
        "keys": keys,
    }
    if args.json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
    else:
        print("frames  : %d -> %s" % (len(frames), args.out))
        print("diff    : avg=%s" % res["diff_avg"])
        if keys:
            print("keys    : " + ", ".join("f%d" % k["index"] for k in keys))
    return 0


if __name__ == "__main__":
    sys.exit(main())
