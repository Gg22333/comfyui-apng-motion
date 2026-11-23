import comfy_lib as L


def _segments(c, segs):
    i = 0
    for cnt in segs:
        yield c[i:i + cnt]
        i += cnt


def test_three_segment_defaults():
    c = L.build_curve([8, 8, 8])
    assert len(c) == 24
    assert c[0] == 1.0
    assert all(0.0 <= v <= 1.0 for v in c)
    for seg in _segments(c, [8, 8, 8]):
        assert all(a > b for a, b in zip(seg, seg[1:]))


def test_four_and_five_segments_unique_within_segment():
    # 跨段使用同一个 ratio 是安全的：latent 对不同，画面必然不同。
    for segs in ([6, 7, 6, 5], [5, 6, 5, 4, 4]):
        c = L.build_curve(segs)
        assert len(c) == sum(segs)
        assert all(0.0 <= v <= 1.0 for v in c)
        for seg in _segments(c, segs):
            assert len(set(seg)) == len(seg), (segs, seg)
            assert all(a > b for a, b in zip(seg, seg[1:])), (segs, seg)


def test_no_adjacent_duplicates():
    c = L.build_curve([6, 7, 6, 5])
    for a, b in zip(c, c[1:]):
        assert a != b


def test_explicit_bounds_are_respected():
    c = L.build_curve([8, 8, 8], starts=[1.0, 0.9, 0.9], ends=[0.1, 0.0, 0.02])
    assert c[0] == 1.0
    assert c[-1] == 0.02


def test_segments_do_not_repeat_the_keyframe():
    """段尾=目标关键帧，下一段段首必须已经离开它；旧曲线会在这里连出两帧。"""
    segs = [5, 5, 4, 7, 6, 7, 5, 6, 5, 5, 5]
    c = L.build_curve(segs)
    assert len(c) == sum(segs) == 60
    assert c[0] == 1.0
    # 最后一段停在 K0 前一格，循环回第 0 帧不会多停一帧
    assert 0.0 < c[-1] < 0.3
    assert all(a != b for a, b in zip(c, c[1:]))
    # 段内严格递减（同一对 latent 上不允许重复 ratio）
    i = 0
    for cnt in segs:
        seg = c[i:i + cnt]
        assert all(a > b for a, b in zip(seg, seg[1:])), seg
        i += cnt


def test_every_keyframe_is_reached_once():
    segs = [5, 5, 4, 7, 6, 7, 5, 6, 5, 5, 5]
    c = L.build_curve(segs)
    ends = []
    i = 0
    for cnt in segs[:-1]:
        i += cnt
        ends.append(c[i - 1])
    # 每个中间关键帧在段尾正好是 0.0，且只出现一次
    assert ends == [0.0] * (len(segs) - 1)


def test_cover_frame_only_once():
    c = L.build_curve([8, 8, 8])
    assert c.count(1.0) == 1
