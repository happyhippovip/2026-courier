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
