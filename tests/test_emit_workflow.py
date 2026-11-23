import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EMIT = ROOT / "scripts" / "emit_workflow.py"


def run(args):
    r = subprocess.run([sys.executable, str(EMIT)] + args,
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def test_three_beats(tmp_path):
    out = tmp_path / "b3.json"
    code, log = run(["--base", str(ROOT / "workflows" / "workflow-sdxl.json"),
                     "--story", str(ROOT / "assets" / "story.example.json"),
                     "--out", str(out)])
    assert code == 0, log
    assert "VALIDATE OK" in log
    wf = json.loads(out.read_text(encoding="utf-8"))
    assert len([n for n in wf["nodes"] if n["type"] == "KSampler"]) == 3
    # 61 基础 + 3 个条件合并 + 1 全局动作编码 + 2 个 Note
    assert len(wf["nodes"]) == 67


def test_four_beats(tmp_path):
    out = tmp_path / "b4.json"
    code, log = run(["--base", str(ROOT / "workflows" / "workflow-sdxl.json"),
                     "--story", str(ROOT / "assets" / "story.4beat.json"),
                     "--out", str(out)])
    assert code == 0, log
    wf = json.loads(out.read_text(encoding="utf-8"))
    assert len(wf["nodes"]) == 70


def test_five_beats_cli(tmp_path):
    out = tmp_path / "b5.json"
    code, log = run(["--base", str(ROOT / "workflows" / "workflow-sdxl.json"),
                     "--beats", "5", "--segs", "5,6,5,4,4",
                     "--lock", "masterpiece, 1girl", "--style", "anime",
                     "--actions", "a|b|c|d|e",
                     "--out", str(out)])
    assert code == 0, log
    wf = json.loads(out.read_text(encoding="utf-8"))
    # motion 留空 -> 不走 ConditioningCombine，只多 1 个全局编码 + 2 个 Note
    assert len(wf["nodes"]) == 71
    assert len([n for n in wf["nodes"] if n["type"] == "ConditioningCombine"]) == 3


def test_same_seed_and_denoise_written_back(tmp_path):
    """回归：已有关键帧 KSampler 也必须回写同 seed / 同 denoise，否则帧间抖动。"""
    out = tmp_path / "b4.json"
    code, log = run(["--base", str(ROOT / "workflows" / "workflow-sdxl.json"),
                     "--story", str(ROOT / "assets" / "story.4beat.json"),
                     "--out", str(out)])
    assert code == 0, log
    wf = json.loads(out.read_text(encoding="utf-8"))
    ks = [n for n in wf["nodes"] if n["type"] == "KSampler"]
    seeds = {n["widgets_values"][0] for n in ks}
    assert len(seeds) == 1, seeds
    assert ks[0]["widgets_values"][-1] == 1.0
    assert all(n["widgets_values"][-1] == 0.4 for n in ks[1:])


def test_seed_offset_mode(tmp_path):
    out = tmp_path / "b4.json"
    code, log = run(["--base", str(ROOT / "workflows" / "workflow-sdxl.json"),
                     "--story", str(ROOT / "assets" / "story.4beat.json"),
                     "--seed-mode", "offset", "--out", str(out)])
    assert code == 0, log
    wf = json.loads(out.read_text(encoding="utf-8"))
    seeds = sorted(n["widgets_values"][0] for n in wf["nodes"] if n["type"] == "KSampler")
    assert seeds == list(range(seeds[0], seeds[0] + 4))


def test_shipped_assets_validate():
    for name in ("workflow-sdxl.json", "workflow-moss.json",
                 "workflow-sdxl-4beat.json", "workflow-moss-4beat.json",
                 "workflow-sdxl-preview.json"):
        code, log = run(["--validate", str(ROOT / "workflows" / name)])
        assert code == 0, name + log


def test_shipped_assets_share_one_seed():
    """所有随包工作流的关键帧必须同 seed，两个环境一样。"""
    names = ("workflow-sdxl.json", "workflow-moss.json",
             "workflow-sdxl-4beat.json", "workflow-moss-4beat.json",
             "workflow-sdxl-preview.json")
    for name in names:
        wf = json.loads((ROOT / "workflows" / name).read_text(encoding="utf-8"))
        seeds = {n["widgets_values"][0] for n in wf["nodes"] if n["type"] == "KSampler"}
        assert len(seeds) == 1, (name, seeds)


def test_rejects_bad_seg_sum(tmp_path):
    code, log = run(["--base", str(ROOT / "workflows" / "workflow-sdxl.json"),
                     "--beats", "4", "--segs", "8,8,8",
                     "--lock", "x", "--actions", "a|b|c|d",
                     "--out", str(tmp_path / "x.json")])
    assert code != 0
    assert ("24" in log) or ("段数" in log)



def test_motion_layer_shared_and_each_frame_kept(tmp_path):
    """全局动作只写一个节点；每帧提示仍在各自的 CLIPTextEncode 里。"""
    out = tmp_path / "b3.json"
    code, log = run(["--base", str(ROOT / "workflows" / "workflow-sdxl.json"),
                     "--story", str(ROOT / "assets" / "story.example.json"),
                     "--motion", "slow blink, stable lighting",
                     "--out", str(out)])
    assert code == 0, log
    wf = json.loads(out.read_text(encoding="utf-8"))
    gen = [n for n in wf["nodes"]
           if n["type"] == "CLIPTextEncode" and "全局动作指导" in (n.get("title") or "")]
    assert len(gen) == 1
    assert gen[0]["widgets_values"] == ["slow blink, stable lighting"]
    combos = [n for n in wf["nodes"] if n["type"] == "ConditioningCombine"]
    assert len(combos) == 3
    encs = [n for n in wf["nodes"]
            if n["type"] == "CLIPTextEncode" and (n.get("title") or "").startswith("K")]
    assert len(encs) == 3


def test_emit_is_idempotent(tmp_path):
    """把 emit 产物再当 base 跑一次，合并层与 Note 不能重复叠加。"""
    once_out = tmp_path / "b3.json"
    twice_out = tmp_path / "b3x2.json"
    code, log = run(["--base", str(ROOT / "workflows" / "workflow-sdxl.json"),
                     "--story", str(ROOT / "assets" / "story.example.json"),
                     "--out", str(once_out)])
    assert code == 0, log
    code, log = run(["--base", str(once_out),
                     "--story", str(ROOT / "assets" / "story.example.json"),
                     "--out", str(twice_out)])
    assert code == 0, log
    a = json.loads(once_out.read_text(encoding="utf-8"))
    b = json.loads(twice_out.read_text(encoding="utf-8"))
    assert len(a["nodes"]) == len(b["nodes"])
    assert len([n for n in b["nodes"] if n["type"] == "ConditioningCombine"]) == 3
    assert len([n for n in b["nodes"] if n["type"] == "Note"]) == 2


def test_linear_curve_has_uniform_steps():
    c = __import__("comfy_lib").build_curve([8, 8, 8], curve="linear")
    seg = c[:8]
    steps = [round(seg[i] - seg[i + 1], 3) for i in range(7)]
    assert max(steps) - min(steps) <= 0.002, steps

def test_frames_60_expands_nodes(tmp_path):
    """--frames 60：插值/解码/batch 三件套自动补齐到 60。"""
    out = tmp_path / "f60.json"
    code, log = run(["--base", str(ROOT / "workflows" / "workflow-moss.json"),
                     "--beats", "4", "--frames", "60", "--segs", "15,15,15,15",
                     "--fps", "30", "--lock", "x", "--actions", "a|b|c|d",
                     "--out", str(out)])
    assert code == 0, log
    wf = json.loads(out.read_text(encoding="utf-8"))
    interps = [n for n in wf["nodes"] if n["type"] == "LatentInterpolate"]
    decodes = [n for n in wf["nodes"] if n["type"] == "VAEDecode"]
    assert len(interps) == 60 and len(decodes) == 60
    b = [n for n in wf["nodes"] if n["type"] == "ImageBatchMulti"][0]
    assert len([i for i in b["inputs"] if i.get("link") is not None]) == 60
    assert b["widgets_values"] == [60]
    ratios = [n["widgets_values"][0] for n in
              sorted(interps, key=lambda n: n.get("order", 0))]
    assert len(ratios) == 60 and ratios[0] == 1.0


def test_frames_auto_split_without_segs(tmp_path):
    """不给 --segs 时按 beats 平均分 60 帧。"""
    out = tmp_path / "f60auto.json"
    code, log = run(["--base", str(ROOT / "workflows" / "workflow-sdxl.json"),
                     "--beats", "4", "--frames", "60",
                     "--lock", "x", "--actions", "a|b|c|d", "--out", str(out)])
    assert code == 0, log
    assert "segs=[15, 15, 15, 15]" in log


def test_frames_8_shrinks(tmp_path):
    out = tmp_path / "f8.json"
    code, log = run(["--base", str(ROOT / "workflows" / "workflow-sdxl.json"),
                     "--beats", "4", "--frames", "8",
                     "--lock", "x", "--actions", "a|b|c|d", "--out", str(out)])
    assert code == 0, log
    wf = json.loads(out.read_text(encoding="utf-8"))
    assert len([n for n in wf["nodes"] if n["type"] == "LatentInterpolate"]) == 8
    assert len([n for n in wf["nodes"] if n["type"] == "VAEDecode"]) == 8
    b = [n for n in wf["nodes"] if n["type"] == "ImageBatchMulti"][0]
    assert b["widgets_values"] == [8]
    assert len(b["inputs"]) == 8


def test_frames_rejects_bad_sum(tmp_path):
    code, log = run(["--base", str(ROOT / "workflows" / "workflow-sdxl.json"),
                     "--beats", "4", "--frames", "60", "--segs", "15,15,15,10",
                     "--lock", "x", "--actions", "a|b|c|d",
                     "--out", str(tmp_path / "x.json")])
    assert code != 0
    assert "frames" in log

def test_empty_motion_bypasses_combine(tmp_path):
    """motion 留空时不能走 ConditioningCombine：空提示会稀释本帧提示，掉画质。"""
    out = tmp_path / "bypass.json"
    code, log = run(["--base", str(ROOT / "workflows" / "workflow-sdxl.json"),
                     "--beats", "4", "--frames", "8", "--lock", "L",
                     "--actions", "a0|a1|a2|a3", "--out", str(out)])
    assert code == 0, log
    wf = json.loads(out.read_text(encoding="utf-8"))
    nodes = {n["id"]: n for n in wf["nodes"]}
    links = {l[0]: l for l in wf["links"]}
    ks = [n for n in nodes.values() if n["type"] == "KSampler"]
    seen = {}
    for n in ks:
        title = n.get("title") or ""
        idx = int(title[1]) if title.startswith("K") and title[1].isdigit() else None
        if idx is None:
            continue
        pos = [i for i in n["inputs"] if i["name"] == "positive"][0]
        src = nodes[links[pos["link"]][1]]
        assert src["type"] == "CLIPTextEncode", (idx, src["type"])
        seen[idx] = src["widgets_values"][0]
    assert len(seen) == 4
    for i in range(4):
        assert "a%d" % i in seen[i], seen


def test_story_segs_rescale_when_frames_override(tmp_path):
    """剧情卡写着 60 帧，命令行改成 30，segs 应重算为 6×5 而不是报错。"""
    story = tmp_path / "story.json"
    story.write_text('{"name":"s","beats":5,"frames":60,"segs":[12,12,12,12,12],'
                     '"lock":"1girl","style":"anime","actions":["a","b","c","d","e"]}',
                     encoding="utf-8")
    out = tmp_path / "wf.json"
    code, log = run(["--base", str(ROOT / "workflows" / "workflow-sdxl.json"), "--story", str(story),
                     "--frames", "30", "--out", str(out)])
    assert code == 0, log
    assert "segs=[6, 6, 6, 6, 6]" in log


def test_moss_zh_compiles_to_prose(tmp_path):
    """moss_zh 模式：三段用换行拼接，每段以中文句号收尾，不掺英文逗号。"""
    out = tmp_path / "moss.json"
    code, log = run(["--base", str(ROOT / "workflows" / "workflow-moss.json"),
                     "--beats", "2", "--frames", "2", "--segs", "1,1", "--fps", "2",
                     "--prompt-mode", "moss_zh",
                     "--lock", "一间卧室。", "--style", "动漫风格。",
                     "--actions", "坐着。|躺下。", "--out", str(out)])
    assert code == 0, log
    wf = json.loads(out.read_text(encoding="utf-8"))
    texts = [n["widgets_values"][0] for n in wf["nodes"]
             if n["type"] == "CLIPTextEncode" and "一间卧室" in str(n.get("widgets_values"))]
    assert texts, "找不到 K0/K1 提示节点"
    for t in texts:
        assert "\n" in t, t
        assert t.rstrip().endswith("。"), t
        assert "一间卧室。, " not in t
    assert any("坐着" in t for t in texts)
    assert any("躺下" in t for t in texts)


def test_size_override(tmp_path):
    out = tmp_path / "size.json"
    code, log = run(["--base", str(ROOT / "workflows" / "workflow-moss.json"),
                     "--beats", "2", "--frames", "2", "--segs", "1,1",
                     "--lock", "x", "--actions", "a|b", "--size", "640", "--out", str(out)])
    assert code == 0, log
    wf = json.loads(out.read_text(encoding="utf-8"))
    lat = [n for n in wf["nodes"] if n["type"].startswith("Empty") and "Latent" in n["type"]]
    assert lat and lat[0]["widgets_values"][0] == 640 and lat[0]["widgets_values"][1] == 640


def test_notes_are_idempotent(tmp_path):
    """--notes-only 跑两次，两个 Note 不能变成四个。"""
    first = tmp_path / "n1.json"
    code, log = run(["--notes-only", "--base", str(ROOT / "workflows" / "workflow-sdxl.json"),
                     "--out", str(first)])
    assert code == 0, log
    wf = json.loads(first.read_text(encoding="utf-8"))
    assert len([n for n in wf["nodes"] if n["type"] == "Note"]) == 2
    second = tmp_path / "n2.json"
    code, log = run(["--notes-only", "--base", str(first), "--out", str(second)])
    assert code == 0, log
    wf2 = json.loads(second.read_text(encoding="utf-8"))
    assert len([n for n in wf2["nodes"] if n["type"] == "Note"]) == 2
