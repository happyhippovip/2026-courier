import json
from server import app as server_app
from scripts.integration_contract import _canonical_hash

server_app.STATE_FILE = "./state_gate.json"
server_app.API_KEY = "test-key"
server_app.VERIFIER_API_KEY = "verifier-key"

client = server_app.app.test_client()
auth = {"Authorization": "Bearer test-key"}

client.post("/workers/register", headers=auth, json={"worker_id": "W-GATE", "platform": "mac", "capabilities": ["macos"]})

goal = client.post("/goals", headers=auth, json={
    "goal_text": "Gate test",
    "workflow_plan": [{"task_id": "T-GATE", "target_agent": "mac", "instruction": "Dangerous step"}]
}).get_json()

claim = client.post("/tasks/claim", headers=auth, json={"worker_id": "W-GATE"}).get_json()["task"]

base_payload = {
    "goal_id": claim["goal_id"], "task_id": claim["task_id"], "attempt_id": claim["attempt_id"],
    "dispatch_id": claim["dispatch_id"], "execution_ref": claim.get("execution_ref"),
    "worker_id": "W-GATE", "run_id": "run-gate", "status": "FAILED", "artifacts": [],
    "runtime_identity": claim.get("server_binding")
}
ident = dict(base_payload)
base_payload["result_id"] = f"result-{_canonical_hash(ident)}"
base_payload["result_data"] = {
    "human_gate": {
        "timestamp": "2026-09-19T06:17:00Z",
        "gate_category": "SECURITY",
        "exact_decision_requested": "Approve production API key generation",
        "why_automation_stopped": "Requires high-privilege IAM",
        "safe_work_remaining": "None in this task",
        "risk_if_executed_without_approval": "Unauthorized prod access",
        "status": "PENDING"
    }
}

r1 = client.post("/tasks/result", headers=auth, json=base_payload)
print(f"STATUS={r1.status_code}")
print(f"STORED_DATA={json.dumps(r1.get_json())}")
