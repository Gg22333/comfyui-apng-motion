import json
import subprocess
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "make_preview.py"


def make_apng(path, n=24, size=64):
    frames = []
    for i in range(n):
        # 每帧整块背景 + 一块移动色块，保证量化后仍然互不相同
        f = Image.new("RGB", (size, size), (20 + i * 6, 40, 90))
        for x in range(8):
            for y in range(8):
                f.putpixel((x + i, y), (250, 240, 230))
        frames.append(f)
    frames[0].save(path, save_all=True, append_images=frames[1:], duration=100, loop=0)


def test_make_preview_outputs_gif_and_webp(tmp_path):
    apng = tmp_path / "in.png"
    make_apng(apng)
    out = tmp_path / "out"
    r = subprocess.run([sys.executable, str(SCRIPT), str(apng),
                        "--out-dir", str(out), "--width", "64"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert r.returncode == 0, r.stdout + r.stderr
    gif = Image.open(out / "preview.gif")
    webp = Image.open(out / "preview.webp")
    assert gif.n_frames == 24
    assert webp.n_frames == 24
    assert gif.size == (64, 64)
    # 全局调色板 + 关抖动：重编码后的相邻帧差异不应比源帧更差
    import re
    src = float(re.search(r"src diff\s*: avg ([\d.]+)", r.stdout).group(1))
    out_diff = float(re.search(r"gif diff\s*: avg ([\d.]+)", r.stdout).group(1))
    assert out_diff <= src + 0.2, (src, out_diff)


def test_make_preview_reports_deterministic_diff(tmp_path):
    apng = tmp_path / "in.png"
    make_apng(apng)
    out = tmp_path / "out"
    r = subprocess.run([sys.executable, str(SCRIPT), str(apng),
                        "--out-dir", str(out), "--width", "64"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert "gif diff" in r.stdout
    assert "webp" in r.stdout
