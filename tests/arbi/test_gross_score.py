from courier_core.arbi.analyzer import StatisticalQualityAnalyzer
from courier_core.arbi.models import NormalizedPair, OrderbookLevel, OrderbookSnapshot
from courier_core.arbi.net_profit import NetProfitBreakdown


def _score(gross, slippage=0.1):
    pair = NormalizedPair("ETH", "USDT")
    book = OrderbookSnapshot(
        exchange="binance",
        pair=pair,
        bids=[OrderbookLevel(100.0, 1.0)],
        asks=[OrderbookLevel(101.0, 1.0)],
        timestamp_utc="2026-10-18T12:00:00Z",
        latency_ms=10.0,
    )
    sell = OrderbookSnapshot(
        exchange="okx",
        pair=pair,
        bids=[OrderbookLevel(100.0, 1.0)],
        asks=[OrderbookLevel(101.0, 1.0)],
        timestamp_utc="2026-10-18T12:00:00Z",
        latency_ms=10.0,
    )
    breakdown = NetProfitBreakdown(
        pair=pair,
        buy_exchange="binance",
        sell_exchange="okx",
        order_size_usd=100.0,
        best_ask_price=101.0,
        best_bid_price=100.0,
        effective_buy_price=101.0,
        effective_sell_price=100.0,
        gross_spread_pct=1.0,
        gross_spread_usd=gross,
        buy_fee_usd=0.1,
        sell_fee_usd=0.1,
        slippage_usd=slippage,
        transfer_cost_usd=0.0,
        rebalance_cost_usd=0.0,
        total_costs_usd=0.2,
        net_profit_usd=9.0,
        net_roi_pct=9.0,
        status="ELIGIBLE",
        reason="fixture",
    )
    return StatisticalQualityAnalyzer.evaluate_and_score(
        breakdown, buy_book=book, sell_book=sell
    )


def test_nan_gross_spread_is_not_a_paper_execute():
    nan = _score(float("nan"))
    inf = _score(float("inf"))
    flag = _score(True)
    clean = _score(10.0)
    heavy = _score(10.0, slippage=5.0)
    assert (
        "NON_FINITE_GROSS" in nan.data_quality_flags,
        nan.heuristic_recommendation,
        nan.confidence_tier,
        "NON_FINITE_GROSS" in inf.data_quality_flags,
        inf.heuristic_recommendation,
        "NON_FINITE_GROSS" in flag.data_quality_flags,
        flag.heuristic_recommendation,
        clean.heuristic_recommendation,
        clean.confidence_tier,
        "NON_FINITE_GROSS" in clean.data_quality_flags,
        "HIGH_SLIPPAGE_DRAG" in heavy.data_quality_flags,
        "NON_FINITE_GROSS" in heavy.data_quality_flags,
        heavy.heuristic_recommendation,
    ) == (
        True,
        "DISCARD",
        "REJECTED",
        True,
        "DISCARD",
        True,
        "DISCARD",
        "EXECUTE_IN_PAPER_MODE",
        "HIGH",
        False,
        True,
        False,
        "OBSERVE_OR_REDUCE_SIZE",
    )
