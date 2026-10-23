from courier_core.arbi.models import NormalizedPair, OrderbookLevel
from courier_core.arbi.stream import L2DeltaEvent, L2OrderbookBookkeeper


def _erase(amount):
    pair = NormalizedPair("BTC", "EUR")
    book = L2OrderbookBookkeeper("binance", pair)
    book.apply_delta(
        L2DeltaEvent(
            exchange="binance",
            pair=pair,
            bids_updated=[OrderbookLevel(100.0, 1.5)],
            asks_updated=[],
            timestamp_utc="2026-10-18T12:00:01Z",
            sequence_id=1,
        )
    )
    try:
        book.apply_delta(
            L2DeltaEvent(
                exchange="binance",
                pair=pair,
                bids_updated=[OrderbookLevel(100.0, amount)],
                asks_updated=[],
                timestamp_utc="2026-10-18T12:00:02Z",
                sequence_id=2,
            )
        )
    except ValueError as exc:
        return (
            "raised",
            str(exc),
            [(level.price, level.amount) for level in book.to_snapshot().bids],
        )
    return ("accepted", [(level.price, level.amount) for level in book.to_snapshot().bids])


def test_negative_level_amount_does_not_erase_the_book():
    assert (
        _erase(-1.0),
        _erase(0.0),
    ) == (
        ("raised", "amount is out of range.", [(100.0, 1.5)]),
        ("accepted", []),
    )
