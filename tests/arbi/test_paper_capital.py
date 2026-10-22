import math

from courier_core.arbi.paper_trading import PaperTradingEngine


def _open(value):
    try:
        engine = PaperTradingEngine(initial_capital_usd=value, simulated_venues=["binance", "kraken"])
    except ValueError as exc:
        return ("raised", str(exc), None)
    total = engine.total_portfolio_usd
    return ("accepted", engine.initial_capital_usd, total)


def test_nan_capital_is_not_a_portfolio():
    nan = _open(float("nan"))
    inf = _open(float("inf"))
    finite = _open(100.0)
    assert (
        nan[0],
        nan[1],
        isinstance(nan[2], float) and math.isnan(nan[2]),
        inf[0],
        inf[1],
        isinstance(inf[2], float) and math.isinf(inf[2]),
        finite[0],
        finite[1],
        finite[2],
    ) == (
        "raised",
        "virtual capital is not a number.",
        False,
        "raised",
        "virtual capital is not a number.",
        False,
        "accepted",
        100.0,
        100.0,
    )
