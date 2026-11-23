# -*- coding: utf-8 -*-
"""动态帧数节点 + --dynamic 工作流 + install_nodes.py 的回归测试。"""
import importlib.util
import json
import subprocess
import sys
import types
from pathlib import Path

import pytest

import comfy_lib as L

ROOT = Path(__file__).resolve().parents[1]
EMIT = ROOT / "scripts" / "emit_workflow.py"
INSTALL = ROOT / "scripts" / "install_nodes.py"
NODES = ROOT / "comfyui_nodes" / "__init__.py"


def run(args, script=EMIT):
    r = subprocess.run([sys.executable, str(script)] + args,
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def load_nodes():
    """节点文件 import torch，但比例函数不用 torch；测试环境没装就塞个空壳。"""
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
    spec = importlib.util.spec_from_file_location("apng_nodes_under_test", NODES)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def roles(n):
    if n == 1:
        return ["first"]
    return ["first"] + ["middle"] * (n - 2) + ["last"]


def test_ratio_parity_with_build_curve():
    mod = load_nodes()
    cases = ([3, 4, 5], [8, 8, 8], [1, 2, 1], [12], [6, 7, 6, 5])
    for segs in cases:
        for curve in ("linear", "ease", "snap"):
            flat = L.build_curve(segs, curve=curve)
            off = 0
            for cnt, role in zip(segs, roles(len(segs))):
                got = mod.segment_ratios(cnt, role, curve)
                assert got == flat[off:off + cnt], (segs, curve, role, got, flat[off:off + cnt])
                off += cnt


def test_dynamic_emit_shape(tmp_path):
    out = tmp_path / "dyn.json"
    code, log = run(["--base", str(ROOT / "workflows" / "workflow-sdxl.json"),
                     "--story", str(ROOT / "assets" / "story.example.json"),
                     "--dynamic", "--out", str(out)])
    assert code == 0, log
    assert "VALIDATE OK" in log
    wf = json.loads(out.read_text(encoding="utf-8"))
    nodes = wf["nodes"]
    typ = [n["type"] for n in nodes]
    assert len(nodes) == 26
    assert len([n for n in nodes if n["type"] == "KSampler"]) == 3
    assert typ.count("APNGLatentInterpolateN") == 3
    assert typ.count("APNGLatentConcat") == 2
    assert typ.count("VAEDecode") == 1
    assert typ.count("APNGFrameStats") == 1
    assert "LatentInterpolate" not in typ
    assert "ImageBatchMulti" not in typ
    interps = [n for n in nodes if n["type"] == "APNGLatentInterpolateN"]
    assert [n["widgets_values"] for n in interps] == [
        [8, "first", "linear"], [8, "middle", "linear"], [8, "last", "linear"]]
    stats = [n for n in nodes if n["type"] == "APNGFrameStats"][0]
    assert stats["widgets_values"] == [10, "8,8,8"]
    dec_id = [n for n in nodes if n["type"] == "VAEDecode"][0]["id"]
    links = {l[0]: l for l in wf["links"]}
    imgs = [i for i in stats["inputs"] if i["name"] == "images"][0]
    assert links[imgs["link"]][1] == dec_id
    for s in ("SaveAnimatedPNG", "SaveAnimatedWEBP", "VHS_VideoCombine"):
        n = [x for x in nodes if x["type"] == s][0]
        i = [x for x in n["inputs"] if x["name"] == "images"][0]
        assert links[i["link"]][1] == dec_id


def test_dynamic_validate_catches_edit_without_stats(tmp_path):
    out = tmp_path / "dyn.json"
    code, log = run(["--base", str(ROOT / "workflows" / "workflow-sdxl.json"),
                     "--story", str(ROOT / "assets" / "story.example.json"),
                     "--dynamic", "--out", str(out)])
    assert code == 0, log
    wf = json.loads(out.read_text(encoding="utf-8"))
    interp = [n for n in wf["nodes"] if n["type"] == "APNGLatentInterpolateN"][0]
    interp["widgets_values"][0] = 4
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(wf, ensure_ascii=False, indent=2), encoding="utf-8")
    code, log = run(["--validate", str(bad)])
    assert code != 0
    assert "不一致" in log
    stats = [n for n in wf["nodes"] if n["type"] == "APNGFrameStats"][0]
    stats["widgets_values"][1] = "4,8,8"
    ok = tmp_path / "ok.json"
    ok.write_text(json.dumps(wf, ensure_ascii=False, indent=2), encoding="utf-8")
    code, log = run(["--validate", str(ok)])
    assert code == 0, log


def test_dynamic_validate_rejects_bad_widgets(tmp_path):
    out = tmp_path / "dyn.json"
    code, log = run(["--base", str(ROOT / "workflows" / "workflow-sdxl.json"),
                     "--story", str(ROOT / "assets" / "story.example.json"),
                     "--dynamic", "--out", str(out)])
    assert code == 0, log
    base = json.loads(out.read_text(encoding="utf-8"))
    for field, value, needle in ((1, "center", "role"), (0, 0, "frames")):
        wf = json.loads(json.dumps(base))
        [n for n in wf["nodes"] if n["type"] == "APNGLatentInterpolateN"][0]["widgets_values"][field] = value
        p = tmp_path / ("bad-%s.json" % needle)
        p.write_text(json.dumps(wf, ensure_ascii=False, indent=2), encoding="utf-8")
        code, log = run(["--validate", str(p)])
        assert code != 0, needle
        assert needle in log, log


