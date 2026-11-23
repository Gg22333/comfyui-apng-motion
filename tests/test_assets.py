import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"


def load(name):
    return json.loads((ASSETS / name).read_text(encoding="utf-8"))


@pytest.mark.parametrize("name", [
    "workflow-sdxl.json", "workflow-moss.json",
    "workflow-sdxl-4beat.json", "workflow-moss-4beat.json",
])
def test_workflow_shape(name):
    wf = load(name)
    nodes = wf["nodes"]
    types = [n["type"] for n in nodes]
    assert types.count("LatentInterpolate") == 24
    assert types.count("VAEDecode") == 24
    assert types.count("ImageBatchMulti") == 1
    assert "SaveAnimatedPNG" in types
    assert "SaveAnimatedWEBP" in types
    assert "VHS_VideoCombine" in types
    assert "SaveImage" not in types
    assert "PreviewImage" not in types


@pytest.mark.parametrize("name", [
    "workflow-sdxl.json", "workflow-moss.json",
    "workflow-sdxl-4beat.json", "workflow-moss-4beat.json",
])
def test_ratios_unique_per_pair(name):
    """同一对 latent 上不能有重复 ratio；不同段之间可以同值。"""
    wf = load(name)
    links = {l[0]: l for l in wf["links"]}
    groups = {}
    for n in wf["nodes"]:
        if n["type"] != "LatentInterpolate":
            continue
        key = tuple(links[i["link"]][1] for i in n["inputs"] if i.get("link") in links)
        groups.setdefault(key, []).append(n["widgets_values"][0])
    assert sum(len(v) for v in groups.values()) == 24
    for key, vals in groups.items():
        assert len(set(vals)) == len(vals), (key, vals)


@pytest.mark.parametrize("name", ["workflow-sdxl.json", "workflow-moss.json"])
def test_keyframes_share_first_latent(name):
    wf = load(name)
    links = {l[0]: l for l in wf["links"]}
    samplers = [n for n in wf["nodes"] if n["type"] == "KSampler"]
    samplers.sort(key=lambda n: n.get("order", 0))
    sources = set()
    for s in samplers[1:]:
        for inp in s["inputs"]:
            if inp["name"] == "latent_image":
                l = links[inp["link"]]
                sources.add((l[1], l[2]))
    assert len(sources) == 1


def test_node_schema_covers_required_types():
    schema = load("node_schema.json")
    for t in ("LatentInterpolate", "SaveAnimatedPNG", "SaveAnimatedWEBP",
              "VHS_VideoCombine", "ImageBatchMulti", "KSampler", "VAEDecode"):
        assert t in schema, t


@pytest.mark.parametrize("name", ["story.example.json", "story.4beat.json"])
def test_story_cards_consistent(name):
    story = load(name)
    assert sum(story["segs"]) == 24
    assert len(story["segs"]) == story["beats"] == len(story["actions"])

