from tests.arbi.test_paper_gross import _attempt


def test_negative_gross_does_not_fill():
    assert (
        _attempt(-1.0),
        _attempt(1.0),
    ) == (
        ("raised", "gross spread is out of range.", None, 100.0, 0),
        ("filled", "FULL_SUCCESS", 0.75, 100.75, 1),
    )
