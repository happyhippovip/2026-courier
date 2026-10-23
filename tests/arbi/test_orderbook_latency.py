from courier_core.arbi.analyzer import StatisticalQualityAnalyzer
from courier_core.arbi.models import NormalizedPair, OrderbookLevel, OrderbookSnapshot


def _flags(latency):
    book = OrderbookSnapshot(
        exchange="binance",
        pair=NormalizedPair("BTC", "USDT"),
        bids=[OrderbookLevel(price=100.0, amount=1.0)],
        asks=[OrderbookLevel(price=101.0, amount=1.0)],
        timestamp_utc="2026-10-18T12:00:00Z",
        latency_ms=latency,
    )
    return StatisticalQualityAnalyzer.audit_orderbook_integrity(book)


def test_nan_latency_is_not_a_healthy_book():
    nan = _flags(float("nan"))
    inf = _flags(float("inf"))
    flag = _flags(True)
    high = _flags(2000.0)
    ok = _flags(10.0)
    assert (
        "NON_FINITE_LATENCY" in nan,
        "HIGH_NETWORK_LATENCY" in nan,
        "NON_FINITE_LATENCY" in inf,
        "HIGH_NETWORK_LATENCY" in inf,
        "NON_FINITE_LATENCY" in flag,
        "HIGH_NETWORK_LATENCY" in high,
        "NON_FINITE_LATENCY" in ok,
        "HIGH_NETWORK_LATENCY" in ok,
        "NON_FINITE_PRICE" in ok,
    ) == (
        True,
        False,
        True,
        False,
        True,
        True,
        False,
        False,
        False,
    )
