"""P0 tripwire: provider cost evidence and CostGate errors fail closed.

An agy spec without cost evidence stays blocked. A positive estimate whose
CostGate call raises does not escape as an uncaught error; the gate returns
BLOCKED. Pure functions only: no subprocess, no spawn, zero cost.
"""
import pytest

from courier_worker.adapters.provider_exec import evaluate_cost_gate, validate


def _agy_spec():
    return validate({"provider": "agy", "prompt": "hello"})


def test_gate_still_blocks_declared_unknown_cost():
    """Guard: the gate itself works for providers that declare cost evidence."""
    verdict = evaluate_cost_gate({"cost_class": "unknown"}, None)
    assert verdict["allowed"] is False
    assert verdict["outcome"] == "BLOCKED"


def test_agy_without_cost_evidence_is_blocked():
    spec = _agy_spec()
    verdict = evaluate_cost_gate(spec, None)
    assert verdict["allowed"] is False


def test_positive_cost_is_blocked_when_costgate_raises(monkeypatch):
    def _boom(*_args, **_kwargs):
        raise RuntimeError("policy unreadable")

    monkeypatch.setattr("scripts.resource_policy.CostGate.evaluate_spend_request", staticmethod(_boom))
    verdict = evaluate_cost_gate({"provider": "muse", "estimated_cost_eur": 1.0}, None)
    assert verdict["allowed"] is False
    assert verdict["outcome"] == "BLOCKED"
    assert verdict["reason_code"] == "COSTGATE_UNAVAILABLE_FOR_SPEND"


def test_agy_accepts_declared_cost_evidence():
    spec = validate(
        {
            "provider": "agy",
            "prompt": "hello",
            "estimated_cost_eur": 0.0,
            "cost_class": "included_quota",
        }
    )
    assert spec["estimated_cost_eur"] == 0.0
    assert spec["cost_class"] == "included_quota"
