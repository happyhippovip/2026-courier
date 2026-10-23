from courier_core.cost_transparency import describe_billing_mode


def test_blank_provider_label_is_not_local():
    assert (
        describe_billing_mode("free", ""),
        describe_billing_mode("free", "local"),
        describe_billing_mode("free", None),
    ) == (
        "Unknown Deterministic (FREE)",
        "Local Deterministic (FREE)",
        "Local Deterministic (FREE)",
    )
