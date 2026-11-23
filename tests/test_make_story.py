import json

import pytest

import make_story


def test_preset_ids_unique_and_actions_match_beats():
    data = make_story.load_presets()
    ids = [p["id"] for p in data["presets"]]
    assert len(ids) == len(set(ids))
    for p in data["presets"]:
        assert len(p["actions"]) == p["beats"], p["id"]
        assert sum(p["segs"]) == p["frames"], p["id"]
        assert len(p["segs"]) == p["beats"], p["id"]
        assert p["actions"][0], p["id"]


def test_build_wave_story_has_emitter_fields():
    data = make_story.load_presets()
    story = make_story.build_story(data, "wave", "masterpiece, 1girl, silver hair")
    for key in ("name", "beats", "frames", "segs", "fps", "denoise", "seed_mode",
                "prefix", "lock", "style", "negative", "actions", "motion", "curve"):
        assert key in story, key
    assert story["beats"] == 4
    assert story["frames"] == 24
    assert story["segs"] == [6, 7, 6, 5]
    assert sum(story["segs"]) == 24
    assert story["lock"].startswith("masterpiece, 1girl, silver hair")
    assert "photo" in story["negative"]


def test_preset_segments_kept_when_frames_unchanged():
    data = make_story.load_presets()
    story = make_story.build_story(data, "rainy-walk", "1girl")
    assert story["frames"] == 60
    assert story["segs"] == [12, 12, 12, 12, 12]


def test_frames_override_redistributes_segments():
    data = make_story.load_presets()
    story = make_story.build_story(data, "laugh", "1girl", frames=30)
    assert story["frames"] == 30
    assert len(story["segs"]) == 4
    assert sum(story["segs"]) == 30
    assert max(story["segs"]) - min(story["segs"]) <= 1


def test_explicit_segs_validated():
    data = make_story.load_presets()
    with pytest.raises(ValueError):
        make_story.build_story(data, "wave", "1girl", frames=24, segs=[6, 6, 6, 5])
    with pytest.raises(ValueError):
        make_story.build_story(data, "wave", "1girl", frames=24, segs=[8, 8, 8])


def test_frames_smaller_than_beats_rejected():
    data = make_story.load_presets()
    with pytest.raises(ValueError):
        make_story.build_story(data, "rainy-walk", "1girl", frames=3)


def test_unknown_preset_lists_known_ids():
    data = make_story.load_presets()
    with pytest.raises(KeyError) as e:
        make_story.find_preset(data, "nope")
    assert "wave" in str(e.value)


def test_story_preset_appends_lock_hint_and_can_disable():
    data = make_story.load_presets()
    with_hint = make_story.build_story(data, "rainy-walk", "1girl")
    without = make_story.build_story(data, "rainy-walk", "1girl", use_hint=False)
    assert "raincoat" in with_hint["lock"]
    assert "raincoat" not in without["lock"]


def test_cli_list_and_write(tmp_path, capsys):
    out = tmp_path / "story.json"
    assert make_story.main(["--list"]) == 0
    assert "wave" in capsys.readouterr().out
    rc = make_story.main([
        "--preset", "sigh", "--lock", "masterpiece, 1girl",
        "--frames", "12", "--fps", "12", "--out", str(out),
    ])
    assert rc == 0
    story = json.loads(out.read_text(encoding="utf-8"))
    assert story["frames"] == 12
    assert story["fps"] == 12
    assert sum(story["segs"]) == 12


def test_cli_missing_lock_fails(tmp_path):
    rc = make_story.main(["--preset", "wave", "--out", str(tmp_path / "x.json")])
    assert rc == 2