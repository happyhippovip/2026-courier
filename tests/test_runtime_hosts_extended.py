import pytest
from dataclasses import FrozenInstanceError

from courier_runtime.hosts import (
    HEALTHY,
    BUSY,
    IDLE,
    DEGRADED,
    OFFLINE,
    RECOVERING,
    SELECTABLE,
    Host,
    Requirement,
    Evidence,
    NoEligibleHost,
    eligible,
    select,
    accept_evidence,
)


def test_selectable_states_contract():
    assert HEALTHY in SELECTABLE
    assert IDLE in SELECTABLE
    assert BUSY in SELECTABLE
    assert DEGRADED not in SELECTABLE
    assert OFFLINE not in SELECTABLE
    assert RECOVERING not in SELECTABLE


def test_host_immutability():
    host = Host("h-1", frozenset({"python"}), cost_per_hour_eur=0.10)
    with pytest.raises(FrozenInstanceError):
        host.cost_per_hour_eur = 0.05
    with pytest.raises(FrozenInstanceError):
        host.health = DEGRADED


def test_eligible_filtering_capabilities():
    req = Requirement(frozenset({"python", "gpu"}))
    h1 = Host("h-python", frozenset({"python"}))
    h2 = Host("h-gpu", frozenset({"gpu"}))
    h3 = Host("h-both", frozenset({"python", "gpu", "linux"}))

    candidates = eligible(req, [h1, h2, h3])
    assert candidates == [h3]


def test_eligible_filtering_health():
    req = Requirement(frozenset({"python"}))
    hosts = [
        Host("h-healthy", frozenset({"python"}), health=HEALTHY),
        Host("h-idle", frozenset({"python"}), health=IDLE),
        Host("h-busy", frozenset({"python"}), health=BUSY),
        Host("h-degraded", frozenset({"python"}), health=DEGRADED),
        Host("h-offline", frozenset({"python"}), health=OFFLINE),
        Host("h-recovering", frozenset({"python"}), health=RECOVERING),
    ]

    candidates = eligible(req, hosts)
    assert {c.device_id for c in candidates} == {"h-healthy", "h-idle", "h-busy"}


def test_eligible_lease_saturation():
    req = Requirement(frozenset({"python"}))
    h_available = Host("h-avail", frozenset({"python"}), active_leases=0, max_leases=1)
    h_saturated = Host("h-sat", frozenset({"python"}), active_leases=2, max_leases=2)
    h_overloaded = Host("h-over", frozenset({"python"}), active_leases=3, max_leases=2)

    candidates = eligible(req, [h_available, h_saturated, h_overloaded])
    assert candidates == [h_available]


def test_eligible_privacy_enforcement():
    req_own = Requirement(frozenset({"python"}), privacy="own")
    req_hosted = Requirement(frozenset({"python"}), privacy="hosted")
    req_any = Requirement(frozenset({"python"}), privacy=None)

    h_own = Host("h-own", frozenset({"python"}), privacy="own")
    h_hosted = Host("h-hosted", frozenset({"python"}), privacy="hosted")

    assert eligible(req_own, [h_own, h_hosted]) == [h_own]
    assert eligible(req_hosted, [h_own, h_hosted]) == [h_hosted]
    assert set(eligible(req_any, [h_own, h_hosted])) == {h_own, h_hosted}


def test_select_cheapest_preference():
    req = Requirement(frozenset({"python"}))
    cheap = Host("h-cheap", frozenset({"python"}), cost_per_hour_eur=0.01)
    pricy = Host("h-pricy", frozenset({"python"}), cost_per_hour_eur=0.50)

    selected = select(req, [pricy, cheap])
    assert selected.device_id == "h-cheap"


def test_select_idle_over_busy_at_equal_cost():
    req = Requirement(frozenset({"python"}))
    h_busy = Host("h-busy", frozenset({"python"}), cost_per_hour_eur=0.10, health=BUSY)
    h_idle = Host("h-idle", frozenset({"python"}), cost_per_hour_eur=0.10, health=IDLE)

    selected = select(req, [h_busy, h_idle])
    assert selected.device_id == "h-idle"


def test_select_stable_tiebreak_by_device_id():
    req = Requirement(frozenset({"python"}))
    h_beta = Host("h-beta", frozenset({"python"}), cost_per_hour_eur=0.10, health=HEALTHY)
    h_alpha = Host("h-alpha", frozenset({"python"}), cost_per_hour_eur=0.10, health=HEALTHY)

    selected = select(req, [h_beta, h_alpha])
    assert selected.device_id == "h-alpha"


def test_select_raises_when_no_candidates():
    req = Requirement(frozenset({"quantum_computing"}))
    hosts = [Host("h-1", frozenset({"python"}))]
    with pytest.raises(NoEligibleHost, match="quantum_computing"):
        select(req, hosts)


def test_accept_evidence_validation():
    hosts = [
        Host("mac-mini", frozenset({"python", "macos"})),
        Host("win-box", frozenset({"python", "windows_native"})),
    ]

    # Valid evidence
    ev_valid = Evidence("wk-10", "macos", "mac-mini", "hash-abc", True)
    accepted, reason = accept_evidence(ev_valid, "macos", hosts)
    assert accepted is True
    assert reason == "accepted"

    # Unknown device
    ev_unknown = Evidence("wk-10", "macos", "unknown-box", "hash-abc", True)
    acc, r = accept_evidence(ev_unknown, "macos", hosts)
    assert acc is False
    assert "unknown device" in r

    # Device lacks capability
    ev_wrong_device = Evidence("wk-10", "macos", "win-box", "hash-abc", True)
    acc, r = accept_evidence(ev_wrong_device, "macos", hosts)
    assert acc is False
    assert "cannot evidence macos" in r

    # Evidence capability mismatch against requirement
    acc, r = accept_evidence(ev_valid, "windows_native", hosts)
    assert acc is False
    assert "cannot evidence windows_native" in r

    # Failed evidence
    ev_failed = Evidence("wk-10", "macos", "mac-mini", "hash-abc", False)
    acc, r = accept_evidence(ev_failed, "macos", hosts)
    assert acc is False
    assert "evidence did not pass" in r
