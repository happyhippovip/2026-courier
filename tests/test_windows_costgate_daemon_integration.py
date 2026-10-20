"""Integration tests for Windows native CostGate and daemon payload harmonization."""

import importlib.util
import math
import os
import sys
from pathlib import Path

import pytest

from scripts.resource_policy import CostGate, ResourcePolicyManager

ROOT = Path(__file__).resolve().parents[1]
DAEMON_PATH = ROOT / "scripts" / "windows_worker" / "daemon.py"


def _load_daemon(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    spec = importlib.util.spec_from_file_location("daemon_under_test", DAEMON_PATH)
    daemon = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(daemon)
    return daemon


def test_resource_policy_fallback_authorizes_windows_native_zero_cost(tmp_path):
    """When no policy file is present, fallback default must include windows_native."""
    empty_dir = tmp_path / "empty_repo"
    empty_dir.mkdir()
    policy = ResourcePolicyManager.get_policy(repo_dir=empty_dir)

    assert "windows_native" in policy["active_paid_resources"]
    entry = policy["active_paid_resources"]["windows_native"]
    assert entry["status"] == "ACTIVE_PAID"
    assert entry["role"] == "LOCAL_EXECUTOR"
    assert entry["cost_per_run_eur"] == 0.0

    # Evaluate zero cost spend under fallback policy
    eval_res = CostGate.evaluate_spend_request("windows_native", estimated_cost_eur=0.0, repo_dir=empty_dir)
    assert eval_res["allowed"] is True
    assert eval_res["reason"] == "AUTHORIZED_ACTIVE_RESOURCE"
    assert eval_res["requires_human_gate"] is False


@pytest.mark.parametrize(
    "bad_cost,expected_reason",
    [
        (None, "UNKNOWN_COST_UNAUTHORIZED"),
        (float("nan"), "UNKNOWN_COST_UNAUTHORIZED"),
        (float("inf"), "UNKNOWN_COST_UNAUTHORIZED"),
        (float("-inf"), "UNKNOWN_COST_UNAUTHORIZED"),
        (True, "UNKNOWN_COST_UNAUTHORIZED"),
        (False, "UNKNOWN_COST_UNAUTHORIZED"),
        ("0.0", "UNKNOWN_COST_UNAUTHORIZED"),
        (-0.01, "INVALID_NEGATIVE_COST"),
        (-10.0, "INVALID_NEGATIVE_COST"),
        (5.0, "SPEND_NOT_ALLOWED_BY_POLICY"),
    ],
)
def test_resource_policy_fallback_blocks_windows_native_invalid_or_unauthorized_cost(tmp_path, bad_cost, expected_reason):
    empty_dir = tmp_path / "empty_repo"
    empty_dir.mkdir()

    eval_res = CostGate.evaluate_spend_request("windows_native", estimated_cost_eur=bad_cost, repo_dir=empty_dir)
    assert eval_res["allowed"] is False
    assert eval_res["reason"] == expected_reason
    assert eval_res["requires_human_gate"] is True


def test_daemon_run_task_costgate_blocks_and_emits_payload(tmp_path, monkeypatch):
    """Proves daemon.run_task and build_result_payload carry blocked=True and block_reason."""
    daemon = _load_daemon(tmp_path, monkeypatch)
    config = {"WORKER_ID": "TEST-WIN-01"}

    task_unknown = {
        "task_id": "test-task-unknown",
        "instruction": "Write-Host 'SHOULD_NOT_EXECUTE'",
        "unknown_cost": True,
        "goal_id": "goal-1",
    }

    result = daemon.run_task(task_unknown, config)
    assert result["status"] == "FAILED"
    assert result["blocked"] is True
    assert result["run_id"] == "cost-gate-blocked"
    assert "COST_GATE_DENIED" in result["stderr"]

    payload = daemon.build_result_payload(task_unknown, result, config)
    assert payload["status"] == "FAILED"
    assert payload["blocked"] is True
    assert payload["block_reason"] == "COST_GATE_DENIED"
    assert payload["run_id"] == "cost-gate-blocked"


def test_daemon_run_task_zero_cost_allowed(tmp_path, monkeypatch):
    """Proves zero-cost task is authorized through CostGate."""
    daemon = _load_daemon(tmp_path, monkeypatch)
    config = {"WORKER_ID": "TEST-WIN-01"}

    task_zero = {
        "task_id": "test-task-zero",
        "instruction": "Write-Output 'HELLO_COURIER_TEST'",
        "estimated_cost_eur": 0.0,
        "goal_id": "goal-zero",
        "artifacts": [],
    }

    result = daemon.run_task(task_zero, config)
    # Under Windows, this executes powershell and returns SUCCESS
    if sys.platform == "win32":
        assert result["status"] == "SUCCESS"
        assert "HELLO_COURIER_TEST" in result["stdout"]
        assert result.get("blocked") is not True
    else:
        # On non-Windows without PowerShell, cost gate passed before shell execution
        assert result.get("run_id") != "cost-gate-blocked"
