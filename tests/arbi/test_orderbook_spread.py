import math

from courier_core.arbi.models import NormalizedPair, OrderbookLevel, OrderbookSnapshot


def _spread(bid, ask):
    book = OrderbookSnapshot(
        exchange="binance",
        pair=NormalizedPair("BTC", "USDT"),
        bids=[OrderbookLevel(price=bid, amount=10.0)],
        asks=[OrderbookLevel(price=ask, amount=10.0)],
        timestamp_utc="2026-10-18T12:00:00Z",
    )
    return book.spread_bps


def _non_finite(value):
    return isinstance(value, float) and (math.isnan(value) or math.isinf(value))


def test_nan_spread_is_not_a_number():
    nan_bid = _spread(float("nan"), 101.0)
    nan_ask = _spread(100.0, float("nan"))
    inf_ask = _spread(100.0, float("inf"))
    finite = _spread(100.0, 101.0)
    zero = _spread(0.0, 0.0)
    assert (
        nan_bid is None,
        _non_finite(nan_bid),
        nan_ask is None,
        _non_finite(nan_ask),
        inf_ask is None,
        _non_finite(inf_ask),
        finite,
        zero is None,
    ) == (
        True,
        False,
        True,
        False,
        True,
        False,
        ((101.0 - 100.0) / 101.0) * 10000.0,
        True,
    )
