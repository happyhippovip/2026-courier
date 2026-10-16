"""ANTIGRAVITY 027 — PRE-DISPATCH COST AUTHORIZATION Test Suite.

Verifies:
A. Known Zero Cost: task with proven zero cost on authorized active resource is admitted.
B. Known Positive Cost: task with positive cost without an authorized grant is blocked.
C. Unknown Cost: task with unverified/unknown/None cost is blocked fail-closed.
D. Expired Grant: task whose previously valid spend grant has expired is blocked.
E. Result of cost-blocked task submitted as supposed success is rejected fail-closed.
F. Replay After Denial: re-submitting an already rejected/blocked task does not dispatch or spend.
"""

import json
import math
import os
import sys
import time
from pathlib import Path
from unittest import mock
import pytest

from courier_runtime.revenue import SpendGrant
from courier_runtime.admission_gate import ExecutionAudit, WindowAdmissionGate, WindowTarget, TerminalGeometry
from scripts.resource_policy import CostGate, ResourcePolicyManager
from scripts.intake_dispatcher import (
    dispatch_intake,
    fingerprint_task_id,
    validate_task_result_submission,
    ADMISSION_BLOCKED,
)


@pytest.fixture
def repo_dir(tmp_path):
    policy_dir = tmp_path / "events" / "policies"
    policy_dir.mkdir(parents=True, exist_ok=True)
    policy = {
        "active_paid_resources": {
            "google_antigravity_plus": {"status": "ACTIVE_PAID", "cost_class": "SUBSCRIPTION"},
        },
        "planned_resources": {
            "future_google_upgrade": {"status": "PLANNED_NOT_ACTIVE"},
        },
        "unauthorized_resources": {
            "on_demand_api_tiers": {"status": "UNAUTHORIZED_PAYG"},
        },
    }
    policy_file = policy_dir / "resource_policy.json"
    policy_file.write_text(json.dumps(policy), encoding="utf-8")
    return tmp_path


# -----------------------------------------------------------------------------
# Case A: Known Zero Cost
# -----------------------------------------------------------------------------
def test_case_a_known_zero_cost_admitted(repo_dir):
    """A. Kosten nachweislich null und Task anderweitig autorisiert -> admitted."""
    res = CostGate.evaluate_spend_request(
        "google_antigravity_plus",
        estimated_cost_eur=0.0,
        requested_action="EXECUTE_TASK",
        repo_dir=repo_dir,
    )
    assert res["allowed"] is True
    assert res["reason"] == "AUTHORIZED_ACTIVE_RESOURCE"
    assert res["requires_human_gate"] is False


def test_case_a_known_zero_cost_window_admission(repo_dir):
    """A (Window Gate): WindowAdmissionGate admits zero cost task on active resource."""
    gate = WindowAdmissionGate()
    target = WindowTarget(
        window_id="win-0",
        title="Terminal 1",
        host="local",
        geometry=TerminalGeometry(cols=100, rows=30),
        custody_state="IDLE",
        is_busy=False,
    )
    decision = gate.evaluate(
        target=target,
        workkey="wk-zero-01",
        session_id="sess-01",
        estimated_cost_eur=0.0,
        resource_id="google_antigravity_plus",
    )
    assert decision.decision == "ADMIT"
    assert decision.receipt_id is not None


# -----------------------------------------------------------------------------
# Case B: Known Positive Cost Without Approval
# -----------------------------------------------------------------------------
def test_case_b_known_positive_cost_without_approval_blocked(repo_dir):
    """B. Bekannte positive Kosten ohne Genehmigung -> blocked."""
    res = CostGate.evaluate_spend_request(
        "google_antigravity_plus",
        estimated_cost_eur=14.50,
        requested_action="EXECUTE_TASK",
        repo_dir=repo_dir,
        grant=None,
    )
    assert res["allowed"] is False
    assert res["reason"] == "SPEND_NOT_ALLOWED_BY_POLICY"
    assert res["requires_human_gate"] is True


