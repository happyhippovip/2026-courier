from tests.arbi.test_paper_latency import _attempt


def test_negative_latency_does_not_fill():
    assert (
        _attempt(-5.0),
        _attempt(45.0),
    ) == (
        ("raised", "latency is out of range.", None, 100.0, 0),
        ("filled", "FULL_SUCCESS", 45.0, 100.75, 1),
    )
