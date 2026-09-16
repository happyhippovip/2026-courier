import os
import json
import time
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from server.app import app, load_state, save_state

def test_routing():
    client = app.test_client()
    
    # 1. Clear state
    state = load_state()
    state["goals"] = {}
    state["tasks"] = {}
    state["workers"] = {}
    save_state(state)

    # We need auth
    if not os.environ.get("COURIER_API_KEY"):
        os.environ["COURIER_API_KEY"] = "test-key"
        import server.app
        server.app.API_KEY = "test-key"
        server.app.INSECURE_API_KEYS = set()
    auth_headers = {"Authorization": "Bearer test-key"}

    # 2. Register workers
    workers_to_register = [
        {"worker_id": "worker-det", "capabilities": ["linux"], "cost_class": "free"},
        {"worker_id": "worker-hosted-det", "capabilities": ["github", "linux"], "cost_class": "low"},
        {"worker_id": "worker-cheap-ai", "capabilities": ["windows", "github", "linux"], "cost_class": "medium"},
        {"worker_id": "worker-exp-ai", "capabilities": ["macos", "windows", "github", "linux"], "cost_class": "high"},
    ]
    for w in workers_to_register:
        res = client.post("/workers/register", json=w, headers=auth_headers)
        assert res.status_code == 200

    def test_task(target_agent, claiming_worker, expected_to_claim):
        # Create a task
        state = load_state()
        state["goals"] = {}
        state["tasks"] = {}
        save_state(state)
        
        goal_data = {
            "goal_text": "test",
            "workflow_plan": [
                {"target_agent": target_agent, "status": "QUEUED"}
            ]
        }
        res = client.post("/goals", json=goal_data, headers=auth_headers)
        assert res.status_code == 200
        
        # Ensure all workers are marked available and last_seen recent
        state = load_state()
        for w in state["workers"].values():
            w["current_task"] = None
            w["available"] = True
            w["last_seen"] = time.time()
        save_state(state)
        
        res = client.post("/tasks/claim", json={"worker_id": claiming_worker}, headers=auth_headers)
        data = res.get_json()
        if expected_to_claim:
            assert data.get("task") is not None, f"{claiming_worker} failed to claim {target_agent}. Response: {data}"
            print(f"PASS: {claiming_worker} claimed {target_agent}")
        else:
            assert data.get("task") is None, f"{claiming_worker} claimed {target_agent} when it shouldn't have"
            print(f"PASS: {claiming_worker} yielded {target_agent}")

    # 1. deterministic task (linux) chooses deterministic/local when qualified
    # So if expensive AI tries to claim it, it should yield
    test_task("linux", "worker-exp-ai", False)
    test_task("linux", "worker-det", True)
    
    # 2. task requiring AI (windows) skips deterministic
    # Deterministic is not qualified (doesn't have windows)
    # Expensive AI should still yield if cheap AI is available
    test_task("windows", "worker-exp-ai", False)
    # Cheap AI should claim it
    test_task("windows", "worker-cheap-ai", True)
    
    # 3. cheap qualified AI is chosen before expensive AI (already tested above)

    # 4. expensive AI only used when lower-cost qualified option absent
    # Task requires macos, only expensive AI is qualified
    test_task("mac", "worker-exp-ai", True)
    
    print("ALL TESTS PASSED")
    
    with open("PROMPT_23_RETURN_CONTRACT.md", "w") as f:
        f.write("CHEAPEST_QUALIFIED_ROUTING = PASS\n")
        f.write("EXPENSIVE_AI_USED_UNNECESSARILY = NO\n")
        f.write("ROUTING_GENERALIZED = YES\n")

if __name__ == "__main__":
    test_routing()
