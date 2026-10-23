"""Tests for L2 WebSocket Stream Provider Protocol and Bookkeeper."""

from courier_core.arbi.models import NormalizedPair, OrderbookLevel
from courier_core.arbi.stream import L2DeltaEvent, L2OrderbookBookkeeper, L2StreamMockFeeder


def test_l2_bookkeeper_delta_application():
    pair = NormalizedPair("BTC", "EUR")
    bookkeeper = L2OrderbookBookkeeper(exchange="binance", pair=pair)

    # Initial levels
    event1 = L2DeltaEvent(
        exchange="binance",
        pair=pair,
        bids_updated=[OrderbookLevel(60000.0, 1.0), OrderbookLevel(59990.0, 2.0)],
        asks_updated=[OrderbookLevel(60010.0, 1.0), OrderbookLevel(60020.0, 2.0)],
        timestamp_utc="2026-10-18T12:00:00Z",
        sequence_id=1,
    )
    bookkeeper.apply_delta(event1)
    snap1 = bookkeeper.to_snapshot()
    assert snap1.best_bid == 60000.0
    assert snap1.best_ask == 60010.0

    # Level removal delta (amount 0) and better bid
    event2 = L2DeltaEvent(
        exchange="binance",
        pair=pair,
        bids_updated=[OrderbookLevel(60005.0, 1.5), OrderbookLevel(59990.0, 0.0)],
        asks_updated=[OrderbookLevel(60010.0, 0.0)],
        timestamp_utc="2026-10-18T12:00:01Z",
        sequence_id=2,
    )
    bookkeeper.apply_delta(event2)
    snap2 = bookkeeper.to_snapshot()
    assert snap2.best_bid == 60005.0
    assert snap2.best_ask == 60020.0
    assert len(snap2.bids) == 2  # 60005 and 60000; 59990 was removed


def test_l2_stream_mock_feeder():
    pair = NormalizedPair("BTC", "EUR")
    feeder = L2StreamMockFeeder(pair, initial_mid=65000.0)
    events = list(feeder.generate_events(count=6))

    assert len(events) == 6
    assert events[0].exchange == "binance"
    assert events[1].exchange == "kraken"
    assert events[0].sequence_id == 1
    assert events[5].sequence_id == 6


def test_bool_level_amount_does_not_change_the_book():
    pair = NormalizedPair("BTC", "EUR")
    seen = []
    for amount in (True, False):
        book = L2OrderbookBookkeeper(exchange="binance", pair=pair)
        book.apply_delta(L2DeltaEvent(
            exchange="binance",
            pair=pair,
            bids_updated=[OrderbookLevel(60000.0, 2.0)],
            asks_updated=[OrderbookLevel(60010.0, 2.0)],
            timestamp_utc="2026-10-18T12:00:00Z",
            sequence_id=1,
        ))
        try:
            book.apply_delta(L2DeltaEvent(
                exchange="binance",
                pair=pair,
                bids_updated=[OrderbookLevel(60000.0, amount)],
                asks_updated=[],
                timestamp_utc="2026-10-18T12:00:01Z",
                sequence_id=2,
            ))
        except ValueError as exc:
            seen.append(("raised", str(exc), book.bids.get(60000.0)))
        else:
            seen.append(("accepted", book.bids.get(60000.0)))
    assert seen == [
        ("raised", "Bool is not a number.", 2.0),
        ("raised", "Bool is not a number.", 2.0),
    ], seen


def test_bool_stream_count_and_mid_are_not_numbers():
    pair = NormalizedPair("BTC", "EUR")
    seen = []
    for count in (True, False):
        feeder = L2StreamMockFeeder(pair, initial_mid=65000.0)
        try:
            events = list(feeder.generate_events(count=count))
        except ValueError as exc:
            seen.append(("count", count, "raised", str(exc)))
        else:
            seen.append(("count", count, "accepted", len(events)))
    try:
        feeder = L2StreamMockFeeder(pair, initial_mid=True)
        events = list(feeder.generate_events(count=1))
    except ValueError as exc:
        seen.append(("mid", "raised", str(exc)))
    else:
        price = events[0].bids_updated[0].price if events else None
        seen.append(("mid", "accepted", price))
    assert seen == [
        ("count", True, "raised", "Bool is not a number."),
        ("count", False, "raised", "Bool is not a number."),
        ("mid", "raised", "Bool is not a number."),
    ], seen
