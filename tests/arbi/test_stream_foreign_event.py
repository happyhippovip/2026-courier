from courier_core.arbi.models import NormalizedPair, OrderbookLevel
from courier_core.arbi.stream import L2DeltaEvent, L2OrderbookBookkeeper


def _send(exchange):
    pair = NormalizedPair("BTC", "EUR")
    book = L2OrderbookBookkeeper("binance", pair)

    def apply(sequence, amount, venue):
        book.apply_delta(
            L2DeltaEvent(
                exchange=venue,
                pair=pair,
                bids_updated=[OrderbookLevel(100.0, amount)],
                asks_updated=[],
                timestamp_utc="2026-10-18T12:00:02Z",
                sequence_id=sequence,
            )
        )

    apply(5, 1.5, "binance")
    try:
        apply(6, 9.0, exchange)
    except ValueError as exc:
        return ("raised", str(exc), book.bids.get(100.0), book.last_sequence)
    return ("applied", book.bids.get(100.0), book.last_sequence)


def test_foreign_exchange_event_is_not_dropped():
    assert (
        _send("kraken"),
        _send("binance"),
    ) == (
        ("raised", "event is for another book.", 1.5, 5),
        ("applied", 9.0, 6),
    )
