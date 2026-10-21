"""Offline test suite for ANTIGRAVITY 027 — PRE-DISPATCH COST AUTHORIZATION.

Verifies:
A. Known zero cost and otherwise authorized task -> Allowed to dispatch.
B. Known positive cost without authorization / grant -> Denied (requires Human Gate).
C. Unknown cost / missing estimation -> Denied (fails closed).
D. Expired or revoked spend grant -> Denied.
E. Result of cost-blocked task cannot be submitted as a bogus success.
F. Replayed attempt of the same prompt/task after denial remains blocked.
"""

import copy
import json
import pytest
from pathlib import Path

from scripts.resource_policy import CostGate
from courier_runtime.revenue import SpendGrant
from server import app as server_app

TEST_SECRET = "test-secret"
TEST_AUTH = {"Authorization": f"Bearer {TEST_SECRET}"}


@pytest.fixture
def test_client(tmp_path, monkeypatch):
    """Sets up an isolated server instance with temporary state."""
    state_file = tmp_path / "central_state.json"
    init_state = {
        "goals": {},
        "tasks": {},
        "workers": {},
        "walls": {},
        "seq": 0,
    }
    state_file.write_text(json.dumps(init_state), encoding="utf-8")
    monkeypatch.setattr(server_app, "STATE_FILE", str(state_file))
    monkeypatch.setattr(server_app, "API_KEY", TEST_SECRET)
    monkeypatch.setattr(server_app, "VERIFIER_API_KEY", "verifier-secret")
    with server_app.app.test_client() as client:
        yield client


# --- Pure CostGate Evaluation Tests ---

def test_case_a_known_zero_cost_authorized():
    """Case A: Known zero cost for an active resource tier is authorized."""
    res = CostGate.evaluate_spend_request("google_antigravity_plus", estimated_cost_eur=0.0)
    assert res["allowed"] is True
    assert res["reason"] == "AUTHORIZED_ACTIVE_RESOURCE"
    assert res["requires_human_gate"] is False


def test_case_b_known_positive_cost_denied_without_grant():
    """Case B: Known positive cost without a spend grant is strictly denied."""
    res = CostGate.evaluate_spend_request("google_antigravity_plus", estimated_cost_eur=15.0)
    assert res["allowed"] is False
    assert res["reason"] == "SPEND_NOT_ALLOWED_BY_POLICY"
    assert res["requires_human_gate"] is True


@pytest.mark.parametrize("unknown_cost", [None, "unknown", "", object(), float("nan"), float("inf"), float("-inf"), True, False, "0", "abc", "inf"])
def test_case_c_unknown_cost_denied(unknown_cost):
    """Case C: Unknown or indeterminate cost fails closed and is denied."""
    res = CostGate.evaluate_spend_request("google_antigravity_plus", estimated_cost_eur=unknown_cost)
    assert res["allowed"] is False
    assert res["reason"] == "UNKNOWN_COST_UNAUTHORIZED"
    assert res["requires_human_gate"] is True


@pytest.mark.parametrize("invalid_neg_cost", [-1, -1.0, -0.0, -99.99])
def test_case_c2_negative_cost_strictly_denied(invalid_neg_cost):
    """Case C2: Negative costs (including negative zero -0.0) are strictly denied."""
    res = CostGate.evaluate_spend_request("google_antigravity_plus", estimated_cost_eur=invalid_neg_cost)
    assert res["allowed"] is False
    assert res["reason"] == "INVALID_NEGATIVE_COST"
    assert res["requires_human_gate"] is True


def test_case_d_expired_or_revoked_grant():
    """Case D: Expired or revoked grant cannot authorize positive spend."""
    # Active grant window: 1000 -> 2000
    expired_grant = SpendGrant("g1", "acct", "api", "llm", 50.0, start=1000.0, end=2000.0)
    res_expired = CostGate.evaluate_spend_request(
        "google_antigravity_plus",
        estimated_cost_eur=10.0,
        grant=expired_grant,
        at=2500.0,  # after end
    )
    assert res_expired["allowed"] is False
    assert res_expired["reason"] == "GRANT_EXPIRED"

    # Revoked grant
    revoked_grant = SpendGrant("g2", "acct", "api", "llm", 50.0, start=1000.0, end=2000.0, revoked=True)
    res_revoked = CostGate.evaluate_spend_request(
        "google_antigravity_plus",
        estimated_cost_eur=10.0,
        grant=revoked_grant,
        at=1500.0,
    )
    assert res_revoked["allowed"] is False
    assert res_revoked["reason"] == "GRANT_REVOKED"


# --- Server Pre-Dispatch Integration Tests ---

