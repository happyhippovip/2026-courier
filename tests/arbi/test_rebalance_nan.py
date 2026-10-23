from courier_core.arbi.rebalance import DeltaNeutralRebalanceEngine, InventoryStatus


def _assess(binance, kraken, pnl=100.0, **settings):
    try:
        engine = DeltaNeutralRebalanceEngine(**settings)
    except ValueError as exc:
        return ("raised", str(exc))
    try:
        assessment = engine.evaluate_inventory_balance(
            InventoryStatus("binance", binance, 0.0),
            InventoryStatus("kraken", kraken, 0.0),
            pnl,
        )
    except ValueError as exc:
        return ("raised", str(exc))
    return (
        assessment.status,
        assessment.rebalance_safe,
        assessment.transfer_amount_quote,
    )


def test_nan_inventory_is_not_a_safe_transfer():
    assert (
        _assess(float("nan"), 100.0),
        _assess(float("inf"), 100.0),
        _assess(100.0, 100.0, pnl=10.0),
        _assess(100.0, 100.0, pnl=10.0, imbalance_threshold_pct=float("nan")),
    ) == (
        ("raised", "inventory is not a number."),
        ("raised", "inventory is not a number."),
        ("BALANCED", True, 0.0),
        ("raised", "rebalance setting is not a number."),
    )
