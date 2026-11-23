# -*- coding: utf-8 -*-
"""detect_env.py — 扫描本机的 ComfyUI 安装，生成 profiles/*.json。

换机器第一步就跑它。不写死盘符：扫所有盘符一层目录 + 已知常见位置，
找到含 main.py 的 ComfyUI 根目录就登记。

用法:
    python detect_env.py                 # 扫描并写 profiles/
    python detect_env.py --root D:\\ComfyUI
    python detect_env.py --list          # 只看，不写文件
"""
import argparse
import glob
import json
import os
import re
import string
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import comfy_lib as L

WANT_NODES = ["comfyui-kjnodes", "ComfyUI-VideoHelperSuite"]
PORTS = list(range(8188, 8197))


def ver_of(root):
    p = os.path.join(root, "comfyui_version.py")
    try:
        s = open(p, encoding="utf-8", errors="replace").read()
        m = re.search(r'__version__\s*=\s*["\']([^"\']+)', s)
        if m:
            return m.group(1)
    except OSError:
        pass
    p = os.path.join(root, "pyproject.toml")
    try:
        s = open(p, encoding="utf-8", errors="replace").read()
        m = re.search(r'^version\s*=\s*["\']([^"\']+)', s, re.M)
        if m:
            return m.group(1)
    except OSError:
        pass
    return "未知"


def find_python(root):
    up = os.path.dirname(root)
    cands = [
        os.path.join(up, "python", "python.exe"),
        os.path.join(up, "python_embeded", "python.exe"),
        os.path.join(root, "python.exe"),
        os.path.join(up, "venv", "Scripts", "python.exe"),
        os.path.join(root, ".venv", "Scripts", "python.exe"),
        os.path.join(up, ".venv", "Scripts", "python.exe"),
        os.path.join(up, "python", "bin", "python3"),
    ]
    for c in cands:
        if os.path.isfile(c):
            return c
    return ""


def models_of(root):
    md = os.path.join(root, "models")
    out = {}
    for sub in ("checkpoints", "diffusion_models", "text_encoders", "vae", "loras",
                "controlnet", "clip_vision"):
        d = os.path.join(md, sub)
        if os.path.isdir(d):
            out[sub] = sorted(
                f for f in os.listdir(d)
                if f.lower().endswith((".safetensors", ".ckpt", ".pt", ".pth", ".gguf"))
            )
    return out


def probe_ports():
    found = {}
    for p in PORTS:
        prof = {"host": "127.0.0.1", "port": p}
        try:
            st = L.get_stats(L.base_url(prof), timeout=0.8)
        except Exception:
            continue
        argv = ((st.get("system") or {}).get("argv") or [])
        found[p] = argv[0] if argv else ""
    return found


def scan_roots(extra):
    roots = []
    if os.environ.get("COMFYUI_PATH"):
        roots.append(os.environ["COMFYUI_PATH"])
    roots += extra
    for letter in string.ascii_uppercase:
        drive = letter + ":\\"
        if not os.path.isdir(drive):
            continue
        try:
            entries = list(os.scandir(drive))
        except OSError:
            continue
        for e in entries:
            if not e.is_dir(follow_symlinks=False):
                continue
            low = e.name.lower()
            if low in ("windows", "program files", "program files (x86)", "$recycle.bin", "system volume information"):
                continue
            if not any(k in low for k in ("comfy", "绘世", "aki", "stable", "sd-webui")):
                continue
            for cand in (os.path.join(e.path, "ComfyUI"), e.path):
                if os.path.isfile(os.path.join(cand, "main.py")):
                    roots.append(cand)
    home = os.path.expanduser("~")
    for cand in (os.path.join(home, "ComfyUI"), os.path.join(home, "Documents", "ComfyUI")):
        if os.path.isfile(os.path.join(cand, "main.py")):
            roots.append(cand)
    seen, uniq = set(), []
    for r in roots:
        r = os.path.abspath(r)
        if r.lower() not in seen and os.path.isfile(os.path.join(r, "main.py")):
            seen.add(r.lower())
            uniq.append(r)
    return uniq


def guess_stack(models):
    dm = [f.lower() for f in models.get("diffusion_models", [])]
    ck = [f.lower() for f in models.get("checkpoints", [])]
    if any("moss" in f for f in dm) or any("moss" in f for f in models.get("text_encoders", [])):
        return "moss"
    if ck:
        return "sdxl"
    if dm:
        return "dit-other"
    return "unknown"


def build_profile(root, port_map):
    up = os.path.basename(os.path.dirname(root)).lower()
    name = "xl" if "xl" in up else ("dit" if "dit" in up else re.sub(r"[^a-z0-9]+", "-", up)[:24] or "comfy")
    models = models_of(root)
    nodes = []
    nd = os.path.join(root, "custom_nodes")
    if os.path.isdir(nd):
        nodes = sorted(n for n in os.listdir(nd) if os.path.isdir(os.path.join(nd, n)))
    port = 0
    for p, argv in port_map.items():
        if root.lower().replace("/", "\\") in str(argv).lower().replace("/", "\\"):
            port = p
            break
    if not port:
        port = 8188 if name == "xl" else (8189 if name == "dit" else 8188)
    wfs = sorted(glob.glob(os.path.join(root, "user", "default", "workflows", "*.json")))
    wf = ""
    for f in wfs:
        if "apng" in os.path.basename(f).lower():
            wf = f
            break
    return {
        "name": name,
        "comfy_root": root,
        "python": find_python(root),
        "host": "127.0.0.1",
        "port": port,
        "stack": guess_stack(models),
        "version": ver_of(root),
        "models": {k: v[:12] for k, v in models.items()},
        "custom_nodes_present": {n: n in nodes for n in WANT_NODES},
        "workflow": wf,
        "fps": 10,
        "prefix_root": "APNG/final",
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", action="append", default=[])
    ap.add_argument("--out", default="")
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args()
    skill = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    outdir = a.out or os.path.join(skill, "profiles")
    roots = scan_roots(a.root)
    if not roots:
        print("没找到 ComfyUI。用 --root <含 main.py 的目录> 指定。")
        return 2
    pm = probe_ports()
    rows, used = [], set()
    for r in roots:
        prof = build_profile(r, pm)
        base = prof["name"]
        i = 2
        while prof["name"] in used:
            prof["name"] = "%s%d" % (base, i)
            i += 1
        used.add(prof["name"])
        rows.append(prof)
        if not a.list:
            L.save_json(os.path.join(outdir, prof["name"] + ".json"), prof)
    print("%-6s %-8s %-6s %-6s %-9s %s" % ("name", "port", "py", "probe", "stack", "root"))
    for p in rows:
        print("%-6s %-8s %-6s %-6s %-9s %s" % (
            p["name"], p["port"],
            "ok" if p["python"] else "-",
            "live" if p["port"] in pm else "off",
            p["stack"], p["comfy_root"]))
    if not a.list:
        print("\nprofiles ->", outdir)
    return 0


if __name__ == "__main__":
    sys.exit(main())

