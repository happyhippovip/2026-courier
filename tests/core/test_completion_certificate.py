"""Tests for Completion Certificate & Binding Goal Closure (User Acceptance Requirement O)."""
import pytest

from courier_core.completion_certificate import (
    PROOF_LEVEL_CRYPTOGRAPHIC,
    PROOF_LEVEL_UNVERIFIED,
    STATUS_ABANDONED,
    STATUS_BLOCKED,
    STATUS_CERTIFIED,
    STATUS_INCOMPLETE,
    derive_completion_certificate,
)


def test_completion_certificate_empty():
    res = derive_completion_certificate(None, None)
    assert res["certified"] is False
    assert res["status"] == STATUS_INCOMPLETE
    assert res["certificate_id"] is None
    assert res["plan_extent"] == "0/0 Steps"


def test_completion_certificate_in_progress():
    goal = {
        "goal_id": "goal-in-prog",
        "goal_text": "In progress pipeline",
        "status": "ACTIVE",
        "workflow_plan": [
            {"task_id": "step-1", "instruction": "Step 1", "status": "RECONCILED"},
            {"task_id": "step-2", "instruction": "Step 2", "status": "QUEUED"},
        ],
    }
    state = {
        "tasks": {
            "step-1": {
                "status": "RECONCILED",
                "result": {"result_id": "r-step-1"},
                "verification": {"verdict": "PASS", "verifier_id": "v-step-1", "result_id": "r-step-1"},
            },
            "step-2": {"status": "QUEUED"},
        }
    }
    res = derive_completion_certificate(goal, state)
    assert res["certified"] is False
    assert res["status"] == STATUS_INCOMPLETE
    assert res["plan_extent"] == "1/2 Steps"
    assert res["proof_level"] == PROOF_LEVEL_UNVERIFIED
    assert "in Bearbeitung" in res["human_summary"]


def test_completion_certificate_blocked_and_abandoned():
    goal_blocked = {
        "goal_id": "goal-b",
        "status": "BLOCKED",
        "workflow_plan": [{"task_id": "step-1"}],
    }
    res_b = derive_completion_certificate(goal_blocked, {})
    assert res_b["certified"] is False
    assert res_b["status"] == STATUS_BLOCKED

    goal_abandoned = {
        "goal_id": "goal-a",
        "status": "ABANDONED",
        "workflow_plan": [{"task_id": "step-1"}],
    }
    res_a = derive_completion_certificate(goal_abandoned, {})
    assert res_a["certified"] is False
    assert res_a["status"] == STATUS_ABANDONED
    assert "ABANDONED" in res_a["human_summary"]


def test_completion_certificate_done_certified():
    goal = {
        "goal_id": "goal-done-01",
        "goal_text": "Analyze financial quarterly report",
        "status": "DONE",
        "workflow_plan": [
            {
                "task_id": "task-fetch",
                "instruction": "Fetch financial document",
                "status": "RECONCILED",
            },
            {
                "task_id": "task-compute",
                "instruction": "Compute metrics",
                "status": "RECONCILED",
            },
        ],
    }
    state = {
        "tasks": {
            "task-fetch": {
                "status": "RECONCILED",
                "result_id": "res-fetch-101",
                "result": {"result_id": "res-fetch-101"},
                "verification": {"verdict": "PASS", "verifier_id": "v1_doc_verifier", "result_id": "res-fetch-101"},
                "artifacts": [{"name": "fin.pdf", "sha256": "abc123"}],
                "attempts": 2,
                "resumed_from": "attempt-1",
            },
            "task-compute": {
                "status": "RECONCILED",
                "result_id": "res-compute-102",
                "result": {"result_id": "res-compute-102"},
                "verification": {"verdict": "PASS", "verifier_id": "v1_calc_verifier", "result_id": "res-compute-102"},
                "artifacts": [{"name": "metrics.csv", "sha256": "def456"}],
                "attempts": 1,
            },
        }
    }

    res = derive_completion_certificate(goal, state)
    assert res["certified"] is True
    assert res["status"] == STATUS_CERTIFIED
    assert res["proof_level"] == PROOF_LEVEL_CRYPTOGRAPHIC
    assert res["certificate_id"].startswith("cert-")
    assert len(res["certificate_id"]) == 69  # "cert-" + 64 hex chars
    assert res["plan_extent"] == "2/2 Steps"
    assert res["retry_occurred"] is True
    assert res["completed_at"] == "NICHT ERFASST (Pre-Timestamp-State)"
    assert "verbindlich abgeschlossen" in res["human_summary"]


