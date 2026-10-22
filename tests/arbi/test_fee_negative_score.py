from tests.arbi.test_fee_score import _score


def test_negative_fee_is_not_a_paper_execute():
    buy = _score(-0.1, 0.1)
    sell = _score(0.1, -0.1)
    clean = _score(0.1, 0.1)
    assert (
        "NEGATIVE_FEE" in buy.data_quality_flags,
        buy.heuristic_recommendation,
        buy.confidence_tier,
        "NEGATIVE_FEE" in sell.data_quality_flags,
        sell.heuristic_recommendation,
        clean.heuristic_recommendation,
        "NEGATIVE_FEE" in clean.data_quality_flags,
    ) == (
        True,
        "DISCARD",
        "REJECTED",
        True,
        "DISCARD",
        "EXECUTE_IN_PAPER_MODE",
        False,
    )
