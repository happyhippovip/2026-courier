import os
import json
import time
import subprocess
import urllib.request
import urllib.error
import sys
from pathlib import Path

# Setup
os.environ["COURIER_API_KEY"] = "test-api-key-12345"
os.environ["COURIER_VERIFIER_API_KEY"] = "test-api-key-12345-verifier"
os.environ["COURIER_STATE_FILE"] = "server/state/test_state.json"

server_proc = subprocess.Popen([sys.executable, "-m", "server.app"], env=os.environ)
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

print("Registering Windows worker...")
http_post("/workers/register", {
    "worker_id": "win1",
    "platform": "windows",
    "capabilities": ["windows"]
})

print("Registering Generic (Linux) worker...")
http_post("/workers/register", {
    "worker_id": "lin1",
    "platform": "linux",
    "capabilities": ["linux"]
})

print("Submitting Windows Goal...")
goal_win, _ = http_post("/goals", {
    "goal_text": "Test windows",
    "workflow_plan": [
        {"instruction": "Do windows task", "target_agent": "windows"}
    ]
})

print("Submitting Linux Goal...")
goal_lin, _ = http_post("/goals", {
    "goal_text": "Test linux",
    "workflow_plan": [
        {"instruction": "Do linux task", "target_agent": "linux"}
    ]
})

print("Windows worker claiming (should get windows task)...")
claim_win, _ = http_post("/tasks/claim", {"worker_id": "win1"})
print("Windows worker claimed:", claim_win)

print("Generic worker claiming (should get linux task)...")
claim_lin, _ = http_post("/tasks/claim", {"worker_id": "lin1"})
print("Generic worker claimed:", claim_lin)

server_proc.terminate()
