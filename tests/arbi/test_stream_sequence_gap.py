from courier_core.arbi.models import NormalizedPair, OrderbookLevel
from courier_core.arbi.stream import L2DeltaEvent, L2OrderbookBookkeeper


def _jump(first, second, amount):
    pair = NormalizedPair("BTC", "EUR")
    book = L2OrderbookBookkeeper("binance", pair)

    def apply(sequence, size):
        book.apply_delta(
            L2DeltaEvent(
                exchange="binance",
                pair=pair,
                bids_updated=[OrderbookLevel(100.0, size)],
                asks_updated=[],
                timestamp_utc="2026-10-18T12:00:01Z",
                sequence_id=sequence,
            )
        )

    apply(first, 1.5)
    try:
        apply(second, amount)
    except ValueError as exc:
        return ("raised", str(exc), book.bids.get(100.0), book.last_sequence)
    return ("applied", book.bids.get(100.0), book.last_sequence)


def test_gapped_stream_sequence_does_not_apply():
    assert (
        _jump(5, 7, 9.0),
        _jump(5, 6, 9.0),
    ) == (
        ("raised", "sequence is gapped.", 1.5, 5),
        ("applied", 9.0, 6),
    )
