from scripts.integration_contract import _canonical_hash
"""A->B reconcile unlock: completing A (claim/result/independent-verify)
makes dependent B claimable with no human continuation step.

Durable acceptance for: result A -> reconcile -> B READY/dispatch.
Server-owned tmp state only; touches no production files.
"""
import hashlib
from server import app as server_app

def make_client(tmp_path, monkeypatch):
    monkeypatch.setattr(server_app, "STATE_FILE", str(tmp_path / "state.json"))
    monkeypatch.setattr(server_app, "API_KEY", "test-secret")
    monkeypatch.setattr(server_app, "VERIFIER_API_KEY", "verifier-secret")
    assert server_app.STATE_FILE == str(tmp_path / "state.json"), "STATE_FILE not correctly set to temporary path"
    return server_app.app.test_client()

def auth():
    return {"Authorization": "Bearer test-secret"}

def verifier_auth():
    return {"Authorization": "Bearer verifier-secret"}

def test_a_reconcile_unlocks_b_without_human_step(tmp_path, monkeypatch):
    http = make_client(tmp_path, monkeypatch)
    assert http.post(
        "/workers/register",
        headers=auth(),
        json={"worker_id": "W-01", "platform": "mac", "capabilities": ["macos"]},
    ).status_code == 200
    goal = http.post(
        "/goals",
        headers=auth(),
        json={
            "goal_text": "A then B",
            "workflow_plan": [
                {
                    "task_id": "task-A",
                    "target_agent": "mac",
                    "instruction": "write a.txt",
                    "artifacts": ["a.txt"],
                },
                {
                    "task_id": "task-B",
                    "target_agent": "mac",
                    "instruction": "write b.txt",
                    "artifacts": ["b.txt"],
                    "depends_on": ["task-A"],
                },
            ],
        },
    ).get_json()

    claimed_a = http.post(
        "/tasks/claim", headers=auth(), json={"worker_id": "W-01", "timeout": 1}
    ).get_json()["task"]
    assert claimed_a["task_id"] == "task-A"

    assert http.post(
        "/workers/register",
        headers=auth(),
        json={"worker_id": "W-02", "timeout": 1, "platform": "mac", "capabilities": ["macos"]},
    ).status_code == 200
    blocked = http.post(
        "/tasks/claim", headers=auth(), json={"worker_id": "W-02", "timeout": 1}
    ).get_json()
    assert blocked.get("task") is None

    result = {
        "goal_id": claimed_a["goal_id"],
        "task_id": "task-A",
        "attempt_id": claimed_a["attempt_id"],
        "dispatch_id": claimed_a["dispatch_id"],
        "execution_ref": claimed_a.get("execution_ref", "exec-test"),
        "worker_id": "W-01",
        "run_id": "pid-test",
        "status": "SUCCESS",
        "artifacts": [
            {"path": "a.txt", "sha256": hashlib.sha256(b"a\n").hexdigest()}
        ],
        "runtime_identity": claimed_a["server_binding"]
    }
    result["result_id"] = f"result-{_canonical_hash(result)}"
    res = http.post("/tasks/result", headers=auth(), json=result)
    print("RESPONSE:", res.get_json())
    assert res.status_code == 200
    verification = {
                "task_id": "task-A",
        "result_id": result["result_id"],
        "verifier_id": "V-01",
        "verdict": "PASS",
        "artifacts": result["artifacts"],
        "received_runtime_identity": claimed_a["server_binding"],
    }
    accepted = http.post("/tasks/verify", headers=verifier_auth(), json=verification)
    assert accepted.status_code == 200

    claimed_b = http.post(
        "/tasks/claim", headers=auth(), json={"worker_id": "W-01", "timeout": 1}
    ).get_json()["task"]
    assert claimed_b["task_id"] == "task-B"
