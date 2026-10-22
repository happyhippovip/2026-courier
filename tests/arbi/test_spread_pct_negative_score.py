from tests.arbi.test_spread_pct_score import _score


def test_negative_spread_percent_is_not_a_paper_execute():
    neg = _score(-1.0)
    clean = _score(1.0)
    assert (
        "NEGATIVE_SPREAD_PCT" in neg.data_quality_flags,
        neg.heuristic_recommendation,
        neg.confidence_tier,
        clean.heuristic_recommendation,
        "NEGATIVE_SPREAD_PCT" in clean.data_quality_flags,
    ) == (
        True,
        "DISCARD",
        "REJECTED",
        "EXECUTE_IN_PAPER_MODE",
        False,
    )
