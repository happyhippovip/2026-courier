from courier_core.arbi.models import NormalizedPair, OrderbookLevel
from courier_core.arbi.stream import L2DeltaEvent, L2OrderbookBookkeeper


def _open(asks):
    pair = NormalizedPair("BTC", "EUR")
    book = L2OrderbookBookkeeper("binance", pair)
    try:
        book.apply_delta(
            L2DeltaEvent(
                exchange="binance",
                pair=pair,
                bids_updated=[OrderbookLevel(100.0, 1.5)],
                asks_updated=asks,
                timestamp_utc="2026-10-18T12:00:02Z",
                sequence_id=5,
            )
        )
    except ValueError as exc:
        return ("raised", str(exc), book.bids.get(100.0), book.last_sequence)
    except Exception as exc:
        return ("crashed", type(exc).__name__, book.bids.get(100.0), book.last_sequence)
    return ("applied", book.bids.get(100.0), book.last_sequence)


def test_missing_ask_levels_do_not_open_the_book():
    assert (
        _open(None),
        _open([]),
    ) == (
        ("raised", "levels are not a list.", None, 0),
        ("applied", 1.5, 5),
    )
