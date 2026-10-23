from tests.arbi.test_spread_pct_score import _score


def test_zero_spread_percent_is_not_a_paper_execute():
    zero = _score(0.0)
    clean = _score(1.0)
    assert (
        "ZERO_SPREAD_PCT" in zero.data_quality_flags,
        zero.heuristic_recommendation,
        zero.confidence_tier,
        "ZERO_SPREAD_PCT" in clean.data_quality_flags,
        clean.heuristic_recommendation,
    ) == (
        True,
        "DISCARD",
        "REJECTED",
        False,
        "EXECUTE_IN_PAPER_MODE",
    )
