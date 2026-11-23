import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EMIT = ROOT / "scripts" / "emit_workflow.py"


def run(args):
    r = subprocess.run([sys.executable, str(EMIT)] + args,
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def test_three_beats(tmp_path):
    out = tmp_path / "b3.json"
    code, log = run(["--base", str(ROOT / "assets" / "workflow-sdxl.json"),
                     "--story", str(ROOT / "assets" / "story.example.json"),
                     "--out", str(out)])
    assert code == 0, log
    assert "VALIDATE OK" in log
    wf = json.loads(out.read_text(encoding="utf-8"))
    assert len([n for n in wf["nodes"] if n["type"] == "KSampler"]) == 3
    assert len(wf["nodes"]) == 61


def test_four_beats(tmp_path):
    out = tmp_path / "b4.json"
    code, log = run(["--base", str(ROOT / "assets" / "workflow-sdxl.json"),
                     "--story", str(ROOT / "assets" / "story.4beat.json"),
                     "--out", str(out)])
    assert code == 0, log
    wf = json.loads(out.read_text(encoding="utf-8"))
    assert len(wf["nodes"]) == 63


def test_five_beats_cli(tmp_path):
    out = tmp_path / "b5.json"
    code, log = run(["--base", str(ROOT / "assets" / "workflow-sdxl.json"),
                     "--beats", "5", "--segs", "5,6,5,4,4",
                     "--lock", "masterpiece, 1girl", "--style", "anime",
                     "--actions", "a|b|c|d|e",
                     "--out", str(out)])
    assert code == 0, log
    wf = json.loads(out.read_text(encoding="utf-8"))
    assert len(wf["nodes"]) == 65


def test_shipped_assets_validate():
    for name in ("workflow-sdxl.json", "workflow-moss.json",
                 "workflow-sdxl-4beat.json", "workflow-moss-4beat.json"):
        code, log = run(["--validate", str(ROOT / "assets" / name)])
        assert code == 0, name + log


def test_rejects_bad_seg_sum(tmp_path):
    code, log = run(["--base", str(ROOT / "assets" / "workflow-sdxl.json"),
                     "--beats", "4", "--segs", "8,8,8",
                     "--lock", "x", "--actions", "a|b|c|d",
                     "--out", str(tmp_path / "x.json")])
    assert code != 0
    assert ("24" in log) or ("段数" in log)

