# -*- coding: utf-8 -*-
"""check_output.py — 检查 ComfyUI 成品落盘结构是否符合"只存成品、三格式同源"。

用法:
    python check_output.py --profile profiles/xl.json
    python check_output.py --root "D:\\ComfyUI\\ComfyUI\\output" --prefix APNG/final
    python check_output.py --profile profiles/xl.json --json
    python check_output.py --profile profiles/xl.json --fix      # 把游离文件移进 archive/stray-*

检查项:
    FAIL  output/APNG 根目录有文件（prefix 被旧值覆盖 / 前端没刷新）
    FAIL  某一组成品缺 APNG / WebP / GIF 中的一路
    WARN  output 根目录有 anim* 残留（历史 SaveImage 或旧 prefix）
    WARN  final 目录里有不符合 anim*_00001_ 命名的散件
    INFO  gif 目录里的同名 .png 是 VHS 首帧预览，可删
退出码: 0 无 FAIL；1 有 FAIL；2 路径不存在。
"""
import argparse
import json
import os
import re
import shutil
import sys
import time

STEM_RE = re.compile(r"^(?P<stem>.+?)_(?P<num>\d+)_?\.(?P<ext>png|webp|gif)$", re.I)
ROOT_JUNK_RE = re.compile(r"^(anim24|anim_base|anim24[-_])", re.I)


def _files(d):
    if not os.path.isdir(d):
        return []
    return sorted(os.path.join(d, f) for f in os.listdir(d) if os.path.isfile(os.path.join(d, f)))


def scan(output_root, prefix="APNG/final"):
    """返回 (rows, stems)。row = (level, kind, path, note)。"""
    rows = []
    groups = {}
    apng = os.path.join(output_root, "APNG")
    if not os.path.isdir(apng):
        rows.append(("FAIL", "apng_dir", apng, "找不到 APNG 目录，确认 output 根路径"))
    else:
        # 1. APNG 根目录不该有文件
        for f in _files(apng):
            rows.append(("FAIL", "stray_root", f,
                         "成品不该落在 APNG 根目录：prefix 被旧值覆盖或前端没刷新"))

        # 2. 三格式目录
        final = os.path.join(apng, "final")
        dirs = {k: os.path.join(final, k) for k in ("apng", "webp", "gif")}
        for k, d in dirs.items():
            if not os.path.isdir(d):
                rows.append(("WARN", "missing_dir", d, "还没出过 %s 成品" % k))

        # 3. 按 stem+序号 归组
        for kind, d in dirs.items():
            for f in _files(d):
                m = STEM_RE.match(os.path.basename(f))
                if not m:
                    rows.append(("WARN", "odd_name", f, "文件名不符合 <name>_<5位>.<ext>（手动改名或固定 stem）"))
                    continue
                key = (m.group("stem"), m.group("num"))
                groups.setdefault(key, {})[kind] = f

        for key, g in sorted(groups.items()):
            missing = [k for k in ("apng", "webp", "gif") if k not in g]
            if missing:
                rows.append(("FAIL", "incomplete", os.path.dirname(next(iter(g.values()))),
                             "%s_%s 缺 %s" % (key[0], key[1], "/".join(missing))))
            # gif 同名 png = VHS 首帧预览
            side = os.path.join(dirs["gif"], "%s_%s.png" % key)
            if os.path.isfile(side):
                rows.append(("INFO", "vhs_sidecar", side, "VHS 首帧预览，可删；不是第四份成品"))

        # 5. archive 只报数量
        arch = os.path.join(apng, "archive")
        n = sum(len(fs) for _, _, fs in os.walk(arch)) if os.path.isdir(arch) else 0
        rows.append(("INFO", "archive", arch, "%d 个留档文件（不参与成品判定）" % n))

    # 4. output 根目录的 anim* 残留
    for f in _files(output_root):
        if ROOT_JUNK_RE.match(os.path.basename(f)):
            rows.append(("WARN", "outside_apng", f, "落在 output 根目录，应在 output/APNG/final/*"))

    return rows, groups


def fix(output_root, rows):
    """把 stray_root / outside_apng 移进 APNG/archive/stray-<时间>/，返回移动清单。"""
    stamp = time.strftime("%Y%m%d-%H%M%S")
    dest = os.path.join(output_root, "APNG", "archive", "stray-" + stamp)
    moved = []
    for level, kind, path, _ in rows:
        if kind not in ("stray_root", "outside_apng"):
            continue
        sub = "apng-root" if kind == "stray_root" else "output-root"
        d = os.path.join(dest, sub)
        os.makedirs(d, exist_ok=True)
        target = os.path.join(d, os.path.basename(path))
        if os.path.exists(target):
            base, ext = os.path.splitext(os.path.basename(path))
            target = os.path.join(d, "%s-%s%s" % (base, stamp, ext))
        shutil.move(path, target)
        moved.append((path, target))
    return dest, moved


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="", help="ComfyUI 的 output 目录")
    ap.add_argument("--profile", default="", help="从 profile 读 comfy_root")
    ap.add_argument("--prefix", default="APNG/final", help="只用于提示，不影响扫描")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--fix", action="store_true", help="把游离文件移进 archive/stray-*")
    a = ap.parse_args()

    root = a.root
    if not root and a.profile:
        with open(a.profile, encoding="utf-8") as f:
            prof = json.load(f)
        root = os.path.join(prof.get("comfy_root", ""), "output")
    if not root:
        skill = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        cands = []
        pdir = os.path.join(skill, "profiles")
        if os.path.isdir(pdir):
            for fn in sorted(os.listdir(pdir)):
                if fn.endswith(".json"):
                    with open(os.path.join(pdir, fn), encoding="utf-8") as f:
                        cands.append(json.load(f).get("comfy_root", ""))
        root = os.path.join(cands[0], "output") if cands and cands[0] else ""
    if not root or not os.path.isdir(root):
        print("找不到 output 目录，用 --profile 或 --root 指定")
        return 2

    rows, groups = scan(root, a.prefix)
    moved = []
    if a.fix:
        dest, moved = fix(root, rows)
        rows, groups = scan(root, a.prefix)

    if a.json:
        print(json.dumps({
            "root": root,
            "groups": [{"stem": k[0], "num": k[1], "formats": sorted(v)} for k, v in sorted(groups.items())],
            "rows": [{"level": l, "kind": k, "path": p, "note": n} for l, k, p, n in rows],
            "moved": moved,
        }, ensure_ascii=False, indent=2))
    else:
        print("output:", root)
        for lv, kind, path, note in rows:
            print("[%-4s] %-13s %s\n         %s" % (lv, kind, path, note))
        if moved:
            print("\n已移动 %d 个游离文件 -> %s" % (len(moved), os.path.dirname(moved[0][1])))
            for src, dst in moved:
                print("  %s -> %s" % (src, dst))
    bad = sum(1 for r in rows if r[0] == "FAIL")
    print("\nFAIL 总数: %d（成品组 %d）" % (bad, len(groups)))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
