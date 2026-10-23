from courier_core.arbi.models import NormalizedPair, OrderbookLevel
from courier_core.arbi.stream import L2DeltaEvent, L2OrderbookBookkeeper


def _open(stamp):
    pair = NormalizedPair("BTC", "EUR")
    book = L2OrderbookBookkeeper("binance", pair)
    try:
        book.apply_delta(
            L2DeltaEvent(
                exchange="binance",
                pair=pair,
                bids_updated=[OrderbookLevel(100.0, 1.5)],
                asks_updated=[],
                timestamp_utc=stamp,
                sequence_id=5,
            )
        )
    except ValueError as exc:
        return ("raised", str(exc), book.bids.get(100.0), book.last_sequence)
    return ("applied", book.bids.get(100.0), book.last_sequence)


def test_first_stream_timestamp_must_be_text():
    assert (
        _open(None),
        _open(""),
        _open(True),
        _open("2026-10-18T12:00:02Z"),
    ) == (
        ("raised", "timestamp is not a time.", None, 0),
        ("raised", "timestamp is not a time.", None, 0),
        ("raised", "Bool is not a number.", None, 0),
        ("applied", 1.5, 5),
    )
