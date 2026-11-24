# -*- coding: utf-8 -*-
"""分镜脚本解析 + 与 emit_workflow 的接线。"""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import shot_script as S  # noqa: E402


BASE = """# 注释
0-7   | 一位红发少女
8-15  | pan_left slow | 微微睁眼
16-23 |               | 张嘴笑
"""


def test_parse_basic():
    spec = S.parse_shot(BASE)
    assert spec["segs"] == [8, 8, 8]
    assert spec["actions"] == ["一位红发少女", "微微睁眼", "张嘴笑"]
    assert spec["camera"] == "pan_left"
    assert spec["speed"] == pytest.approx(0.6)
    assert spec["amp"] == pytest.approx(1.0)


def test_gap_rejected():
    with pytest.raises(ValueError):
        S.parse_shot("0-7 | a\n9-15 | b\n")


def test_not_starting_at_zero_rejected():
    with pytest.raises(ValueError):
        S.parse_shot("1-7 | a\n8-15 | b\n")


def test_camera_conflict_rejected():
    with pytest.raises(ValueError):
        S.parse_shot("0-7 | pan_left | a\n8-15 | zoom_in | b\n")


def test_bad_modifier_rejected():
    with pytest.raises(ValueError):
        S.parse_shot("0-7 | pan_left wobbly | a\n8-15 | b\n")


def test_single_beat_rejected():
    with pytest.raises(ValueError):
        S.parse_shot("0-23 | a\n")


def test_amp_word():
    spec = S.parse_shot("0-7 | pan_left slow large | a\n8-15 | b\n")
    assert spec["speed"] == pytest.approx(0.6)
    assert spec["amp"] == pytest.approx(1.4)


def test_emit_uses_shot(tmp_path):
    shot = tmp_path / "shot.txt"
    shot.write_text(BASE, encoding="utf-8")
    out = tmp_path / "out.json"
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "emit_workflow.py"),
                        "--base", str(ROOT / "workflows" / "workflow-sdxl.json"),
                        "--shot", str(shot), "--dynamic", "--out", str(out)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert r.returncode == 0, r.stdout + r.stderr
    wf = json.loads(out.read_text(encoding="utf-8"))
    interps = [n["widgets_values"][0] for n in wf["nodes"] if n["type"] == "APNGLatentInterpolateN"]
    assert interps == [8, 8, 8]
    cam = [n["widgets_values"] for n in wf["nodes"] if n["type"] == "APNGCameraMove"][0]
    assert cam[0] == pytest.approx(-0.12 * 512 * 0.6, abs=0.01)
