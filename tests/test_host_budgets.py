"""Issue #76 slice: budgets with emergency reserve + lane hibernation (RED).

Gap: nothing in the tree models an explicit resource budget with an
emergency reserve, and nothing decides PHYSICAL hibernation of idle or
quota-blocked lanes -- WAITING stays logical, so idle windows keep
watchers/renderers/pollers alive overnight (the 2026-10-02 Mac incident).

Mission mapping under test:
  64 logical lanes != 64 local heavy processes (heavy budget is 1,
  machine-wide, imported -- never redefined here).
  quota-exhausted or idle  -> checkpoint-first HIBERNATE, stop pollers.
  UNKNOWN mission state     -> raise, never a healthy default.
"""

from __future__ import annotations

import pytest

from scripts import host_budgets as HB


def _lanes():
    return [HB.Lane("active-1", HB.ACTIVE),
            HB.Lane("idle-1", HB.IDLE),
            HB.Lane("quota-1", HB.QUOTA_BLOCKED),
            HB.Lane("wait-1", HB.WAITING_LONG)]


def test_heavy_limit_is_one_machine_wide_and_imported():
    from scripts.resource_governor import HostPressureController
    assert HB.MAX_HEAVY_LOCAL_JOBS_MACHINE_WIDE == 1
    assert HB.MAX_HEAVY_LOCAL_JOBS_MACHINE_WIDE == HostPressureController.MAX_HEAVY_JOBS


def test_reserve_is_untouchable_for_normal_work():
    b = HB.Budget(name="fd", limit=10, reserved=3, used=7)
    assert b.fits_normal(1) is False   # only the reserve is left
    assert b.fits_emergency(1) is True  # checkpoint path may use reserve
    with pytest.raises(HB.BudgetExceeded):
        b.charge(1, emergency=False)
    assert b.used == 7  # failed charge changes nothing


def test_second_heavy_never_fits():
    budgets = HB.default_budgets()
    assert HB.admit_work(budgets, "HEAVY", "NOMINAL") is True
    assert HB.admit_work(budgets, "HEAVY", "NOMINAL") is False
    assert budgets["heavy_jobs"].used == 1


def test_quota_exhausted_night_hibernates_and_stops_pollers():
    plan = HB.plan_hibernation(_lanes(), health="PRESSURED",
                               quota_exhausted=True)
    assert plan["checkpoint_first"] is True
    assert sorted(plan["hibernate"]) == ["idle-1", "quota-1", "wait-1"]
    assert plan["keep"] == ["active-1"]
    assert plan["stop_pollers"] is True  # no overnight heat from idle lanes


def test_idle_hibernates_even_when_host_looks_fine():
    plan = HB.plan_hibernation(_lanes(), health="NOMINAL",
                               quota_exhausted=False)
    assert "idle-1" in plan["hibernate"]
    assert "quota-1" in plan["hibernate"]
    assert plan["stop_pollers"] is False  # provider alive: keep cadence


def test_emergency_hibernates_everything_but_checkpoint():
    plan = HB.plan_hibernation(_lanes(), health="EMERGENCY",
                               quota_exhausted=False)
    assert sorted(plan["hibernate"]) == ["active-1", "idle-1", "quota-1", "wait-1"]
    assert plan["keep"] == []
    assert plan["keep_checkpoint_service"] is True


def test_hibernation_is_idempotent_and_exact():
    lanes = _lanes() + [HB.Lane("sleeping-1", HB.HIBERNATED)]
    first = HB.plan_hibernation(lanes, health="NOMINAL", quota_exhausted=False)
    assert "sleeping-1" not in first["hibernate"]  # already down, not re-listed
    assert first["broad_actions"] == []  # exact lane ids only, never killall


def test_unknown_mission_state_raises_never_healthy():
    with pytest.raises(ValueError):
        HB.mission_state_to_health("SOME_NEW_STATE")
    with pytest.raises(ValueError):
        HB.mission_state_to_health("HEALTHY-typo")


def test_mission_state_mapping():
    assert HB.mission_state_to_health("NOMINAL") == "HEALTHY"
    assert HB.mission_state_to_health("WATCH") == "PRESSURED"
    assert HB.mission_state_to_health("RECOVERING") == "RESOURCE_PAUSE"
    for passthrough in ("PRESSURED", "DEGRADED", "RESOURCE_PAUSE", "EMERGENCY"):
        assert HB.mission_state_to_health(passthrough) == passthrough


