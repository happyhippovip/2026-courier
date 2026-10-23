from tests.arbi.test_sell_price_score import _score


def test_negative_sell_price_is_not_a_paper_execute():
    neg = _score(-100.0)
    clean = _score(100.0)
    assert (
        "NEGATIVE_SELL_PRICE" in neg.data_quality_flags,
        neg.heuristic_recommendation,
        neg.confidence_tier,
        clean.heuristic_recommendation,
        "NEGATIVE_SELL_PRICE" in clean.data_quality_flags,
    ) == (
        True,
        "DISCARD",
        "REJECTED",
        "EXECUTE_IN_PAPER_MODE",
        False,
    )
