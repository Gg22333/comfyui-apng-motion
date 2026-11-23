# -*- coding: utf-8 -*-
"""make_preview.py — 把成品 APNG 重编码成网页预览 GIF / WebP。

和 VHS 直接出 GIF 的区别：
  - 全局固定调色板：所有帧共用一份 256 色，消除逐帧调色板漂移
  - dither=NONE：不做误差扩散，避免相邻帧噪点不同被看成"色块闪"
  - 可缩放：512 缩到 384，抖动颗粒视觉更小、体积更小
  - 同时出 WebP：真彩、体积小，作为网页主预览

节奏：给 --story 就按剧情卡的 fps / dwell / ease 写逐帧延时，
不给就整片等速（--fps）。GIF 的延时量化到 10 ms，WebP 用量秒精度。

用法:
    python make_preview.py <apng> --out-dir docs/assets --width 384
    python make_preview.py <apng> --story ../assets/story.diet.json --out-dir docs/assets
    python make_preview.py <apng> --out-dir docs/assets --width 512 --no-resize
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


def load_frames(path, width):
    im = Image.open(path)
    frames = []
    for i in range(getattr(im, "n_frames", 1)):
        im.seek(i)
        f = im.convert("RGB")
        if width and f.width != width:
            h = round(f.height * width / f.width)
            f = f.resize((width, h), Image.LANCZOS)
        frames.append(f)
    return frames


def bbox_diff(frames):
    from PIL import ImageChops
    prev = None
    out = []
    for f in frames:
        if prev is not None:
            s = ImageChops.difference(prev, f).convert("L")
            h = s.histogram()
            tot = sum(h)
            out.append(sum(v * c for v, c in enumerate(h)) / tot)
        prev = f
    return out


def delays_for(n, a, story):
    """按剧情卡 / 命令行算逐帧延时；返回 (gif_ms, webp_ms, segs)。"""
    fps = a.fps or float(story.get("fps", 10) or 10)
    ease = a.ease if a.ease >= 0 else float(story.get("ease", 0.3))
    dwell = [float(x) for x in a.dwell.split(",") if x.strip()] if a.dwell else (story.get("dwell") or None)
    segs_txt = a.segs or ",".join(str(x) for x in (story.get("segs") or []))
    segs = [int(x) for x in segs_txt.split(",") if x.strip()] if segs_txt else [n]
    if sum(segs) != n:
        print("WARN: segs 之和 %d != 帧数 %d，退回整片等速" % (sum(segs), n))
        segs, dwell = [n], None
    gif = T.frame_delays(n, segs, fps, dwell=dwell, ease=ease, quantum=10)
    webp = T.frame_delays(n, segs, fps, dwell=dwell, ease=ease, quantum=1)
    return gif, webp, segs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("apng")
    ap.add_argument("--out-dir", default="docs/assets")
    ap.add_argument("--width", type=int, default=384)
    ap.add_argument("--fps", type=float, default=0)
    ap.add_argument("--story", default="", help="剧情卡 JSON；读 fps / segs / dwell / ease")
    ap.add_argument("--segs", default="")
    ap.add_argument("--dwell", default="")
    ap.add_argument("--ease", type=float, default=-1)
    ap.add_argument("--webp-quality", type=int, default=100,
                    help="WebP 质量；默认 100，保证帧数不被合并（libwebp 会丢弃近重复帧）")
    ap.add_argument("--prefix", default="preview")
    ap.add_argument("--no-resize", action="store_true")
    a = ap.parse_args()

    story = json.load(open(a.story, encoding="utf-8")) if a.story else {}
    width = 0 if a.no_resize else a.width
    frames = load_frames(a.apng, width)
    if not frames:
        print("读不到帧")
        return 2
    os.makedirs(a.out_dir, exist_ok=True)
    gif_ms, webp_ms, segs = delays_for(len(frames), a, story)

    # --- GIF：全局调色板 + 无抖动 ---
    pal = frames[0].quantize(colors=256, method=Image.MEDIANCUT)
    q = [f.quantize(palette=pal, dither=Image.NONE) for f in frames]
    gif_path = os.path.join(a.out_dir, a.prefix + ".gif")
    q[0].save(gif_path, save_all=True, append_images=q[1:], duration=gif_ms,
              loop=0, disposal=1, optimize=True)

    # --- WebP：真彩，网页主预览 ---
    # libwebp 的动画编码器会把「近似重复」的帧合并（60 帧常变 58 帧）。
    # 质量 90 时最容易发生；100 可保住全部帧，仍比 lossless 小得多。
    webp_path = os.path.join(a.out_dir, a.prefix + ".webp")
    frames[0].save(webp_path, save_all=True, append_images=frames[1:], duration=webp_ms,
                   loop=0, quality=a.webp_quality, method=6)
    got = Image.open(webp_path).n_frames
    if got != len(frames):
        print("WARN webp 帧数 %d != 源 %d，回退 lossless" % (got, len(frames)))
        frames[0].save(webp_path, save_all=True, append_images=frames[1:], duration=webp_ms,
                       loop=0, lossless=True, quality=100, method=6)
        got = Image.open(webp_path).n_frames

    d = bbox_diff(frames)
    gd = bbox_diff([x.convert("RGB") for x in q])
    bt = T.beat_totals(gif_ms, segs)
    print("frames      : %d  size=%s" % (len(frames), frames[0].size))
    print("gif         : %s  %.0f KB" % (gif_path, os.path.getsize(gif_path) / 1024))
    print("webp        : %s  %.0f KB  frames=%d  q=%d" % (
        webp_path, os.path.getsize(webp_path) / 1024, got, a.webp_quality))
    print("timing      : gif=%.2f s  webp=%.2f s  frame=%d..%d ms" % (
        sum(gif_ms) / 1000.0, sum(webp_ms) / 1000.0, min(webp_ms), max(webp_ms)))
    print("beats       : " + "  ".join("%.0fms" % x for x in bt))
    print("src diff    : avg %.2f max %.2f" % (sum(d) / len(d), max(d)))
    print("gif diff    : avg %.2f max %.2f" % (sum(gd) / len(gd), max(gd)))
    return 0


if __name__ == "__main__":
    sys.exit(main())