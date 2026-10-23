from tests.arbi.test_rebalance_nan import _assess


def test_negative_imbalance_threshold_does_not_rebalance_a_flat_book():
    assert (
        _assess(500.0, 500.0, pnl=100.0, imbalance_threshold_pct=-1.0),
        _assess(500.0, 500.0, pnl=100.0, imbalance_threshold_pct=25.0),
    ) == (
        ("raised", "rebalance setting is out of range."),
        ("BALANCED", True, 0.0),
    )
