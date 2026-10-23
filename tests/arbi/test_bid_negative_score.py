from tests.arbi.test_bid_score import _score


def test_negative_bid_is_not_a_paper_execute():
    neg = _score(-100.0)
    clean = _score(100.0)
    assert (
        "NEGATIVE_BID" in neg.data_quality_flags,
        neg.heuristic_recommendation,
        neg.confidence_tier,
        clean.heuristic_recommendation,
        "NEGATIVE_BID" in clean.data_quality_flags,
    ) == (
        True,
        "DISCARD",
        "REJECTED",
        "EXECUTE_IN_PAPER_MODE",
        False,
    )
