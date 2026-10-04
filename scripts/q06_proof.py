import os
import json
import time
import subprocess
import urllib.request
import threading
import sys
import uuid
from pathlib import Path

os.environ["COURIER_API_KEY"] = "test-key"
os.environ["COURIER_VERIFIER_API_KEY"] = "test-key-verifier"
os.environ["COURIER_STATE_FILE"] = "./q06_state.json"
os.environ["COURIER_WORKER_CONFIG"] = "q06_config.json"
os.environ["COURIER_WORKER_HOME"] = "q06_home"
os.environ["COURIER_ARTIFACT_UPLOAD"] = "true"

if os.path.exists(os.environ["COURIER_STATE_FILE"]):
    os.remove(os.environ["COURIER_STATE_FILE"])
if os.path.exists("q06_state.json.sig"):
    os.remove("q06_state.json.sig")

Path("q06_home/state").mkdir(parents=True, exist_ok=True)
Path("q06_home/logs").mkdir(parents=True, exist_ok=True)
with open(os.environ["COURIER_WORKER_CONFIG"], "w") as f:
    json.dump({
        "WORKER_ID": "MAC-01",
        "PLATFORM": "mac",
        "CAPABILITIES": ["macos"],
        "COURIER_SERVER": "http://127.0.0.1:8081",
        "COURIER_API_KEY": "test-key",
        "SLEEP_SECONDS": 1,
        "ARTIFACT_UPLOAD": True
    }, f)

from server.app import app
def run_server():
    app.run(host="127.0.0.1", port=8081, use_reloader=False)

server_thread = threading.Thread(target=run_server, daemon=True)
server_thread.start()
time.sleep(2)

def run_verifier():
    from scripts import courier_verifier
    courier_verifier.API_KEY = "test-key"
    courier_verifier.VERIFIER_API_KEY = "test-key-verifier"
    courier_verifier.COURIER_SERVER = "http://127.0.0.1:8081"
    courier_verifier.API_URL = "http://127.0.0.1:8081"
    courier_verifier.VERIFIER_ID = "V-01"
    courier_verifier.HEADERS = {"Authorization": "Bearer test-key-verifier", "Content-Type": "application/json"}
    
    # We also need a dummy fetch artifact if upload is not configured?
    # No, I enabled COURIER_ARTIFACT_UPLOAD=true so it will upload it!
    # Wait, the artifact will be saved in COURIER_ARTIFACT_STORE (default server/artifacts).
    courier_verifier.run_loop()

verifier_thread = threading.Thread(target=run_verifier, daemon=True)
verifier_thread.start()

def run_worker():
    from scripts.mac_worker import daemon
    daemon.CONFIG_PATH = Path("q06_config.json")
    daemon.STATE_DIR = Path("q06_home/state")
    daemon.LOGS_DIR = Path("q06_home/logs")
    daemon.loop()

worker_thread = threading.Thread(target=run_worker, daemon=True)
worker_thread.start()
time.sleep(2)

def http_post(endpoint, data):
    url = f"http://127.0.0.1:8081{endpoint}"
    req = urllib.request.Request(url, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", "Bearer test-key")
    try:
        with urllib.request.urlopen(req, data=json.dumps(data).encode("utf-8"), timeout=5) as response:
            return json.loads(response.read().decode("utf-8")), response.getcode()
    except Exception as e:
        print(f"Error {endpoint}: {e}")
        return None, 500

def http_get(endpoint):
    url = f"http://127.0.0.1:8081{endpoint}"
    req = urllib.request.Request(url, method="GET")
    req.add_header("Authorization", "Bearer test-key")
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            return json.loads(response.read().decode("utf-8")), response.getcode()
    except Exception as e:
        print(f"Error {endpoint}: {e}")
        return None, 500

print("Submitting Goal...")
res, code = http_post("/goals", {
    "goal_text": "two steps",
    "workflow_plan": [
        {"task_id": "a", "target_agent": "mac_desktop", "instruction": "echo 'content_a' > a.txt", "artifacts": ["a.txt"]},
        {"task_id": "b", "target_agent": "mac_desktop", "instruction": "echo 'content_b' > b.txt", "artifacts": ["b.txt"]}
    ]
})

goal_id = res["goal_id"]
print(f"Goal created: {goal_id}")

for i in range(20):
    time.sleep(2)
    state, _ = http_get(f"/goals/{goal_id}")
    if state:
        st = state.get("goal", {}).get("status")
        print(f"Goal status: {st}")
        if st == "DONE":
            print("Q06 Proof successful: Real Mac A->B canary finished automatically!")
            sys.exit(0)

print("Timeout waiting for goal to finish!")
sys.exit(1)
