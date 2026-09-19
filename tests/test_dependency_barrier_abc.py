import hashlib
import json
import pytest
import copy
from server import app as server_app
from scripts.integration_contract import _canonical_hash

def auth():
    return {"Authorization": "Bearer test-secret"}

def verifier_auth():
    return {"Authorization": "Bearer verifier-secret"}

def make_result(task, worker_id, artifacts):
    payload = {
        "goal_id": task["goal_id"],
        "task_id": task["task_id"],
        "attempt_id": task["attempt_id"],
        "dispatch_id": task["dispatch_id"],
        "execution_ref": task.get("execution_ref"),
        "worker_id": worker_id,
        "run_id": "run-test",
        "status": "SUCCESS",
        "artifacts": artifacts,
        "runtime_identity": task.get("server_binding")
    }
    ident = dict(payload)
    payload["result_id"] = f"result-{_canonical_hash(ident)}"
    return payload

def test_abc_dependency_barrier(tmp_path, monkeypatch):
    monkeypatch.setattr(server_app, "STATE_FILE", str(tmp_path / "state.json"))
    monkeypatch.setattr(server_app, "API_KEY", "test-secret")
    monkeypatch.setattr(server_app, "VERIFIER_API_KEY", "verifier-secret")
    http = server_app.app.test_client()
    
    # Register workers
    http.post("/workers/register", headers=auth(), json={"worker_id": "W-A", "platform": "mac", "capabilities": ["macos"]})
    http.post("/workers/register", headers=auth(), json={"worker_id": "W-B", "platform": "mac", "capabilities": ["macos"]})
    http.post("/workers/register", headers=auth(), json={"worker_id": "W-C", "platform": "mac", "capabilities": ["macos"]})
    
    # Goal: C depends on A and B
    http.post("/goals", headers=auth(), json={
        "goal_text": "A+B -> C",
        "workflow_plan": [
            {"task_id": "A", "target_agent": "mac", "instruction": "A", "artifacts": ["a.txt"]},
            {"task_id": "B", "target_agent": "mac", "instruction": "B", "artifacts": ["b.txt"]},
            {"task_id": "C", "target_agent": "mac", "instruction": "C", "depends_on": ["A", "B"]},
        ],
    })
    
    # Claim A and B
    task_a = http.post("/tasks/claim", headers=auth(), json={"worker_id": "W-A"}).get_json()["task"]
    task_b = http.post("/tasks/claim", headers=auth(), json={"worker_id": "W-B"}).get_json()["task"]
    assert set([task_a["task_id"], task_b["task_id"]]) == {"A", "B"}
    
    # Worker C is available, but C is blocked
    blocked_c = http.post("/tasks/claim", headers=auth(), json={"worker_id": "W-C"}).get_json()
    assert blocked_c.get("task") is None, "Worker availability ist nicht allein der Grund für Sperre"
    
    # 1. A result empfangen aber nicht verifiziert -> C gesperrt
    res_a = make_result(task_a, "W-A", [{"path": "a.txt", "sha256": "0"*64}])
    assert http.post("/tasks/result", headers=auth(), json=res_a).status_code == 200
    
    blocked_c2 = http.post("/tasks/claim", headers=auth(), json={"worker_id": "W-C"}).get_json()
    assert blocked_c2.get("task") is None, "A result received but unverified -> C blocked"
    
    # 2. A gültig (verified), B offen -> C gesperrt
    v_a = {
        "task_id": task_a["task_id"], "result_id": res_a["result_id"],
        "verifier_id": "V-1", "verdict": "PASS", "artifacts": res_a["artifacts"],
        "received_runtime_identity": task_a["server_binding"]
    }
    assert http.post("/tasks/verify", headers=verifier_auth(), json=v_a).status_code == 200
    
    blocked_c3 = http.post("/tasks/claim", headers=auth(), json={"worker_id": "W-C"}).get_json()
    assert blocked_c3.get("task") is None, "A valid, B open -> C blocked"
    
    # 3. Falsches/stales Result -> keine Freigabe
    # Let's try to verify B with forged result ID
    v_b_forged = {
        "task_id": task_b["task_id"], "result_id": "forged",
        "verifier_id": "V-1", "verdict": "PASS", "artifacts": [],
        "received_runtime_identity": task_b["server_binding"]
    }
    assert http.post("/tasks/verify", headers=verifier_auth(), json=v_b_forged).status_code in (400, 409)
    assert http.post("/tasks/claim", headers=auth(), json={"worker_id": "W-C"}).get_json().get("task") is None
    
    # 4. A+B gültig -> C freigegeben
    res_b = make_result(task_b, "W-B", [{"path": "b.txt", "sha256": "1"*64}])
    assert http.post("/tasks/result", headers=auth(), json=res_b).status_code == 200
    v_b = {
        "task_id": task_b["task_id"], "result_id": res_b["result_id"],
        "verifier_id": "V-1", "verdict": "PASS", "artifacts": res_b["artifacts"],
        "received_runtime_identity": task_b["server_binding"]
    }
    assert http.post("/tasks/verify", headers=verifier_auth(), json=v_b).status_code == 200
    
    task_c = http.post("/tasks/claim", headers=auth(), json={"worker_id": "W-C"}).get_json()["task"]
    assert task_c["task_id"] == "C", "A+B verified -> C unlocked exactly once"
    
    # 5. doppelte A/B-Abschlussmeldung -> C nicht doppelt
    # Verify A again
    dup_v_a = http.post("/tasks/verify", headers=verifier_auth(), json=v_a)
    assert dup_v_a.status_code == 200
    assert dup_v_a.get_json()["status"] == "ACK_DUPLICATE"
    
    # Does claiming again give anything? C is already claimed, so it shouldn't give C again
    http.post("/workers/register", headers=auth(), json={"worker_id": "W-C2", "platform": "mac", "capabilities": ["macos"]})
    dup_c = http.post("/tasks/claim", headers=auth(), json={"worker_id": "W-C2"}).get_json()
    assert dup_c.get("task") is None, "C not unlocked twice"
    
