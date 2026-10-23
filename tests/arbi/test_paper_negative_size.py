from tests.arbi.test_paper_order_size import _attempt


def test_negative_order_size_does_not_fill():
    assert (
        _attempt(-10.0),
        _attempt(10.0),
    ) == (
        ("raised", "order size is out of range.", None, 100.0, 0),
        ("filled", "FULL_SUCCESS", 10.0, 100.75, 1),
    )
