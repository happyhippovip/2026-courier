from courier_core.arbi.models import NormalizedPair
from courier_core.arbi.stream import L2StreamMockFeeder


def _events(count):
    feeder = L2StreamMockFeeder(NormalizedPair("BTC", "USDT"), initial_mid=60000.0)
    try:
        events = list(feeder.generate_events(count))
    except ValueError as exc:
        return ("raised", str(exc), feeder._seq)
    except Exception as exc:
        return ("crashed", type(exc).__name__, feeder._seq)
    return ("emitted", len(events), feeder._seq)


def test_nan_stream_count_is_not_a_number():
    assert (
        _events(float("nan")),
        _events(float("inf")),
        _events(10.0),
        _events(2),
    ) == (
        ("raised", "count is not a number.", 0),
        ("raised", "count is not a number.", 0),
        ("raised", "count is not a number.", 0),
        ("emitted", 2, 2),
    )
