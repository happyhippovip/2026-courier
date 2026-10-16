import pytest
import os
import json
import server.app as server_app
from server.app import app, save_state, load_state

@pytest.fixture
def client(monkeypatch):
    app.config["TESTING"] = True
    monkeypatch.setattr(server_app, "API_KEY", "test-token")
    
    # Create fresh state
    state = {
        "tasks": {},
        "goals": {
            "test_goal": {
                "goal_id": "test_goal",
                "status": "ACTIVE",
                "workflow_plan": [
                    {
                        "task_id": "task_1",
                        "goal_id": "test_goal",
                        "status": "QUEUED",
                        "target_agent": "linux",
                        "target_capability": "linux"
                    }
                ]
            }
        },
        "workers": {}
    }
    with app.test_request_context():
        save_state(state)
        
    with app.test_client() as client:
        yield client

def test_cost_aware_routing(client):
    headers = {"Authorization": "Bearer test-token"}
    
    # 1. Register a cheap worker
    client.post("/workers/register", json={
        "worker_id": "cheap-worker",
        "platform": "muse",
        "capabilities": ["linux"],
        "cost_class": "free"
    }, headers=headers)
    
    # 2. Register an expensive worker
    client.post("/workers/register", json={
        "worker_id": "expensive-worker",
        "platform": "opus",
        "capabilities": ["linux"],
        "cost_class": "high"
    }, headers=headers)
    
    # 3. Register an opaque worker
    client.post("/workers/register", json={
        "worker_id": "opaque-worker",
        "platform": "opus",
        "capabilities": ["linux"]
        # no cost_class
    }, headers=headers)
    
    # 4. Expensive worker tries to claim but there's no escalation_reason in task -> Refused (task: null)
    res = client.post("/tasks/claim", json={"worker_id": "expensive-worker"}, headers=headers)
    data = res.get_json()
    assert data.get("task") is None, "Expensive worker should be refused because cheap worker is available"
    
    # 5. Opaque worker tries to claim -> Refused (task: null)
    res = client.post("/tasks/claim", json={"worker_id": "opaque-worker"}, headers=headers)
    data = res.get_json()
    assert data.get("task") is None, "Opaque worker should be refused because unknown defaults to high"
    
    # 6. Cheap worker claims it -> Succeeds
    res = client.post("/tasks/claim", json={"worker_id": "cheap-worker"}, headers=headers)
    data = res.get_json()
    assert data.get("task") is not None
    assert data["task"]["routing_decision"]["COST_CLASS"] == "free"
    assert data["task"]["routing_decision"]["CHEAPER_CAPABLE_OPTION_AVAILABLE"] is False

def test_expensive_escalation(client):
    headers = {"Authorization": "Bearer test-token"}
    
    # Add escalation reason to task
    with app.test_request_context():
        state = load_state()
        state["goals"]["test_goal"]["workflow_plan"][0]["escalation_reason"] = "Need deep reasoning"
        save_state(state)
        
    client.post("/workers/register", json={
        "worker_id": "cheap-worker",
        "platform": "muse",
        "capabilities": ["linux"],
        "cost_class": "free"
    }, headers=headers)
    
    client.post("/workers/register", json={
        "worker_id": "expensive-worker",
        "platform": "opus",
        "capabilities": ["linux"],
        "cost_class": "high"
    }, headers=headers)
    
    res = client.post("/tasks/claim", json={"worker_id": "expensive-worker"}, headers=headers)
    data = res.get_json()
    assert data.get("task") is not None, "Expensive worker should succeed because escalation_reason is present"
    decision = data["task"]["routing_decision"]
    assert decision["COST_CLASS"] == "high"
    assert decision["CHEAPER_CAPABLE_OPTION_AVAILABLE"] is True
    assert decision["ESCALATION_REASON"] == "Need deep reasoning"
    assert decision["USER_WARNING_REQUIRED"] is True