def test_case_e_cost_blocked_task_cannot_accept_result(test_client):
    """Case E: A task blocked by CostGate is never dispatched and cannot receive results."""
    # Register worker
    test_client.post("/workers/register", json={
        "worker_id": "W-01",
        "capabilities": ["linux"],
        "cost_class": "low"
    }, headers=TEST_AUTH)

    # Submit goal with a step that has unapproved positive cost
    goal_res = test_client.post("/goals", json={
        "goal_text": "Paid cloud task",
        "workflow_plan": [{
            "task_id": "task-paid-01",
            "instruction": "Run expensive query",
            "target_agent": "linux",
            "estimated_cost_eur": 25.0,  # Positive cost without grant
        }]
    }, headers=TEST_AUTH)
    assert goal_res.status_code == 200

    # Worker attempts claim -> must be denied pre-dispatch
    claim_res = test_client.post("/tasks/claim", json={"worker_id": "W-01"}, headers=TEST_AUTH)
    assert claim_res.status_code == 200
    claim_data = claim_res.get_json()
    assert claim_data["task"] is None
    assert claim_data.get("reason") == "SPEND_NOT_ALLOWED_BY_POLICY"

    # Verify task state is marked blocked in state
    state = server_app.load_state()
    blocked_task = state["tasks"].get("task-paid-01") or state["goals"][list(state["goals"].keys())[0]]["workflow_plan"][0]
    assert blocked_task["status"] == "BLOCKED_COST_AUTHORIZATION"

    # Worker or attacker attempts to submit a bogus success result for the blocked task
    result_res = test_client.post("/tasks/result", json={
        "task_id": "task-paid-01",
        "worker_id": "W-01",
        "attempt_id": "task-paid-01:attempt:1",
        "dispatch_id": "dsp-fake",
        "status": "SUCCESS",
        "artifacts": [{"path": "out.txt", "sha256": "0"*64}]
    }, headers=TEST_AUTH)
    # Must fail closed: task is not DISPATCHED, result is rejected
    assert result_res.status_code == 409
    assert "not awaiting a result" in result_res.get_json().get("error", "").lower()


def test_case_f_replay_after_denial_remains_blocked(test_client):
    """Case F: Repeated claims/prompts for an unapproved task remain strictly blocked."""
    test_client.post("/workers/register", json={
        "worker_id": "W-02",
        "capabilities": ["linux"],
        "cost_class": "free"
    }, headers=TEST_AUTH)

    # Goal with unknown cost
    test_client.post("/goals", json={
        "goal_text": "Indeterminate cost task",
        "workflow_plan": [{
            "task_id": "task-unknown-01",
            "instruction": "Open-ended web scrape",
            "target_agent": "linux",
            "estimated_cost_eur": None,  # Unknown cost
        }]
    }, headers=TEST_AUTH)

    # First claim attempt
    claim1 = test_client.post("/tasks/claim", json={"worker_id": "W-02"}, headers=TEST_AUTH).get_json()
    assert claim1["task"] is None
    assert claim1["reason"] == "UNKNOWN_COST_UNAUTHORIZED"

    # Repeated claim attempt (same prompt / same queue condition)
    claim2 = test_client.post("/tasks/claim", json={"worker_id": "W-02"}, headers=TEST_AUTH).get_json()
    assert claim2["task"] is None
    # Still denied, no money or side-effects minted
    assert claim2.get("reason") in ("UNKNOWN_COST_UNAUTHORIZED", None)


def test_case_g_server_boolean_or_nan_cost_blocked(test_client):
    """Case G: Tasks with boolean or non-finite cost cannot be dispatched via server."""
    test_client.post("/workers/register", json={
        "worker_id": "W-03",
        "capabilities": ["linux"],
        "cost_class": "free"
    }, headers=TEST_AUTH)

    # Goal with boolean False cost (which in raw Python could cast to 0.0)
    test_client.post("/goals", json={
        "goal_text": "Bool cost task",
        "workflow_plan": [{
            "task_id": "task-bool-01",
            "instruction": "Test boolean cost rejection",
            "target_agent": "linux",
            "estimated_cost_eur": False,
        }]
    }, headers=TEST_AUTH)

    claim = test_client.post("/tasks/claim", json={"worker_id": "W-03"}, headers=TEST_AUTH).get_json()
    assert claim["task"] is None
    assert claim["reason"] == "UNKNOWN_COST_UNAUTHORIZED"


def test_case_h_invalid_grant_limits():
    """Case H: Spend grants with invalid, non-finite, negative, or bool limits are rejected."""
    for bad_limit in [float("nan"), float("inf"), -5.0, True, False, "100"]:
        grant = SpendGrant("g_bad", "acct", "api", "llm", bad_limit, start=1000.0, end=2000.0)
        res = CostGate.evaluate_spend_request(
            "google_antigravity_plus",
            estimated_cost_eur=10.0,
            grant=grant,
            at=1500.0,
        )
        assert res["allowed"] is False
        assert res["reason"] == "INVALID_GRANT_LIMIT"
        assert res["requires_human_gate"] is True



