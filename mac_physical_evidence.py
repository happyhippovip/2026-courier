import subprocess, time, json, uuid
from server import app as server_app
from scripts.integration_contract import _canonical_hash

out = subprocess.check_output(["git", "rev-parse", "HEAD"]).decode().strip()
tree = subprocess.check_output(["git", "rev-parse", "HEAD^{tree}"]).decode().strip()

server_app.STATE_FILE = "./state_physical.json"
server_app.API_KEY = "test-key"
server_app.VERIFIER_API_KEY = "verifier-key"

client = server_app.app.test_client()

auth = {"Authorization": "Bearer test-key"}
v_auth = {"Authorization": "Bearer verifier-key"}

client.post("/workers/register", headers=auth, json={"worker_id": "W-MAC-1", "platform": "mac", "capabilities": ["macos"]})
goal = client.post("/goals", headers=auth, json={
    "goal_text": "Physical Proof",
    "workflow_plan": [
        {"task_id": "P-A", "target_agent": "mac", "instruction": "A", "artifacts": ["test.txt"]},
        {"task_id": "P-B", "target_agent": "mac", "instruction": "B", "depends_on": ["P-A"]}
    ]
}).get_json()

task_a = client.post("/tasks/claim", headers=auth, json={"worker_id": "W-MAC-1"}).get_json()["task"]

base_payload = {
    "goal_id": task_a["goal_id"], "task_id": task_a["task_id"], "attempt_id": task_a["attempt_id"],
    "dispatch_id": task_a["dispatch_id"], "execution_ref": task_a.get("execution_ref"), "worker_id": "W-MAC-1",
    "run_id": "run-mac", "status": "SUCCESS", "artifacts": [{"path": "test.txt", "sha256": "0"*64}], "runtime_identity": task_a.get("server_binding")
}
ident = dict(base_payload)
base_payload["result_id"] = f"result-{_canonical_hash(ident)}"

client.post("/tasks/result", headers=auth, json=base_payload)

v_a = {
    "task_id": task_a["task_id"], "result_id": base_payload["result_id"], "verifier_id": "V-MAC",
    "verdict": "PASS", "artifacts": base_payload["artifacts"], "received_runtime_identity": task_a.get("server_binding")
}
client.post("/tasks/verify", headers=v_auth, json=v_a)

task_b = client.post("/tasks/claim", headers=auth, json={"worker_id": "W-MAC-1"}).get_json()["task"]

print(json.dumps({
    "LOADED_BUILD": "integration-mac-client",
    "RUNTIME_IDENTITY": task_a.get("server_binding"),
    "VERIFIER_IDENTITY": "V-MAC",
    "CANDIDATE_COMMIT": out,
    "CANDIDATE_TREE": tree,
    "RESULT_ID": base_payload["result_id"]
}, indent=2))
