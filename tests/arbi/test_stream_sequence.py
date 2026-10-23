import math

from courier_core.arbi.models import NormalizedPair, OrderbookLevel
from courier_core.arbi.stream import L2DeltaEvent, L2OrderbookBookkeeper


def _apply(sequence):
    pair = NormalizedPair("BTC", "USDT")
    book = L2OrderbookBookkeeper("binance", pair)
    event = L2DeltaEvent(
        exchange="binance",
        pair=pair,
        bids_updated=[OrderbookLevel(100.0, 1.5)],
        asks_updated=[],
        timestamp_utc="2026-10-18T12:00:00Z",
        sequence_id=sequence,
    )
    try:
        book.apply_delta(event)
    except ValueError as exc:
        return ("raised", str(exc), book.bids.get(100.0), book.last_sequence)
    stored = book.last_sequence
    if isinstance(stored, float) and math.isnan(stored):
        stored = "nan"
    return ("applied", book.bids.get(100.0), stored)


def test_nan_stream_sequence_does_not_change_the_book():
    assert (
        _apply(float("nan")),
        _apply(float("inf")),
        _apply(True),
        _apply(7),
    ) == (
        ("raised", "sequence is not a number.", None, 0),
        ("raised", "sequence is not a number.", None, 0),
        ("raised", "Bool is not a number.", None, 0),
        ("applied", 1.5, 7),
    )
