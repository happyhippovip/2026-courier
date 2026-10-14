"""Test hardening for courier_runtime.hosts (P9-hosts).

Covers branches NOT pinned by tests/test_runtime_own_computer.py
(which already covers cheapest-select, DEGRADED exclusion, and the
basic evidence accept/reject pair): lease caps, privacy forcing,
IDLE-before-BUSY ordering, cost ties, unselectable health states,
unknown devices, unpassed evidence, and the frozen-dataclass contract.
Pure unit tests: no I/O, no network, no subprocesses.
"""
import dataclasses

import pytest

from courier_runtime.hosts import (
    BUSY,
    DEGRADED,
    HEALTHY,
    IDLE,
    OFFLINE,
    RECOVERING,
    SELECTABLE,
    Evidence,
    Host,
    NoEligibleHost,
    Requirement,
    accept_evidence,
    eligible,
    select,
)


def host(device_id, caps=("python",), **kw):
    base = dict(device_id=device_id, capabilities=frozenset(caps))
    base.update(kw)
    return Host(**base)


def req(caps=("python",), **kw):
    base = dict(capabilities=frozenset(caps))
    base.update(kw)
    return Requirement(**base)


# -- registry constants and defaults -------------------------------------------

def test_selectable_contains_only_runnable_states():
    assert SELECTABLE == {HEALTHY, IDLE, BUSY}


def test_host_defaults():
    h = host("d1")
    assert h.health == HEALTHY
    assert h.cost_per_hour_eur == 0.0
    assert h.privacy == "own"
    assert (h.active_leases, h.max_leases) == (0, 1)


def test_requirement_privacy_defaults_to_none():
    assert req().privacy is None


def test_host_and_requirement_are_frozen():
    h = host("d1")
    with pytest.raises(dataclasses.FrozenInstanceError):
        h.health = BUSY
    with pytest.raises(dataclasses.FrozenInstanceError):
        req().privacy = "own"


# -- eligible() -----------------------------------------------------------------

def test_empty_requirement_matches_any_selectable_host():
    hosts = [host("d1"), host("d2", health=OFFLINE)]
    assert eligible(req(()), hosts) == [hosts[0]]


def test_lease_cap_excludes_full_host():
    full = host("full", active_leases=1, max_leases=1)
    free = host("free", active_leases=0, max_leases=1)
    assert eligible(req(), [full, free]) == [free]


def test_lease_below_cap_stays_eligible():
    h = host("d1", active_leases=1, max_leases=3)
    assert eligible(req(), [h]) == [h]


def test_privacy_forcing_selects_only_own_devices():
    hosts = [host("cloud", privacy="hosted"), host("mac", privacy="own")]
    assert eligible(req(privacy="own"), hosts) == [hosts[1]]


def test_privacy_forcing_with_no_own_device_is_empty():
    assert eligible(req(privacy="own"), [host("c1", privacy="hosted")]) == []


def test_offline_and_recovering_are_never_eligible():
    hosts = [host("o", health=OFFLINE), host("r", health=RECOVERING),
             host("d", health=DEGRADED), host("ok")]
    assert eligible(req(), hosts) == [hosts[3]]


def test_capability_subset_required():
    hosts = [host("py", ("python",)), host("pywin", ("python", "windows_native"))]
    assert eligible(req(("python", "windows_native")), hosts) == [hosts[1]]


# -- select() --------------------------------------------------------------------

def test_idle_beats_busy_at_equal_cost():
    hosts = [host("busy", health=BUSY, cost_per_hour_eur=0.1),
             host("idle", health=IDLE, cost_per_hour_eur=0.1)]
    assert select(req(), hosts).device_id == "idle"


def test_cheapest_wins_regardless_of_order():
    hosts = [host("zz", cost_per_hour_eur=0.5), host("aa", cost_per_hour_eur=0.9),
             host("mm", cost_per_hour_eur=0.1)]
    assert select(req(), hosts).device_id == "mm"


def test_cost_tie_breaks_on_device_id():
    hosts = [host("b"), host("a")]
    assert select(req(), hosts).device_id == "a"


def test_busy_host_selected_when_it_is_the_only_option():
    assert select(req(), [host("solo", health=BUSY)]).device_id == "solo"


def test_no_eligible_host_raises_with_capability_in_message():
    with pytest.raises(NoEligibleHost, match="windows_native"):
        select(req(("windows_native",)), [host("py", ("python",))])


def test_no_hosts_at_all_raises():
    with pytest.raises(NoEligibleHost):
        select(req(), [])


def test_select_honours_privacy_forcing():
    hosts = [host("cheap-cloud", privacy="hosted", cost_per_hour_eur=0.01),
             host("mac", privacy="own", cost_per_hour_eur=0.5)]
    assert select(req(privacy="own"), hosts).device_id == "mac"


# -- accept_evidence() -------------------------------------------------------------

def ev(device_id="d1", capability="python", passed=True):
    return Evidence("wk", capability, device_id, "abc123", passed)


def test_unknown_device_rejected():
    ok, reason = accept_evidence(ev("ghost"), "python", [host("d1")])
    assert (ok, reason) == (False, "unknown device ghost")


def test_unpassed_evidence_rejected_even_from_capable_host():
    hosts = [host("d1", ("python",))]
    ok, reason = accept_evidence(ev(passed=False), "python", hosts)
    assert (ok, reason) == (False, "evidence did not pass")


def test_host_missing_capability_rejected():
    hosts = [host("d1", ("python",))]
    ok, reason = accept_evidence(ev(capability="gpu"), "gpu", hosts)
    assert ok is False and "cannot evidence gpu" in reason


def test_accepted_evidence_returns_accepted_reason():
    hosts = [host("d1", ("python", "gpu"))]
    assert accept_evidence(ev(capability="gpu"), "gpu", hosts) == (True, "accepted")


def test_evidence_for_wrong_requirement_rejected():
    hosts = [host("d1", ("python",))]
    ok, _ = accept_evidence(ev(capability="python"), "gpu", hosts)
    assert ok is False
