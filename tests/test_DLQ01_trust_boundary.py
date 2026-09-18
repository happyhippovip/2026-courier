import pytest
import hashlib
from tests.test_ab_reconcile_unlock import make_client, auth

def verifier_auth():
    return {"Authorization": f"Bearer verifier-secret"}

def make_result(claimed, result_id="res-1"):
    return {
        "goal_id": claimed["goal_id"],
        "task_id": claimed["task_id"],
        "attempt_id": claimed["attempt_id"],
        "dispatch_id": claimed["dispatch_id"],
        "execution_ref": claimed.get("execution_ref", "exec-test"),
        "worker_id": claimed["worker_id"],
        "run_id": "pid-test",
        "result_id": result_id,
        "status": "SUCCESS",
        "artifacts": [{"path": "a.txt", "sha256": hashlib.sha256(b"a\n").hexdigest()}]
    }

def test_genuine_attestation_and_alias_attack_and_replay(tmp_path, monkeypatch):
    http = make_client(tmp_path, monkeypatch)
    http.post("/workers/register", headers=auth(), json={"worker_id": "W-01", "platform": "mac", "capabilities": ["macos"]})
    goal = http.post("/goals", headers=auth(), json={
        "goal_text": "A",
        "workflow_plan": [{"task_id": "task-A", "target_agent": "mac", "instruction": "Do something", "artifacts": ["a.txt"]}]
    }).json
    
    claimed = http.post("/tasks/claim", headers=auth(), json={"worker_id": "W-01", "capabilities": ["macos"]}).json["task"]
    claimed["worker_id"] = "W-01"

    result_json = make_result(claimed)
    res = http.post("/tasks/result", headers=auth(), json=result_json)
    assert res.status_code == 200
    
    # Genuine attestation
    v = http.post("/tasks/verify", headers=verifier_auth(), json={
        "task_id": claimed["task_id"], "verifier_id": "V-01", "result_id": "res-1", "verdict": "PASS", "artifacts": result_json["artifacts"]
    })
    assert v.status_code == 200
    
    # Replay with same alias -> ACK_DUPLICATE
    v2 = http.post("/tasks/verify", headers=verifier_auth(), json={
        "task_id": claimed["task_id"], "verifier_id": "V-01", "result_id": "res-1", "verdict": "PASS", "artifacts": result_json["artifacts"]
    })
    assert v2.json["status"] == "ACK_DUPLICATE"
    
    # Alias attack: Replay with different alias -> REJECT
    v3 = http.post("/tasks/verify", headers=verifier_auth(), json={
        "task_id": claimed["task_id"], "verifier_id": "V-02", "result_id": "res-1", "verdict": "PASS", "artifacts": result_json["artifacts"]
    })
    assert v3.status_code == 403

def test_unattested_evidence_rejected(tmp_path, monkeypatch):
    http = make_client(tmp_path, monkeypatch)
    http.post("/workers/register", headers=auth(), json={"worker_id": "W-01", "platform": "mac", "capabilities": ["macos"]})
    goal = http.post("/goals", headers=auth(), json={
        "goal_text": "A",
        "workflow_plan": [{"task_id": "task-A", "target_agent": "mac", "instruction": "Do something", "artifacts": ["a.txt"]}]
    }).json
    
    claimed = http.post("/tasks/claim", headers=auth(), json={"worker_id": "W-01", "capabilities": ["macos"]}).json["task"]
    claimed["worker_id"] = "W-01"
    
    http.post("/tasks/result", headers=auth(), json=make_result(claimed))
    
    t = http.get("/goals/" + goal["goal_id"], headers=auth()).json["tasks"][0]
    assert t["status"] == "RESULT_RECEIVED"

