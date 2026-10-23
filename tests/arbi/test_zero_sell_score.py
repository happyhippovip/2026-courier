from tests.arbi.test_sell_price_score import _score


def test_zero_sell_price_is_not_a_paper_execute():
    zero = _score(0.0)
    clean = _score(100.0)
    assert (
        "ZERO_SELL_PRICE" in zero.data_quality_flags,
        zero.heuristic_recommendation,
        zero.confidence_tier,
        "ZERO_SELL_PRICE" in clean.data_quality_flags,
        clean.heuristic_recommendation,
    ) == (
        True,
        "DISCARD",
        "REJECTED",
        False,
        "EXECUTE_IN_PAPER_MODE",
    )
