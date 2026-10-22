from tests.arbi.test_triangular_fee import _cycle


def test_fee_above_100_percent_is_not_a_cycle():
    assert (
        _cycle(150.0),
        _cycle(100.0),
        _cycle(0.1),
    ) == (
        ("BLOCKED_INVALID_PRICE", 0.0),
        ("BLOCKED_NEGATIVE_NET", -100.0),
        ("ELIGIBLE", 3.0236),
    )
