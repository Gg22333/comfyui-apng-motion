"""从动作库（assets/motion-presets.json）生成剧情卡。

用法：
    python scripts/make_story.py --list
    python scripts/make_story.py --preset laugh --lock "masterpiece, 1girl, silver hair" --out story.json
    python scripts/make_story.py --preset rainy-walk --lock "masterpiece, 1girl" --frames 30 --out story.json
"""

import argparse
import json
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PRESETS = ROOT / "assets" / "motion-presets.json"


def load_presets(path=DEFAULT_PRESETS):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    presets = data.get("presets") or []
    if not presets:
        raise ValueError("动作库里没有 presets：%s" % path)
    return data


def find_preset(data, preset_id):
    for p in data["presets"]:
        if p.get("id") == preset_id:
            return p
    known = ", ".join(p.get("id", "?") for p in data["presets"])
    raise KeyError("未知动作 %r；可选：%s" % (preset_id, known))


def spread(frames, beats):
    """把 frames 平均分成 beats 段，余数给前几拍。"""
    if beats <= 0:
        raise ValueError("beats 必须 > 0")
    if frames < beats:
        raise ValueError("frames=%d 小于 beats=%d：每拍至少 1 帧" % (frames, beats))
    q, r = divmod(frames, beats)
    return [q + (1 if i < r else 0) for i in range(beats)]


def build_story(data, preset_id, lock, style=None, name=None, frames=None, fps=None,
                segs=None, denoise=None, motion=None, negative=None, curve=None,
                prefix=None, seed_mode=None, use_hint=True, seed=None):
    p = find_preset(data, preset_id)
    d = data.get("defaults") or {}
    beats = int(p["beats"])
    preset_frames = int(p.get("frames") or 24)
    n_frames = int(frames or preset_frames)
    if segs:
        n_segs = [int(x) for x in segs]
    elif n_frames == preset_frames and p.get("segs"):
        n_segs = [int(x) for x in p["segs"]]
    else:
        n_segs = spread(n_frames, beats)
    if len(n_segs) != beats:
        raise ValueError("segs 段数 %d != beats %d" % (len(n_segs), beats))
    if sum(n_segs) != n_frames:
        raise ValueError("segs 之和 %d != frames %d" % (sum(n_segs), n_frames))
    actions = list(p.get("actions") or [])
    if len(actions) != beats:
        raise ValueError("动作库损坏：%s 的 actions 有 %d 条，beats=%d" % (preset_id, len(actions), beats))

    lock_text = (lock or "").strip()
    hint = (p.get("lock_hint") or "").strip() if use_hint else ""
    if hint:
        lock_text = (lock_text.rstrip(", ") + ", " + hint).strip(", ") if lock_text else hint
    # moss_zh 类预设自带完整的中文场景+人物段落，用户没覆盖就直接用
    if not lock_text and p.get("lock_full"):
        lock_text = p["lock_full"]
    if not lock_text:
        raise ValueError("必须给 --lock（角色/场景的不变量），否则每拍会换人")

    neg = negative if negative is not None else (p.get("negative") or d.get("negative", ""))
    extra = (p.get("negative_extra") or "").strip()
    if extra:
        neg = (neg.rstrip(", ") + ", " + extra).strip(", ")

    story = {
        "name": name or ("anim-%s" % preset_id),
        "beats": beats,
        "frames": n_frames,
        "segs": n_segs,
        "fps": float(fps if fps is not None else p.get("fps", 10)),
        "denoise": float(denoise if denoise is not None else p.get("denoise", 0.45)),
        "seed_mode": seed_mode or "same",
        "prefix": prefix or "APNG/final",
        "lock": lock_text,
        "style": style if style is not None else p.get("style", d.get("style", "")),
        "negative": neg,
        "actions": actions,
        "motion": motion if motion is not None else p.get("motion", d.get("motion", "")),
        "curve": curve or p.get("curve", d.get("curve", "linear")),
    }
    if seed:
        story["seed"] = int(seed)
    mode = p.get("prompt_mode") or "tags"
    if mode != "tags":
        story["prompt_mode"] = mode
    return story


def _width(text):
    """终端显示宽度：CJK 全角按 2 列算。"""
    return sum(2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1 for ch in text)


def _pad(text, width):
    return text + " " * max(0, width - _width(text))


def format_table(data):
    rows = [("id", "名称", "拍", "帧", "标签", "用途")]
    for p in data["presets"]:
        rows.append((
            p.get("id", ""),
            p.get("name_zh", ""),
            str(p.get("beats", "")),
            str(p.get("frames", "")),
            ",".join(p.get("tags") or []),
            p.get("summary_zh", ""),
        ))
    widths = [max(_width(r[i]) for r in rows) for i in range(len(rows[0]))]
    lines = []
    for i, r in enumerate(rows):
        lines.append("  ".join(_pad(cell, widths[j]) for j, cell in enumerate(r)).rstrip())
        if i == 0:
            lines.append("  ".join("-" * w for w in widths))
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description="从动作库生成 ComfyUI 剧情卡（story JSON）")
    ap.add_argument("--presets", default=str(DEFAULT_PRESETS))
    ap.add_argument("--list", action="store_true", help="列出全部动作")
    ap.add_argument("--preset", default="")
    ap.add_argument("--lock", default="", help="不变的角色/场景提示词")
    ap.add_argument("--style", default=None)
    ap.add_argument("--name", default="")
    ap.add_argument("--frames", type=int, default=0)
    ap.add_argument("--fps", type=float, default=None)
    ap.add_argument("--segs", default="", help="逗号分隔，如 6,7,6,5；缺省按拍平均分")
    ap.add_argument("--denoise", type=float, default=None)
    ap.add_argument("--motion", default=None)
    ap.add_argument("--negative", default=None)
    ap.add_argument("--curve", choices=["linear", "ease", "snap"], default=None)
    ap.add_argument("--prefix", default=None)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--seed-mode", choices=["same", "offset", "different"], default=None)
    ap.add_argument("--no-hint", action="store_true", help="不追加动作自带的场景提示")
    ap.add_argument("--out", default="", help="输出路径；不给就打到 stdout")
    a = ap.parse_args(argv)

    try:
        data = load_presets(a.presets)
        if a.list or not a.preset:
            print(format_table(data))
            return 0 if a.list else 1
        segs = [int(x) for x in a.segs.split(",") if x.strip()] or None
        story = build_story(
            data, a.preset, a.lock, style=a.style, name=a.name or None,
            frames=a.frames or None, fps=a.fps, segs=segs, denoise=a.denoise,
            motion=a.motion, negative=a.negative, curve=a.curve, prefix=a.prefix,
            seed_mode=a.seed_mode, use_hint=not a.no_hint, seed=a.seed or None,
        )
    except (KeyError, ValueError) as e:
        print(str(e), file=sys.stderr)
        return 2

    text = json.dumps(story, ensure_ascii=False, indent=2) + "\n"
    if a.out:
        out = Path(a.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
        print("写出 %s  (%d 拍 / %d 帧 / %s fps)" % (out, story["beats"], story["frames"], story["fps"]))
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())