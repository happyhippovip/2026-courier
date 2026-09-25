from scripts.integration_contract import _canonical_hash
import pytest
from server import app as server_app

def auth():
    return {"Authorization": "Bearer test-secret"}

@pytest.fixture
def motor(tmp_path, monkeypatch):
    monkeypatch.setattr(server_app, "STATE_FILE", str(tmp_path / "state.json"))
    monkeypatch.setattr(server_app, "BATCH_QUEUE_DIR", str(tmp_path / "empty-batches"))
    monkeypatch.setattr(server_app, "API_KEY", "test-secret")
    monkeypatch.setattr(server_app, "VERIFIER_API_KEY", "verifier-secret")
    assert server_app.STATE_FILE == str(tmp_path / "state.json"), "STATE_FILE not correctly set to temporary path"
    return server_app.app.test_client()

def register(http, worker_id):
    resp = http.post(
        "/workers/register",
        headers=auth(),
        json={"worker_id": worker_id, "platform": "test", "capabilities": ["linux"], "provider": "local"}
    )
    assert resp.status_code == 200

def submit(http, tasks):
    resp = http.post("/goals", headers=auth(), json={"goal_text": "cannon test", "workflow_plan": tasks, "estimated_cost": 0.0})
    assert resp.status_code == 200
    return resp.get_json()["goal_id"]

def claim(http, worker_id):
    resp = http.post("/tasks/claim", headers=auth(), json={"worker_id": worker_id})
    return resp.get_json().get("task") if resp.status_code == 200 else None

def complete(http, worker_id, task, status="SUCCESS"):
    tid = task["task_id"]
    payload = {
        "worker_id": worker_id,
        "task_id": tid,
        "status": status,
        "artifacts": [],
        "raw_result": {"status": status},
        "attempt_id": task["attempt_id"],
        "dispatch_id": task["dispatch_id"],
        "execution_ref": task["execution_ref"],
        "goal_id": task["goal_id"],
        "run_id": f"run-{tid}-deterministic",
        "runtime_identity": task.get("server_binding")
    }
    identity = dict(payload)
    identity.pop("raw_result", None)
    payload["result_id"] = f"result-{_canonical_hash(identity)}"
    resp = http.post("/tasks/result", headers=auth(), json=payload)
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "ACK_RESULT_RECEIVED"

def verify(http, worker_id, task):
    headers={"Authorization": "Bearer verifier-secret"}
    tid = task["task_id"]
    payload = {
        "worker_id": worker_id,
        "task_id": tid,
        "status": "SUCCESS",
        "artifacts": [],
        "attempt_id": task["attempt_id"],
        "dispatch_id": task["dispatch_id"],
        "execution_ref": task["execution_ref"],
        "goal_id": task["goal_id"],
        "run_id": f"run-{tid}-deterministic",
        "runtime_identity": task.get("server_binding")
    }
    result_id = f"result-{_canonical_hash(payload)}"
    resp = http.post("/tasks/verify", headers=headers, json={"task_id": tid, "verdict": "PASS", "received_runtime_identity": task["server_binding"], "verifier_id": "V1", "result_id": result_id, "artifacts": []}); print("VERIFY RESP:", resp.status_code, resp.get_data(), flush=True)
    assert resp.status_code == 200

def provider_wait(http, worker_id, task):
    resp = http.post(f"/tasks/{task['task_id']}/provider_wait", headers=auth(), json={"worker_id": worker_id, "reason": "blocked"})
    assert resp.status_code == 200

def test_motor_cannon_5_tasks(motor):
    register(motor, "W1")
    register(motor, "W2")
    
    tasks = [
        {"task_id": "A", "target_agent": "linux", "instruction": "Task A"},
        {"task_id": "B", "target_agent": "linux", "instruction": "Task B", "depends_on": ["A"]},
        {"task_id": "C", "target_agent": "linux", "instruction": "Task C"},
        {"task_id": "D", "target_agent": "linux", "instruction": "Task D", "depends_on": ["C"]},
        {"task_id": "E", "target_agent": "linux", "instruction": "Task E", "depends_on": ["B", "D"]}
    ]
    
    goal_id = submit(motor, tasks)
    
    # Claim A and C
    t1 = claim(motor, "W1")
    t2 = claim(motor, "W2")
    assert {t1["task_id"], t2["task_id"]} == {"A", "C"}
    
    # Provider wait C
    c_worker = "W1" if t1["task_id"] == "C" else "W2"
    a_worker = "W1" if t1["task_id"] == "A" else "W2"
    c_task = t1 if t1["task_id"] == "C" else t2
    a_task = t1 if t1["task_id"] == "A" else t2
    
    provider_wait(motor, c_worker, c_task)
    
    # Complete A
    complete(motor, a_worker, a_task)
    verify(motor, a_worker, a_task)
    
    # Now B should be ready, C is still blocked
    t3 = claim(motor, "W1")
    assert t3["task_id"] == "B"
    
    complete(motor, "W1", t3)
    verify(motor, "W1", t3)
    
    # No more tasks ready until C finishes
    assert claim(motor, "W2") is None
    
    # Complete C (pretend provider wait finished, how?)
    # Resume endpoint!
    resp = motor.post(f"/tasks/C/resume", headers=auth())
    assert resp.status_code == 200
    
    t4 = claim(motor, "W2")
    assert t4["task_id"] == "C"
    complete(motor, "W2", t4)
    verify(motor, "W2", t4)
    
    t5 = claim(motor, "W1")
    assert t5["task_id"] == "D"
    complete(motor, "W1", t5)
    verify(motor, "W1", t5)
    
    print("GOALS:", motor.get(f"/goals/{goal_id}", headers=auth()).get_json(), flush=True)
    t6 = claim(motor, "W1") or claim(motor, "W2")
    assert t6["task_id"] == "E"
    e_worker = "W1" if t6["worker_id"] == "W1" else "W2"
    complete(motor, e_worker, t6)
    verify(motor, e_worker, t6)

def test_motor_cannon_100_tasks(motor):
    register(motor, "W1")
    
    tasks = []
    # 100 tasks, each depending on the previous
    for i in range(100):
        t = {"task_id": f"T{i}", "target_agent": "linux", "instruction": f"Task {i}"}
        if i > 0:
            t["depends_on"] = [f"T{i-1}"]
        tasks.append(t)
        
    goal_id = submit(motor, tasks)
    
    for i in range(100):
        t = claim(motor, "W1")
        assert t["task_id"] == f"T{i}"
        complete(motor, "W1", t)
        verify(motor, "W1", t)
        
    assert claim(motor, "W1") is None
