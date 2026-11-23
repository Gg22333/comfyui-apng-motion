# -*- coding: utf-8 -*-
"""sync_workflows.py — 把 workflows/ 与 assets/ 的 JSON 同步到 docs/assets/ 下，供网页下载。

源（要维护的）：
    workflows/workflow-*.json   ComfyUI 工作流，可直接拖进 ComfyUI
    assets/*.json               剧情卡、动作库、节点定义

目标（生成的，进 .gitignore）：
    docs/assets/workflows/*.json
    docs/assets/presets/*.json

用法:
    python scripts/sync_workflows.py
    python scripts/sync_workflows.py --check      # 只检查有没有漂移，CI 用
    python scripts/sync_workflows.py --dest-root docs/assets
"""
import argparse
import hashlib
import os
import shutil
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAIRS = [("workflows", "workflows"), ("assets", "presets")]


def digest(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def collect(src_dir):
    if not os.path.isdir(src_dir):
        return []
    return sorted(n for n in os.listdir(src_dir) if n.endswith(".json"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="只检查，不写文件；有漂移返回 1")
    ap.add_argument("--dest-root", default=os.path.join("docs", "assets"))
    ap.add_argument("--root", default=ROOT)
    a = ap.parse_args()

    dest_root = a.dest_root if os.path.isabs(a.dest_root) else os.path.join(a.root, a.dest_root)
    total, stale, extra = 0, [], []
    for src_name, dest_name in PAIRS:
        src_dir = os.path.join(a.root, src_name)
        dst_dir = os.path.join(dest_root, dest_name)
        names = collect(src_dir)
        # 目标目录里已经不存在于源目录的旧文件：删掉，否则迁移后残留会一直被当成 drift
        if os.path.isdir(dst_dir):
            for old in collect(dst_dir):
                if old not in names:
                    extra.append(old)
                    if not a.check:
                        try:
                            os.remove(os.path.join(dst_dir, old))
                        except OSError:
                            pass
        for n in names:
            total += 1
            src = os.path.join(src_dir, n)
            dst = os.path.join(dst_dir, n)
            if os.path.isfile(dst) and digest(src) == digest(dst):
                continue
            try:
                stale.append(os.path.relpath(dst, a.root))
            except ValueError:
                stale.append(dst)
            if not a.check:
                os.makedirs(dst_dir, exist_ok=True)
                shutil.copyfile(src, dst)

    if a.check:
        if stale or extra:
            print("DRIFT %d/%d 个文件没同步，%d 个多余：" % (len(stale), total, len(extra)))
            for s in stale:
                print("  -", s)
            for s in extra:
                print("  x", s)
            print("跑 python scripts/sync_workflows.py 重新生成")
            return 1
        print("SAME  %d 个文件已同步" % total)
        return 0

    try:
        where = os.path.relpath(dest_root, a.root)
    except ValueError:
        where = dest_root
    print("synced %d 个文件 -> %s" % (len(stale), where))
    if extra:
        print("pruned %d 个过期文件" % len(extra))
    for s in stale:
        print("  +", s)
    return 0


if __name__ == "__main__":
    sys.exit(main())
