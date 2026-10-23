from tests.arbi.test_bid_score import _score


def test_zero_quote_bid_is_not_a_paper_execute():
    zero = _score(0.0)
    clean = _score(100.0)
    assert (
        "ZERO_BID" in zero.data_quality_flags,
        zero.heuristic_recommendation,
        zero.confidence_tier,
        "ZERO_BID" in clean.data_quality_flags,
        clean.heuristic_recommendation,
    ) == (
        True,
        "DISCARD",
        "REJECTED",
        False,
        "EXECUTE_IN_PAPER_MODE",
    )
