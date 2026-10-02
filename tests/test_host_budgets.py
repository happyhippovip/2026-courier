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
