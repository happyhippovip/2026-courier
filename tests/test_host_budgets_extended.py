import pytest
from scripts import host_budgets as HB


def test_mission_state_to_health_mappings():
    assert HB.mission_state_to_health("NOMINAL") == "HEALTHY"
    assert HB.mission_state_to_health("WATCH") == "PRESSURED"
    assert HB.mission_state_to_health("RECOVERING") == "RESOURCE_PAUSE"
    assert HB.mission_state_to_health("PRESSURED") == "PRESSURED"
    assert HB.mission_state_to_health("DEGRADED") == "DEGRADED"
    assert HB.mission_state_to_health("RESOURCE_PAUSE") == "RESOURCE_PAUSE"
    assert HB.mission_state_to_health("EMERGENCY") == "EMERGENCY"

    with pytest.raises(ValueError) as exc:
        HB.mission_state_to_health("UNKNOWN_STATE")
    assert "unknown mission host state" in str(exc.value)


def test_budget_release_boundary():
    b = HB.Budget("workers", limit=5, reserved=1, used=3)
    b.release(2)
    assert b.used == 1
    # Release more than used clamps to 0
    b.release(10)
    assert b.used == 0


def test_admit_work_unknown_work_class():
    budgets = HB.default_budgets()
    with pytest.raises(ValueError) as exc:
        HB.admit_work(budgets, "QUANTUM_TASK", "HEALTHY")
    assert "unknown work class" in str(exc.value)


def test_admit_work_pause_and_emergency_states():
    budgets = HB.default_budgets()

    # In RESOURCE_PAUSE, normal work is denied
    assert HB.admit_work(budgets, "LIGHT", "RESOURCE_PAUSE", emergency=False) is False

    # In EMERGENCY, normal work is denied
    assert HB.admit_work(budgets, "LIGHT", "EMERGENCY", emergency=False) is False

    # In DEGRADED, HEAVY work is denied
    assert HB.admit_work(budgets, "HEAVY", "DEGRADED", emergency=False) is False

    # But LIGHT work is allowed in DEGRADED
    assert HB.admit_work(budgets, "LIGHT", "DEGRADED", emergency=False) is True


def test_admit_work_atomicity_on_failure():
    budgets = HB.default_budgets()
    # Artificially exhaust spawn budget
    budgets["spawn"].used = budgets["spawn"].limit

    # Attempting to admit HEAVY needs both heavy_jobs and spawn
    orig_heavy = budgets["heavy_jobs"].used
    assert HB.admit_work(budgets, "HEAVY", "NOMINAL") is False
    # heavy_jobs was charged first in iteration, but should be rolled back cleanly on spawn BudgetExceeded
    assert budgets["heavy_jobs"].used == orig_heavy
