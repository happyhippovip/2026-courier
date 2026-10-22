from tests.arbi.test_paper_negative_transfer import _attempt


def test_transfer_cost_reduces_the_fill():
    charged = _attempt(5.0)
    clean = _attempt(0.0)
    assert (
        charged,
        clean,
    ) == (
        ("filled", "FULL_SUCCESS", -4.25, 95.75, 1),
        ("filled", "FULL_SUCCESS", 0.75, 100.75, 1),
    )
