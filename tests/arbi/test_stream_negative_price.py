from tests.arbi.test_stream_level import _seen


def test_negative_level_price_does_not_enter_the_book():
    assert (
        _seen(-1.0, 1.5),
        _seen(100.0, 1.5),
    ) == (
        ("raised", "price is out of range.", []),
        ("accepted", [(100.0, 1.5)]),
    )
