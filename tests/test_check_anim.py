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


def test_drift_without_evidence_is_unknown(tmp_path):
    p = str(tmp_path / "drift.png")
    make_apng(p, [0, 15, 30])          # drift = 30，超过默认 20
    code, log = run(p)
    assert code == 0, log
    assert "UNKNOWN" in log and "不算通过" in log


def test_json_verdict_unknown(tmp_path):
    p = str(tmp_path / "drift.png")
    make_apng(p, [0, 15, 30])
    code, log = run(p, "--json")
    assert code == 0, log
    assert '"color_verdict": "unknown"' in log


def test_camera_flag_marks_ok(tmp_path):
    p = str(tmp_path / "mild.png")
    make_apng(p, [0, 5, 10])          # drift = 10，镜头阈值内
    code, log = run(p, "--camera", "--json")
    assert code == 0, log
    assert '"color_verdict": "ok"' in log


def test_camera_relaxes_drift(tmp_path):
    p = str(tmp_path / "drift.png")
    make_apng(p, [0, 15, 30])
    code, log = run(p, "--camera")
    assert code == 0, log
    assert "FAIL" not in log, log
    assert "已放宽漂移阈值" in log


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


def test_curve_reports_shape(tmp_path):
    p = str(tmp_path / "rise.png")
    make_apng(p, [0, 5, 10, 15, 20, 25, 30])
    code, log = run(p, "--curve")
    assert code == 0, log
    assert "curve   :" in log
    assert "shape   : 累积" in log


def test_curve_closed_loop(tmp_path):
    p = str(tmp_path / "loop.png")
    make_apng(p, [0, 10, 20, 10, 0])
    code, log = run(p, "--curve")
    assert code == 0, log
    assert "shape   : 闭合" in log


def _write_wf(tmp_path, camera):
    import json
    wf = {"nodes": [{"id": 1, "type": "APNGCameraMove",
                     "widgets_values": camera}]}
    q = tmp_path / "wf.json"
    q.write_text(json.dumps(wf), encoding="utf-8")
    return str(q)


def test_workflow_marks_camera(tmp_path):
    p = str(tmp_path / "drift.png")
    make_apng(p, [0, 15, 30])
    wf = _write_wf(tmp_path, [12, 6, 1.15, 8, "sine", True, "reflection"])
    code, log = run(p, "--workflow", wf)
    assert code == 0, log
    assert "按 --camera 处理" in log
    assert "FAIL" not in log, log


def test_workflow_neutral_camera_is_static(tmp_path):
    p = str(tmp_path / "drift.png")
    make_apng(p, [0, 15, 30])
    wf = _write_wf(tmp_path, [0, 0, 1, 0, "sine", True, "reflection"])
    code, log = run(p, "--workflow", wf)
    assert code == 0, log
    assert "没有非中立镜头" in log
    assert "FAIL" in log

