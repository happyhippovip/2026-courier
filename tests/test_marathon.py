import hashlib
import json
import threading
import time
import os
import subprocess
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest

from server import app as server_app

def client(tmp_path, monkeypatch):
    monkeypatch.setattr(server_app, "STATE_FILE", str(tmp_path / "state.json"))
    monkeypatch.setattr(server_app, "API_KEY", "test-secret")
    monkeypatch.setattr(server_app, "VERIFIER_API_KEY", "verifier-secret")
    return server_app.app.test_client()

def auth():
    return {"Authorization": "Bearer test-secret"}

def verifier_auth():
    return {"Authorization": "Bearer verifier-secret"}

def test_marathon_units_4_to_8(tmp_path, monkeypatch):
    http = client(tmp_path, monkeypatch)
    
    # Register worker
    http.post("/workers/register", headers=auth(), json={"worker_id": "MAC-01", "platform": "mac", "capabilities": ["macos"]})
    
    # 4 & 5: Verify/Reconcile and NEXT_READY B-Autostart
    goal_res = http.post(
        "/goals",
        headers=auth(),
        json={
            "goal_text": "two steps",
            "workflow_plan": [
                {"task_id": "t1", "target_agent": "mac_desktop", "artifacts": ["dummy1.txt"]},
                {"task_id": "t2", "target_agent": "mac_desktop", "artifacts": ["dummy2.txt"]}
            ],
        },
    ).get_json()
    goal_id = goal_res["goal_id"]
    
    # Claim t1
    claim1 = http.post("/tasks/claim", headers=auth(), json={"worker_id": "MAC-01"}).get_json()
    t1 = claim1["task"]
    assert t1["task_id"] == "t1"
    
    # Result t1
    from scripts.integration_contract import _canonical_hash
    import time
    ident1 = {
        "goal_id": t1["goal_id"], "task_id": t1["task_id"], "attempt_id": t1["attempt_id"],
        "dispatch_id": t1["dispatch_id"], "worker_id": t1["worker_id"], "run_id": "r1",
        "status": "SUCCESS", "artifacts": [{"path": "dummy1.txt", "sha256": "0"*64}]
    }
    ident1["result_id"] = f"result-{_canonical_hash(ident1)}"
    ident1["execution_start_at"] = time.time()
    ident1["execution_end_at"] = time.time() + 1
    r_res = http.post("/tasks/result", headers=auth(), json=ident1)
    print("Result response:", r_res.status_code, r_res.get_json())

    
    # Verify t1 (PASS -> Reconciled -> next task ready)
    # Verify t1 (PASS -> Reconciled -> next task ready)
    v_res = http.post("/tasks/verify", headers=verifier_auth(), json={
        "task_id": t1["task_id"], "verifier_id": "V-01", "result_id": ident1["result_id"],
        "verdict": "PASS", "artifacts": ident1["artifacts"]
    })
    print("Verify response:", v_res.status_code, v_res.get_json())

    
    # Claim t2 (B-Autostart proves it advanced)
    claim2 = http.post("/tasks/claim", headers=auth(), json={"worker_id": "MAC-01"}).get_json()
    t2 = claim2["task"]
    assert t2["task_id"] == "t2"
    
    # 6: Failure Preservation
    ident2 = {
        "goal_id": t2["goal_id"], "task_id": t2["task_id"], "attempt_id": t2["attempt_id"],
        "dispatch_id": t2["dispatch_id"], "worker_id": t2["worker_id"], "run_id": "r2",
        "status": "SUCCESS", "artifacts": [{"path": "dummy2.txt", "sha256": "1"*64}]
    }
    ident2["result_id"] = f"result-{_canonical_hash(ident2)}"
    ident2["execution_start_at"] = time.time()
    ident2["execution_end_at"] = time.time() + 1
    http.post("/tasks/result", headers=auth(), json=ident2)
    
    http.post("/tasks/verify", headers=verifier_auth(), json={
        "task_id": t2["task_id"], "verifier_id": "V-01", "result_id": ident2["result_id"],
        "verdict": "FAIL", "artifacts": ident2["artifacts"]
    })
    
    state = server_app.load_state()
    assert state["tasks"]["t2"]["status"] == "FAILED_VERIFICATION"
    assert state["goals"][goal_id]["status"] == "BLOCKED"
    
    # 7: Restart S1-S9
    http.post(f"/tasks/t2/resume", headers=auth(), json={"action": "retry"})
    
    state = server_app.load_state()
    assert state["tasks"]["t2"]["status"] == "QUEUED"
    assert state["goals"][goal_id]["status"] == "ACTIVE"
    
    # 8: Evidence / Observability
    assert state["tasks"]["t2"]["resumed_from"] == "FAILED_VERIFICATION"
    
    print("All units verified successfully!")
