from courier_core.cost_transparency import describe_billing_mode


def test_blank_billing_class_is_not_free():
    assert (
        describe_billing_mode("", "local"),
        describe_billing_mode("free", "local"),
        describe_billing_mode(None, "local"),
    ) == (
        "Local (UNKNOWN)",
        "Local Deterministic (FREE)",
        "Local Deterministic (FREE)",
    )