def test_case_i_unknown_cost_boolean_flag_blocked(test_client):
    """Case I: Tasks with unknown_cost=True are strictly blocked pre-dispatch."""
    test_client.post("/workers/register", json={
        "worker_id": "W-04",
        "capabilities": ["linux"],
        "cost_class": "free"
    }, headers=TEST_AUTH)

    test_client.post("/goals", json={
        "goal_text": "Task with unknown_cost=True",
        "workflow_plan": [{
            "task_id": "task-flag-01",
            "instruction": "Test unknown_cost flag",
            "target_agent": "linux",
            "unknown_cost": True,
        }]
    }, headers=TEST_AUTH)

    claim = test_client.post("/tasks/claim", json={"worker_id": "W-04"}, headers=TEST_AUTH).get_json()
    assert claim["task"] is None
    assert claim["reason"] == "UNKNOWN_COST_UNAUTHORIZED"


def test_case_j_missing_cost_in_state_fails_closed_and_is_blocked(test_client):
    """Case J: A task injected into state without estimated_cost_eur fails closed and is blocked."""
    test_client.post("/workers/register", json={
        "worker_id": "W-05",
        "capabilities": ["linux"],
        "cost_class": "free"
    }, headers=TEST_AUTH)

    # Directly create a goal in state where a task completely lacks estimated_cost_eur
    state = server_app.load_state()
    goal_id = "goal-raw-missing-cost"
    task_id = "task-raw-missing-cost"
    raw_task = {
        "task_id": task_id,
        "goal_id": goal_id,
        "instruction": "Unannotated raw task",
        "target_agent": "linux",
        "target_capability": "linux",
        "status": "QUEUED",
        "attempts": 0,
    }
    state["goals"][goal_id] = {
        "goal_id": goal_id,
        "goal_text": "Goal with unannotated task",
        "status": "ACTIVE",
        "budget_limit": 0.0,
        "budget_spent": 0.0,
        "workflow_plan": [raw_task],
        "current_step_index": 0,
    }
    state["tasks"][task_id] = raw_task
    server_app.save_state(state)

    claim = test_client.post("/tasks/claim", json={"worker_id": "W-05"}, headers=TEST_AUTH).get_json()
    assert claim["task"] is None
    assert claim["reason"] == "UNKNOWN_COST_UNAUTHORIZED"

    # Verify task state is marked blocked
    updated_state = server_app.load_state()
    assert updated_state["tasks"][task_id]["status"] == "BLOCKED_COST_AUTHORIZATION"
    assert updated_state["tasks"][task_id]["blocked_reason"] == "UNKNOWN_COST_UNAUTHORIZED"


def test_case_k_unknown_cost_truthy_string_blocked(test_client):
    """Case K: Tasks with truthy unknown_cost strings (e.g. 'true') are strictly blocked."""
    test_client.post("/workers/register", json={
        "worker_id": "W-06",
        "capabilities": ["linux"],
        "cost_class": "free"
    }, headers=TEST_AUTH)

    test_client.post("/goals", json={
        "goal_text": "Task with unknown_cost='true'",
        "workflow_plan": [{
            "task_id": "task-flag-str-01",
            "instruction": "Test truthy unknown_cost string",
            "target_agent": "linux",
            "unknown_cost": "true",
        }]
    }, headers=TEST_AUTH)

    claim = test_client.post("/tasks/claim", json={"worker_id": "W-06"}, headers=TEST_AUTH).get_json()
    assert claim["task"] is None
    assert claim["reason"] == "UNKNOWN_COST_UNAUTHORIZED"


def test_case_l_prepare_task_sanitizes_missing_cost_and_preserves_unknown():
    """Case L: prepare_task binds estimated_cost_eur=0.0 by default, and None for unknown."""
    from scripts.integration_contract import prepare_task

    # 1. Default zero-cost for standard tasks
    t1 = prepare_task({"task_id": "t1", "goal_id": "g1", "target_agent": "windows"})
    assert t1["estimated_cost_eur"] == 0.0

    # 2. Preserves explicit positive cost
    t2 = prepare_task({"task_id": "t2", "goal_id": "g1", "target_agent": "windows", "estimated_cost_eur": 12.5})
    assert t2["estimated_cost_eur"] == 12.5

    # 3. Preserves explicit None
    t3 = prepare_task({"task_id": "t3", "goal_id": "g1", "target_agent": "windows", "estimated_cost_eur": None})
    assert t3["estimated_cost_eur"] is None

    # 4. Sets None when unknown_cost is True or truthy
    t4 = prepare_task({"task_id": "t4", "goal_id": "g1", "target_agent": "windows", "unknown_cost": True})
    assert t4["estimated_cost_eur"] is None

    t5 = prepare_task({"task_id": "t5", "goal_id": "g1", "target_agent": "windows", "unknown_cost": "yes"})
    assert t5["estimated_cost_eur"] is None
