from courier_core.arbi.models import NormalizedPair, OrderbookLevel
from courier_core.arbi.stream import L2DeltaEvent, L2OrderbookBookkeeper


def _send(pair):
    book_pair = NormalizedPair("BTC", "EUR")
    book = L2OrderbookBookkeeper("binance", book_pair)

    def apply(sequence, amount, event_pair):
        book.apply_delta(
            L2DeltaEvent(
                exchange="binance",
                pair=event_pair,
                bids_updated=[OrderbookLevel(100.0, amount)],
                asks_updated=[],
                timestamp_utc="2026-10-18T12:00:02Z",
                sequence_id=sequence,
            )
        )

    apply(5, 1.5, book_pair)
    try:
        apply(6, 9.0, pair)
    except ValueError as exc:
        return ("raised", str(exc), book.bids.get(100.0), book.last_sequence)
    return ("applied", book.bids.get(100.0), book.last_sequence)


def test_foreign_pair_event_is_not_dropped():
    assert (
        _send(NormalizedPair("ETH", "EUR")),
        _send(NormalizedPair("BTC", "EUR")),
    ) == (
        ("raised", "event is for another book.", 1.5, 5),
        ("applied", 9.0, 6),
    )
