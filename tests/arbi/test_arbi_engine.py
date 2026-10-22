"""Tests for Courier Symphony Arbi Bronze Engine.

Covers:
- False-positive spreads (fees > spread)
- Incomplete/stale orderbooks
- Depth-based slippage calculation
- Multi-exchange symbol mapping (Binance, Bybit, OKX)
- Paper trading virtual bankrolls & partial fill handling
- Triangular arbitrage execution
- Deterministic AI quality & risk scoring
"""

import pytest
from courier_core.arbi.models import (
    ExchangeFeeSchedule,
    NormalizedPair,
    OrderbookLevel,
    OrderbookSnapshot,
    SymbolMapper,
)
from courier_core.arbi.net_profit import NetProfitBreakdown, NetProfitEngine
from courier_core.arbi.paper_trading import PaperTradingEngine
from courier_core.arbi.strategies import ArbitrageStrategies
from courier_core.arbi.analyzer import StatisticalQualityAnalyzer


def _mock_book(exchange: str, pair: NormalizedPair, best_bid: float, best_ask: float, depth: float = 1.0) -> OrderbookSnapshot:
    bids = [
        OrderbookLevel(price=best_bid, amount=depth),
        OrderbookLevel(price=best_bid * 0.999, amount=depth * 2),
    ]
    asks = [
        OrderbookLevel(price=best_ask, amount=depth),
        OrderbookLevel(price=best_ask * 1.001, amount=depth * 2),
    ]
    return OrderbookSnapshot(
        exchange=exchange,
        pair=pair,
        bids=bids,
        asks=asks,
        timestamp_utc="2026-10-18T12:00:00Z",
        latency_ms=25.0,
    )


def test_symbol_mapper_consistency():
    pair = NormalizedPair("BTC", "USDT")
    assert SymbolMapper.to_exchange_symbol("binance", pair) == "BTCUSDT"
    assert SymbolMapper.to_exchange_symbol("kraken", pair) == "XBTUSDT"
    assert SymbolMapper.to_exchange_symbol("bybit", pair) == "BTCUSDT"
    assert SymbolMapper.to_exchange_symbol("okx", pair) == "BTC-USDT"

    pair_eur = NormalizedPair("BTC", "EUR")
    assert SymbolMapper.to_exchange_symbol("kraken", pair_eur) == "XBTEUR"
    assert SymbolMapper.from_exchange_symbol("kraken", "XBTEUR") == pair_eur
    assert SymbolMapper.from_exchange_symbol("kraken", "XXBTZEUR") == pair_eur

    assert SymbolMapper.from_exchange_symbol("binance", "BTCUSDT") == pair
    assert SymbolMapper.from_exchange_symbol("okx", "BTC-USDT") == pair
    assert SymbolMapper.from_exchange_symbol("bybit", "ETHUSDC") == NormalizedPair("ETH", "USDC")


def test_binance_kraken_two_way_arbitrage():
    # Test Binance -> Kraken and Kraken -> Binance calculations
    pair = NormalizedPair("BTC", "EUR")
    binance_book = _mock_book("binance", pair, best_bid=60000.0, best_ask=60050.0, depth=5.0)
    kraken_book = _mock_book("kraken", pair, best_bid=60300.0, best_ask=60350.0, depth=5.0)

    # Direction 1: Buy Binance (60,050), Sell Kraken (60,300) -> Spread ~ +0.416%
    # Taker fees: Binance 0.10%, Kraken 0.26% = 0.36% total -> Net positive
    bd1 = NetProfitEngine.evaluate_opportunity(pair, binance_book, kraken_book, order_size_usd=100.0)
    assert bd1.status == "ELIGIBLE"
    assert bd1.net_profit_usd > 0
    assert bd1.buy_exchange == "binance"
    assert bd1.sell_exchange == "kraken"

    # Direction 2: Buy Kraken (60,350), Sell Binance (60,000) -> Negative spread
    bd2 = NetProfitEngine.evaluate_opportunity(pair, kraken_book, binance_book, order_size_usd=100.0)
    assert bd2.status == "BLOCKED_NEGATIVE_NET"
    assert bd2.net_profit_usd < 0


