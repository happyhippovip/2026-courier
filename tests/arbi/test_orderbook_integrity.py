from courier_core.arbi.analyzer import StatisticalQualityAnalyzer
from courier_core.arbi.models import NormalizedPair, OrderbookLevel, OrderbookSnapshot


def _flags(bid, ask):
    book = OrderbookSnapshot(
        exchange="binance",
        pair=NormalizedPair("BTC", "USDT"),
        bids=[OrderbookLevel(price=bid, amount=1.0)],
        asks=[OrderbookLevel(price=ask, amount=1.0)],
        timestamp_utc="2026-10-18T12:00:00Z",
    )
    return StatisticalQualityAnalyzer.audit_orderbook_integrity(book)


def test_nan_quote_is_not_a_clean_book():
    nan_bid = _flags(float("nan"), 101.0)
    inf_ask = _flags(100.0, float("inf"))
    finite = _flags(100.0, 101.0)
    crossed = _flags(3000.0, 2900.0)
    assert (
        "NON_FINITE_PRICE" in nan_bid,
        "CROSSED_INTERNAL_ORDERBOOK" in nan_bid,
        "NON_FINITE_PRICE" in inf_ask,
        "NON_FINITE_PRICE" in finite,
        "CROSSED_INTERNAL_ORDERBOOK" in finite,
        "NON_FINITE_PRICE" in crossed,
        "CROSSED_INTERNAL_ORDERBOOK" in crossed,
    ) == (
        True,
        False,
        True,
        False,
        False,
        False,
        True,
    )
