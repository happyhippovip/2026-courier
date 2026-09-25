import pytest
import os
import sys

os.environ["COURIER_API_KEY"] = "test"
import keyring
class MockKeyring:
    def get_password(self, s, u): return "test"
keyring.get_password = MockKeyring().get_password

from tests.test_DLQ01_trust_boundary import make_client, auth, make_result

def test_debug(tmp_path, monkeypatch):
    http = make_client(tmp_path, monkeypatch)
    http.post("/workers/register", headers=auth(), json={"worker_id": "W-01", "platform": "mac", "capabilities": ["macos"]})
    goal = http.post("/goals", headers=auth(), json={
        "goal_text": "A",
        "workflow_plan": [{"task_id": "task-A", "target_agent": "mac", "instruction": "Do something", "artifacts": ["a.txt"]}]
    }).json
    
    claimed = http.post("/tasks/claim", headers=auth(), json={"worker_id": "W-01", "capabilities": ["macos"]}).json["task"]
    claimed["worker_id"] = "W-01"

    result_json = make_result(claimed)
    res = http.post("/tasks/result", headers=auth(), json=result_json)
    print("STATUS:", res.status_code)
    print("BODY:", res.json)

