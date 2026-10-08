import pytest
from courier_runtime.update_gate import CapabilityState, compare


def test_update_with_multiple_lost_capabilities():
    before = CapabilityState(
        "1.0.0",
        {"CAP-AUTH": True, "CAP-JOURNAL": True, "CAP-FENCE": True, "CAP-BETA": False},
        "digest-abc"
    )
    after = CapabilityState(
        "1.0.1",
        {"CAP-AUTH": False, "CAP-JOURNAL": True, "CAP-FENCE": False, "CAP-BETA": False},
        "digest-abc"
    )
    res = compare(before, after)
    assert res["decision"] == "REJECT"
    assert res["lost"] == ["CAP-AUTH", "CAP-FENCE"]
    assert "lost: ['CAP-AUTH', 'CAP-FENCE']" in res["reasons"]
    assert res["recovery"]["action"] == "RESUME_FROM_CHECKPOINT"
    assert res["recovery"]["keep_version"] == "1.0.0"
    assert res["recovery"]["discard_version"] == "1.0.1"


def test_update_with_multiple_new_proposed_capabilities():
    before = CapabilityState("2.0.0", {"C1": True}, "hash-xyz")
    after = CapabilityState("2.1.0", {"C1": True, "C2": True, "C3": True}, "hash-xyz")
    res = compare(before, after)
    assert res["decision"] == "ACCEPT"
    assert res["lost"] == []
    assert res["proposed"] == ["C2", "C3"]
    assert res["switch_to"] == "2.1.0"
    assert any("2 new capabilities proposed" in r for r in res["reasons"])


def test_simultaneous_lost_capability_and_corrupted_replay_digest():
    before = CapabilityState("1.0.0", {"SEC-1": True, "NET-1": True}, "sha-1")
    after = CapabilityState("1.0.1", {"SEC-1": False, "NET-1": True}, "sha-corrupted-2")
    res = compare(before, after)
    assert res["decision"] == "REJECT"
    assert res["lost"] == ["SEC-1"]
    assert any("lost:" in r for r in res["reasons"])
    assert any("journal replay projects to a different history" in r for r in res["reasons"])


def test_identical_version_and_capabilities_clean_accept():
    before = CapabilityState("1.0.0", {"CORE": True}, "digest-1")
    after = CapabilityState("1.0.0", {"CORE": True}, "digest-1")
    res = compare(before, after)
    assert res["decision"] == "ACCEPT"
    assert res["lost"] == []
    assert res["proposed"] == []
    assert res["reasons"] == ["kept all 1 accepted capabilities"]
