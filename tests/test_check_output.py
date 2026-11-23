# -*- coding: utf-8 -*-
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))

import check_output as C


def touch(path, data=b"x"):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)


def levels(rows, kind):
    return [r for r in rows if r[1] == kind]


def test_clean_tree(tmp_path):
    root = str(tmp_path)
    for fmt, ext in (("apng", ".png"), ("webp", ".webp"), ("gif", ".gif")):
        touch(os.path.join(root, "APNG", "final", fmt, "anim24_00001" + ("_" if fmt != "gif" else "") + ext))
    touch(os.path.join(root, "APNG", "final", "gif", "anim24_00001.png"))
    rows, groups = C.scan(root)
    assert not levels(rows, "stray_root")
    assert not levels(rows, "incomplete")
    assert ("anim24", "00001") in groups
    assert len(levels(rows, "vhs_sidecar")) == 1


def test_stray_root_and_fix(tmp_path):
    root = str(tmp_path)
    stray = os.path.join(root, "APNG", "anim24_00001_.png")
    touch(stray)
    rows, _ = C.scan(root)
    assert len(levels(rows, "stray_root")) == 1
    dest, moved = C.fix(root, rows)
    assert moved and not os.path.exists(stray)
    assert os.path.isfile(moved[0][1])
    rows2, _ = C.scan(root)
    assert not levels(rows2, "stray_root")


def test_incomplete_trio(tmp_path):
    root = str(tmp_path)
    touch(os.path.join(root, "APNG", "final", "apng", "anim24_00001_.png"))
    rows, _ = C.scan(root)
    inc = levels(rows, "incomplete")
    assert inc and "webp" in inc[0][3] and "gif" in inc[0][3]


def test_outside_output_root(tmp_path):
    root = str(tmp_path)
    touch(os.path.join(root, "anim_base_00001_.png"))
    rows, _ = C.scan(root)
    assert len(levels(rows, "outside_apng")) == 1
