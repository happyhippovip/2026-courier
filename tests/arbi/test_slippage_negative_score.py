from tests.arbi.test_slippage_score import _score


def test_negative_slippage_is_not_a_paper_execute():
    neg = _score(-1.0)
    small = _score(0.1)
    assert (
        "NEGATIVE_SLIPPAGE" in neg.data_quality_flags,
        neg.heuristic_recommendation,
        neg.confidence_tier,
        small.heuristic_recommendation,
        "NEGATIVE_SLIPPAGE" in small.data_quality_flags,
    ) == (
        True,
        "DISCARD",
        "REJECTED",
        "EXECUTE_IN_PAPER_MODE",
        False,
    )
