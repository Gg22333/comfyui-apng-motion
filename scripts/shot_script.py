# -*- coding: utf-8 -*-
"""shot_script.py — 一行一拍的分镜脚本。

    # 注释
    0-7   | 一位红发少女站在窗边
    8-15  | pan_left slow | 微微睁眼
    16-23 |                 | 张嘴笑

字段：
    帧范围 | [镜头] | 提示词
- 帧范围是闭区间，必须从 0 开始且首尾相接；
- 镜头可选，写法是「预设名 + 可选 slow/fast + 可选 small/large」；
- 全文件只允许一种镜头（我们的图里只有一个镜头节点），出现冲突直接报错。

命名参考了 Difforum 的脚本思路（MIT），解析器与容错是本项目自己的实现。
"""

SPEED = {"very_slow": 0.4, "slow": 0.6, "slowly": 0.6, "medium": 1.0,
         "fast": 1.5, "quick": 1.5, "very_fast": 2.0}
AMP = {"subtle": 0.4, "small": 0.5, "slight": 0.5, "gentle": 0.6,
       "big": 1.4, "large": 1.4, "huge": 1.8}


def _parse_camera(text):
    """'pan_left slow small' -> ('pan_left', 0.6, 0.5)"""
    words = [w for w in str(text).replace(",", " ").split() if w]
    if not words:
        return None
    name = words[0].lower()
    speed, amp = 1.0, 1.0
    for w in words[1:]:
        key = w.lower()
        if key in SPEED:
            speed = SPEED[key]
        elif key in AMP:
            amp = AMP[key]
        else:
            raise ValueError("镜头 %r 后面无法识别的修饰词 %r" % (name, w))
    return name, speed, amp


def parse_shot(text):
    segs, actions, cams = [], [], []
    expect = 0
    for no, raw in enumerate(str(text).splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) < 2:
            raise ValueError("第 %d 行至少要有「帧范围 | 提示词」" % no)
        rng = parts[0]
        if "-" not in rng:
            raise ValueError("第 %d 行帧范围要写成 0-7，收到 %r" % (no, rng))
        a, b = rng.split("-", 1)
        try:
            start, end = int(a.strip()), int(b.strip())
        except ValueError:
            raise ValueError("第 %d 行帧范围不是整数：%r" % (no, rng))
        if end < start:
            raise ValueError("第 %d 行终点 %d 小于起点 %d" % (no, end, start))
        if start != expect:
            raise ValueError("第 %d 行从 %d 开始，上一行到 %d；必须首尾相接且从 0 开始"
                             % (no, start, expect - 1))
        if len(parts) == 2:
            cam_text, prompt = "", parts[1]
        elif len(parts) == 3:
            cam_text, prompt = parts[1], parts[2]
        else:
            raise ValueError("第 %d 行字段太多：最多「范围 | 镜头 | 提示词」" % no)
        if not prompt:
            raise ValueError("第 %d 行提示词为空" % no)
        segs.append(end - start + 1)
        actions.append(prompt)
        cam = _parse_camera(cam_text) if cam_text else None
        if cam:
            cams.append((no, cam))
        expect = end + 1

    if not segs:
        raise ValueError("脚本里没有有效行")
    if len(segs) < 2:
        raise ValueError("至少两拍（当前 %d 拍）" % len(segs))

    camera, speed, amp = "", 1.0, 1.0
    if cams:
        first = cams[0][1]
        for no, cam in cams[1:]:
            if cam[0] != first[0]:
                raise ValueError("第 %d 行的镜头 %r 与第 %d 行的 %r 冲突；一张图只能一个镜头"
                                 % (no, cam[0], cams[0][0], first[0]))
        camera, speed, amp = first
    return {"segs": segs, "actions": actions, "camera": camera, "speed": speed, "amp": amp}
