from tests.arbi.test_rebalance_nan import _assess


def test_negative_inventory_is_not_a_transfer():
    assert (
        _assess(-100.0, 200.0, pnl=100.0),
        _assess(800.0, 200.0, pnl=25.0),
    ) == (
        ("raised", "inventory is out of range."),
        ("REBALANCE_RECOMMENDED", True, 300.0),
    )
