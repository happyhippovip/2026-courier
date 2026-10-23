from courier_core.cost_transparency import describe_billing_mode


def test_numeric_zero_billing_mode_is_not_free():
    assert (
        describe_billing_mode(0, "local"),
        describe_billing_mode("free", "local"),
        describe_billing_mode(None, "local"),
    ) == (
        "Local (UNKNOWN)",
        "Local Deterministic (FREE)",
        "Local Deterministic (FREE)",
    )
