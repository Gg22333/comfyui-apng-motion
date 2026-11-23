# -*- coding: utf-8 -*-
"""make_storyboard.py — 把成品 APNG 的关键拍抽出来，拼成一张联系表（contact sheet）。

用途：在网页/README 上让人一眼看出「这是一段有剧情的故事」，
而不是四张脸在原地循环。图上是每一拍的真实成片，不是示意图。

用法:
    python scripts/make_storyboard.py out/apng/anim60.png --segs 10,12,4,12,10,12 \
        --out docs/assets/storyboard-diet.webp
    python scripts/make_storyboard.py anim24.png --segs 8,8,8 --cols 3 --tile 360

参数:
    --segs   每拍帧数；第 i 拍取累计帧的下标（K0=0，K1=segs[0]，...）
    --cols   一行几格，默认 3
    --tile   每格边长（正方形缩放），默认 320
    --gap    格子间距，默认 10
    --labels 自定义标签，逗号分隔；不给就用 K0/K1/...
"""
import argparse
import os
import sys

from PIL import Image, ImageDraw, ImageFont

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

FONT_CANDIDATES = [
    r"C:\Windows\Fonts\msyh.ttc",
    r"C:\Windows\Fonts\msyhbd.ttc",
    r"C:\Windows\Fonts\simhei.ttf",
    "/System/Library/Fonts/PingFang.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
]


def load_font(size):
    for p in FONT_CANDIDATES:
        if os.path.isfile(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    return ImageFont.load_default()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("apng")
    ap.add_argument("--segs", required=True, help="每拍帧数，逗号分隔")
    ap.add_argument("--out", required=True)
    ap.add_argument("--cols", type=int, default=3)
    ap.add_argument("--tile", type=int, default=320)
    ap.add_argument("--gap", type=int, default=10)
    ap.add_argument("--labels", default="", help="逗号分隔的自定义标签")
    ap.add_argument("--quality", type=int, default=92)
    a = ap.parse_args()

    segs = [int(x) for x in a.segs.split(",") if x.strip()]
    if not segs:
        print("--segs 为空")
        return 2
    im = Image.open(a.apng)
    n = getattr(im, "n_frames", 1)

    idx, acc = [0], 0
    for s in segs:
        acc += s
        if acc < n:
            idx.append(acc)
    labels = [x.strip() for x in a.labels.split(",") if x.strip()]
    if len(labels) < len(idx):
        labels += ["K%d" % i for i in range(len(labels), len(idx))]

    tiles = []
    for i in idx:
        im.seek(i)
        f = im.convert("RGB")
        side = min(f.size)
        left = (f.width - side) // 2
        top = (f.height - side) // 2
        f = f.crop((left, top, left + side, top + side)).resize((a.tile, a.tile), Image.LANCZOS)
        tiles.append(f)

    label_h = max(22, a.tile // 12)
    font = load_font(label_h - 4)
    cols = max(1, a.cols)
    rows = (len(tiles) + cols - 1) // cols
    W = cols * a.tile + (cols + 1) * a.gap
    H = rows * (a.tile + label_h) + (rows + 1) * a.gap
    sheet = Image.new("RGB", (W, H), (24, 24, 28))
    d = ImageDraw.Draw(sheet)

    for i, t in enumerate(tiles):
        r, c = divmod(i, cols)
        x = a.gap + c * (a.tile + a.gap)
        y = a.gap + r * (a.tile + label_h + a.gap)
        sheet.paste(t, (x, y))
        d.text((x + 6, y + a.tile + 2), labels[i], fill=(240, 240, 240), font=font)

    out = os.path.abspath(a.out)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    if out.lower().endswith(".webp"):
        sheet.save(out, quality=a.quality, method=6)
    else:
        sheet.save(out)
    print("storyboard: %s  %dx%d  %d 格  %.0f KB" % (
        out, W, H, len(tiles), os.path.getsize(out) / 1024))
    print("frames    : " + ", ".join("%s=f%d" % (labels[i], j) for i, j in enumerate(idx)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