def test_static_mode_unchanged(tmp_path):
    out = tmp_path / "static.json"
    code, log = run(["--base", str(ROOT / "workflows" / "workflow-sdxl.json"),
                     "--story", str(ROOT / "assets" / "story.example.json"),
                     "--out", str(out)])
    assert code == 0, log
    wf = json.loads(out.read_text(encoding="utf-8"))
    typ = [n["type"] for n in wf["nodes"]]
    assert len(wf["nodes"]) == 67
    assert typ.count("LatentInterpolate") == 24
    assert not any(t.startswith("APNG") for t in typ)


def test_install_nodes_copies_and_checks(tmp_path):
    root = tmp_path / "ComfyUI"
    (root / "custom_nodes").mkdir(parents=True)
    profile = tmp_path / "xl.json"
    profile.write_text(json.dumps({"comfy_root": str(root)}), encoding="utf-8")
    code, log = run(["--profile", str(profile)], script=INSTALL)
    assert code == 0, log
    dst = root / "custom_nodes" / "apng_motion_nodes" / "__init__.py"
    assert dst.is_file()
    assert dst.read_text(encoding="utf-8") == NODES.read_text(encoding="utf-8")
    code, log = run(["--profile", str(profile), "--check"], script=INSTALL)
    assert code == 0, log
    assert "SAME" in log

def test_shipped_dynamic_workflows_validate():
    for name in ("workflow-sdxl-dynamic.json", "workflow-moss-dynamic.json",
                 "workflow-sdxl-dynamic-camera.json", "workflow-moss-dynamic-camera.json"):
        p = ROOT / "workflows" / name
        assert p.is_file(), name
        code, log = run(["--validate", str(p)])
        assert code == 0, name + log

def test_dynamic_emit_is_idempotent(tmp_path):
    once = tmp_path / "d1.json"
    twice = tmp_path / "d2.json"
    base = str(ROOT / "workflows" / "workflow-sdxl.json")
    story = str(ROOT / "assets" / "story.example.json")
    code, log = run(["--base", base, "--story", story, "--dynamic", "--out", str(once)])
    assert code == 0, log
    code, log = run(["--base", str(once), "--story", story, "--dynamic", "--out", str(twice)])
    assert code == 0, log
    a = json.loads(once.read_text(encoding="utf-8"))
    b = json.loads(twice.read_text(encoding="utf-8"))
    assert len(a["nodes"]) == len(b["nodes"]) == 26
    assert [n["type"] for n in a["nodes"]].count("APNGLatentInterpolateN") == 3
    assert [n["type"] for n in b["nodes"]].count("APNGLatentInterpolateN") == 3


def _emit_camera(tmp_path, name="cam.json"):
    out = tmp_path / name
    code, log = run(["--base", str(ROOT / "workflows" / "workflow-sdxl.json"),
                     "--story", str(ROOT / "assets" / "story.example.json"),
                     "--dynamic", "--camera", "--out", str(out)])
    assert code == 0, log
    return json.loads(out.read_text(encoding="utf-8"))


def _write(tmp_path, wf, name):
    p = tmp_path / name
    p.write_text(json.dumps(wf, ensure_ascii=False, indent=2), encoding="utf-8")
    return p


def test_camera_progress_and_easing():
    mod = load_nodes()
    assert mod.camera_progress(5, "sine", True) == pytest.approx([0.0, 0.5, 1.0, 0.5, 0.0])
    assert mod.camera_progress(5, "linear", False) == pytest.approx([0.0, 0.25, 0.5, 0.75, 1.0])
    assert mod.camera_progress(1, "sine", True) == [0.0]
    for name in mod.CAMERA_EASINGS:
        ps = mod.camera_progress(9, name, False)
        assert ps[0] == 0.0 and abs(ps[-1] - 1.0) < 1e-9, name
        lp = mod.camera_progress(9, name, True)
        assert lp[0] == 0.0 and abs(lp[0] - lp[-1]) < 1e-9, name


def test_camera_emit_shape(tmp_path):
    wf = _emit_camera(tmp_path)
    nodes = wf["nodes"]
    typ = [n["type"] for n in nodes]
    assert len(nodes) == 27
    assert typ.count("APNGCameraMove") == 1
    cam = [n for n in nodes if n["type"] == "APNGCameraMove"][0]
    assert cam["widgets_values"] == [0.0, 0.0, 1.0, 0.0, "sine", True, "reflection"]
    links = {l[0]: l for l in wf["links"]}
    dec_id = [n for n in nodes if n["type"] == "VAEDecode"][0]["id"]
    assert links[[i for i in cam["inputs"] if i["name"] == "images"][0]["link"]][1] == dec_id
    for t in ("APNGFrameStats", "SaveAnimatedPNG", "SaveAnimatedWEBP", "VHS_VideoCombine"):
        n = [x for x in nodes if x["type"] == t][0]
        i = [x for x in n["inputs"] if x["name"] == "images"][0]
        assert links[i["link"]][1] == cam["id"], t


