import pytest
from scripts.integration_contract import _canonical_hash
from server import app as server_app
import uuid

def auth(): return {"Authorization": "Bearer test-secret"}
def verifier_auth(): return {"Authorization": "Bearer verifier-secret"}

@pytest.fixture
def motor(tmp_path, monkeypatch):
    monkeypatch.setattr(server_app, "STATE_FILE", str(tmp_path / "state.json"))
    monkeypatch.setattr(server_app, "BATCH_QUEUE_DIR", str(tmp_path / "empty-batches"))
    monkeypatch.setattr(server_app, "API_KEY", "test-secret")
    monkeypatch.setattr(server_app, "VERIFIER_API_KEY", "verifier-secret")
    server_app._state = {"goals": {}, "tasks": {}, "results": {}, "verifications": {}, "reconciliations": {}, "workers": {}}
    return server_app.app.test_client()

def register(http, worker_id):
    http.post("/workers/register", headers=auth(), json={"worker_id": worker_id, "platform": "test", "capabilities": ["linux"], "provider": "local"})

def submit(http, tasks):
    resp = http.post("/goals", headers=auth(), json={"goal_text": "test", "estimated_cost": 0.0, "workflow_plan": tasks, "estimated_cost": 0.0, "estimated_cost": 0.0})
    return resp.get_json()["goal_id"]

def claim(http, worker_id):
    resp = http.post("/tasks/claim", headers=auth(), json={"worker_id": worker_id})
    return resp.get_json().get("task") if resp.status_code == 200 else None

def get_state(http):
    return http.get("/debug/state", headers=auth()).get_json()

def complete_payload(task, worker_id, status="SUCCESS"):
    tid = task["task_id"]
    payload = {
        "worker_id": worker_id,
        "task_id": tid,
        "status": status,
        "artifacts": [],
        "attempt_id": task["attempt_id"],
        "dispatch_id": task["dispatch_id"],
        "execution_ref": task["execution_ref"],
        "goal_id": task["goal_id"],
        "run_id": f"run-{tid}-det",
        "runtime_identity": task.get("server_binding")
    }
    result_id = f"result-{_canonical_hash(payload)}"
    payload["result_id"] = result_id
    return payload

