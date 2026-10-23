from tests.arbi.test_paper_negative_rebalance import _attempt


def test_non_finite_rebalance_does_not_fill():
    assert (
        _attempt(float("nan")),
        _attempt(float("inf")),
        _attempt(True),
        _attempt(0.0),
    ) == (
        ("raised", "rebalance cost is not a number.", None, 100.0, 0),
        ("raised", "rebalance cost is not a number.", None, 100.0, 0),
        ("raised", "Bool is not a number.", None, 100.0, 0),
        ("filled", "FULL_SUCCESS", 0.75, 100.75, 1),
    )
