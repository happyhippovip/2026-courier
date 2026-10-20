"""A missing provider estimate stays missing and blocks before launch.

An explicit finite 0.0 remains the free path. agy may carry that declaration;
it is not invented when the caller omits it. Pure functions only: no subprocess.
"""
from courier_worker.adapters.provider_exec import evaluate_cost_gate, validate


def _agy_spec():
    return validate({"provider": "agy", "prompt": "hello"})


def test_gate_still_blocks_declared_unknown_cost():
    """Guard: the gate itself works for providers that declare cost evidence."""
    verdict = evaluate_cost_gate({"cost_class": "unknown"}, None)
    assert verdict["allowed"] is False
    assert verdict["outcome"] == "BLOCKED"
    assert verdict["reason_code"] == "UNKNOWN_COST_BLOCKED"


def test_agy_without_cost_evidence_is_blocked():
    spec = _agy_spec()
    assert spec.get("estimated_cost_eur") is None
    verdict = evaluate_cost_gate(spec, None)
    assert verdict["allowed"] is False
    assert verdict["reason_code"] == "UNKNOWN_COST_BLOCKED"


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
    assert evaluate_cost_gate(spec, None)["allowed"] is True


def test_missing_estimate_is_not_rewritten_to_zero():
    spec = validate({"provider": "muse", "prompt": "hello"})
    assert spec["estimated_cost_eur"] is None
    blocked = evaluate_cost_gate(spec, None)
    assert blocked["allowed"] is False
    assert blocked["reason_code"] == "UNKNOWN_COST_BLOCKED"
    explicit = validate({"provider": "muse", "prompt": "hello", "estimated_cost_eur": 0.0})
    assert explicit["estimated_cost_eur"] == 0.0
    assert evaluate_cost_gate(explicit, None)["allowed"] is True
    flagged = evaluate_cost_gate(
        {"estimated_cost_eur": 0.0, "unknown_cost": True}, None,
    )
    assert flagged["allowed"] is False
    assert flagged["reason_code"] == "UNKNOWN_COST_BLOCKED"
