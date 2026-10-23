from courier_core.arbi.models import NormalizedPair
from courier_core.arbi.net_profit import NetProfitBreakdown
from courier_core.arbi.paper_trading import PaperTradingEngine


def _fill(rebalance):
    breakdown = NetProfitBreakdown(
        pair=NormalizedPair("ETH", "USDT"),
        buy_exchange="binance",
        sell_exchange="kraken",
        order_size_usd=10.0,
        best_ask_price=101.0,
        best_bid_price=100.0,
        effective_buy_price=101.0,
        effective_sell_price=100.0,
        gross_spread_pct=1.0,
        gross_spread_usd=1.0,
        buy_fee_usd=0.1,
        sell_fee_usd=0.1,
        slippage_usd=0.05,
        transfer_cost_usd=0.0,
        rebalance_cost_usd=rebalance,
        total_costs_usd=0.25,
        net_profit_usd=0.75,
        net_roi_pct=7.5,
        status="ELIGIBLE",
        reason="fixture",
    )
    engine = PaperTradingEngine(initial_capital_usd=100.0, simulated_venues=["binance", "kraken"])
    record = engine.execute_paper_arbitrage(breakdown)
    return (record.fees_usd, record.net_pnl_usd, record.gross_spread_usd)


def test_recorded_fees_include_the_rebalance():
    assert (
        _fill(5.0),
        _fill(0.0),
    ) == (
        (5.2, -4.25, 1.0),
        (0.2, 0.75, 1.0),
    )
