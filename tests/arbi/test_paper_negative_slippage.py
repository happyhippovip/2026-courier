from tests.arbi.test_paper_slippage import _attempt


def test_negative_slippage_does_not_fill():
    assert (
        _attempt(-1.0),
        _attempt(-0.05),
        _attempt(0.05),
    ) == (
        ("raised", "slippage is out of range.", None, 100.0, 0),
        ("raised", "slippage is out of range.", None, 100.0, 0),
        ("filled", "FULL_SUCCESS", 0.75, 100.75, 1),
    )
