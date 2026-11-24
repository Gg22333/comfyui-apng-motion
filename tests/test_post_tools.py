# -*- coding: utf-8 -*-
"""拆帧 / 后处理循环 / 有效帧率。"""
import json
import os
import subprocess
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SPLIT = ROOT / "scripts" / "split_frames.py"
LOOP = ROOT / "scripts" / "make_loop.py"
CHECK = ROOT / "scripts" / "check_anim.py"


def make_seq(path, n=5, size=(32, 32)):
    frames = []
    for i in range(n):
        im = Image.new("RGB", size, (i * 40 % 256, 60, 90))
        frames.append(im)
    frames[0].save(path, save_all=True, append_images=frames[1:], duration=100, loop=0)


def run(script, *args):
    r = subprocess.run([sys.executable, str(script)] + [str(a) for a in args],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def test_split_all_frames(tmp_path):
    src = tmp_path / "a.png"
    make_seq(src)
    out = tmp_path / "frames"
    code, log = run(SPLIT, src, "--out", out)
    assert code == 0, log
    assert len(list(out.glob("frame_*.png"))) == 5


def test_split_pick_keys(tmp_path):
    src = tmp_path / "a.png"
    make_seq(src)
    out = tmp_path / "frames"
    code, log = run(SPLIT, src, "--out", out, "--pick", "3", "--json")
    assert code == 0, log
    data = json.loads(log[log.index("{"):])
    assert len(data["keys"]) == 3
    assert len(list(out.glob("key_*.png"))) == 3


def test_loop_ping_pong(tmp_path):
    src = tmp_path / "a.png"
    make_seq(src, 5)
    out = tmp_path / "pp.png"
    code, log = run(LOOP, src, "--ping-pong", "--out", out)
    assert code == 0, log
    assert Image.open(out).n_frames == 8      # 5 + 3


def test_loop_holds_and_repeat(tmp_path):
    src = tmp_path / "a.gif"
    make_seq(src, 4)
    out = tmp_path / "h.gif"
    code, log = run(LOOP, src, "--hold-first", "2", "--hold-last", "2", "--repeat", "2", "--out", out)
    assert code == 0, log
    assert Image.open(out).n_frames == (4 + 4) * 2


def test_effective_fps(tmp_path):
    src = tmp_path / "a.png"
    make_seq(src, 5)
    code, log = run(CHECK, src, "--json")
    assert code == 0, log
    data = json.loads(log[log.index("{"):])
    assert data["effective_fps"] == 10.0
