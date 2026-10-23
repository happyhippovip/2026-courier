from courier_core.arbi.analyzer import StatisticalQualityAnalyzer
from courier_core.arbi.models import NormalizedPair, OrderbookLevel, OrderbookSnapshot
from courier_core.arbi.net_profit import NetProfitBreakdown


def _score(latency):
    pair = NormalizedPair("ETH", "USDT")
    book = OrderbookSnapshot(
        exchange="binance",
        pair=pair,
        bids=[OrderbookLevel(100.0, 1.0)],
        asks=[OrderbookLevel(101.0, 1.0)],
        timestamp_utc="2026-10-18T12:00:00Z",
        latency_ms=latency,
    )
    sell = OrderbookSnapshot(
        exchange="okx",
        pair=pair,
        bids=[OrderbookLevel(100.0, 1.0)],
        asks=[OrderbookLevel(101.0, 1.0)],
        timestamp_utc="2026-10-18T12:00:00Z",
        latency_ms=latency,
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
        gross_spread_usd=10.0,
        buy_fee_usd=0.1,
        sell_fee_usd=0.1,
        slippage_usd=0.1,
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


def test_negative_book_latency_is_not_a_paper_execute():
    neg = _score(-5.0)
    clean = _score(10.0)
    assert (
        "NEGATIVE_LATENCY" in neg.data_quality_flags,
        neg.heuristic_recommendation,
        neg.confidence_tier,
        "NEGATIVE_LATENCY" in clean.data_quality_flags,
        clean.heuristic_recommendation,
    ) == (
        True,
        "DISCARD",
        "REJECTED",
        False,
        "EXECUTE_IN_PAPER_MODE",
    )
