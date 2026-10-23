from courier_core.arbi.models import NormalizedPair, OrderbookLevel
from courier_core.arbi.stream import L2DeltaEvent, L2OrderbookBookkeeper


def _repeat():
    pair = NormalizedPair("BTC", "EUR")
    book = L2OrderbookBookkeeper("binance", pair)

    def apply(sequence, amount):
        book.apply_delta(
            L2DeltaEvent(
                exchange="binance",
                pair=pair,
                bids_updated=[OrderbookLevel(100.0, amount)],
                asks_updated=[],
                timestamp_utc="2026-10-18T12:00:01Z",
                sequence_id=sequence,
            )
        )

    apply(5, 1.5)
    try:
        apply(5, 9.0)
    except ValueError as exc:
        return ("raised", str(exc), book.bids.get(100.0), book.last_sequence)
    return ("applied", book.bids.get(100.0), book.last_sequence)


def test_duplicate_stream_sequence_does_not_rewrite_the_book():
    assert _repeat() == ("raised", "sequence is stale.", 1.5, 5)