def test_case_b_known_positive_cost_intake_dispatch_blocked(tmp_path, monkeypatch):
    """B (Intake Dispatch): Positive cost without grant transitions intake to BLOCKED."""
    monkeypatch.chdir(tmp_path)
    state_file = str(tmp_path / "central_state.json")

    intake = {
        "customer_reference": "ref-b-paid",
        "target_owner": "owner",
        "target_repo": "repo",
        "target_sha": "sha123",
        "estimated_cost_eur": 25.0,
        "grant": None,
    }
    intake_file = tmp_path / "intake_b.json"
    intake_file.write_text(json.dumps(intake))

    task_id = dispatch_intake(str(intake_file), state_file=state_file)

    with open(state_file) as f:
        state = json.load(f)

    assert state["tasks"][task_id]["admission"] == ADMISSION_BLOCKED
    assert state["tasks"][task_id]["state"] == "BLOCKED"
    assert "SPEND_NOT_ALLOWED_BY_POLICY" in state["tasks"][task_id]["blocked_reason"]
    assert state["tasks"][task_id]["model_calls"] == 0


# -----------------------------------------------------------------------------
# Case C: Unknown Cost
# -----------------------------------------------------------------------------
@pytest.mark.parametrize("unknown_val", [None, "unknown", float("nan"), float("inf"), -5.0, True])
def test_case_c_unknown_cost_fail_closed(repo_dir, unknown_val):
    """C. Kosten sind unbekannt -> fail-closed (UNKNOWN_COST)."""
    res = CostGate.evaluate_spend_request(
        "google_antigravity_plus",
        estimated_cost_eur=unknown_val,
        repo_dir=repo_dir,
    )
    assert res["allowed"] is False
    assert res["reason"] == "UNKNOWN_COST"
    assert res["requires_human_gate"] is True


def test_case_c_unknown_cost_window_admission_rejected():
    """C (Window Gate): Window admission rejects unknown cost."""
    gate = WindowAdmissionGate()
    target = WindowTarget(
        window_id="win-c",
        title="Terminal 1",
        host="local",
        geometry=TerminalGeometry(cols=100, rows=30),
        custody_state="IDLE",
        is_busy=False,
    )
    decision = gate.evaluate(
        target=target,
        workkey="wk-unknown-01",
        session_id="sess-c",
        estimated_cost_eur=None,  # unknown
    )
    assert decision.decision == "REJECT"
    assert any("UNKNOWN_COST" in r for r in decision.reasons)


# -----------------------------------------------------------------------------
# Case D: Expired Grant
# -----------------------------------------------------------------------------
def test_case_d_expired_grant_rejected(repo_dir):
    """D. Früher gültige Kostenfreigabe ist abgelaufen -> EXPIRED_GRANT."""
    # Grant was valid from t=100 to t=200
    expired_grant = SpendGrant(
        grant_id="sg-old-001",
        account="acct-main",
        purpose="cloud",
        service="google_antigravity_plus",
        max_spend_eur=50.0,
        start=100.0,
        end=200.0,
    )
    current_time = 250.0  # past expiration

    res = CostGate.evaluate_spend_request(
        "google_antigravity_plus",
        estimated_cost_eur=10.0,
        requested_action="EXECUTE_TASK",
        repo_dir=repo_dir,
        grant=expired_grant,
        current_time=current_time,
    )
    assert res["allowed"] is False
    assert res["reason"] == "EXPIRED_GRANT"
    assert "expired" in res["message"].lower()


def test_case_d_valid_active_grant_accepted(repo_dir):
    """D (Counter-Check): Unexpired, active grant within bounds is accepted."""
    active_grant = SpendGrant(
        grant_id="sg-act-002",
        account="acct-main",
        purpose="cloud",
        service="google_antigravity_plus",
        max_spend_eur=50.0,
        start=100.0,
        end=500.0,
    )
    current_time = 250.0  # inside window

    res = CostGate.evaluate_spend_request(
        "google_antigravity_plus",
        estimated_cost_eur=15.0,
        requested_action="EXECUTE_TASK",
        repo_dir=repo_dir,
        grant=active_grant,
        current_time=current_time,
    )
    assert res["allowed"] is True
    assert res["reason"] == "AUTHORIZED_BY_SPEND_GRANT"
    assert res["grant_id"] == "sg-act-002"