def test_bool_order_size_is_not_one_dollar():
    pair = NormalizedPair("BTC", "EUR")
    buy = _mock_book("binance", pair, best_bid=60000.0, best_ask=60050.0, depth=5.0)
    sell = _mock_book("kraken", pair, best_bid=60300.0, best_ask=60350.0, depth=5.0)
    seen = []
    for size in (True, False):
        try:
            bd = NetProfitEngine.evaluate_opportunity(pair, buy, sell, order_size_usd=size)
        except ValueError as exc:
            seen.append(("raised", str(exc)))
        except Exception as exc:
            seen.append((type(exc).__name__, str(exc)))
        else:
            seen.append(("accepted", bd.order_size_usd, bd.status, bd.net_profit_usd))
    try:
        walked = NetProfitEngine.calculate_effective_price_and_slippage(buy.asks, True, is_buy=True)
    except ValueError as exc:
        walked = ("raised", str(exc))
    seen.append(walked)
    assert seen == [
        ("raised", "Bool is not a number."),
        ("raised", "Bool is not a number."),
        ("raised", "Bool is not a number."),
    ], seen


def test_bool_quote_is_not_one_dollar():
    pair = NormalizedPair("BTC", "EUR")
    buy = _mock_book("binance", pair, best_bid=60000.0, best_ask=60050.0, depth=5.0)
    sell = _mock_book("kraken", pair, best_bid=60300.0, best_ask=60350.0, depth=5.0)
    buy.asks[0] = OrderbookLevel(True, 5.0)
    sell.bids[0] = OrderbookLevel(True, 5.0)
    try:
        breakdown = NetProfitEngine.evaluate_opportunity(pair, buy, sell, order_size_usd=100.0)
    except ValueError as exc:
        seen = ("raised", str(exc))
    else:
        seen = (
            "accepted",
            breakdown.best_ask_price,
            breakdown.best_bid_price,
            breakdown.status,
            breakdown.net_profit_usd,
        )
    assert seen == ("raised", "Bool is not a number."), seen


def test_bool_fee_is_not_one_percent():
    pair = NormalizedPair("BTC", "USDT")
    buy = _mock_book("binance", pair, best_bid=64950.0, best_ask=65000.0, depth=10.0)
    sell = _mock_book("bybit", pair, best_bid=65500.0, best_ask=65550.0, depth=10.0)
    seen = []
    schedules = (
        ("taker", ExchangeFeeSchedule("binance", 0.1, True)),
        ("maker", ExchangeFeeSchedule("binance", True, 0.1)),
        ("withdraw", ExchangeFeeSchedule("binance", 0.1, 0.1, withdrawal_fee_usd=True)),
        ("zero", ExchangeFeeSchedule("binance", 0.1, False)),
    )
    for name, sched in schedules:
        try:
            breakdown = NetProfitEngine.evaluate_opportunity(
                pair, buy, sell, order_size_usd=100.0, buy_fee_sched=sched, include_transfer=(name == "withdraw"),
            )
        except ValueError as exc:
            seen.append((name, "raised", str(exc)))
        else:
            seen.append((name, "accepted", breakdown.buy_fee_usd, breakdown.transfer_cost_usd, breakdown.status))
    assert seen == [
        ("taker", "raised", "Bool is not a number."),
        ("maker", "raised", "Bool is not a number."),
        ("withdraw", "raised", "Bool is not a number."),
        ("zero", "raised", "Bool is not a number."),
    ], seen


def test_net_profit_blocks_when_fees_exceed_spread():
    # Binance ask: 65,000 | OKX bid: 65,050
    # Gross spread = 50 USD on 65,000 = ~0.0769%
    # But taker fees (0.10% + 0.10% = 0.20%) = ~130 USD on 65,000
    pair = NormalizedPair("BTC", "USDT")
    buy_book = _mock_book("binance", pair, best_bid=64990.0, best_ask=65000.0, depth=10.0)
    sell_book = _mock_book("okx", pair, best_bid=65050.0, best_ask=65060.0, depth=10.0)

    breakdown = NetProfitEngine.evaluate_opportunity(pair, buy_book, sell_book, order_size_usd=100.0)
    assert breakdown.status == "BLOCKED_NEGATIVE_NET"
    assert breakdown.net_profit_usd < 0
    assert "exceed gross spread" in breakdown.reason


