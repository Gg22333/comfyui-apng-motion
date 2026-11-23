# -*- coding: utf-8 -*-
"""install.py — 把 skill 装到 Codex / magpie 的 skills 目录。

用法:
    python install.py                 # 装到 skill.json 里列的、且父目录存在的目标
    python install.py --dest D:\\skills\\comfyui-apng-motion
    python install.py --dry-run
    python install.py --with-profiles   # 连本机 profiles 一起拷（默认不拷）

覆盖前会把旧 SKILL.md 备份成 SKILL.md.bak-YYYYmmdd-HHMMSS。
"""
import argparse
import datetime
import json
import os
import shutil
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SKILL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKIP_DIRS = {"__pycache__", "dist", ".git"}
SKIP_SUFFIX = (".bak", ".pyc", ".tmp")


def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dest", action="append", default=[])
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--with-profiles", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--check", action="store_true", help="只比对源目录与已安装目录的哈希，不写文件")
    ap.add_argument("--link", action="store_true",
                    help="把目标改成指向源目录的 junction/软链（物理只有一份；依赖源目录路径）")
    return ap.parse_args()


def walk_files(src, with_profiles):
    out = []
    for root, dirs, files in os.walk(src):
        dirs[:] = [x for x in dirs if x not in SKIP_DIRS]
        rel = os.path.relpath(root, src)
        if rel == "profiles" and not with_profiles:
            dirs[:] = []
            continue
        for f in files:
            if f.endswith(SKIP_SUFFIX) or ".bak-" in f:
                continue
            out.append(os.path.relpath(os.path.join(root, f), src))
    return out


def check_install(src, dst, with_profiles):
    import hashlib
    missing, diff = [], []
    files = walk_files(src, with_profiles)
    for rel in files:
        p = os.path.join(dst, rel)
        if not os.path.isfile(p):
            missing.append(rel)
            continue
        a = hashlib.sha256(open(os.path.join(src, rel), "rb").read()).hexdigest()
        b = hashlib.sha256(open(p, "rb").read()).hexdigest()
        if a != b:
            diff.append(rel)
    extra = []
    for root, dirs, fs in os.walk(dst):
        dirs[:] = [x for x in dirs if x not in SKIP_DIRS]
        rel = os.path.relpath(root, dst)
        if rel == "profiles" and not with_profiles:
            dirs[:] = []
            continue
        for f in fs:
            if f.endswith(SKIP_SUFFIX) or ".bak-" in f:
                continue
            r = os.path.relpath(os.path.join(root, f), dst)
            if r not in files:
                extra.append(r)
    return files, missing, diff, extra


def copy_tree(src, dst, with_profiles, dry):
    n = 0
    for root, dirs, files in os.walk(src):
        dirs[:] = [x for x in dirs if x not in SKIP_DIRS]
        rel = os.path.relpath(root, src)
        if rel == "profiles" and not with_profiles:
            dirs[:] = []
            continue
        out = os.path.join(dst, rel) if rel != "." else dst
        if not dry:
            os.makedirs(out, exist_ok=True)
        for f in files:
            if f.endswith(SKIP_SUFFIX) or ".bak-" in f:
                continue
            if rel == "profiles" and not with_profiles:
                continue
            s, t = os.path.join(root, f), os.path.join(out, f)
            if not dry:
                shutil.copy2(s, t)
            n += 1
    return n


def main():
    a = parse_args()
    man = json.load(open(os.path.join(SKILL, "skill.json"), encoding="utf-8-sig"))
    targets = []
    if a.dest:
        targets = list(a.dest)
    else:
        for t in man.get("targets", []):
            t = os.path.expanduser(t)
            if a.all or os.path.isdir(t) or os.path.isdir(os.path.dirname(t)):
                targets.append(t)
    if not targets:
        print("没有可用目标。用 --dest 指定，或先建好 ~/.codex/skills")
        return 2
    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    fails = 0
    for t in targets:
        t = os.path.abspath(os.path.expanduser(t))
        if a.check:
            files, missing, diff, extra = check_install(SKILL, t, a.with_profiles)
            state = "SAME" if not (missing or diff or extra) else "DRIFT"
            print("[%-5s] %-6s %s" % (state, "%d files" % len(files), t))
            for x in missing:
                print("   MISS", x)
            for x in diff:
                print("   DIFF", x)
            for x in extra:
                print("   EXTRA", x)
            fails += 0 if state == "SAME" else 1
            continue
        print(("[dry] " if a.dry_run else "install ") + t)
        if a.link and not a.dry_run:
            src_abs = os.path.abspath(SKILL)
            if os.path.isdir(t):
                bak = t + ".bak-" + ts
                os.rename(t, bak)
                print("  moved old ->", bak)
            os.makedirs(os.path.dirname(t), exist_ok=True)
            if os.name == "nt":
                import subprocess
                r = subprocess.run(["cmd", "/c", "mklink", "/J", t, src_abs],
                                   capture_output=True, text=True)
                if r.returncode != 0:
                    print("  link failed:", (r.stdout or r.stderr).strip())
                    fails += 1
                    continue
            else:
                os.symlink(src_abs, t, target_is_directory=True)
            print("  linked ->", src_abs)
            continue
        if os.path.isfile(os.path.join(t, "SKILL.md")) and not a.dry_run:
            bak = os.path.join(t, "SKILL.md.bak-" + ts)
            shutil.copy2(os.path.join(t, "SKILL.md"), bak)
            print("  backup:", bak)
        n = copy_tree(SKILL, t, a.with_profiles, a.dry_run)
        print("  files:", n, "| profiles:", "yes" if a.with_profiles else "no")
    if a.check:
        print("\n漂移目录数:", fails)
        return 1 if fails else 0
    print("\ndone. 卸载 = 删掉目标目录。")
    return 0


if __name__ == "__main__":
    sys.exit(main())


