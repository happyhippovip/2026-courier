import pytest
from server.app import app, load_state, save_state
import json
import os

os.environ["COURIER_API_KEY"] = "test"
os.environ["COURIER_VERIFIER_API_KEY"] = "test"

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_result_duplicate_invariant(client):
    headers = {"Authorization": "Bearer test"}
    state = load_state()
    task_id = "task-dup-1"
    state["tasks"][task_id] = {
        "task_id": task_id,
        "worker_id": "worker-1",
        "status": "DISPATCHED",
        "instruction": "test",
        "capabilities": [],
        "goal_id": "goal-1",
        "attempt_id": "1",
        "dispatch_id": "1",
        "execution_ref": "1"
    }
    save_state(state)

    payload1 = {
        "task_id": task_id,
        "worker_id": "worker-1",
        "result_id": "res-1",
        "status": "SUCCESS",
        "artifacts": [{"path": "file.txt", "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"}],
        "attempt_id": "1",
        "dispatch_id": "1",
        "execution_ref": "1",
        "goal_id": "goal-1",
        "run_id": "run-1"
    }
    resp1 = client.post("/tasks/result", json=payload1, headers=headers)
    assert resp1.status_code == 200

    resp2 = client.post("/tasks/result", json=payload1, headers=headers)
    assert resp2.status_code == 200
    assert resp2.get_json()["status"] == "ACK_DUPLICATE"

    payload_contradictory = {
        "task_id": task_id,
        "worker_id": "worker-1",
        "result_id": "res-2-different",
        "status": "SUCCESS",
        "artifacts": [],
        "attempt_id": "1",
        "dispatch_id": "1",
        "execution_ref": "1",
        "goal_id": "goal-1",
        "run_id": "run-1"
    }
    resp3 = client.post("/tasks/result", json=payload_contradictory, headers=headers)
    assert resp3.status_code == 409
    assert resp3.get_json()["status"] == "CONFLICT"
    assert resp3.get_json()["reason"] == "CONTRADICTORY_DUPLICATE"

    state = load_state()
    assert state["tasks"][task_id]["result"]["result_id"] == "res-1"

    payload_worker2 = dict(payload1)
    payload_worker2["worker_id"] = "worker-2"
    resp4 = client.post("/tasks/result", json=payload_worker2, headers=headers)
    assert resp4.status_code == 409
    assert resp4.get_json()["status"] == "CONFLICT"