def test_net_profit_allows_viable_spread():
    # Buy at 65,000, sell at 65,500 (+0.769% spread vs 0.20% fees)
    pair = NormalizedPair("BTC", "USDT")
    buy_book = _mock_book("binance", pair, best_bid=64950.0, best_ask=65000.0, depth=10.0)
    sell_book = _mock_book("bybit", pair, best_bid=65500.0, best_ask=65550.0, depth=10.0)

    breakdown = NetProfitEngine.evaluate_opportunity(pair, buy_book, sell_book, order_size_usd=100.0)
    assert breakdown.status == "ELIGIBLE"
    assert breakdown.net_profit_usd > 0
    assert breakdown.net_roi_pct > 0.4


def test_orderbook_slippage_calculation():
    # Ask 1: 100 USD (qty 0.5) -> absorbs 50 USD
    # Ask 2: 110 USD (qty 1.0) -> absorbs next 50 USD
    levels = [
        OrderbookLevel(price=100.0, amount=0.5),
        OrderbookLevel(price=110.0, amount=1.0),
    ]
    eff_price, slippage_usd, ok = NetProfitEngine.calculate_effective_price_and_slippage(levels, target_usd=100.0, is_buy=True)
    assert ok is True
    assert eff_price > 100.0
    assert slippage_usd > 0.0


def test_insufficient_depth_blocks_opportunity():
    pair = NormalizedPair("SOL", "USDT")
    # Book only has 0.1 SOL at 150 = 15 USD total liquidity
    buy_book = _mock_book("binance", pair, best_bid=149.0, best_ask=150.0, depth=0.1)
    sell_book = _mock_book("bybit", pair, best_bid=155.0, best_ask=156.0, depth=10.0)

    breakdown = NetProfitEngine.evaluate_opportunity(pair, buy_book, sell_book, order_size_usd=500.0)
    assert breakdown.status == "BLOCKED_INSUFFICIENT_DEPTH"


def test_paper_trading_virtual_balance_tracking():
    engine = PaperTradingEngine(initial_capital_usd=100.0, simulated_venues=["binance", "bybit"])
    # 50 USD allocated to each venue
    assert engine.virtual_balances["binance"]["USDT"] == 50.0
    assert engine.virtual_balances["bybit"]["USDT"] == 50.0

    pair = NormalizedPair("BTC", "USDT")
    buy_book = _mock_book("binance", pair, best_bid=64950.0, best_ask=65000.0, depth=10.0)
    sell_book = _mock_book("bybit", pair, best_bid=65500.0, best_ask=65550.0, depth=10.0)
    breakdown = NetProfitEngine.evaluate_opportunity(pair, buy_book, sell_book, order_size_usd=20.0)

    rec = engine.execute_paper_arbitrage(breakdown)
    assert rec.execution_status == "FULL_SUCCESS"
    assert rec.net_pnl_usd > 0
    assert engine.total_realized_pnl_usd > 0
    assert engine.win_rate_pct == 100.0


def test_bool_capital_is_not_one_dollar():
    seen = []
    for value in (True, False):
        try:
            engine = PaperTradingEngine(initial_capital_usd=value, simulated_venues=["binance", "kraken"])
        except ValueError as exc:
            seen.append(("raised", str(exc)))
        else:
            seen.append((
                "accepted",
                engine.initial_capital_usd,
                {venue: balances["USDT"] for venue, balances in engine.virtual_balances.items()},
            ))
    assert seen == [
        ("raised", "Bool is not a number."),
        ("raised", "Bool is not a number."),
    ], seen