def test_hibernation_releases_budget_back_to_baseline():
    budgets = HB.default_budgets()
    assert HB.admit_work(budgets, "LIGHT", "NOMINAL") is True
    HB.release(budgets, "LIGHT")
    assert budgets["light_workers"].used == 0  # baseline restored, readmit clean
    assert HB.admit_work(budgets, "LIGHT", "NOMINAL") is True


def test_unknown_lane_state_hibernates_fail_closed():
    lanes = [HB.Lane("known-active", HB.ACTIVE),
             HB.Lane("mystery-1", "SOME_NEW_STATE")]
    plan = HB.plan_hibernation(lanes, health="NOMINAL",
                               quota_exhausted=False)
    assert "mystery-1" in plan["hibernate"]  # never kept alive unread
    assert plan["unknown"] == ["mystery-1"]  # reported for reclassification
    assert plan["keep"] == ["known-active"]


def test_pressured_admits_light_only_never_heavy():
    assert HB.admission_state("HEALTHY") == HB.OPEN
    assert HB.admission_state("NOMINAL") == HB.OPEN  # mission-worded ok
    assert HB.admission_state("PRESSURED") == HB.LIGHT_ONLY
    assert HB.admission_state("WATCH") == HB.LIGHT_ONLY
    assert HB.admission_state("DEGRADED") == HB.LIGHT_ONLY
    assert HB.admission_state("RESOURCE_PAUSE") == HB.CLOSED
    assert HB.admission_state("RECOVERING") == HB.CLOSED
    assert HB.admission_state("EMERGENCY") == HB.CLOSED
    budgets = HB.default_budgets()
    assert HB.admit_work(budgets, "HEAVY", "PRESSURED") is False
    assert budgets["heavy_jobs"].used == 0  # refused charge changes nothing
    assert HB.admit_work(budgets, "LIGHT", "PRESSURED") is True
    with pytest.raises(ValueError):
        HB.admission_state("SOME_NEW_SIGNAL")
    with pytest.raises(ValueError):
        HB.admit_work(HB.default_budgets(), "LIGHT", "SOME_NEW_SIGNAL")


def test_telemetry_escalates_never_clears():
    assert HB.escalate_health("HEALTHY", memory_pressure="HIGH") == "PRESSURED"
    assert HB.escalate_health("HEALTHY",
                              memory_pressure="CRITICAL") == "RESOURCE_PAUSE"
    assert HB.escalate_health("HEALTHY",
                              memory_pressure="UNKNOWN") == "PRESSURED"
    assert HB.escalate_health("HEALTHY", swap_paging=True) == "PRESSURED"
    assert HB.escalate_health("HEALTHY", disk_free_gb=1.5) == "RESOURCE_PAUSE"
    assert HB.escalate_health("HEALTHY", disk_free_gb=601.0) == "HEALTHY"
    # escalate-only: a DEGRADED host is never talked back to healthy
    assert HB.escalate_health("DEGRADED",
                              memory_pressure="NOMINAL") == "DEGRADED"
    with pytest.raises(ValueError):
        HB.escalate_health("SOME_NEW_SIGNAL")
    with pytest.raises(ValueError):
        HB.escalate_health("HEALTHY", memory_pressure="SMOKING")


def test_recovery_needs_consecutive_healthy_probes():
    gate = HB.RecoveryHysteresis(required_healthy=3)
    assert gate.probe(True) is False  # one green sample is not recovery
    assert gate.probe(True) is False
    assert gate.probe(True) is True
    gate.probe(False)  # a single bad sample resets the streak
    assert gate.probe(True) is False


def test_weak_profile_admits_less_but_heavy_stays_one():
    low, normal = HB.default_budgets("low"), HB.default_budgets()
    assert low["light_workers"].limit < normal["light_workers"].limit
    assert low["heavy_jobs"].limit == 1 == normal["heavy_jobs"].limit
    assert HB.admit_work(low, "HEAVY", "HEALTHY") is True
    assert HB.admit_work(low, "HEAVY", "HEALTHY") is False  # still single-flight
    with pytest.raises(ValueError):
        HB.default_budgets("gaming-rig-9000")


def test_unproven_cleanup_blocks_heavy_only():
    budgets = HB.default_budgets()
    assert HB.admit_work(budgets, "HEAVY", "HEALTHY",
                         cleanup_proven=False) is False
    assert budgets["heavy_jobs"].used == 0  # refused charge changes nothing
    assert HB.admit_work(budgets, "LIGHT", "HEALTHY",
                         cleanup_proven=False) is True
    assert HB.admit_work(budgets, "HEAVY", "HEALTHY",
                         cleanup_proven=True) is True
