from tests.arbi.test_buy_price_score import _score


def test_zero_buy_price_is_not_a_paper_execute():
    zero = _score(0.0)
    clean = _score(101.0)
    assert (
        "ZERO_BUY_PRICE" in zero.data_quality_flags,
        zero.heuristic_recommendation,
        zero.confidence_tier,
        "ZERO_BUY_PRICE" in clean.data_quality_flags,
        clean.heuristic_recommendation,
    ) == (
        True,
        "DISCARD",
        "REJECTED",
        False,
        "EXECUTE_IN_PAPER_MODE",
    )
