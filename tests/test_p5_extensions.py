import pytest
from server.app import app, load_state

@pytest.fixture
def client(monkeypatch):
    import server.app
    monkeypatch.setattr(server.app, "API_KEY", "test-secret")
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client

def auth():
    return {"Authorization": "Bearer test-secret"}

def test_p5_features(client):
    # Register worker with P5 features
    resp = client.post("/workers/register", headers=auth(), json={
        "worker_id": "W-P5",
        "capabilities": ["linux"], "groups": ["researchers", "writers"],
        "community_id": "enterprise-x"
    })
    assert resp.status_code == 200

    # 1. Profiles
    resp = client.get("/profiles")
    assert resp.status_code == 200
    data = resp.get_json()
    assert any(p["id"] == "W-P5" and "researchers" in p["groups"] for p in data["profiles"])

    # Update custom profile
    resp = client.post("/users/W-P5", headers=auth(), json={"custom_profile": {"name": "Test Worker"}})
    assert resp.status_code == 200
    
    resp = client.get("/users/W-P5")
    assert resp.status_code == 200
    assert resp.get_json()["custom_profile"]["name"] == "Test Worker"

    # 2. Groups
    resp = client.get("/groups")
    assert resp.status_code == 200
    data = resp.get_json()
    assert any(g["name"] == "researchers" and g["active_workers"] > 0 for g in data["groups"])

    # 3. Community Isolation
    resp = client.post("/goals", headers=auth(), json={
        "goal_text": "community task",
        "community_id": "enterprise-x", "estimated_cost": 0.0,
        "workflow_plan": [{"task_id": "T1", "instruction": "do", "target_agent": "linux", "required_groups": ["researchers"]}]
    })
    assert resp.status_code == 200
    
    resp2 = client.post("/goals", headers=auth(), json={
        "goal_text": "other community task",
        "community_id": "other-community", "estimated_cost": 0.0,
        "workflow_plan": [{"task_id": "T2", "instruction": "do", "target_agent": "linux"}]
    })
    assert resp2.status_code == 200

    # Claim task
    resp = client.post("/tasks/claim", headers=auth(), json={"worker_id": "W-P5"})
    assert resp.status_code == 200
    task = resp.get_json().get("task")
    assert task is not None
    assert task["task_id"] == "T1" # Only gets the task for enterprise-x
    
    # 4. Chat
    goal_id = task["goal_id"]
    resp = client.post(f"/goals/{goal_id}/chat", json={"message": "hello", "sender": "W-P5"})
    assert resp.status_code == 200
    
    resp = client.get(f"/goals/{goal_id}/chat")
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data["chat_history"]) == 1
    assert data["chat_history"][0]["message"] == "hello"

