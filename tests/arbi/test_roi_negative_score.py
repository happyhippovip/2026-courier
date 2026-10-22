from tests.arbi.test_roi_score import _score


def test_negative_roi_is_not_a_paper_execute():
    neg = _score(-1.0)
    clean = _score(9.0)
    assert (
        "NEGATIVE_ROI" in neg.data_quality_flags,
        neg.heuristic_recommendation,
        neg.confidence_tier,
        clean.heuristic_recommendation,
        "NEGATIVE_ROI" in clean.data_quality_flags,
    ) == (
        True,
        "DISCARD",
        "REJECTED",
        "EXECUTE_IN_PAPER_MODE",
        False,
    )
