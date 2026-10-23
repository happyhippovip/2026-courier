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
        )
    except Exception as exc:
        return ("crashed", type(exc).__name__, book.bids.get(100.0), book.last_sequence)
    return ("applied", book.bids.get(100.0), book.last_sequence)


def test_non_text_stream_timestamp_does_not_apply():
    assert (
        _stamp(None),
        _stamp(True),
        _stamp("2026-10-18T12:00:03Z"),
    ) == (
        ("raised", "timestamp is not a time.", 1.5, 5),
        ("raised", "Bool is not a number.", 1.5, 5),
        ("applied", 9.0, 6),
    )