def test_completion_certificate_with_timestamp():
    goal = {
        "goal_id": "goal-timed",
        "status": "DONE",
        "completed_at": "2026-10-16T18:15:00Z",
        "workflow_plan": [
            {"task_id": "t-1", "status": "RECONCILED"},
        ],
    }
    state = {
        "tasks": {
            "t-1": {"status": "RECONCILED", "result": {"result_id": "r-t-1"},
                    "verification": {"verdict": "PASS", "verifier_id": "v-timed", "result_id": "r-t-1"}}
        }
    }
    res = derive_completion_certificate(goal, state)
    assert res["certified"] is True
    assert res["completed_at"] == "2026-10-16T18:15:00Z"


def test_missing_verifier_is_not_invented_and_does_not_certify():
    goal = {
        "goal_id": "goal-no-verifier",
        "status": "DONE",
        "workflow_plan": [{"task_id": "t-1", "status": "SUCCESS"}],
    }
    state = {
        "tasks": {
            "t-1": {
                "status": "SUCCESS",
                "result": {"result_id": "r-t-1"},
                "verification": {"verdict": "PASS", "result_id": "r-t-1"},
            }
        }
    }
    res = derive_completion_certificate(goal, state)
    assert res["certified"] is False
    assert res["status"] == STATUS_INCOMPLETE
    assert res["plan_extent"] == "0/1 Steps"
    assert res["steps"][0]["verifier_id"] == "unrecorded"
    assert "courier_verifier" not in res["human_summary"]
    assert res["proof_level"] == PROOF_LEVEL_UNVERIFIED


def test_status_word_does_not_fill_plan_extent():
    goal = {
        "goal_id": "goal-status-word",
        "status": "ACTIVE",
        "workflow_plan": [{"task_id": "t-1", "status": "DONE"}],
    }
    state = {"tasks": {"t-1": {"status": "SUCCESS"}}}
    res = derive_completion_certificate(goal, state)
    assert res["certified"] is False
    assert res["plan_extent"] == "0/1 Steps"
    assert res["steps"][0]["verifier_id"] == "unrecorded"


def test_server_goal_certificate_endpoint(tmp_path, monkeypatch):
    import server.app as courier_server

    monkeypatch.setattr(courier_server, "STATE_FILE", str(tmp_path / "state.json"))
    monkeypatch.setattr(courier_server, "API_KEY", "test-secret")
    app = courier_server.app
    client = app.test_client()
    headers = {"Authorization": "Bearer test-secret"}

    goal_id = "test-cert-goal"
    state = {
        "goals": {
            goal_id: {
                "goal_id": goal_id,
                "status": "DONE",
                "workflow_plan": [
                    {
                        "task_id": "t-done",
                        "instruction": "Step Done",
                        "status": "RECONCILED",
                    }
                ],
            }
        },
        "tasks": {
            "t-done": {
                "status": "RECONCILED",
                "result": {"result_id": "r-t-done"},
                "verification": {"verdict": "PASS", "verifier_id": "v-done", "result_id": "r-t-done"},
            }
        },
        "workers": {},
    }
    courier_server.save_state(state)

    res = client.get(f"/goals/{goal_id}/certificate", headers=headers)
    assert res.status_code == 200
    data = res.get_json()
    assert data["certified"] is True
    assert data["status"] == STATUS_CERTIFIED
    assert data["plan_extent"] == "1/1 Steps"

    # Also test that GET /goals/<id> now includes certificate
    res_goal = client.get(f"/goals/{goal_id}", headers=headers)
    assert res_goal.status_code == 200
    goal_data = res_goal.get_json()
    assert "certificate" in goal_data
    assert goal_data["certificate"]["certified"] is True

    # 404 for non-existent
    res_404 = client.get("/goals/nonexistent/certificate", headers=headers)
    assert res_404.status_code == 404


