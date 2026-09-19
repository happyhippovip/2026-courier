import subprocess, time, json
import urllib.request
from urllib.error import HTTPError

out = subprocess.check_output(["git", "rev-parse", "HEAD"]).decode().strip()
tree = subprocess.check_output(["git", "rev-parse", "HEAD^{tree}"]).decode().strip()

server = subprocess.Popen(["python3", "-m", "flask", "run", "--port", "8085"], env={"FLASK_APP": "server/app.py", "COURIER_API_KEY": "test-key", "COURIER_VERIFIER_API_KEY": "verifier-key", "PATH": "/usr/local/bin:/usr/bin:/bin"})
time.sleep(2)

def req(url, payload=None, auth_key="test-key"):
    req = urllib.request.Request("http://localhost:8085" + url, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", f"Bearer {auth_key}")
    try:
        if payload:
            res = urllib.request.urlopen(req, data=json.dumps(payload).encode())
        else:
            res = urllib.request.urlopen(req)
        return json.loads(res.read())
    except HTTPError as e:
        print(e.read().decode())
        raise

try:
    req("/workers/register", {"worker_id": "W-MAC-1", "platform": "mac", "capabilities": ["macos"], "cost_class": "low", "runtime_sha": out})
    goal_res = req("/goals", {
        "goal_text": "Physical Proof",
        "workflow_plan": [
            {"task_id": "P-A", "target_agent": "mac", "instruction": "echo 'Hello'", "artifacts": ["test.txt"]},
            {"task_id": "P-B", "target_agent": "mac", "instruction": "echo 'World'", "depends_on": ["P-A"]}
        ]
    })
    
    task_a = req("/tasks/claim", {"worker_id": "W-MAC-1"})["task"]
    
    from scripts.integration_contract import _canonical_hash
    base_payload = {
        "goal_id": task_a["goal_id"], "task_id": task_a["task_id"], "attempt_id": task_a["attempt_id"],
        "dispatch_id": task_a["dispatch_id"], "execution_ref": task_a.get("execution_ref"), "worker_id": "W-MAC-1",
        "run_id": "run-mac", "status": "SUCCESS", "artifacts": [{"path": "test.txt", "sha256": "0"*64}], "runtime_identity": task_a.get("server_binding")
    }
    ident = dict(base_payload)
    base_payload["result_id"] = f"result-{_canonical_hash(ident)}"
    
    req("/tasks/result", base_payload)
    
    v_a = {
        "task_id": task_a["task_id"], "result_id": base_payload["result_id"], "verifier_id": "V-MAC",
        "verdict": "PASS", "artifacts": base_payload["artifacts"], "received_runtime_identity": task_a.get("server_binding")
    }
    req("/tasks/verify", v_a, "verifier-key")
    
    task_b = req("/tasks/claim", {"worker_id": "W-MAC-1"})["task"]
    
    print(json.dumps({
        "commit": out,
        "tree": tree,
        "server_binding": task_a.get("server_binding"),
        "verifier_id": "V-MAC",
        "result_a": base_payload["result_id"],
        "task_b_claimed": task_b["task_id"]
    }))
    
finally:
    server.terminate()
