from courier_core.arbi.models import NormalizedPair, OrderbookLevel
from courier_core.arbi.stream import L2DeltaEvent, L2OrderbookBookkeeper


def _open(bids):
    pair = NormalizedPair("BTC", "EUR")
    book = L2OrderbookBookkeeper("binance", pair)
    try:
        book.apply_delta(
            L2DeltaEvent(
                exchange="binance",
                pair=pair,
                bids_updated=bids,
                asks_updated=[],
                timestamp_utc="2026-10-18T12:00:02Z",
                sequence_id=5,
            )
        )
    except ValueError as exc:
        return (
            "raised",
            str(exc),
            book.bids.get(100.0),
            book.bids.get(101.0),
            book.last_sequence,
        )
    return ("applied", book.bids.get(100.0), book.bids.get(101.0), book.last_sequence)


def test_a_later_bad_level_does_not_keep_the_earlier_quote():
    assert (
        _open([OrderbookLevel(100.0, 1.5), OrderbookLevel(-1.0, 2.0)]),
        _open([OrderbookLevel(100.0, 1.5), OrderbookLevel(101.0, 2.0)]),
    ) == (
        ("raised", "price is out of range.", None, None, 0),
        ("applied", 1.5, 2.0, 5),
    )
