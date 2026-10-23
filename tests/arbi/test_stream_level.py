from courier_core.arbi.models import NormalizedPair, OrderbookLevel
from courier_core.arbi.stream import L2DeltaEvent, L2OrderbookBookkeeper


def _seen(price, amount):
    pair = NormalizedPair("BTC", "EUR")
    book = L2OrderbookBookkeeper("binance", pair)
    try:
        book.apply_delta(
            L2DeltaEvent(
                exchange="binance",
                pair=pair,
                bids_updated=[OrderbookLevel(price, amount)],
                asks_updated=[],
                timestamp_utc="2026-10-18T12:00:01Z",
                sequence_id=1,
            )
        )
    except ValueError as exc:
        return ("raised", str(exc), [(level.price, level.amount) for level in book.to_snapshot().bids])
    return ("accepted", [(level.price, level.amount) for level in book.to_snapshot().bids])


def test_nan_level_does_not_enter_the_book():
    assert (
        _seen(100.0, float("nan")),
        _seen(100.0, float("inf")),
        _seen(float("nan"), 1.0),
        _seen(100.0, 1.5),
    ) == (
        ("raised", "amount is not a number.", []),
        ("raised", "amount is not a number.", []),
        ("raised", "price is not a number.", []),
        ("accepted", [(100.0, 1.5)]),
    )
