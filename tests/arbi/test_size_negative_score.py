from tests.arbi.test_size_score import _score


def test_negative_order_size_is_not_a_paper_execute():
    neg = _score(-100.0)
    clean = _score(100.0)
    assert (
        "NEGATIVE_SIZE" in neg.data_quality_flags,
        neg.heuristic_recommendation,
        neg.confidence_tier,
        clean.heuristic_recommendation,
        "NEGATIVE_SIZE" in clean.data_quality_flags,
    ) == (
        True,
        "DISCARD",
        "REJECTED",
        "EXECUTE_IN_PAPER_MODE",
        False,
    )
