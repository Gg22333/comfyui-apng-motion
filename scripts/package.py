# -*- coding: utf-8 -*-
"""package.py — 打成可分发的 zip（确定性时间戳 + SHA256）。

用法:
    python package.py
    python package.py --with-profiles
    python package.py --out D:\\dist
产物: dist/comfyui-apng-motion-<version>.zip 与同名 .sha256
"""
import argparse
import hashlib
import json
import os
import sys
import zipfile

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SKILL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKIP_DIRS = {"__pycache__", "dist", ".git", "profiles", ".github", "tests"}
FIXED = (2020, 1, 1, 0, 0, 0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(SKILL, "dist"))
    ap.add_argument("--with-profiles", action="store_true")
    a = ap.parse_args()
    man = json.load(open(os.path.join(SKILL, "skill.json"), encoding="utf-8-sig"))
    name = "comfyui-apng-motion-%s" % man["version"]
    os.makedirs(a.out, exist_ok=True)
    zpath = os.path.join(a.out, name + ".zip")

    files = []
    for root, dirs, fs in os.walk(SKILL):
        dirs[:] = sorted(x for x in dirs if x not in SKIP_DIRS or (x == "profiles" and a.with_profiles))
        rel = os.path.relpath(root, SKILL)
        if rel.startswith("dist"):
            continue
        for f in sorted(fs):
            if f.endswith((".bak", ".pyc", ".tmp")) or ".bak-" in f:
                continue
            if rel == "profiles" and not a.with_profiles:
                continue
            if rel.replace("\\", "/") == "docs/assets":
                continue
            files.append(os.path.relpath(os.path.join(root, f), SKILL))
    files.sort()

    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for rel in files:
            zi = zipfile.ZipInfo("comfyui-apng-motion/" + rel.replace("\\", "/"), FIXED)
            zi.compress_type = zipfile.ZIP_DEFLATED
            zi.external_attr = 0o644 << 16
            with open(os.path.join(SKILL, rel), "rb") as fh:
                z.writestr(zi, fh.read())

    h = hashlib.sha256()
    with open(zpath, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    digest = h.hexdigest()
    with open(zpath + ".sha256", "w", encoding="utf-8", newline="\n") as fh:
        fh.write("%s  %s\n" % (digest, os.path.basename(zpath)))

    print("zip   :", zpath)
    print("files :", len(files))
    print("size  : %.1f KB" % (os.path.getsize(zpath) / 1024.0))
    print("sha256:", digest)
    for f in files:
        print("  ", f)
    return 0


if __name__ == "__main__":
    sys.exit(main())


