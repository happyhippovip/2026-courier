import pytest
from courier_runtime.update_gate import CapabilityState, compare


def test_compare_no_capabilities_identical_digest():
    before = CapabilityState("1.0.0", {}, "digest-1")
    after = CapabilityState("1.0.1", {}, "digest-1")

    res = compare(before, after)
    assert res["decision"] == "ACCEPT"
    assert res["lost"] == []
    assert res["proposed"] == []
    assert res["switch_to"] == "1.0.1"
    assert "kept all 0 accepted capabilities" in res["reasons"][0]


def test_compare_multiple_new_capabilities():
    before = CapabilityState("1.0.0", {"CAP-A": True}, "digest-1")
    after = CapabilityState("1.1.0", {"CAP-A": True, "CAP-B": True, "CAP-C": True}, "digest-1")

    res = compare(before, after)
    assert res["decision"] == "ACCEPT"
    assert res["proposed"] == ["CAP-B", "CAP-C"]
    assert any("2 new capabilities proposed" in r for r in res["reasons"])


def test_compare_lost_and_digest_mismatch_together():
    before = CapabilityState("1.0.0", {"CAP-A": True, "CAP-B": True}, "digest-orig")
    after = CapabilityState("2.0.0-broken", {"CAP-A": True, "CAP-B": False}, "digest-corrupted")

    res = compare(before, after)
    assert res["decision"] == "REJECT"
    assert res["lost"] == ["CAP-B"]
    assert any("lost: ['CAP-B']" in r for r in res["reasons"])
    assert any("journal replay projects to a different history" in r for r in res["reasons"])
    assert res["recovery"]["keep_version"] == "1.0.0"
    assert res["recovery"]["discard_version"] == "2.0.0-broken"
    assert res["recovery"]["action"] == "RESUME_FROM_CHECKPOINT"
