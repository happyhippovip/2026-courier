import os, json
from server import app as server_app
from scripts.integration_contract import _canonical_hash

server_app.STATE_FILE = "./state_lineage.json"
server_app.API_KEY = "test-key"
server_app.VERIFIER_API_KEY = "verifier-key"

client = server_app.app.test_client()
auth = {"Authorization": "Bearer test-key"}
v_auth = {"Authorization": "Bearer verifier-key"}

# Register worker
client.post("/workers/register", headers=auth, json={"worker_id": "W-LINEAGE", "platform": "mac", "capabilities": ["macos"]})

# Submit Goal with 2 tasks
goal_resp = client.post("/goals", headers=auth, json={
    "goal_text": "Lineage test",
    "workflow_plan": [
        {"task_id": "T-LIN-1", "target_agent": "mac", "instruction": "Step 1", "artifacts": []},
        {"task_id": "T-LIN-2", "target_agent": "mac", "instruction": "Step 2", "depends_on": ["T-LIN-1"]}
    ]
}).get_json()

goal_id = goal_resp["goal_id"]

# Claim T1
claim_1 = client.post("/tasks/claim", headers=auth, json={"worker_id": "W-LINEAGE"}).get_json()["task"]

# Provide Result T1 with dummy cost data to test the fields if they are accepted, otherwise just normal result
base_payload = {
    "goal_id": goal_id, "task_id": claim_1["task_id"], "attempt_id": claim_1["attempt_id"],
    "dispatch_id": claim_1["dispatch_id"], "execution_ref": claim_1.get("execution_ref"),
    "worker_id": "W-LINEAGE", "run_id": "run-lin-1", "status": "SUCCESS", "artifacts": [],
    "runtime_identity": claim_1.get("server_binding")
}
ident = dict(base_payload)
base_payload["result_id"] = f"result-{_canonical_hash(ident)}"
# Attach mock cost data in result_data to see if server preserves it
base_payload["result_data"] = {
    "usage": {"input_tokens": 100, "output_tokens": 50, "measurement_basis": "PROVIDER_REPORTED"}
}

client.post("/tasks/result", headers=auth, json=base_payload)

# Verify T1
v_a = {
    "task_id": claim_1["task_id"], "result_id": base_payload["result_id"], "verifier_id": "V-LINEAGE",
    "verdict": "PASS", "artifacts": [], "received_runtime_identity": claim_1.get("server_binding")
}
client.post("/tasks/verify", headers=v_auth, json=v_a)

# Claim T2
claim_2 = client.post("/tasks/claim", headers=auth, json={"worker_id": "W-LINEAGE"}).get_json()["task"]

print(f"GOAL_ID={goal_id}")
print(f"TASK_ID={claim_1['task_id']}")
print(f"REQUEST_ID={claim_1.get('dispatch_id')}")
print(f"RESULT_ID={base_payload['result_id']}")
print(f"WORKER={claim_1['worker_id']}")
print(f"NEXT_TASK_CAUSAL_LINK={claim_2['task_id']}")

