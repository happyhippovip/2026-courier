from courier_core.arbi.models import NormalizedPair
from courier_core.arbi.net_profit import NetProfitBreakdown
from courier_core.arbi.paper_trading import PaperTradingEngine


def _breakdown(gross):
    return NetProfitBreakdown(
        pair=NormalizedPair("ETH", "USDT"),
        buy_exchange="binance",
        sell_exchange="kraken",
        order_size_usd=10.0,
        best_ask_price=101.0,
        best_bid_price=100.0,
        effective_buy_price=101.0,
        effective_sell_price=100.0,
        gross_spread_pct=1.0,
        gross_spread_usd=gross,
        buy_fee_usd=0.1,
        sell_fee_usd=0.1,
        slippage_usd=0.05,
        transfer_cost_usd=0.0,
        rebalance_cost_usd=0.0,
        total_costs_usd=0.25,
        net_profit_usd=0.75,
        net_roi_pct=7.5,
        status="ELIGIBLE",
        reason="fixture",
    )


def _attempt(gross):
    engine = PaperTradingEngine(initial_capital_usd=100.0, simulated_venues=["binance", "kraken"])
    try:
        record = engine.execute_paper_arbitrage(_breakdown(gross))
    except ValueError as exc:
        return (
            "raised",
            str(exc),
            None,
            engine.total_portfolio_usd,
            len(engine.trade_history),
        )
    return (
        "filled",
        record.execution_status,
        record.net_pnl_usd,
        engine.total_portfolio_usd,
        len(engine.trade_history),
    )


def test_nan_gross_does_not_fill():
    assert (
        _attempt(float("nan")),
        _attempt(float("inf")),
        _attempt(True),
        _attempt(1.0),
    ) == (
        ("raised", "gross spread is not a number.", None, 100.0, 0),
        ("raised", "gross spread is not a number.", None, 100.0, 0),
        ("raised", "Bool is not a number.", None, 100.0, 0),
        ("filled", "FULL_SUCCESS", 0.75, 100.75, 1),
    )
