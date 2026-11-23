# -*- coding: utf-8 -*-
"""check_anim.py — 检查 APNG / WebP / GIF 动图是否完整、是否够顺、每拍有没有真的动。

用法:
    python check_anim.py "D:/output/anim24_00001_.png"
    python check_anim.py "D:/output/anim24_00001_.png" --expect 24
    python check_anim.py "D:/output/anim60_00001_.png" --segs 10,12,4,12,10,12
    python check_anim.py "D:/output/anim24_00001.gif" --json

输出: 格式、尺寸、帧数、每帧时长、循环次数、相邻帧平均像素差。
给 --segs 时额外输出每一拍的边界差和画面下半区的差异。

退出码: 0 正常 / 1 帧数与 --expect 不符（或 --strict 下拍检查失败）/
        2 文件不存在或打不开。

identical_pairs > 0 表示有完全相同的相邻帧：Pillow 写 APNG 时会把它们合并、
把 duration 相加（PIL/PngImagePlugin.py 里 bbox 为空就 continue），
表现就是"排了 24 帧，导出只剩 19 帧"。曲线里不要放完全重复的 ratio。

拍检查阈值（经验值，512-640 的一格）：
    表演拍  full >= 2.0     关键帧之间要有真实换姿势
    下半身  lower >= 1.0    只动脸不动身体，说明构图被裁成半身了
    循环接点 0.3 <= full <= 6.0
    颜色漂移 drift <= 20
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


def lower_diff(a, b, frac=0.5):
    """画面下半部分的平均差。用来判断「身体有没有动」，而不只是脸。"""
    h = a.height
    box = (0, int(h * frac), a.width, h)
    return mean_abs_diff(a.crop(box), b.crop(box))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--expect", type=int, default=0, help="期望帧数，不符则退出码 1")
    ap.add_argument("--segs", default="", help="每拍帧数，逗号分隔；给了就逐拍检查")
    ap.add_argument("--story", default="", help="剧情卡 JSON；从里面读 segs")
    ap.add_argument("--strict", action="store_true", help="拍检查失败也返回退出码 1")
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

    # ---- 逐拍检查 ----
    beat_rows, beat_fail = [], 0
    segs_txt = args.segs
    if not segs_txt and args.story:
        with open(args.story, encoding="utf-8") as fh:
            segs_txt = ",".join(str(x) for x in (json.load(fh).get("segs") or []))
    segs = [int(x) for x in segs_txt.split(",") if x.strip()] if segs_txt else []
    if segs:
        if sum(segs) != n:
            print("WARN    : segs 之和 %d != 实际帧数 %d，拍检查按实际帧数截断" % (sum(segs), n))
        # 段边界两侧本来就都是同一个关键帧（段尾≈K(i+1)，段首=K(i+1)），
        # 直接比相邻帧只会得到接近 0 的差值。要衡量「这一拍有没有换姿势」，
        # 应该比段首（K_i）与段尾（≈K_i+1）。
        starts, acc = [], 0
        for s in segs:
            starts.append(acc)
            acc += s
        for i, st in enumerate(starts):
            en = min(st + segs[i], n) - 1
            if en <= st:
                continue
            full = mean_abs_diff(frames[st], frames[en])
            low = lower_diff(frames[st], frames[en])
            ok = full >= 2.0 and low >= 1.0
            if not ok:
                beat_fail += 1
            ms = sum(x for x in durations[st:en + 1] if isinstance(x, (int, float)))
            beat_rows.append({
                "beat": "K%d->K%d" % (i, (i + 1) % len(segs)),
                "at_frame": st,
                "ms": int(ms),
                "full": round(full, 2),
                "lower": round(low, 2),
                "ok": ok,
            })
        loop_full = mean_abs_diff(frames[-1], frames[0])
        loop_low = lower_diff(frames[-1], frames[0])
        loop_ok = 0.3 <= loop_full <= 6.0
        beat_rows.append({
            "beat": "K%d->K0" % len(segs),
            "at_frame": n - 1,
            "ms": None,
            "full": round(loop_full, 2),
            "lower": round(loop_low, 2),
            "ok": loop_ok,
        })
        # 循环接点太软/太硬也计入
        if not loop_ok:
            beat_fail += 1
        res["beats"] = beat_rows
        res["beat_fail"] = beat_fail

    if args.json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
    else:
        print(f"file    : {res['file']}")
        print(f"format  : {res['format']}  size={res['size']}  frames={res['frames']}  loop={res['loop']}")
        ms_all = [d for d in durations if isinstance(d, (int, float))]
        if ms_all and min(ms_all) != max(ms_all):
            print(f"timing  : {max(ms_all)} / {min(ms_all)} ms/frame (per-frame)  "
                  f"total={res['total_s']} s")
        else:
            print(f"timing  : {res['duration_ms']} ms/frame  total={res['total_s']} s")
        print(f"diff    : min={res['diff_min']}  max={res['diff_max']}  avg={res['diff_avg']}")
        print(f"color   : drift={res['color_drift']}（相对第 1 帧的平均 RGB 最大偏移）")
        if drift > 20:
            print("FAIL    : 颜色漂移 > 20，大概率是色块闪，回去查 denoise 和提示词里的光照词")
        elif drift > 6:
            print("WARN    : 颜色漂移偏大，检查关键帧里是否有 eyes closed / 光照词变化")
        if identical:
            print(f"WARN    : {identical} 对相邻帧完全相同，APNG 会被合并、时长相加")
        elif diffs and min(diffs) < 0.15:
            print("WARN    : 有几乎相同的相邻帧，属停顿帧，正常；但别让它等于 0")
        if beat_rows:
            print("beats   :")
            for r in beat_rows:
                flag = "OK  " if r["ok"] else "FAIL"
                ms_cell = "%5dms" % r["ms"] if r.get("ms") is not None else "  wrap"
                print("  %s %-7s @f%-3d %s full=%-7s lower=%-7s" % (
                    flag, r["beat"], r["at_frame"], ms_cell,
                    r["full"], r["lower"]))
            thin = [r["beat"] for r in beat_rows
                    if r.get("ms") is not None and r["ms"] < 200]
            if thin:
                print("提示    : %s 短于 200 ms，观感是一闪而过；调高对应 dwell 或降 fps" % ", ".join(thin))
            if beat_fail:
                print("提示    : 表演拍 full<2.0 = 换姿势幅度不够；lower<1.0 = 只动了脸，"
                      "把镜头拉成全身，或把动作写到腿和手。")

    if args.expect and n != args.expect:
        print(f"FAIL    : 帧数 {n} != 期望 {args.expect}")
        return 1
    if args.strict and beat_fail:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
