from courier_core.arbi.strategies import ArbitrageStrategies


def _cycle(**overrides):
    kwargs = dict(
        price_a_b=60000.0,
        price_b_c=0.05,
        price_c_a=3100.0,
        capital_usd=100.0,
        taker_fee_pct=0.1,
    )
    kwargs.update(overrides)
    try:
        opp = ArbitrageStrategies.evaluate_triangular_arbitrage("binance", **kwargs)
    except Exception as exc:
        return ("crashed", type(exc).__name__)
    return (opp.status, opp.net_roi_pct)


def test_nonpositive_triangular_price_is_not_a_cycle():
    assert (
        _cycle(price_a_b=0),
        _cycle(price_b_c=0),
        _cycle(price_c_a=0),
        _cycle(capital_usd=0),
        _cycle(price_a_b=-60000.0),
        _cycle(),
    ) == (
        ("BLOCKED_INVALID_PRICE", 0.0),
        ("BLOCKED_INVALID_PRICE", 0.0),
        ("BLOCKED_INVALID_PRICE", 0.0),
        ("BLOCKED_INVALID_PRICE", 0.0),
        ("BLOCKED_INVALID_PRICE", 0.0),
        ("ELIGIBLE", 3.0236),
    )
