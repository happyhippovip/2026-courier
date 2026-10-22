from courier_core.arbi.strategies import ArbitrageStrategies


def _cycle(**overrides):
    values = {
        "exchange": "binance",
        "price_a_b": 60000.0,
        "price_b_c": 0.05,
        "price_c_a": 3100.0,
        "capital_usd": 100.0,
        "taker_fee_pct": 0.10,
    }
    values.update(overrides)
    return ArbitrageStrategies.evaluate_triangular_arbitrage(**values)


def test_nan_triangular_price_is_not_a_negative_net():
    nan = _cycle(price_a_b=float("nan"))
    inf = _cycle(price_a_b=float("inf"))
    finite = _cycle()
    assert (
        nan.status,
        "nan" in nan.reason.lower(),
        inf.status,
        "nan" in inf.reason.lower(),
        finite.status,
        finite.output_capital_usd > 100.0,
        finite.net_roi_pct > 0.0,
    ) == (
        "BLOCKED_INVALID_PRICE",
        False,
        "BLOCKED_INVALID_PRICE",
        False,
        "ELIGIBLE",
        True,
        True,
    )
