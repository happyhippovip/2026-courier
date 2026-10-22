from courier_core.arbi.analyzer import StatisticalQualityAnalyzer
from courier_core.arbi.models import NormalizedPair, OrderbookLevel, OrderbookSnapshot


def _stale(flag):
    book = OrderbookSnapshot(
        exchange="binance",
        pair=NormalizedPair("BTC", "USDT"),
        bids=[OrderbookLevel(price=100.0, amount=1.0)],
        asks=[OrderbookLevel(price=101.0, amount=1.0)],
        timestamp_utc="2026-10-18T12:00:00Z",
        latency_ms=10.0,
        is_stale=flag,
    )
    return "STALE_DATA_TIMESTAMP" in StatisticalQualityAnalyzer.audit_orderbook_integrity(book)


def test_text_false_stale_is_not_stale():
    assert (
        _stale("false"),
        _stale("0"),
        _stale(False),
        _stale(True),
        _stale(1),
    ) == (
        False,
        False,
        False,
        True,
        False,
    )