def test_camera_validate_rejects_bad_widgets_and_rewire(tmp_path):
    base = _emit_camera(tmp_path, "cam-base.json")
    for field, value, needle in ((4, "swing", "easing"), (5, "yes", "loop"), (6, "clamp", "border")):
        wf = json.loads(json.dumps(base))
        [n for n in wf["nodes"] if n["type"] == "APNGCameraMove"][0]["widgets_values"][field] = value
        code, log = run(["--validate", str(_write(tmp_path, wf, "bad-%s.json" % needle))])
        assert code != 0, needle
        assert needle in log, log
    wf = json.loads(json.dumps(base))
    cam_id = [n for n in wf["nodes"] if n["type"] == "APNGCameraMove"][0]["id"]
    dec_id = [n for n in wf["nodes"] if n["type"] == "VAEDecode"][0]["id"]
    for l in wf["links"]:
        if l[1] == cam_id:
            l[1] = dec_id
    code, log = run(["--validate", str(_write(tmp_path, wf, "rewired.json"))])
    assert code != 0
    assert "镜头节点" in log, log


def test_camera_motion_detection():
    import emit_workflow as E
    assert E.camera_motion({"nodes": []}) is False
    neutral = {"nodes": [{"type": "APNGCameraMove",
                          "widgets_values": [0, 0, 1, 0, "sine", True, "reflection"]}]}
    assert E.camera_motion(neutral) is False
    for i in range(4):
        w = [0, 0, 1, 0, "sine", True, "reflection"]
        w[i] = [8, -8, 1.2, 15][i]
        moved = {"nodes": [{"type": "APNGCameraMove", "widgets_values": w}]}
        assert E.camera_motion(moved) is True, i
    broken = {"nodes": [{"type": "APNGCameraMove", "widgets_values": ["x"]}]}
    assert E.camera_motion(broken) is False


def test_camera_node_rejected_in_static_graph(tmp_path):
    out = tmp_path / "static.json"
    code, log = run(["--base", str(ROOT / "workflows" / "workflow-sdxl.json"),
                     "--story", str(ROOT / "assets" / "story.example.json"),
                     "--out", str(out)])
    assert code == 0, log
    wf = json.loads(out.read_text(encoding="utf-8"))
    nid = max(n["id"] for n in wf["nodes"]) + 1
    wf["nodes"].append({
        "id": nid, "type": "APNGCameraMove", "pos": [0, 0], "size": [320, 260],
        "flags": {}, "order": 99, "mode": 0,
        "inputs": [{"name": "images", "type": "IMAGE", "link": None}],
        "outputs": [{"name": "IMAGE", "type": "IMAGE", "links": []}],
        "widgets_values": [0.0, 0.0, 1.0, 0.0, "sine", True, "reflection"],
    })
    code, log = run(["--validate", str(_write(tmp_path, wf, "static-cam.json"))])
    assert code != 0
    assert "只支持 --dynamic 模式" in log, log


def test_camera_move_direction_zoom_and_loop():
    try:
        import torch
        if not hasattr(torch, "zeros"):
            raise ImportError("stub torch")
    except Exception:
        pytest.skip("需要真 torch 才验证仿射几何")
    mod = load_nodes()
    node = mod.APNGCameraMove()
    img = torch.zeros((1, 8, 8, 3))
    img[0, 4, 4] = 1.0
    pair = img.repeat(2, 1, 1, 1)
    for x, expect_col in ((2.0, 6), (-2.0, 2)):
        out = node.move(pair, x, 0.0, 1.0, 0.0, "linear", False, "zeros")[0]
        row = out[1, 4, :, 0]
        assert int(row.argmax()) == expect_col, (x, row.tolist())
        assert float(row.max()) > 0.99
        assert torch.allclose(out[0], img[0], atol=1e-6)
    zoomed = node.move(pair, 0.0, 0.0, 2.0, 0.0, "linear", False, "reflection")[0]
    flat = zoomed[1, :, :, 0]
    assert int(flat.argmax()) == 4 * 8 + 4
    assert float(flat.max()) > 0.25
    assert int((flat > 0.01).sum()) > 1
    rotimg = torch.zeros((2, 9, 9, 3))
    rotimg[:, 4, 7] = 1.0
    rot = node.move(rotimg, 0.0, 0.0, 1.0, 90.0, "linear", False, "zeros")[0]
    assert divmod(int(rot[1, :, :, 0].argmax()), 9) == (1, 4)
    looped = node.move(pair, 6.0, 4.0, 1.4, 20.0, "sine", True, "reflection")[0]
    assert torch.allclose(looped[0], looped[-1], atol=1e-5)
