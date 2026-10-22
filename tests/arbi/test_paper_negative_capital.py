from tests.arbi.test_paper_capital import _open


def test_negative_capital_is_not_a_portfolio():
    assert (
        _open(-10.0),
        _open(0.0),
        _open(100.0),
    ) == (
        ("raised", "virtual capital is out of range.", None),
        ("accepted", 0.0, 0.0),
        ("accepted", 100.0, 100.0),
    )