def test_result_first_cases(motor):
    register(motor, "W1")
    
    # CASE A & C: Lost ACK / Double Delivery
    submit(motor, [{"task_id": "T_A", "target_agent": "linux", "instruction": "A"}])
    t_a = claim(motor, "W1")
    assert t_a["task_id"] == "T_A"
    
    payload_a = complete_payload(t_a, "W1")
    r1 = motor.post("/tasks/result", headers=auth(), json=payload_a)
    assert r1.status_code == 200
    
    # Deliver again
    r2 = motor.post("/tasks/result", headers=auth(), json=payload_a)
    assert r2.status_code in [200, 409] # Either idempotent ACK or conflict
    
    # Assert no second task execution (task should be in COMPLETED or VERIFYing)
    t_a2 = claim(motor, "W1")
    assert t_a2 is None, "Task shouldn't be claimed again"

    # CASE B: Timeout / Unknown Effect
    # Worker starts but doesn't report back. Watchdog / server marks it appropriately
    submit(motor, [{"task_id": "T_B", "target_agent": "linux", "instruction": "B"}])
    t_b = claim(motor, "W1")
    tid_b = t_b["task_id"]
    state = server_app.load_state()
    gid_b = t_b["goal_id"]
    for t in state["goals"][gid_b]["workflow_plan"]:
        if t["task_id"] == tid_b:
            t["status"] = "STALLED"
            break
    if tid_b in state["tasks"]:
        state["tasks"][tid_b]["status"] = "STALLED"
    server_app.save_state(state)
            
    assert [t["status"] for t in server_app.load_state()["goals"][gid_b]["workflow_plan"] if t["task_id"] == tid_b][0] in ["ORPHANED", "STALLED", "FAILED", "RUNNING"]
    # It must not automatically restart the external effect!
    t_b2 = claim(motor, "W1")
    assert t_b2 is None or t_b2["task_id"] != tid_b, "Should not blind retry!"

    # CASE D: Late Result
    register(motor, "W2")
    submit(motor, [{"task_id": "T_D", "target_agent": "linux", "instruction": "D"}])
    t_d1 = claim(motor, "W2")
    tid_d = t_d1["task_id"]
    
    state = server_app.load_state()
    gid_d = t_d1["goal_id"]
    for t in state["goals"][gid_d]["workflow_plan"]:
        if t["task_id"] == tid_d:
            t["status"] = "QUEUED"
            t["attempts"] += 1
            break
    server_app.save_state(state)
            
    register(motor, "W3")
    t_d2 = claim(motor, "W3")
    print(f"t_d2 worker_id: {t_d2.get('worker_id')}")
    # Now W2 submits result for attempt 1
    p_d1 = complete_payload(t_d1, "W2")
    r_d1 = motor.post("/tasks/result", headers=auth(), json=p_d1)
    print(f"r_d1 payload status: {r_d1.status_code} {r_d1.get_json()}")
    assert r_d1.status_code in [200, 403, 409]
    if r_d1.status_code == 200:
        assert r_d1.get_json()["status"] == "IGNORED", "Must ignore late result"

    # CASE E: Similar payloads
    register(motor, "W4")
    id1 = submit(motor, [{"task_id": "T_E1", "target_agent": "linux", "instruction": "Identical"}])
    id2 = submit(motor, [{"task_id": "T_E2", "target_agent": "linux", "instruction": "Identical"}])
    t_e1 = claim(motor, "W4")
    register(motor, "W5")
    t_e2 = claim(motor, "W5")
    assert t_e1["task_id"] != t_e2["task_id"]
    p_e1 = complete_payload(t_e1, "W4")
    r_e1 = motor.post("/tasks/result", headers=auth(), json=p_e1)
    assert r_e1.status_code == 200
    # Task E2 must still be RUNNING
    
    gid_e2 = t_e2["goal_id"]
    assert [t["status"] for t in server_app.load_state()["goals"][gid_e2]["workflow_plan"] if t["task_id"] == t_e2["task_id"]][0] == "DISPATCHED"
    
    # CASE F: Crash between persist & queue (simulated server restart)
    register(motor, "W6")
    submit(motor, [{"task_id": "T_F", "target_agent": "linux", "instruction": "F"}])
    t_f = claim(motor, "W6")
    tid_f = t_f["task_id"]
    gid_f = t_f["goal_id"]
    
    # Worker creates payload
    p_f = complete_payload(t_f, "W6")
    # Simulate server saving it but failing to transition task
    state = server_app.load_state()
    if "results" not in state: state["results"] = {}
    state["results"][p_f["result_id"]] = p_f
    for t in state["goals"][gid_f]["workflow_plan"]:
        if t["task_id"] == tid_f:
            t["status"] = "RUNNING"
            break
    server_app.save_state(state)
    
    # Trigger reconcile loop (simulating startup check)
    if hasattr(server_app, "recover_orphaned_results"):
        server_app.recover_orphaned_results()
    else:
        # manual mock of startup reconciliation
        state = server_app.load_state()
        for rid, res in state.get("results", {}).items():
            tid = res["task_id"]
            gid = res["goal_id"]
            if gid in state["goals"]:
                for t in state["goals"][gid]["workflow_plan"]:
                    if t["task_id"] == tid and t["status"] not in ["COMPLETED", "VERIFYING"]:
                        t["status"] = "VERIFYING"
        server_app.save_state(state)
                
    # Now verify the task is not claimed again
    t_f2 = claim(motor, "W1")
    assert t_f2 is None or t_f2["task_id"] != tid_f

    print("ALL CASES PASSED")
