import uuid, json, subprocess
from server import app as server_app
from scripts.integration_contract import _canonical_hash

server_app.STATE_FILE = "./state_smoke.json"
server_app.API_KEY = "test-key"
server_app.VERIFIER_API_KEY = "verifier-key"

client = server_app.app.test_client()

auth = {"Authorization": "Bearer test-key"}
v_auth = {"Authorization": "Bearer verifier-key"}

client.post("/workers/register", headers=auth, json={"worker_id": "W-SMOKE", "platform": "mac", "capabilities": ["macos"]})
goal = client.post("/goals", headers=auth, json={
    "goal_text": "Smoke test",
    "workflow_plan": [
        {"task_id": "T-SMOKE", "target_agent": "mac", "instruction": "Smoke test local", "artifacts": ["test.txt"]}
    ]
}).get_json()

task = client.post("/tasks/claim", headers=auth, json={"worker_id": "W-SMOKE"}).get_json()["task"]

base_payload = {
    "goal_id": task["goal_id"], "task_id": task["task_id"], "attempt_id": task["attempt_id"],
    "dispatch_id": task["dispatch_id"], "execution_ref": task.get("execution_ref"), "worker_id": "W-SMOKE",
    "run_id": "run-smoke", "status": "SUCCESS", "artifacts": [{"path": "test.txt", "sha256": "0"*64}], "runtime_identity": task.get("server_binding")
}
ident = dict(base_payload)
base_payload["result_id"] = f"result-{_canonical_hash(ident)}"

r1 = client.post("/tasks/result", headers=auth, json=base_payload)

v_a = {
    "task_id": task["task_id"], "result_id": base_payload["result_id"], "verifier_id": "V-SMOKE",
    "verdict": "PASS", "artifacts": base_payload["artifacts"], "received_runtime_identity": task.get("server_binding")
}
r2 = client.post("/tasks/verify", headers=v_auth, json=v_a)

if r1.status_code == 200 and r2.status_code == 200:
    print("SMOKE_TEST=PASS")
else:
    print(f"SMOKE_TEST=FAIL {r1.status_code} {r2.status_code}")