def test_bool_fill_rate_is_not_a_fraction():
    pair = NormalizedPair("BTC", "USDT")
    breakdown = NetProfitBreakdown(
        pair=pair,
        buy_exchange="binance",
        sell_exchange="kraken",
        order_size_usd=20.0,
        best_ask_price=100.0,
        best_bid_price=101.0,
        effective_buy_price=100.0,
        effective_sell_price=101.0,
        gross_spread_pct=1.0,
        gross_spread_usd=1.0,
        buy_fee_usd=0.1,
        sell_fee_usd=0.1,
        slippage_usd=0.0,
        transfer_cost_usd=0.0,
        rebalance_cost_usd=0.0,
        total_costs_usd=0.2,
        net_profit_usd=0.8,
        net_roi_pct=4.0,
        status="ELIGIBLE",
        reason="test",
    )
    engine = PaperTradingEngine(initial_capital_usd=100.0, simulated_venues=["binance", "kraken"])
    try:
        rec = engine.execute_paper_arbitrage(
            breakdown,
            simulated_latency_ms=True,
            second_leg_fail_rate=True,
            partial_fill_pct=True,
        )
    except ValueError as exc:
        seen = ("raised", str(exc), len(engine.trade_history))
    else:
        seen = (
            "accepted",
            rec.execution_status,
            rec.order_size_usd,
            rec.simulated_latency_ms,
            len(engine.trade_history),
        )
    assert seen == ("raised", "Bool is not a number.", 0), seen


def test_triangular_arbitrage_cycle():
    # USDT -> BTC (60,000) -> ETH (0.05 BTC = 3,000 USD equivalent) -> USDT (3,100)
    tri = ArbitrageStrategies.evaluate_triangular_arbitrage(
        exchange="binance",
        price_a_b=60000.0,
        price_b_c=0.05,
        price_c_a=3100.0,
        capital_usd=100.0,
        taker_fee_pct=0.10,
    )
    assert tri.status == "ELIGIBLE"
    assert tri.output_capital_usd > 100.0
    assert tri.net_roi_pct > 0.0


def test_bool_triangular_inputs_are_not_numbers():
    seen = []
    for kwargs in ({"capital_usd": True}, {"capital_usd": False}, {"taker_fee_pct": True}):
        try:
            tri = ArbitrageStrategies.evaluate_triangular_arbitrage(
                exchange="binance",
                price_a_b=60000.0,
                price_b_c=0.05,
                price_c_a=3100.0,
                **kwargs,
            )
        except ValueError as exc:
            seen.append(("raised", str(exc)))
        except Exception as exc:
            seen.append((type(exc).__name__, str(exc)))
        else:
            seen.append((
                "accepted",
                tri.input_capital_usd,
                tri.total_fees_usd,
                tri.status,
                tri.output_capital_usd,
            ))
    assert seen == [
        ("raised", "Bool is not a number."),
        ("raised", "Bool is not a number."),
        ("raised", "Bool is not a number."),
    ], seen


def test_statistical_quality_scoring_blocks_crossed_book():
    pair = NormalizedPair("ETH", "USDT")
    # Crossed orderbook (bid > ask)
    bad_book = OrderbookSnapshot(
        exchange="binance",
        pair=pair,
        bids=[OrderbookLevel(3000.0, 1.0)],
        asks=[OrderbookLevel(2900.0, 1.0)],
        timestamp_utc="2026-10-18T12:00:00Z",
    )
    flags = StatisticalQualityAnalyzer.audit_orderbook_integrity(bad_book)
    assert "CROSSED_INTERNAL_ORDERBOOK" in flags

    breakdown = NetProfitBreakdown(
        pair=pair, buy_exchange="binance", sell_exchange="okx", order_size_usd=100.0,
        best_ask_price=2900.0, best_bid_price=3000.0, effective_buy_price=2900.0, effective_sell_price=3000.0,
        gross_spread_pct=3.4, gross_spread_usd=3.4, buy_fee_usd=0.1, sell_fee_usd=0.1, slippage_usd=0.0,
        transfer_cost_usd=0.0, rebalance_cost_usd=0.0, total_costs_usd=0.2, net_profit_usd=3.2, net_roi_pct=3.2,
        status="ELIGIBLE", reason="test",
    )
    assessment = StatisticalQualityAnalyzer.evaluate_and_score(breakdown, buy_book=bad_book)
    assert "CROSSED_INTERNAL_ORDERBOOK" in assessment.data_quality_flags
    assert assessment.confidence_tier != "HIGH"
