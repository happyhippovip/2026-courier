from tests.arbi.test_rebalance_nan import _assess


def test_negative_transfer_fee_is_not_a_safe_rebalance():
    assert (
        _assess(800.0, 200.0, pnl=2.0, fixed_transfer_fee_eur=-1.0),
        _assess(800.0, 200.0, pnl=2.0, fixed_transfer_fee_eur=1.5),
    ) == (
        ("raised", "rebalance setting is out of range."),
        ("REBALANCE_BLOCKED_INSUFFICIENT_PROFIT", False, 300.0),
    )
