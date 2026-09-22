import os
import pytest

from scripts.integration_contract import _canonical_hash
from server.app import app, load_state, save_state
app.config['TESTING'] = True


@pytest.fixture
def client(monkeypatch):
    import server.app
    monkeypatch.setattr(server.app, "API_KEY", "TEST")
    with app.test_client() as client:
        yield client

def reset_state():
    state = load_state()
    state.update({"goals": {}, "tasks": {}, "workers": {}})
    # DLQ-05: locks live outside tasks/workers; clear them for isolation so a
    # previous run's backoff cannot leak into this run.
    state["provider_locks"] = {}
    save_state(state)

def test_waiting_provider_does_not_stall_global_queue(client):
    reset_state()
    import server.app
    pass

    # Register worker
    res = client.post("/workers/register", json={"worker_id": "W1", "platform": "linux", "capabilities": ["linux"]}, headers={"Authorization": "Bearer TEST"})
    assert res.status_code == 200

    # Submit goal with 3 parallel tasks
    goal = {
        "goal_text": "Test Goal",
        "workflow_plan": [
            {"task_id": "A", "instruction": "Task A", "capabilities": ["linux"], "depends_on": [], "status": "QUEUED"},
            {"task_id": "B", "instruction": "Task B", "capabilities": ["linux"], "depends_on": [], "status": "QUEUED"},
            {"task_id": "C", "instruction": "Task C", "capabilities": ["linux"], "depends_on": [], "status": "QUEUED"}
        ]
    }
    res = client.post("/goals", json=goal, headers={"Authorization": "Bearer TEST"})
    assert res.status_code == 200
    goal_id = res.json["goal_id"]

    # Claim Task A
    res = client.post("/tasks/claim", json={"worker_id": "W1"}, headers={"Authorization": "Bearer TEST"})
    task_a = res.json.get("task")
    assert task_a["task_id"] == "A"

    # Set Task A to WAITING_PROVIDER
    res = client.post(f"/tasks/A/provider_wait", json={"worker_id": "W1", "wait_type": "WAITING_PROVIDER"}, headers={"Authorization": "Bearer TEST"})
    assert res.status_code == 200

    # Goal should remain ACTIVE
    res = client.get(f"/goals/{goal_id}", headers={"Authorization": "Bearer TEST"})
    assert res.json["goal"]["status"] == "ACTIVE"

    # DLQ-05: W1's own quota pool is locked, so W1 itself is backed off
    # (PROVIDER_QUOTA_LOCKED) -- the cluster lock replaced per-task backoff.
    res = client.post("/tasks/claim", json={"worker_id": "W1"}, headers={"Authorization": "Bearer TEST"})
    assert res.json.get("task") is None
    assert res.json.get("reason") == "PROVIDER_QUOTA_LOCKED"

    # True negative (DLQ-05 invariant): an independent worker on its own pool
    # keeps processing READY work while W1 is locked.
    res = client.post("/workers/register", json={"worker_id": "W2", "platform": "linux", "capabilities": ["linux"]}, headers={"Authorization": "Bearer TEST"})
    assert res.status_code == 200
    res = client.post("/tasks/claim", json={"worker_id": "W2"}, headers={"Authorization": "Bearer TEST"})
    task_b = res.json.get("task")
    assert task_b is not None, "Independent worker W2 was blocked by W1's quota lock!"
    assert task_b["task_id"] == "B"

    # Set Task B to SUCCESS
    res_b_ident = {
        "goal_id": goal_id, "task_id": "B", "attempt_id": task_b["attempt_id"],
        "dispatch_id": task_b["dispatch_id"], "execution_ref": task_b["execution_ref"],
        "worker_id": "W2", "run_id": "run1", "status": "SUCCESS", "artifacts": [],
        "runtime_identity": task_b.get("server_binding")
    }
    res_b_payload = dict(res_b_ident)
    res_b_payload["result_id"] = f"result-{_canonical_hash(res_b_ident)}"
    res = client.post("/tasks/result", json=res_b_payload, headers={"Authorization": "Bearer TEST"})
    assert res.status_code == 200, res.json


    # Worker 2 should be able to claim Task C immediately
    res = client.post("/tasks/claim", json={"worker_id": "W2"}, headers={"Authorization": "Bearer TEST"})
    task_c = res.json.get("task")
    print("Claim C:", res.json)
    assert task_c is not None, "Task C was blocked by Task A's WAITING_PROVIDER state!"
    assert task_c["task_id"] == "C"

