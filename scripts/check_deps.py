# -*- coding: utf-8 -*-
"""check_deps.py — 依赖自检（不联网、不出图）。

检查：Python 版本、Pillow、curl（可选）、profiles 里记录的 ComfyUI 版本与插件。
用法:
    python check_deps.py
    python check_deps.py --json
退出码: 0 核心依赖齐；1 缺核心依赖（Python / Pillow）。
"""
import argparse
import glob
import json
import os
import platform
import shutil
import subprocess
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

MIN_PY = (3, 9)
MIN_PIL = (9, 0)
SKILL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def parse_ver(s):
    out = []
    for part in str(s).replace("-", ".").split("."):
        num = "".join(ch for ch in part if ch.isdigit())
        if num == "":
            break
        out.append(int(num))
    return tuple(out) or (0,)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    rows, bad = [], 0

    py = sys.version_info[:3]
    ok = py[:2] >= MIN_PY
    rows.append(("OK" if ok else "FAIL", "python", "%d.%d.%d (>=%d.%d)" % (py + MIN_PY)))
    bad += 0 if ok else 1

    try:
        import PIL
        from PIL import Image  # noqa: F401
        pv = parse_ver(getattr(PIL, "__version__", "0"))
        ok = pv >= MIN_PIL
        rows.append(("OK" if ok else "FAIL", "Pillow", "%s (>=9.0，check_anim 需要)" % getattr(PIL, "__version__", "?")))
        bad += 0 if ok else 1
    except Exception as e:
        rows.append(("FAIL", "Pillow", "当前解释器缺失：%s" % e))
        bad += 1

    curl = shutil.which("curl") or shutil.which("curl.exe")
    rows.append(("OK" if curl else "WARN", "curl", curl or "未找到（只影响 --run 的兜底通道）"))

    profs = sorted(glob.glob(os.path.join(SKILL, "profiles", "*.json")))
    if not profs:
        rows.append(("WARN", "profiles", "没有 profile，先跑 scripts/detect_env.py"))
    for p in profs:
        try:
            pr = json.load(open(p, encoding="utf-8-sig"))
        except Exception as e:
            rows.append(("FAIL", "profile", "%s 读不了：%s" % (os.path.basename(p), e)))
            bad += 1
            continue
        pyexe = pr.get("python") or ""
        pil = ""
        if pyexe and os.path.isfile(pyexe):
            try:
                r = subprocess.run([pyexe, "-c", "import PIL;print(PIL.__version__)"],
                                   capture_output=True, text=True, timeout=20)
                pil = (r.stdout or "").strip() if r.returncode == 0 else ""
            except Exception:
                pil = ""
        if pil:
            rows.append(("OK", "pillow@" + pr.get("name", "?"), pil + "  ← check_anim 用这个解释器跑"))
        elif pyexe:
            rows.append(("WARN", "pillow@" + pr.get("name", "?"), "该环境没装 Pillow：%s -m pip install Pillow" % pyexe))
        cn = pr.get("custom_nodes_present") or {}
        miss = [k for k, v in cn.items() if not v]
        lv = "OK" if not miss else "WARN"
        rows.append((lv, "profile:" + pr.get("name", "?"),
                     "comfy %s / %s / %s" % (pr.get("version", "?"), pr.get("stack", "?"),
                                             "插件齐" if not miss else "缺 " + ",".join(miss))))

    if any(r[0] == "OK" and r[1].startswith("pillow@") for r in rows):
        for i, (l, n, d) in enumerate(rows):
            if l == "FAIL" and n == "Pillow":
                rows[i] = ("WARN", n, d + "（profiles 里的解释器有 Pillow，直接用它跑）")
                bad -= 1

    if a.json:
        print(json.dumps([{"level": l, "name": n, "detail": d} for l, n, d in rows],
                         ensure_ascii=False, indent=2))
    else:
        print("platform:", platform.platform())
        for l, n, d in rows:
            print("[%-4s] %-18s %s" % (l, n, d))
        print("\n安装缺失依赖:")
        print("  python -m pip install -r requirements.txt")
        print("  或直接用 ComfyUI 自带解释器跑 check_anim（profiles 里那条 OK 的路径）")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())