# --- REDTEAM R1 negative tests -------------------------------------------
import pytest as _pytest


@_pytest.mark.parametrize("task", [
    {"status": "DONE"},
    {"status": "SUCCESS"},
    {"status": "RECONCILED"},
    {"status": "SUCCESS", "verification": {"verdict": "FAIL", "verifier_id": "v"}},
    {"status": "RECONCILED", "result": {"result_id": "r2"},
     "verification": {"verdict": "PASS", "verifier_id": "v", "result_id": "r1"}},
])
def test_no_certificate_without_bound_verifier_pass(task):
    goal = {"goal_id": "g", "status": "DONE", "workflow_plan": [{"task_id": "t"}]}
    res = derive_completion_certificate(goal, {"tasks": {"t": task}})
    assert res["certified"] is False
    assert res["proof_level"] != "VERIFIED_CRYPTOGRAPHIC"


# --- REDTEAM R1 F1 rev2 (Pruefer 5fd06fed FAIL on 649253a3) ----------------
# A verifier PASS only binds when result_id is a non-empty string on BOTH
# sides; None == None or "" == "" must not certify.
@_pytest.mark.parametrize("task", [
    # PASS, no result_id anywhere
    {"status": "RECONCILED", "verification": {"verdict": "PASS", "verifier_id": "v"}},
    {"status": "RECONCILED", "result": {},
     "verification": {"verdict": "PASS", "verifier_id": "v"}},
    # explicit None on both sides / on one side
    {"status": "RECONCILED", "result": {"result_id": None},
     "verification": {"verdict": "PASS", "verifier_id": "v", "result_id": None}},
    {"status": "RECONCILED", "result": {"result_id": "r1"},
     "verification": {"verdict": "PASS", "verifier_id": "v", "result_id": None}},
    {"status": "RECONCILED", "result": {"result_id": None},
     "verification": {"verdict": "PASS", "verifier_id": "v", "result_id": "r1"}},
    # empty string on both sides / on one side
    {"status": "RECONCILED", "result": {"result_id": ""},
     "verification": {"verdict": "PASS", "verifier_id": "v", "result_id": ""}},
    {"status": "RECONCILED", "result": {"result_id": "r1"},
     "verification": {"verdict": "PASS", "verifier_id": "v", "result_id": ""}},
    {"status": "RECONCILED", "result": {"result_id": ""},
     "verification": {"verdict": "PASS", "verifier_id": "v", "result_id": "r1"}},
], ids=["pass-no-result-id-anywhere", "pass-empty-result-dict",
        "none-both", "none-verifier", "none-result",
        "empty-both", "empty-verifier", "empty-result"])
def test_no_certificate_for_pass_without_nonempty_result_id(task):
    goal = {"goal_id": "g", "status": "DONE", "workflow_plan": [{"task_id": "t"}]}
    res = derive_completion_certificate(goal, {"tasks": {"t": task}})
    assert res["certified"] is False
    assert res["status"] != STATUS_CERTIFIED
    assert res["proof_level"] != PROOF_LEVEL_CRYPTOGRAPHIC


def test_certificate_for_pass_bound_to_same_nonempty_result_id():
    goal = {"goal_id": "g", "status": "DONE", "workflow_plan": [{"task_id": "t"}]}
    task = {"status": "RECONCILED", "result": {"result_id": "r1"},
            "verification": {"verdict": "PASS", "verifier_id": "v", "result_id": "r1"}}
    res = derive_completion_certificate(goal, {"tasks": {"t": task}})
    assert res["certified"] is True
    assert res["proof_level"] == PROOF_LEVEL_CRYPTOGRAPHIC
