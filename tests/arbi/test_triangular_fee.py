from courier_core.arbi.strategies import ArbitrageStrategies


def _cycle(fee):
    try:
        opp = ArbitrageStrategies.evaluate_triangular_arbitrage(
            exchange="binance",
            price_a_b=60000.0,
            price_b_c=0.05,
            price_c_a=3100.0,
            capital_usd=100.0,
            taker_fee_pct=fee,
        )
    except Exception as exc:
        return ("crashed", type(exc).__name__)
    return (opp.status, opp.net_roi_pct)


def test_negative_triangular_fee_is_not_eligible():
    assert (
        _cycle(-1.0),
        _cycle(-0.1),
        _cycle(0.0),
        _cycle(0.1),
    ) == (
        ("BLOCKED_INVALID_PRICE", 0.0),
        ("BLOCKED_INVALID_PRICE", 0.0),
        ("ELIGIBLE", 3.3333),
        ("ELIGIBLE", 3.0236),
    )
