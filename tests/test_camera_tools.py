# -*- coding: utf-8 -*-
"""镜头预设 + 预览脚本的测试。"""
import importlib.util
import os
import subprocess
import sys
import types
from pathlib import Path

import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import camera_presets as CP  # noqa: E402
import make_camera_preview as P  # noqa: E402

PREVIEW = ROOT / "scripts" / "make_camera_preview.py"
NODES = ROOT / "comfyui_nodes" / "__init__.py"


def load_nodes():
    try:
        import torch  # noqa: F401
        import torch.nn.functional  # noqa: F401
    except Exception:
        fake = types.ModuleType("torch")
        nn = types.ModuleType("torch.nn")
        fn = types.ModuleType("torch.nn.functional")
        fake.nn = nn
        nn.functional = fn
        sys.modules.setdefault("torch", fake)
        sys.modules.setdefault("torch.nn", nn)
        sys.modules.setdefault("torch.nn.functional", fn)
    spec = importlib.util.spec_from_file_location("apng_nodes_camera", NODES)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def centroid(img):
    px = img.convert("L").load()
    w, h = img.size
    sx = sy = n = 0
    for y in range(h):
        for x in range(w):
            if px[x, y] > 128:
                sx += x
                sy += y
                n += 1
    assert n, "没有亮像素"
    return sx / n, sy / n


def test_resolve_values():
    v = CP.resolve("dolly_in", 512, 512)
    assert v["zoom"] == pytest.approx(1.18)
    v = CP.resolve("pan_left", 512, 512)
    assert v["x"] == pytest.approx(-61.44)
    v = CP.resolve("pan_left", 512, 512, speed=2.0, amp=0.5)
    assert v["x"] == pytest.approx(-61.44)


def test_alias_and_rejections():
    assert CP.resolve("push_in", 512, 512) == CP.resolve("dolly_in", 512, 512)
    with pytest.raises(ValueError):
        CP.resolve("orbit_left", 512, 512)
    with pytest.raises(ValueError):
        CP.resolve("no_such_move", 512, 512)


def test_progress_parity_with_node():
    mod = load_nodes()
    for name in CP.CAMERA_EASINGS:
        for loop in (True, False):
            a = CP.camera_progress(9, name, loop)
            b = mod.camera_progress(9, name, loop)
            assert all(abs(x - y) < 1e-12 for x, y in zip(a, b)), (name, loop)


def test_preview_directions():
    img = Image.new("RGB", (64, 64), (0, 0, 0))
    for y in range(30, 35):
        for x in range(30, 35):
            img.putpixel((x, y), (255, 255, 255))
    assert centroid(img) == (32.0, 32.0)
    right = P.build(img, 2, x=8, y=0, easing="linear", loop=False)[1]
    assert centroid(right) == (40.0, 32.0)
    down = P.build(img, 2, x=0, y=6, easing="linear", loop=False)[1]
    assert centroid(down) == (32.0, 38.0)


def test_preview_gif_keeps_all_frames(tmp_path):
    src = tmp_path / "still.png"
    img = Image.new("RGB", (64, 64), (30, 60, 90))
    img.save(src)
    out = tmp_path / "prev.gif"
    r = subprocess.run([sys.executable, str(PREVIEW), str(src), "--preset", "dolly_in",
                        "--frames", "12", "--fps", "8", "--out", str(out)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert r.returncode == 0, r.stdout + r.stderr
    assert out.is_file()
    im = Image.open(out)
    assert im.n_frames == 12
