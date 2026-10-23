from tests.arbi.test_paper_fail_rate import _attempt


def test_fail_rate_outside_zero_to_one_does_not_fill():
    assert (
        _attempt(-1.0),
        _attempt(2.0),
        _attempt(0.0),
        _attempt(1.0),
    ) == (
        ("raised", "fail rate is out of range.", 100.0, 0),
        ("raised", "fail rate is out of range.", 100.0, 0),
        ("filled", "FULL_SUCCESS", 0.75, 100.75, 1),
        ("filled", "SECOND_LEG_FAILED", -0.25, 99.75, 1),
    )
