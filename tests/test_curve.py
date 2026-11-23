import comfy_lib as L


def test_three_segment_defaults():
    c = L.build_curve([8, 8, 8])
    assert len(c) == 24
    assert len(set(c)) == 24
    assert c[0] == 1.0
    assert all(0.0 <= v <= 1.0 for v in c)


def test_four_and_five_segments_unique():
    for segs in ([6, 7, 6, 5], [5, 6, 5, 4, 4]):
        c = L.build_curve(segs)
        assert len(c) == 24
        assert len(set(c)) == 24, segs
        assert all(0.0 <= v <= 1.0 for v in c)


def test_no_adjacent_duplicates():
    c = L.build_curve([6, 7, 6, 5])
    for a, b in zip(c, c[1:]):
        assert a != b


def test_explicit_bounds_are_respected():
    c = L.build_curve([8, 8, 8], starts=[1.0, 0.9, 0.9], ends=[0.1, 0.0, 0.02])
    assert c[0] == 1.0
    assert c[-1] == 0.02
