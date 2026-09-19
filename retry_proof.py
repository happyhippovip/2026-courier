import json
from server import app as server_app
from scripts.integration_contract import _canonical_hash

server_app.STATE_FILE = "./state_retry.json"
server_app.API_KEY = "test-key"
server_app.VERIFIER_API_KEY = "verifier-key"

client = server_app.app.test_client()
auth = {"Authorization": "Bearer test-key"}

client.post("/workers/register", headers=auth, json={"worker_id": "W-RETRY", "platform": "mac", "capabilities": ["macos"]})

goal = client.post("/goals", headers=auth, json={
    "goal_text": "Retry test",
    "workflow_plan": [{"task_id": "T-RETRY", "target_agent": "mac", "instruction": "Failing step"}]
}).get_json()

claim = client.post("/tasks/claim", headers=auth, json={"worker_id": "W-RETRY"}).get_json()["task"]

base_payload = {
    "goal_id": claim["goal_id"], "task_id": claim["task_id"], "attempt_id": claim["attempt_id"],
    "dispatch_id": claim["dispatch_id"], "execution_ref": claim.get("execution_ref"),
    "worker_id": "W-RETRY", "run_id": "run-retry", "status": "FAILED", "artifacts": [],
    "runtime_identity": claim.get("server_binding")
}
ident = dict(base_payload)
base_payload["result_id"] = f"result-{_canonical_hash(ident)}"
base_payload["result_data"] = {
    "retry_metadata": {
        "previous_attempt_id": None,
        "retry_reason": "Rate limit hit",
        "failure_category": "RATE_LIMIT",
        "idempotency_key": "idem-123",
        "previous_effect_exists": False,
        "retry_allowed": True,
        "retry_executed": False,
        "duplicate_prevented": True,
        "intervention_type": "AUTOMATIC",
        "evidence_ref": "log-456"
    }
}

r1 = client.post("/tasks/result", headers=auth, json=base_payload)
print(f"STATUS={r1.status_code}")
print(f"STORED_DATA={json.dumps(r1.get_json())}")
