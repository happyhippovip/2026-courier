"""P0 tripwire: agy provider path must become cost-gated (owner decision pending).

Finding (V76/1, HEAD 5afbffb48, proven by pure-function probe): an agy spec
carries no cost evidence (``_validate_agy`` sets none; ``AGY_PARAM_KEYS``
rejects cost keys with UNKNOWN_KEY), so ``evaluate_cost_gate()`` allows it
without ever consulting CostGate. UNKNOWN_COST=BLOCK requires this to block
until the deployment declares agy cost explicitly.

Scope stays #714-owned (DRAFT/CONFLICTING): this file changes no product
code and touches no foreign test file. The xfail tests below flip to XPASS
the moment the owner lands the decision (option A: fail-closed default;
option B: explicit included-quota contract — option B keeps test 1 xfailed
by design and must update it).

Pure functions only: no subprocess, no spawn, zero cost.
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
