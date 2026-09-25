import os
import json
import time
import subprocess
import urllib.request
import urllib.error
import sys

# Setup
os.environ["COURIER_API_KEY"] = "test-api-key-12345"
os.environ["COURIER_VERIFIER_API_KEY"] = "test-api-key-12345-verifier"
os.environ["COURIER_STATE_FILE"] = "server/state/test_state.json"

if os.path.exists(os.environ["COURIER_STATE_FILE"]):
    os.remove(os.environ["COURIER_STATE_FILE"])

import threading
from server.app import app
def run_server():
    app.run(host="0.0.0.0", port=8080, use_reloader=False)

server_thread = threading.Thread(target=run_server, daemon=True)
server_thread.start()
time.sleep(2)


def http_post(endpoint, data):
    url = f"http://127.0.0.1:8080{endpoint}"
    req = urllib.request.Request(url, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", "Bearer test-api-key-12345")
    try:
        with urllib.request.urlopen(req, data=json.dumps(data).encode("utf-8"), timeout=5) as response:
            return json.loads(response.read().decode("utf-8")), response.getcode()
    except Exception as e:
        print(f"Error {endpoint}: {e}")
        return None, 500

try:
    print("1. Submitting Windows Goal...")
    http_post("/goals", {
        "goal_text": "Windows task",
        "workflow_plan": [
            {"instruction": "Do windows task", "target_agent": "windows"}
        ]
    })

    print("2. Submitting Generic (Linux) Goal...")
    http_post("/goals", {
        "goal_text": "Linux task",
        "workflow_plan": [
            {"instruction": "Do linux task", "target_agent": "linux"}
        ]
    })

    print("3. Registering Linux worker...")
    http_post("/workers/register", {
        "worker_id": "lin1",
        "platform": "linux",
        "capabilities": ["linux"]
    })

    print("4. Windows worker is ABSENT. Linux worker claiming tasks...")
    claim_lin, _ = http_post("/tasks/claim", {"worker_id": "lin1"})
    
    if claim_lin and claim_lin.get("task"):
        task = claim_lin["task"]
        print(f"Linux worker claimed: {task['target_agent']} task")
        if task["target_agent"] == "linux":
            print("PASS: Linux worker successfully claimed its task despite Windows task being blocked/queued first.")
        else:
            print(f"FAIL: Linux worker claimed a {task['target_agent']} task.")
    else:
        print("FAIL: Linux worker failed to claim any task.")
        
    print("5. Attempting to claim again with Linux worker...")
    claim_lin2, _ = http_post("/tasks/claim", {"worker_id": "lin1"})
    if claim_lin2 and not claim_lin2.get("task"):
        print("PASS: Linux worker correctly received no tasks (Windows task remains queued).")
    else:
        print("FAIL: Linux worker claimed something it shouldn't have.")

except Exception as e:
    print(e)
print("Done")
