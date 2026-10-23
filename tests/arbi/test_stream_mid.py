from courier_core.arbi.models import NormalizedPair
from courier_core.arbi.stream import L2StreamMockFeeder


def _emit(mid):
    pair = NormalizedPair("BTC", "EUR")
    try:
        feeder = L2StreamMockFeeder(pair, initial_mid=mid)
        events = list(feeder.generate_events(count=1))
    except ValueError as exc:
        return ("raised", str(exc))
    price = events[0].bids_updated[0].price if events else None
    return ("emitted", price)


def test_nan_mid_does_not_emit_a_price():
    assert (
        _emit(float("nan")),
        _emit(float("inf")),
        _emit(60000.0),
    ) == (
        ("raised", "mid is not a number."),
        ("raised", "mid is not a number."),
        ("emitted", 60000.0),
    )
