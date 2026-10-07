from courier_runtime.update_gate import CapabilityState, compare

# -- update capability gate ----------------------------------------------------------

BEFORE = CapabilityState("1.0.0", {"LEDGER-01": True, "GOLDEN-01": True, "HUB-03": False}, "d1")


def test_update_that_keeps_capabilities_is_accepted_and_new_ones_only_proposed():
    after = CapabilityState("1.1.0", {"LEDGER-01": True, "GOLDEN-01": True, "HUB-03": True}, "d1")
    result = compare(BEFORE, after)
    assert result["decision"] == "ACCEPT" and result["proposed"] == ["HUB-03"] and result["switch_to"] == "1.1.0"


def test_update_that_loses_a_capability_is_rejected_with_recovery():
    after = CapabilityState("1.1.0", {"LEDGER-01": True, "GOLDEN-01": False}, "d1")
    result = compare(BEFORE, after)
    assert result["decision"] == "REJECT" and result["lost"] == ["GOLDEN-01"]
    assert result["recovery"]["keep_version"] == "1.0.0"


def test_update_that_changes_history_projection_is_rejected():
    after = CapabilityState("1.1.0", dict(BEFORE.capabilities), "d2")
    assert compare(BEFORE, after)["decision"] == "REJECT"
