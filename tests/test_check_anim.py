# -*- coding: utf-8 -*-
"""check_anim.py --camera：镜头位移带来的漂移不该被判成色块闪。"""
import os
import subprocess
import sys

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHECK = os.path.join(ROOT, "scripts", "check_anim.py")


def make_apng(path, levels):
    frames = [Image.new("RGB", (8, 8), (v, v, v)) for v in levels]
    frames[0].save(path, save_all=True, append_images=frames[1:], duration=100, loop=0)


def run(path, *extra):
    r = subprocess.run([sys.executable, CHECK, path] + list(extra),
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def test_drift_fails_without_camera(tmp_path):
    p = str(tmp_path / "drift.png")
    make_apng(p, [0, 15, 30])          # drift = 30，超过默认 20
    code, log = run(p)
    assert code == 0, log
    assert "FAIL" in log and "颜色漂移" in log


def test_camera_relaxes_drift(tmp_path):
    p = str(tmp_path / "drift.png")
    make_apng(p, [0, 15, 30])
    code, log = run(p, "--camera")
    assert code == 0, log
    assert "FAIL" not in log, log
    assert "--camera 已放宽漂移阈值" in log


def test_camera_still_fails_when_absurd(tmp_path):
    p = str(tmp_path / "wild.png")
    make_apng(p, [0, 60, 120])         # drift = 120，镜头也救不了
    code, log = run(p, "--camera")
    assert code == 0, log
    assert "FAIL" in log


def test_json_reports_camera_flag(tmp_path):
    p = str(tmp_path / "drift.png")
    make_apng(p, [0, 15, 30])
    code, log = run(p, "--camera", "--json")
    assert code == 0, log
    assert '"camera": true' in log
