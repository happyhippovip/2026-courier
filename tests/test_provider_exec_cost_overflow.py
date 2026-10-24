"""PE-1: an estimate too large for a float blocks instead of crashing the worker before the gate answers."""
import pytest

from courier_worker.adapters.provider_exec import evaluate_cost_gate


@pytest.mark.parametrize("estimate", [10**400, -(10**400)])
def test_an_overflowing_estimate_is_blocked_not_raised(estimate):
    verdict = evaluate_cost_gate({"provider": "agy", "estimated_cost_eur": estimate}, None)
    assert verdict["allowed"] is False and verdict["reason_code"] == "INVALID_COST_ESTIMATE"
