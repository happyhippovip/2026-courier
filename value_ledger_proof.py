import json
from server import app as server_app
from scripts.integration_contract import _canonical_hash

server_app.STATE_FILE = "./state_value.json"
server_app.API_KEY = "test-key"
server_app.VERIFIER_API_KEY = "verifier-key"

client = server_app.app.test_client()
auth = {"Authorization": "Bearer test-key"}

client.post("/workers/register", headers=auth, json={"worker_id": "W-VALUE", "platform": "mac", "capabilities": ["macos"]})

goal = client.post("/goals", headers=auth, json={
    "goal_text": "Value test",
    "workflow_plan": [{"task_id": "T-VAL", "target_agent": "mac", "instruction": "Step 1"}]
}).get_json()

claim = client.post("/tasks/claim", headers=auth, json={"worker_id": "W-VALUE"}).get_json()["task"]

base_payload = {
    "goal_id": claim["goal_id"], "task_id": claim["task_id"], "attempt_id": claim["attempt_id"],
    "dispatch_id": claim["dispatch_id"], "execution_ref": claim.get("execution_ref"),
    "worker_id": "W-VALUE", "run_id": "run-val", "status": "SUCCESS", "artifacts": [],
    "runtime_identity": claim.get("server_binding")
}
ident = dict(base_payload)
base_payload["result_id"] = f"result-{_canonical_hash(ident)}"
base_payload["result_data"] = {
    "asset_created": "Sales Tool",
    "business_problem": "Lead gen",
    "customer_relevance": "High",
    "revenue_status": "BUILT",
    "confirmed_revenue_eur": 0,
    "confirmed_recurring_revenue_eur_month": 0,
    "estimated_opportunity_value_eur": 500,
    "target_contribution": "FIRST_REAL_REVENUE"
}

r1 = client.post("/tasks/result", headers=auth, json=base_payload)
print(f"STATUS={r1.status_code}")
print(f"STORED_DATA={json.dumps(r1.get_json())}")
