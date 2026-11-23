# -*- coding: utf-8 -*-
"""retime.py — 只改逐帧停留，不动一个像素。

ComfyUI 的保存节点只有一个全局 fps，每拍停留表达不出来。
已经出片之后再改节奏，不需要重跑采样：

    读 APNG -> 按剧情卡的 fps / dwell / ease 算每帧延时 -> 重写 fcTL 的 delay

像素、尺寸、帧数全部保持不变；体积基本不变；没有 GPU 参与。

用法:
    python retime.py anim.png --story ../assets/story.diet.json
    python retime.py anim.png --story card.json --out anim-retimed.png
    python retime.py anim.png --fps 20 --segs 5,5,4,7,6,7,5,6,5,5,5
    python retime.py anim.png --story card.json --dwell 1,1,1.1,1.3,1,1.3,1,1,0.9,0.95,0.95

不写 --out 时输出到同目录的 <name>.retimed.png。
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import timing as T

try:
    from PIL import Image
except ImportError:
    print("需要 Pillow: pip install Pillow")
    sys.exit(2)


def parse_list(text):
    return [float(x) for x in str(text).split(",") if str(x).strip()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("apng")
    ap.add_argument("--story", default="", help="剧情卡 JSON；读 fps / segs / dwell / ease")
    ap.add_argument("--out", default="")
    ap.add_argument("--fps", type=float, default=0)
    ap.add_argument("--segs", default="")
    ap.add_argument("--dwell", default="")
    ap.add_argument("--ease", type=float, default=-1)
    a = ap.parse_args()

    story = json.load(open(a.story, encoding="utf-8")) if a.story else {}
    fps = a.fps or float(story.get("fps", 10) or 10)
    ease = a.ease if a.ease >= 0 else float(story.get("ease", 0.3))
    dwell = parse_list(a.dwell) if a.dwell else (story.get("dwell") or None)
    segs_txt = a.segs or ",".join(str(x) for x in (story.get("segs") or []))

    try:
        im = Image.open(a.apng)
    except Exception as exc:
        print("OPEN FAILED:", exc)
        return 2
    n = getattr(im, "n_frames", 1)
    if n < 2:
        print("只有 %d 帧，不是动图" % n)
        return 2

    if segs_txt:
        segs = [int(x) for x in segs_txt.split(",") if x.strip()]
    else:
        segs = [n]
    if dwell and len(dwell) != len(segs):
        print("dwell 长度 %d != 段数 %d" % (len(dwell), len(segs)))
        return 2

    try:
        delays = T.frame_delays(n, segs, fps, dwell=dwell, ease=ease, quantum=1)
    except ValueError as exc:
        print("参数错误:", exc)
        return 2

    loop = im.info.get("loop", 0)
    frames = []
    for i in range(n):
        im.seek(i)
        frames.append(im.convert("RGBA"))

    out = a.out or os.path.join(
        os.path.dirname(os.path.abspath(a.apng)),
        os.path.splitext(os.path.basename(a.apng))[0] + ".retimed.png")
    frames[0].save(out, save_all=True, append_images=frames[1:],
                   duration=delays, loop=loop, disposal=1)

    got = Image.open(out)
    bt = T.beat_totals(delays, segs)
    print("in      : %s  frames=%d  %d ms/frame" % (
        a.apng, n, im.info.get("duration") or 0))
    print("out     : %s  frames=%d" % (out, got.n_frames))
    print("timing  : fps=%g  total=%.3f s  frame=%d..%d ms  ease=%g" % (
        fps, sum(delays) / 1000.0, min(delays), max(delays), ease))
    print("beats   : " + "  ".join("%.0fms" % x for x in bt))
    short = [i for i, x in enumerate(bt) if x < 200]
    if short:
        print("WARN    : 第 %s 拍短于 0.20 s，观感是一闪而过；调高对应 dwell" % (
            ",".join("K%d" % i for i in short)))
    return 0


if __name__ == "__main__":
    sys.exit(main())