from tests.arbi.test_cost_score import _score


def test_negative_total_cost_is_not_a_paper_execute():
    neg = _score(-1.0)
    clean = _score(0.2)
    assert (
        "NEGATIVE_COST" in neg.data_quality_flags,
        neg.heuristic_recommendation,
        neg.confidence_tier,
        clean.heuristic_recommendation,
        "NEGATIVE_COST" in clean.data_quality_flags,
    ) == (
        True,
        "DISCARD",
        "REJECTED",
        "EXECUTE_IN_PAPER_MODE",
        False,
    )
