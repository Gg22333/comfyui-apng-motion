import json
from pathlib import Path

import pytest

import timing as T

ROOT = Path(__file__).resolve().parents[1]
SEGS11 = [5, 5, 4, 7, 6, 7, 5, 6, 5, 5, 5]


def story():
    return json.loads((ROOT / "assets" / "story.diet.json").read_text(encoding="utf-8"))


def test_length_equals_frames():
    d = T.frame_delays(60, SEGS11, 20)
    assert len(d) == 60


def test_total_duration_is_exact():
    for frames, segs, fps in [(24, [8, 8, 8], 10), (60, SEGS11, 20), (8, [3, 3, 2], 8)]:
        d = T.frame_delays(frames, segs, fps, quantum=1)
        assert abs(sum(d) - frames * 1000.0 / fps) < 0.5


def test_ease_zero_is_uniform():
    d = T.frame_delays(24, [8, 8, 8], 10, ease=0.0)
    assert len(set(d)) <= 2  # 取整后最多差 1 ms


def test_ease_slows_the_edges_of_each_segment():
    d = T.frame_delays(60, SEGS11, 20, ease=0.5)
    for a, b in T.seg_ranges(SEGS11):
        if b - a < 3:
            continue
        mid = d[a:b]
        assert mid[0] >= max(mid)
        assert mid[-1] >= min(mid)
        assert mid[0] > mid[(b - a) // 2]


def test_dwell_moves_time_but_preserves_total():
    base = T.frame_delays(60, SEGS11, 20)
    heavy = T.frame_delays(60, SEGS11, 20, dwell=[1.0] * 10 + [2.0])
    assert sum(base) == sum(heavy)
    assert T.beat_totals(heavy, SEGS11)[-1] > T.beat_totals(base, SEGS11)[-1]


def test_dwell_length_must_match_segments():
    with pytest.raises(ValueError):
        T.frame_delays(60, SEGS11, 20, dwell=[1.0, 1.0])


def test_segs_must_sum_to_frames():
    with pytest.raises(ValueError):
        T.frame_delays(60, [5, 5, 5], 20)


def test_gif_quantum_keeps_total_within_one_frame():
    d = T.frame_delays(60, SEGS11, 24, quantum=10)
    assert all(x % 10 == 0 for x in d)
    assert abs(sum(d) - 2500) <= 10 * 2


def test_summary_shape():
    s = T.summary(60, SEGS11, 20)
    assert s["frames"] == 60
    assert s["target_s"] == 3.0
    assert abs(s["total_s"] - 3.0) < 0.01
    assert len(s["beats_ms"]) == 11
    assert len(s["delays"]) == 60


def test_shipped_story_is_three_seconds():
    st = story()
    assert st["fps"] == 20
    assert st["frames"] == 60
    assert len(st["dwell"]) == st["beats"] == len(st["segs"])
    s = T.summary(st["frames"], st["segs"], st["fps"],
                  dwell=st["dwell"], ease=st["ease"])
    assert s["total_s"] == 3.0
    # 每一拍都要够长，不能有一闪而过
    assert min(s["beats_ms"]) >= 200, s["beats_ms"]