# -*- coding: utf-8 -*-
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SYNC = ROOT / "scripts" / "sync_workflows.py"


def run(args):
    r = subprocess.run([sys.executable, str(SYNC)] + args,
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def test_mirror_is_in_sync(tmp_path):
    code, log = run(["--dest-root", str(tmp_path / "assets")])
    assert code == 0, log
    assert (tmp_path / "assets" / "workflows" / "workflow-moss.json").is_file()
    assert (tmp_path / "assets" / "presets" / "motion-presets.json").is_file()
    code, log = run(["--check", "--dest-root", str(tmp_path / "assets")])
    assert code == 0, log
    assert "SAME" in log


def test_check_detects_drift(tmp_path):
    code, log = run(["--dest-root", str(tmp_path / "assets")])
    assert code == 0, log
    target = tmp_path / "assets" / "workflows" / "workflow-moss.json"
    target.write_text("{}\n", encoding="utf-8")
    code, log = run(["--check", "--dest-root", str(tmp_path / "assets")])
    assert code == 1, log
    assert "DRIFT" in log
