import json
from pathlib import Path

import comfy_lib as L

ROOT = Path(__file__).resolve().parents[1]


def test_ui_to_api_widgets_and_links():
    wf = json.loads((ROOT / "workflows" / "workflow-sdxl.json").read_text(encoding="utf-8"))
    info = json.loads((ROOT / "assets" / "node_schema.json").read_text(encoding="utf-8"))
    api = L.ui_to_api(wf, info)

    ks = api["5"]
    assert ks["class_type"] == "KSampler"
    assert ks["inputs"]["seed"] == 123456789
    assert ks["inputs"]["steps"] == 20
    assert ks["inputs"]["cfg"] == 6.0
    assert ks["inputs"]["latent_image"] == ["4", 0]

    png = api["59"]
    assert png["class_type"] == "SaveAnimatedPNG"
    assert png["inputs"]["filename_prefix"].startswith("APNG/final/apng")
    assert png["inputs"]["fps"] == 10

    interp = api["10"]
    assert interp["inputs"]["samples1"] == ["5", 0]
    assert interp["inputs"]["samples2"] == ["7", 0]
    assert interp["inputs"]["ratio"] == 1.0
