#!/usr/bin/env python
"""check_anim.py — 检查 APNG / WebP / GIF 动图是否完整、是否够顺。

用法:
    python check_anim.py "D:/output/anim24_00001_.png"
    python check_anim.py "D:/output/anim24_00001_.png" --expect 24
    python check_anim.py "D:/output/anim24_00001.gif" --json

输出: 格式、尺寸、帧数、每帧时长、循环次数、相邻帧平均像素差。
退出码: 0 正常 / 1 帧数与 --expect 不符 / 2 文件不存在或打不开。

identical_pairs > 0 表示有完全相同的相邻帧：Pillow 写 APNG 时会把它们合并、
把 duration 相加（PIL/PngImagePlugin.py 里 bbox 为空就 continue），
表现就是"排了 24 帧，导出只剩 19 帧"。曲线里不要放完全重复的 ratio。
"""
import argparse
import json
import os
import sys

from PIL import Image, ImageChops, ImageStat

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def mean_abs_diff(a, b):
    hist = ImageChops.difference(a, b).convert("L").histogram()
    total = sum(i * v for i, v in enumerate(hist))
    count = sum(hist)
    return total / count if count else 0.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--expect", type=int, default=0, help="期望帧数，不符则退出码 1")
    ap.add_argument("--json", action="store_true", help="只输出 JSON")
    args = ap.parse_args()

    if not os.path.exists(args.path):
        print("MISSING:", args.path)
        return 2
    try:
        im = Image.open(args.path)
    except Exception as exc:
        print("OPEN FAILED:", exc)
        return 2

    n = getattr(im, "n_frames", 1)
    durations, frames = [], []
    for i in range(n):
        im.seek(i)
        durations.append(im.info.get("duration"))
        frames.append(im.convert("RGB"))

    means = [ImageStat.Stat(f).mean[:3] for f in frames]
    drift = 0.0
    if means:
        base_m = means[0]
        for m in means[1:]:
            drift = max(drift, max(abs(m[i] - base_m[i]) for i in range(3)))

    diffs, identical = [], 0
    for i in range(1, n):
        diff = ImageChops.difference(frames[i - 1], frames[i])
        if diff.getbbox() is None:
            identical += 1
        diffs.append(round(mean_abs_diff(frames[i - 1], frames[i]), 2))

    total_ms = sum(d for d in durations if isinstance(d, (int, float)))
    res = {
        "file": args.path,
        "format": im.format,
        "size": list(im.size),
        "frames": n,
        "duration_ms": durations[0] if durations else None,
        "total_ms": total_ms,
        "total_s": round(total_ms / 1000.0, 2),
        "loop": im.info.get("loop"),
        "diff_min": min(diffs) if diffs else None,
        "diff_max": max(diffs) if diffs else None,
        "diff_avg": round(sum(diffs) / len(diffs), 2) if diffs else None,
        "identical_pairs": identical,
        "color_drift": round(drift, 2),
    }

    if args.json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
    else:
        print(f"file    : {res['file']}")
        print(f"format  : {res['format']}  size={res['size']}  frames={res['frames']}  loop={res['loop']}")
        print(f"timing  : {res['duration_ms']} ms/frame  total={res['total_s']} s")
        print(f"diff    : min={res['diff_min']}  max={res['diff_max']}  avg={res['diff_avg']}")
        print(f"color   : drift={res['color_drift']}（相对第 1 帧的平均 RGB 最大偏移）")
        if drift > 6:
            print("WARN    : 颜色漂移偏大，检查关键帧里是否有 eyes closed / 光照词变化")
        if identical:
            print(f"WARN    : {identical} 对相邻帧完全相同，APNG 会被合并、时长相加")
        elif diffs and min(diffs) < 0.15:
            print("WARN    : 有几乎相同的相邻帧，属停顿帧，正常；但别让它等于 0")

    if args.expect and n != args.expect:
        print(f"FAIL    : 帧数 {n} != 期望 {args.expect}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

