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



# -- U1: disk floor -------------------------------------------------------------
def test_disk_floor_blocks_when_below_floor(tmp_path):
    assert HB.disk_floor_ok(str(tmp_path), floor_bytes=1) is True
    assert HB.disk_floor_ok(str(tmp_path), floor_bytes=10 ** 18) is False


def test_disk_floor_unknown_path_fails_closed():
    assert HB.disk_floor_ok("/nonexistent-courier-path-xyz", floor_bytes=1) is False
    assert HB.disk_free_bytes("/nonexistent-courier-path-xyz") is None


# -- U2: swap/memory trend -------------------------------------------------------
def test_trend_classifies_direction():
    assert HB.trend([10.0, 11.0, 12.5, 14.0]) == "RISING"
    assert HB.trend([14.0, 12.0, 11.0, 10.0]) == "FALLING"
    assert HB.trend([10.0, 10.0, 10.0, 10.0]) == "FLAT"


def test_trend_needs_history_and_rejects_gaps():
    assert HB.trend([]) == "UNKNOWN"
    assert HB.trend([10.0, 11.0]) == "UNKNOWN"
    assert HB.trend([10.0, None, 12.0, 14.0]) == "UNKNOWN"


def test_rising_trend_blocks_new_heavy():
    assert HB.trend_blocks_heavy("RISING") is True
    assert HB.trend_blocks_heavy("FLAT") is False
    assert HB.trend_blocks_heavy("FALLING") is False
    assert HB.trend_blocks_heavy("UNKNOWN") is True  # unknown is not permission


# -- U3: hysteresis --------------------------------------------------------------
def test_hysteresis_gates_immediately_and_clears_slowly():
    gate = HB.HysteresisGate(calm_required=3)
    assert gate.observe(False) is False
    assert gate.observe(True) is True  # escalate at once
    assert gate.observe(False) is True  # 1 calm: still gated
    assert gate.observe(False) is True  # 2 calm: still gated
    assert gate.observe(False) is False  # 3 calm: released
    assert gate.observe(True) is True  # flap re-gates at once


# -- U4: OPEN / LIGHT_ONLY / CLOSED ----------------------------------------------
def test_lane_mode_tristate():
    assert HB.lane_mode("NOMINAL") == "OPEN"
    for s in ("WATCH", "PRESSURED", "DEGRADED"):
        assert HB.lane_mode(s) == "LIGHT_ONLY"
    for s in ("RESOURCE_PAUSE", "EMERGENCY", "RECOVERING"):
        assert HB.lane_mode(s) == "CLOSED"


def test_lane_mode_unknown_raises():
    with pytest.raises(ValueError):
        HB.lane_mode("COZY")


# -- U5: cleanup evidence gates retirement ---------------------------------------
def test_failed_cleanup_transfers_instead_of_hibernating():
    lanes = [HB.Lane("bad-1", HB.IDLE, cleanup=HB.CLEANUP_FAILED),
             HB.Lane("ok-1", HB.IDLE, cleanup=HB.CLEANUP_UNKNOWN)]
    plan = HB.plan_hibernation(lanes, health="NOMINAL", quota_exhausted=False)
    assert plan["transfer"] == ["bad-1"]  # continue or transfer, never drop
    assert "bad-1" not in plan["hibernate"]
    assert "ok-1" in plan["hibernate"]  # UNKNOWN allowed, checkpoint-first


# -- U6: retirement checklist ------------------------------------------------------
def test_retirement_check_all_green_retires():
    assert HB.retirement_check(True, True, True, True, True, HB.CLEANUP_UNKNOWN) == "RETIRE"
    assert HB.retirement_check(True, True, True, True, True, HB.CLEANUP_PROVEN) == "RETIRE"


def test_retirement_check_missing_evidence_continues():
    assert HB.retirement_check(True, False, True, True, True, HB.CLEANUP_PROVEN) == "CONTINUE"
    assert HB.retirement_check(True, True, True, False, True, HB.CLEANUP_PROVEN) == "CONTINUE"


def test_retirement_check_failed_cleanup_transfers():
    assert HB.retirement_check(True, True, True, True, True, HB.CLEANUP_FAILED) == "TRANSFER"
