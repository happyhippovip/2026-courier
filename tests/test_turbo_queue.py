import pytest
import os
import tempfile
from pathlib import Path

@pytest.fixture
def app_state(monkeypatch):
    import server.app
    temp_dir = tempfile.mkdtemp()
    state_file = Path(temp_dir) / "central_state.json"
    monkeypatch.setattr(server.app, "STATE_FILE", str(state_file))
    
    server.app.app.config['TESTING'] = True
    with server.app.app.test_client() as client:
        yield client

def test_turbo_queue_parallel_ab_wait_c(app_state):
    import server.app
    server.app.API_KEY = "test"
    auth = {"Authorization": "Bearer test"}
    r1 = app_state.post("/workers/register", json={"worker_id": "w1", "capabilities": ["mock"]}, headers=auth)
    w1_id = "w1"
    
    r2 = app_state.post("/workers/register", json={"worker_id": "w2", "capabilities": ["mock"]}, headers=auth)
    w2_id = "w2"

    goal_data = {
        "goal_text": "Turbo test",
        "workflow_plan": [
            {"task_id": "A", "target_agent": "mock", "instruction": "Do A"},
            {"task_id": "B", "target_agent": "mock", "instruction": "Do B"},
            {"task_id": "C", "target_agent": "mock", "instruction": "Do C", "depends_on": ["A", "B"]}
        ]
    }
    app_state.post("/goals", json=goal_data, headers=auth)

    # In server/app.py claim_task(), worker claims ONE task.
    t1 = app_state.post("/tasks/claim", json={"worker_id": w1_id}, headers=auth).json.get("task")
    t2 = app_state.post("/tasks/claim", json={"worker_id": w2_id}, headers=auth).json.get("task")

    assert t1 is not None
    assert t2 is not None
    assert set([t1["task_id"], t2["task_id"]]) == {"A", "B"}
    
    # Finish A
    state = server.app.load_state()
    state["tasks"]["A"]["status"] = "RECONCILED"
    state["goals"][t1["goal_id"]]["workflow_plan"][0]["status"] = "RECONCILED"
    # Also free up worker 1
    state["workers"]["w1"]["current_task"] = None
    state["workers"]["w1"]["available"] = True
    server.app.save_state(state)
    
    # Claim with w1 -> Should be None because C is blocked by B
    t3 = app_state.post("/tasks/claim", json={"worker_id": w1_id}, headers=auth).json.get("task")
    assert t3 is None, "C should wait for B to finish"

    # Finish B
    state = server.app.load_state()
    state["tasks"]["B"]["status"] = "RECONCILED"
    state["goals"][t1["goal_id"]]["workflow_plan"][1]["status"] = "RECONCILED"
    server.app.save_state(state)

    # Claim with w1 -> Should be C
    t_c = app_state.post("/tasks/claim", json={"worker_id": w1_id}, headers=auth).json.get("task")
    assert t_c is not None
    assert t_c["task_id"] == "C"

