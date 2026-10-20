from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from courier_core.provider_cost_guard import (
    evaluate_cost_gate,
    record_cost_gate_audit,
    CostGateVerdict,
)


def test_zero_cost_local_provider_is_approved():
    spec = {
        "provider": "local_bridge",
        "model": "deterministic-v1",
        "cost_estimate_eur": 0.0,
    }
    verdict = evaluate_cost_gate(spec)
    assert isinstance(verdict, CostGateVerdict)
    assert verdict.allowed is True
    assert verdict.reason == "ZERO_COST_APPROVED"
    assert verdict.cost_eur == 0.0


def test_unknown_cost_is_strictly_blocked():
    # Missing cost estimate
    spec_missing = {
        "provider": "google_vertex",
        "model": "gemini-1.5-flash",
    }
    verdict = evaluate_cost_gate(spec_missing)
    assert verdict.allowed is False
    assert verdict.reason == "UNKNOWN_COST_BLOCKED"

    # None cost estimate
    spec_none = {
        "provider": "google_vertex",
        "model": "gemini-1.5-flash",
        "cost_estimate_eur": None,
    }
    verdict2 = evaluate_cost_gate(spec_none)
    assert verdict2.allowed is False
    assert verdict2.reason == "UNKNOWN_COST_BLOCKED"


def test_positive_cost_exceeds_zero_limit_and_is_blocked():
    spec = {
        "provider": "anthropic",
        "model": "claude-3-5-sonnet",
        "cost_estimate_eur": 0.005,
    }
    verdict = evaluate_cost_gate(spec, autonomous_limit_eur=0.0)
    assert verdict.allowed is False
    assert verdict.reason == "AUTONOMOUS_SPEND_LIMIT_EXCEEDED"
    assert verdict.cost_eur == 0.005


def test_negative_cost_or_invalid_type_is_blocked():
    spec = {
        "provider": "local",
        "model": "m1",
        "cost_estimate_eur": -1.0,
    }
    verdict = evaluate_cost_gate(spec)
    assert verdict.allowed is False
    assert verdict.reason == "INVALID_SPEC"

    # Boolean False must never be coerced to 0.0 EUR
    verdict_bool = evaluate_cost_gate({"provider": "local", "model": "m1", "cost_estimate_eur": False})
    assert verdict_bool.allowed is False
    assert verdict_bool.reason == "INVALID_SPEC"

    # NaN autonomous limit must fail closed, never open
    verdict_nan_limit = evaluate_cost_gate(
        {"provider": "local", "model": "m1", "cost_estimate_eur": 0.0},
        autonomous_limit_eur=float("nan"),
    )
    assert verdict_nan_limit.allowed is False
    assert verdict_nan_limit.reason == "INVALID_SPEC"


def test_empty_or_malformed_spec_is_blocked():
    verdict = evaluate_cost_gate({})
    assert verdict.allowed is False
    assert verdict.reason == "INVALID_SPEC"


def test_record_cost_gate_audit_appends_cleanly(tmp_path: Path):
    ledger = tmp_path / "cost_audit.jsonl"
    spec = {
        "provider": "mock_provider",
        "model": "mock-v1",
        "cost_estimate_eur": 0.0,
    }
    verdict = evaluate_cost_gate(spec)
    record_cost_gate_audit(ledger, verdict, context={"task_id": "t-100"})

    assert ledger.exists()
    lines = ledger.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["allowed"] is True
    assert record["provider"] == "mock_provider"
    assert record["context"]["task_id"] == "t-100"


def test_cli_invocation_happy_and_blocked(tmp_path: Path):
    spec_ok = tmp_path / "ok.json"
    spec_ok.write_text(json.dumps({"provider": "local", "model": "m", "cost_estimate_eur": 0.0}))

    root = Path(__file__).resolve().parents[1]
    env = {**os.environ, "PYTHONPATH": str(root)}
    res_ok = subprocess.run(
        [sys.executable, "-m", "courier_core.provider_cost_guard", str(spec_ok)],
        capture_output=True,
        text=True,
        cwd=root,
        env=env,
    )
    assert res_ok.returncode == 0
    data_ok = json.loads(res_ok.stdout)
    assert data_ok["allowed"] is True

    spec_blocked = tmp_path / "blocked.json"
    spec_blocked.write_text(json.dumps({"provider": "payg", "model": "heavy", "cost_estimate_eur": 1.5}))

    res_blocked = subprocess.run(
        [sys.executable, "-m", "courier_core.provider_cost_guard", str(spec_blocked)],
        capture_output=True,
        text=True,
        cwd=root,
        env=env,
    )
    assert res_blocked.returncode == 1
    data_blocked = json.loads(res_blocked.stdout)
    assert data_blocked["allowed"] is False
    assert data_blocked["reason"] == "AUTONOMOUS_SPEND_LIMIT_EXCEEDED"
