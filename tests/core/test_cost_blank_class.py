from tests.core.test_cost_zero_class import _card


def test_blank_cost_class_is_not_free():
    assert (
        _card(""),
        _card("free"),
    ) == (
        (0, True, "unknown"),
        (1, False, "free"),
    )
