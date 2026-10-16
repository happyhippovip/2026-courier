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


@pytest.mark.parametrize("unknown_cost", [None, "unknown", "", object()])
def test_case_c_unknown_cost_denied(unknown_cost):
    """Case C: Unknown or indeterminate cost fails closed and is denied."""
    res = CostGate.evaluate_spend_request("google_antigravity_plus", estimated_cost_eur=unknown_cost)
    assert res["allowed"] is False
    assert res["reason"] == "UNKNOWN_COST_UNAUTHORIZED"
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
