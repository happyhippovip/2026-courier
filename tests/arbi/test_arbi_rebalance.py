"""Tests for Delta-Neutral Rebalance Engine."""

from courier_core.arbi.rebalance import (
    DeltaNeutralRebalanceEngine,
    InventoryStatus,
    RebalanceAssessment,
)


def test_rebalance_balanced_inventories():
    engine = DeltaNeutralRebalanceEngine(imbalance_threshold_pct=20.0)
    b_inv = InventoryStatus(venue="binance", quote_balance=500.0, base_balance=0.0)
    k_inv = InventoryStatus(venue="kraken", quote_balance=510.0, base_balance=0.0)

    assessment = engine.evaluate_inventory_balance(b_inv, k_inv, accumulated_pnl_eur=50.0)
    assert assessment.is_rebalance_needed is False
    assert assessment.status == "BALANCED"


def test_rebalance_skew_triggers_recommended_when_profitable():
    engine = DeltaNeutralRebalanceEngine(imbalance_threshold_pct=25.0, fixed_transfer_fee_eur=1.50)
    # Severe skew: 800 EUR on Binance, 200 EUR on Kraken (diff: 60%)
    b_inv = InventoryStatus(venue="binance", quote_balance=800.0, base_balance=0.0)
    k_inv = InventoryStatus(venue="kraken", quote_balance=200.0, base_balance=0.0)

    # 25 EUR accumulated profit > 1.50 * 3.0 (4.50 EUR threshold)
    assessment = engine.evaluate_inventory_balance(b_inv, k_inv, accumulated_pnl_eur=25.0)
    assert assessment.is_rebalance_needed is True
    assert assessment.source_venue == "binance"
    assert assessment.destination_venue == "kraken"
    assert assessment.transfer_amount_quote == 300.0
    assert assessment.rebalance_safe is True
    assert assessment.status == "REBALANCE_RECOMMENDED"


def test_rebalance_skew_blocks_when_profit_insufficient():
    engine = DeltaNeutralRebalanceEngine(imbalance_threshold_pct=25.0, fixed_transfer_fee_eur=1.50, min_profit_to_rebalance_ratio=3.0)
    b_inv = InventoryStatus(venue="binance", quote_balance=800.0, base_balance=0.0)
    k_inv = InventoryStatus(venue="kraken", quote_balance=200.0, base_balance=0.0)

    # Only 2.00 EUR profit < 4.50 EUR threshold -> Must block rebalancing
    assessment = engine.evaluate_inventory_balance(b_inv, k_inv, accumulated_pnl_eur=2.00)
    assert assessment.is_rebalance_needed is True
    assert assessment.rebalance_safe is False
    assert assessment.status == "REBALANCE_BLOCKED_INSUFFICIENT_PROFIT"


def test_bool_rebalance_settings_are_not_numbers():
    mild_binance = InventoryStatus(venue="binance", quote_balance=500.0, base_balance=0.0)
    mild_kraken = InventoryStatus(venue="kraken", quote_balance=600.0, base_balance=0.0)
    skewed_binance = InventoryStatus(venue="binance", quote_balance=800.0, base_balance=0.0)
    skewed_kraken = InventoryStatus(venue="kraken", quote_balance=200.0, base_balance=0.0)
    seen = []
    cases = (
        ("threshold", DeltaNeutralRebalanceEngine, {"imbalance_threshold_pct": True}, mild_binance, mild_kraken, 25.0),
        ("fee", DeltaNeutralRebalanceEngine, {"fixed_transfer_fee_eur": True}, skewed_binance, skewed_kraken, 25.0),
        ("ratio", DeltaNeutralRebalanceEngine, {"min_profit_to_rebalance_ratio": True}, skewed_binance, skewed_kraken, 2.0),
    )
    for name, factory, kwargs, left, right, pnl in cases:
        try:
            engine = factory(**kwargs)
            assessment = engine.evaluate_inventory_balance(left, right, accumulated_pnl_eur=pnl)
        except ValueError as exc:
            seen.append((name, "raised", str(exc)))
        else:
            seen.append((
                name,
                "accepted",
                assessment.status,
                assessment.is_rebalance_needed,
                assessment.rebalance_safe,
                assessment.transfer_amount_quote,
                assessment.estimated_network_fee,
            ))
    assert seen == [
        ("threshold", "raised", "Bool is not a number."),
        ("fee", "raised", "Bool is not a number."),
        ("ratio", "raised", "Bool is not a number."),
    ], seen


def test_bool_inventory_is_not_one_euro():
    engine = DeltaNeutralRebalanceEngine()
    seen = []
    for quote in (True, False):
        try:
            assessment = engine.evaluate_inventory_balance(
                InventoryStatus(venue="binance", quote_balance=quote, base_balance=0.0),
                InventoryStatus(venue="kraken", quote_balance=100.0, base_balance=0.0),
                accumulated_pnl_eur=25.0,
            )
        except ValueError as exc:
            seen.append((quote, "raised", str(exc)))
        else:
            seen.append((
                quote,
                "accepted",
                assessment.status,
                assessment.transfer_amount_quote,
                assessment.source_venue,
            ))
    assert seen == [
        (True, "raised", "Bool is not a number."),
        (False, "raised", "Bool is not a number."),
    ], seen