# -----------------------------------------------------------------------------
# Case E: Result of Cost-Blocked Task Submitted as Supposed Success
# -----------------------------------------------------------------------------
def test_case_e_result_of_cost_blocked_task_rejected_by_audit():
    """E (ExecutionAudit): Execution not cost-authorized cannot claim pass."""
    audit = ExecutionAudit(
        command="run_model_pipeline",
        execution_handle="h-unauth-01",
        started=True,
        completed=True,
        exit_code=0,
        output_captured=True,
        cost_authorized=False,  # cost was not authorized
    )
    assert audit.is_passed is False
    valid, reason = audit.validate_verdict(claimed_pass=True)
    assert valid is False
    assert "COST_AUTHORIZATION_DENIED" in reason


def test_case_e_result_of_blocked_task_rejected_in_central_state(tmp_path, monkeypatch):
    """E (Central State): Submitting result for a cost-blocked task is rejected."""
    monkeypatch.chdir(tmp_path)
    state_file = str(tmp_path / "central_state.json")

    # Simulate task that was blocked for cost
    intake = {
        "customer_reference": "ref-e-unauth",
        "target_owner": "owner",
        "target_repo": "repo",
        "target_sha": "shaE",
        "estimated_cost_eur": 100.0,
        "grant": None,
    }
    intake_file = tmp_path / "intake_e.json"
    intake_file.write_text(json.dumps(intake))

    task_id = dispatch_intake(str(intake_file), state_file=state_file)

    # Attempt to submit result for blocked task
    allowed, message = validate_task_result_submission(task_id, state_file=state_file)
    assert allowed is False
    assert "TASK_BLOCKED_UNAUTHORIZED" in message


# -----------------------------------------------------------------------------
# Case F: Replay After Denial (Repeated Prompts Do Not Circumvent Block)
# -----------------------------------------------------------------------------
def test_case_f_replay_after_denial_no_spend_no_dispatch(tmp_path, monkeypatch):
    """F: Re-offering the identical prompt/intake retains BLOCKED and makes 0 model calls."""
    monkeypatch.chdir(tmp_path)
    state_file = str(tmp_path / "central_state.json")

    intake = {
        "customer_reference": "ref-f-repeat",
        "target_owner": "owner",
        "target_repo": "repo",
        "target_sha": "shaF",
        "estimated_cost_eur": 50.0,  # positive unapproved cost
        "grant": None,
    }
    intake_file = tmp_path / "intake_f.json"
    intake_file.write_text(json.dumps(intake))

    # Sweep 1: Blocked by CostGate
    task_id_1 = dispatch_intake(str(intake_file), state_file=state_file)

    with open(state_file) as f:
        state_1 = json.load(f)
    assert state_1["tasks"][task_id_1]["state"] == "BLOCKED"
    assert state_1["tasks"][task_id_1]["model_calls"] == 0

    # Sweep 2: Identical prompt/intake submitted again
    subprocess_spawns = []
    with mock.patch("subprocess.run", side_effect=lambda *args, **kw: subprocess_spawns.append(args)):
        task_id_2 = dispatch_intake(str(intake_file), state_file=state_file)

    # Must be identical task ID
    assert task_id_1 == task_id_2

    # Verification: zero subprocesses spawned, zero model calls, still BLOCKED
    assert len(subprocess_spawns) == 0

    with open(state_file) as f:
        state_2 = json.load(f)
    assert state_2["tasks"][task_id_2]["state"] == "BLOCKED"
    assert state_2["tasks"][task_id_2]["model_calls"] == 0
