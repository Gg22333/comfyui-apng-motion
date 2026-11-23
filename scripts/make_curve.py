#!/usr/bin/env python
"""make_curve.py — 生成 LatentInterpolate 的 ratio 曲线（改节奏 / 加剧情拍用）。

ratio 是 samples1 的权重：1.0 = samples1，0.0 = samples2。
每一段都从"贴着上一关键帧"走到"贴着下一关键帧"：
段起点接近 1.0、段终点接近 0.0，两段在关节处一前一后地靠近同一个关键帧，
播放时自然形成 1–2 帧停顿。

关键帧链：K0(首帧) -> K1 -> K2 -> ... -> KN-1 -> K0
段数 = 关键帧数（最后一段回到首帧）。

用法:
    python make_curve.py                                  # 默认 3 段 8/8/8
    python make_curve.py --segs 6,7,6,5                   # 4 拍剧情，24 帧
    python make_curve.py --segs 5,6,5,4,4 --power 2.2     # 5 拍
    python make_curve.py --segs 6,7,6,5 --starts 1,0.95,0.92,0.9 --ends 0.05,0.04,0.03,0.01
    python make_curve.py --json                           # 只输出 JSON 数组

说明:
    - 3 段时不传 --starts/--ends，默认值与现用曲线同族（1.0/0.92/0.88、0.08/0.0/0.01）。
    - 每段帧数建议 >= 4；低于 4 帧那段看不出动作，只算一次跳。
    - 输出会做唯一化：相邻 ratio 差小于 0.004 就继续往下压，
      避免像素相同的相邻帧被 APNG 编码器合并（Pillow 会丢帧并累加 duration）。
"""
import argparse
import json
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

EPS = 0.004


def flist(s):
    return [float(x) for x in s.split(",") if x.strip() != ""]


def build_segment(count, start, end, power):
    if count <= 0:
        return []
    if count == 1:
        return [start]
    out = []
    for i in range(count):
        t = i / (count - 1)
        out.append(start + (end - start) * (t ** power))
    return out


def defaults(n):
    if n == 3:
        return [1.0, 0.92, 0.88], [0.08, 0.0, 0.01], [3.0, 1.2, 2.5]
    starts = [1.0] + [0.94, 0.92, 0.90, 0.88, 0.86][: n - 1]
    ends = [0.05, 0.04, 0.03, 0.02, 0.02][: n - 1] + [0.01]
    return starts, ends, [1.8] * n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--frames", type=int, default=24)
    ap.add_argument("--segs", default="8,8,8", help="每段帧数，逗号分隔；段数 = 关键帧数")
    ap.add_argument("--starts", default="", help="每段起点 ratio；留空用默认")
    ap.add_argument("--ends", default="", help="每段终点 ratio；留空用默认")
    ap.add_argument("--power", default="", help="每段缓动指数；留空用默认，单值则全段同用")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    segs = [int(x) for x in args.segs.split(",") if x.strip()]
    n = len(segs)
    if n < 2:
        raise SystemExit("至少 2 段（最少 3 个关键帧）")
    if sum(segs) != args.frames:
        raise SystemExit(
            "segs 之和 %d != frames %d；把多出的帧减到最长的那段"
            % (sum(segs), args.frames)
        )
    if min(segs) < 3:
        print("WARN: 有一段少于 3 帧，那一段基本只是跳，不是动", file=sys.stderr)

    ds, de, dp = defaults(n)
    starts = flist(args.starts) if args.starts else ds
    ends = flist(args.ends) if args.ends else de
    if args.power:
        pw = flist(args.power)
        powers = pw * n if len(pw) == 1 else pw
    else:
        powers = dp
    if not (len(starts) == len(ends) == len(powers) == n):
        raise SystemExit("--starts / --ends / --power 的个数必须等于段数 %d" % n)

    raw = []
    for count, start, end, power in zip(segs, starts, ends, powers):
        raw += build_segment(count, start, end, power)

    curve, used = [], set()
    for r in raw:
        v = round(min(max(r, 0.0), 1.0), 3)
        if v in used:
            for k in range(1, 250):
                hit = None
                for cand in (round(v + k * 0.004, 3), round(v - k * 0.004, 3)):
                    if 0.0 <= cand <= 1.0 and cand not in used:
                        hit = cand
                        break
                if hit is not None:
                    v = hit
                    break
        used.add(v)
        curve.append(v)

    if args.json:
        print(json.dumps(curve))
        return

    names = ["K0"] + ["K%d" % i for i in range(1, n)] + ["K0"]
    print("frames=%d  segs=%s  starts=%s  ends=%s" % (args.frames, segs, starts, ends))
    print("%3s  %6s  %s" % ("帧", "ratio", "段"))
    i = 0
    for seg in range(n):
        lab = "%s -> %s" % (names[seg], names[seg + 1])
        for _ in range(segs[seg]):
            print("%3d  %6s  %s" % (i + 1, curve[i], lab))
            i += 1
    print("\nJSON:", json.dumps(curve))


if __name__ == "__main__":
    main()

