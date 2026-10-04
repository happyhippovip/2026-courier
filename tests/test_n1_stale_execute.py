import json
import time
import tempfile
import pathlib

from test_server_integration_contract import client, auth
from server import app as server_app

def test_stale_result_submission_is_rejected():
    """N1: Proves that a stale execution result is rejected by the server."""
    with tempfile.TemporaryDirectory() as td:
        tmp_path = pathlib.Path(td)
        class DummyMonkey:
            def setattr(self, obj, name, val):
                setattr(obj, name, val)
        
        http = client(tmp_path, DummyMonkey())
        state_file = tmp_path / "state.json"
        
        # 1. Register a worker
        res = http.post("/workers/register", headers=auth(), json={"worker_id": "MAC-01", "capabilities": ["mac", "macos"]})
        assert res.status_code == 200

        # 2. Add a goal and task
        state = json.loads(state_file.read_text())
        state["goals"]["goal-1"] = {
            "status": "ACTIVE",
            "workflow_plan": [{"task_id": "task-1", "goal_id": "goal-1", "status": "QUEUED", "target_agent": "mac", "target_capability": "mac"}]
        }
        state["tasks"]["task-1"] = {
            "task_id": "task-1",
            "goal_id": "goal-1",
            "status": "QUEUED",
            "mode": "NATIVE",
            "target_capability": "mac",
            "instruction": "test",
            "artifacts": []
        }
        server_app.save_state(state)

        # 3. Claim the task
        res = http.post("/tasks/claim", headers=auth(), json={"worker_id": "MAC-01"})
        assert res.status_code == 200, res.text
        task = res.json["task"]
        assert task["task_id"] == "task-1"

        # 4. Simulate the worker becoming stale and the task being quarantined
        state = json.loads(state_file.read_text())
        state["workers"]["MAC-01"]["last_seen"] = time.time() - 600
        server_app.save_state(state)
        http.post("/tasks/reclaim_stale", headers=auth())
        
        # Verify task is quarantined
        state = json.loads(state_file.read_text())
        assert state["tasks"]["task-1"]["status"] == "HUMAN_REQUIRED"

        # 5. The stale worker reappears and attempts to submit a result
        res = http.post("/tasks/result", headers=auth(), json={
            "worker_id": "MAC-01",
            "task_id": "task-1",
            "dispatch_id": task["dispatch_id"],
            "status": "SUCCESS",
            "execution_mode": "NATIVE",
            "artifacts": []
        })
        
        # Server must reject the stale result with 409 Conflict
        assert res.status_code == 409
        assert res.json["error"] == "Task is not awaiting a result"
        
        # Ensure ledger wasn't modified by the stale result
        state = json.loads(state_file.read_text())
        assert state["tasks"]["task-1"]["status"] == "HUMAN_REQUIRED"
        assert "result" not in state["tasks"]["task-1"]
        print("TEST PASSED")

if __name__ == '__main__':
    test_stale_result_submission_is_rejected()

