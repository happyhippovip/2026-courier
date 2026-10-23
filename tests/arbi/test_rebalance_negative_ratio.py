from tests.arbi.test_rebalance_nan import _assess


def test_negative_rebalance_ratio_is_not_a_safe_rebalance():
    assert (
        _assess(800.0, 200.0, pnl=2.0, min_profit_to_rebalance_ratio=-3.0),
        _assess(800.0, 200.0, pnl=2.0, min_profit_to_rebalance_ratio=3.0),
    ) == (
        ("raised", "rebalance setting is out of range."),
        ("REBALANCE_BLOCKED_INSUFFICIENT_PROFIT", False, 300.0),
    )
