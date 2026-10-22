from tests.arbi.test_paper_fee import _attempt


def test_negative_fee_does_not_fill():
    assert (
        _attempt(-0.1, 0.1),
        _attempt(0.1, -0.1),
        _attempt(0.1, 0.1),
    ) == (
        ("raised", "fee is out of range.", None, 100.0, 0),
        ("raised", "fee is out of range.", None, 100.0, 0),
        ("filled", "FULL_SUCCESS", 0.75, 100.75, 1),
    )
