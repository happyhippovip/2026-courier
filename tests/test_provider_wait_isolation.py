import pytest
import time
import json
import os

os.environ.setdefault("COURIER_API_KEY", "test-key-12345")
os.environ.setdefault("COURIER_VERIFIER_API_KEY", "test-key-verifier-12345")

from server.app import app, STATE_FILE, STATE_LOCK
import server.app as app_module

@pytest.fixture
def client():
    app.config["TESTING"] = True
    
    with STATE_LOCK:
        if os.path.exists(STATE_FILE):
            os.remove(STATE_FILE)
            
        with open(STATE_FILE, "w") as f:
            json.dump({
                "schema_version": 2,
                "workers": {},
                "tasks": {},
                "goals": {},
                "provider_locks": {},
                "worker_quota_pools": {
                    "worker-1": "pool-A",
                    "worker-2": "pool-A",
                    "worker-3": "pool-B"
                }
            }, f)
            
    with app.test_client() as client:
        yield client
        
    with STATE_LOCK:
        if os.path.exists(STATE_FILE):
            os.remove(STATE_FILE)


def register_worker(client, worker_id, provider):
    response = client.post("/workers/register", json={
        "worker_id": worker_id,
        "provider": provider,
        "capabilities": [provider, "macos"]
    }, headers={"Authorization": f"Bearer {app_module.API_KEY}"})
    assert response.status_code == 200

def create_task(client, task_id, required_provider):
    # Direct state manipulation for test speed
    with STATE_LOCK:
        with open(STATE_FILE, "r") as f:
            state = json.load(f)
            
        state["tasks"][task_id] = {
            "task_id": task_id,
            "status": "QUEUED",
            "goal_id": "goal-1",
            "target_capability": required_provider,
            "required_capabilities": [required_provider],
            "retry_state": {"provider": 0},
            "next_retry_at": 0
        }
        
        # Add to goal
        if "goal-1" not in state["goals"]:
            state["goals"]["goal-1"] = {"status": "ACTIVE", "workflow_plan": []}
            
        state["goals"]["goal-1"]["workflow_plan"].append(state["tasks"][task_id])
        
        with open(STATE_FILE, "w") as f:
            json.dump(state, f)

def claim_task(client, worker_id):
    response = client.post("/tasks/claim", json={"worker_id": worker_id}, headers={"Authorization": f"Bearer {app_module.API_KEY}"})
    return response.get_json()

def provider_wait(client, worker_id, task_id):
    response = client.post(f"/tasks/{task_id}/provider_wait", json={
        "worker_id": worker_id,
        "reason": "429 Too Many Requests"
    }, headers={"Authorization": f"Bearer {app_module.API_KEY}"})
    return response.get_json()

def test_provider_wait_isolation(client):
    # Scenario 1: Pool A gets 429.
    register_worker(client, "worker-1", "openai")
    register_worker(client, "worker-2", "openai")
    
    create_task(client, "task-1", "openai")
    create_task(client, "task-2", "openai")
    
    claim1 = claim_task(client, "worker-1")
    assert claim1["task"]["task_id"] == "task-1"
    
    # worker-1 hits 429
    provider_wait(client, "worker-1", "task-1")
    
    # Scenario 2 & 1: worker-2 is in the same pool and provider, should be locked out!
    claim2 = claim_task(client, "worker-2")
    assert claim2.get("task") is None
    assert claim2.get("reason") == "PROVIDER_QUOTA_LOCKED"
    
    # Scenario 3: same provider, different independent quota_resource_id (worker-3 in pool-B)
    register_worker(client, "worker-3", "openai")
    claim3 = claim_task(client, "worker-3")
    assert claim3["task"]["task_id"] == "task-2"  # worker-3 successfully claims the remaining task!
    
    # Scenario 4: restart with X locked
    # Simulate restart by clearing and reloading from STATE_FILE
    with STATE_LOCK:
        with open(STATE_FILE, "r") as f:
            state = json.load(f)
            # manually push next_retry_at into the past for task-1 to test lock expiry
            state["provider_locks"]["pool-A:openai"] = time.time() - 10
            state["tasks"]["task-1"]["next_retry_at"] = time.time() - 10
            with open(STATE_FILE, "w") as f:
                json.dump(state, f)
                
    # Scenario 5: expiry occurs -> X resumes automatically
    claim1_retry = claim_task(client, "worker-1")
    assert claim1_retry["task"]["task_id"] == "task-1"  # Automatically re-claimed
    assert claim1_retry["task"]["status"] == "DISPATCHED"

    # Scenario 6: concurrent 429s -> one deterministic lock state
    create_task(client, "task-3", "openai")
    create_task(client, "task-4", "openai")
    
    # worker-1 has task-1, worker-2 claims task-3
    claim2_retry = claim_task(client, "worker-2")
    assert claim2_retry["task"]["task_id"] == "task-3"
    
    # Both report 429
    provider_wait(client, "worker-1", "task-1")
    provider_wait(client, "worker-2", "task-3")
    
    with STATE_LOCK:
        with open(STATE_FILE, "r") as f:
            state = json.load(f)
            # The lock should just be a single value far in the future
            lock_val = state["provider_locks"]["pool-A:openai"]
            assert lock_val > time.time() + 1
            
    # Scenario 7: forged resource ID
    # worker-4 tries to send a heartbeat saying they are in "pool-A" (they can't do this via heartbeat!)
    # But wait, workers can't send pool_id in heartbeat anyway, the server configures it.
    # What if they forge their `provider` string?
    # If worker-4 says `provider="anthropic"`, they can only lock `worker-4:anthropic`.
    register_worker(client, "worker-4", "anthropic")
    create_task(client, "task-5", "anthropic")
    claim4 = claim_task(client, "worker-4")
    assert claim4["task"]["task_id"] == "task-5"
    
    provider_wait(client, "worker-4", "task-5")
    
    # worker-4's provider is locked, but it does NOT affect pool-A or worker-3
    with STATE_LOCK:
        with open(STATE_FILE, "r") as f:
            state = json.load(f)
            assert state["provider_locks"]["worker-4:anthropic"] > time.time()
            assert "pool-A:anthropic" not in state["provider_locks"]

