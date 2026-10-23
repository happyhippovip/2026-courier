from courier_core.arbi.models import NormalizedPair, OrderbookLevel
from courier_core.arbi.stream import L2DeltaEvent, L2OrderbookBookkeeper


def _stamp(second_stamp):
    pair = NormalizedPair("BTC", "EUR")
    book = L2OrderbookBookkeeper("binance", pair)

    def apply(sequence, amount, stamp):
        book.apply_delta(
            L2DeltaEvent(
                exchange="binance",
                pair=pair,
                bids_updated=[OrderbookLevel(100.0, amount)],
                asks_updated=[],
                timestamp_utc=stamp,
                sequence_id=sequence,
            )
        )

    apply(5, 1.5, "2026-10-18T12:00:02Z")
    try:
        apply(6, 9.0, second_stamp)
    except ValueError as exc:
        return (
            "raised",
            str(exc),
            book.bids.get(100.0),
            book.last_sequence,
            book.last_update_utc,
        )
    return ("applied", book.bids.get(100.0), book.last_sequence, book.last_update_utc)


def test_older_stream_timestamp_does_not_apply():
    assert (
        _stamp("2026-10-18T12:00:01Z"),
        _stamp("2026-10-18T12:00:02Z"),
    ) == (
        ("raised", "timestamp is stale.", 1.5, 5, "2026-10-18T12:00:02Z"),
        ("applied", 9.0, 6, "2026-10-18T12:00:02Z"),
    )
