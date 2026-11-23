# -*- coding: utf-8 -*-
"""install_nodes.py — 把 comfyui_nodes 装进 ComfyUI 的 custom_nodes。

用法:
    python install_nodes.py                       # 给 profiles/*.json 里 comfy_root 存在的每台装
    python install_nodes.py --profile xl          # 只装指定 profile（名字或路径都行）
    python install_nodes.py --profile ..\\profiles\\dit.json
    python install_nodes.py --check               # 只比对已安装节点与源目录哈希
    python install_nodes.py --dry-run

安装目标: <comfy_root>/custom_nodes/apng_motion_nodes/
装完要重启 ComfyUI 才会注册 APNG Motion 三个节点。
"""
import argparse
import hashlib
import json
import os
import shutil
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SKILL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(SKILL, "comfyui_nodes")
DEST_NAME = "apng_motion_nodes"
SKIP_DIRS = {"__pycache__", ".pytest_cache", ".ruff_cache"}
SKIP_SUFFIX = (".pyc", ".pyo", ".tmp")


def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", action="append", default=[],
                    help="profile 名（xl / dit）或 profiles/*.json 的路径，可重复")
    ap.add_argument("--all", action="store_true", help="不过滤 comfy_root 是否存在")
    ap.add_argument("--check", action="store_true", help="只比对哈希，不写文件")
    ap.add_argument("--dry-run", action="store_true")
    return ap.parse_args()


def profile_files(selected, want_all):
    pdir = os.path.join(SKILL, "profiles")
    if selected:
        out = []
        for s in selected:
            p = s if os.path.isfile(s) else os.path.join(pdir, s if s.endswith(".json") else s + ".json")
            if not os.path.isfile(p):
                raise SystemExit("找不到 profile: %s" % s)
            out.append(os.path.abspath(p))
        return out
    if not os.path.isdir(pdir):
        return []
    out = []
    for name in sorted(os.listdir(pdir)):
        if not name.endswith(".json"):
            continue
        p = os.path.join(pdir, name)
        try:
            with open(p, encoding="utf-8-sig") as f:
                root = (json.load(f).get("comfy_root") or "").strip()
        except Exception:
            continue
        if root and (want_all or os.path.isdir(root)):
            out.append(p)
    return out


def src_files():
    out = []
    for root, dirs, files in os.walk(SRC):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for f in files:
            if f.endswith(SKIP_SUFFIX) or ".bak-" in f:
                continue
            out.append(os.path.relpath(os.path.join(root, f), SRC))
    return sorted(out)


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def check(dst):
    files = src_files()
    missing, diff = [], []
    for rel in files:
        p = os.path.join(dst, rel)
        if not os.path.isfile(p):
            missing.append(rel)
        elif sha(os.path.join(SRC, rel)) != sha(p):
            diff.append(rel)
    return files, missing, diff


def copy_tree(dst, dry):
    n = 0
    for rel in src_files():
        s, t = os.path.join(SRC, rel), os.path.join(dst, rel)
        if not dry:
            os.makedirs(os.path.dirname(t), exist_ok=True)
            shutil.copy2(s, t)
        n += 1
    return n


def main():
    a = parse_args()
    if not os.path.isdir(SRC):
        print("源目录不存在:", SRC)
        return 2
    profiles = profile_files(a.profile, a.all)
    if not profiles:
        print("没有可用 profile。用 --profile xl 指定，或在 profiles/*.json 里写 comfy_root")
        return 2
    fails = 0
    for p in profiles:
        try:
            with open(p, encoding="utf-8-sig") as f:
                man = json.load(f)
        except Exception as e:
            print("[SKIP ]", p, "读取失败:", e)
            fails += 1
            continue
        root = (man.get("comfy_root") or "").strip()
        if not root:
            print("[SKIP ]", p, "没有 comfy_root")
            continue
        if not os.path.isdir(root):
            print("[SKIP ]", p, "comfy_root 不存在:", root)
            fails += 1
            continue
        custom = os.path.join(root, "custom_nodes")
        if not os.path.isdir(custom):
            print("[SKIP ]", p, "没有 custom_nodes:", custom)
            fails += 1
            continue
        dst = os.path.join(custom, DEST_NAME)
        tag = os.path.splitext(os.path.basename(p))[0]
        if a.check:
            files, missing, diff = check(dst)
            state = "SAME" if not (missing or diff) else "DRIFT"
            print("[%-5s] %-6s %s" % (state, "%d files" % len(files), dst))
            for x in missing:
                print("   MISS", x)
            for x in diff:
                print("   DIFF", x)
            fails += 0 if state == "SAME" else 1
            continue
        print("%s %-6s %s" % ("[dry]  " if a.dry_run else "install", tag, dst))
        n = copy_tree(dst, a.dry_run)
        print("  files:", n)
        if not a.dry_run:
            print("  重启 ComfyUI 后生效；/object_info/APNGLatentInterpolateN 应能查到")
    if a.check:
        print("\n漂移目录数:", fails)
        return 1 if fails else 0
    print("\ndone. 卸载 = 删掉目标 apng_motion_nodes 目录。")
    return 0 if fails == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
