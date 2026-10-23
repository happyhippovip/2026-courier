from tests.arbi.test_stream_count import _events


def test_negative_stream_count_emits_nothing():
    assert (
        _events(-3),
        _events(0),
        _events(2),
    ) == (
        ("raised", "count is out of range.", 0),
        ("emitted", 0, 0),
        ("emitted", 2, 2),
    )
