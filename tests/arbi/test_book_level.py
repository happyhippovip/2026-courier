from courier_core.arbi.scanner import MultiExchangeScanner


def _level(price, amount):
    try:
        level = MultiExchangeScanner._book_level(price, amount)
    except ValueError as exc:
        return ("raised", str(exc))
    return ("level", level.price, level.amount)


def test_nan_book_level_is_not_a_price():
    assert (
        _level(float("nan"), 1.0),
        _level(float("inf"), 1.0),
        _level(100.0, float("nan")),
        _level("nan", "1"),
        _level(100.0, 1.0),
        _level(True, 1.0),
    ) == (
        ("raised", "price is not a number."),
        ("raised", "price is not a number."),
        ("raised", "amount is not a number."),
        ("raised", "price is not a number."),
        ("level", 100.0, 1.0),
        ("raised", "Bool is not a number."),
    )
