from tests.arbi.test_stream_mid import _emit


def test_zero_mid_does_not_emit_a_price():
    assert (
        _emit(0.0),
        _emit(60000.0),
    ) == (
        ("raised", "mid is out of range."),
        ("emitted", 60000.0),
    )
