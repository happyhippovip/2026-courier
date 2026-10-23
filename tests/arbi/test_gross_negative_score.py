from tests.arbi.test_gross_score import _score


def test_negative_gross_spread_is_not_a_paper_execute():
    neg = _score(-10.0)
    clean = _score(10.0)
    assert (
        "NEGATIVE_GROSS" in neg.data_quality_flags,
        neg.heuristic_recommendation,
        neg.confidence_tier,
        "HIGH_SLIPPAGE_DRAG" in neg.data_quality_flags,
        clean.heuristic_recommendation,
        "NEGATIVE_GROSS" in clean.data_quality_flags,
    ) == (
        True,
        "DISCARD",
        "REJECTED",
        False,
        "EXECUTE_IN_PAPER_MODE",
        False,
    )
