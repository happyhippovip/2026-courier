import os
os.environ["COURIER_API_KEY"] = "test"
os.environ["COURIER_VERIFIER_API_KEY"] = "test"

import sys
from tests.test_DLQ01_trust_boundary import make_client, auth, make_result, verifier_auth
from _pytest.monkeypatch import MonkeyPatch
from pathlib import Path

def run_it():
    tmp_path = Path("/tmp/pytest_fake2")
    tmp_path.mkdir(exist_ok=True)
    monkeypatch = MonkeyPatch()
    
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
    print("RESULT RES:", res.status_code, res.json)
    
    v = http.post("/tasks/verify", headers=verifier_auth(), json={
        "task_id": claimed["task_id"], "verifier_id": "V-01", "result_id": result_json["result_id"], "verdict": "PASS", "artifacts": result_json["artifacts"]
    })
    print("VERIFY RES:", v.status_code, v.json)

run_it()
