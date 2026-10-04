import os
import json
import time
import threading
import sys
import urllib.request
from pathlib import Path

os.environ["COURIER_API_KEY"] = "test-key"
os.environ["COURIER_VERIFIER_API_KEY"] = "test-key-verifier"
os.environ["COURIER_SERVER"] = "http://127.0.0.1:8081"
os.environ["COURIER_STATE_FILE"] = "./q14_state.json"
os.environ["COURIER_GITHUB_DISPATCH_DIR"] = "events/github-dispatch"
if os.path.exists(os.environ["COURIER_STATE_FILE"]):
    os.remove(os.environ["COURIER_STATE_FILE"])
if os.path.exists(os.environ["COURIER_STATE_FILE"] + ".sig"):
    os.remove(os.environ["COURIER_STATE_FILE"] + ".sig")

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
    courier_verifier.run_loop()

verifier_thread = threading.Thread(target=run_verifier, daemon=True)
verifier_thread.start()

def run_dispatcher():
    from scripts import courier_github_dispatcher
    courier_github_dispatcher.API_KEY = "test-key"
    courier_github_dispatcher.API_URL = "http://127.0.0.1:8081"
    courier_github_dispatcher.HEADERS = {"Authorization": "Bearer test-key", "Content-Type": "application/json"}
    courier_github_dispatcher.run_loop()

dispatcher_thread = threading.Thread(target=run_dispatcher, daemon=True)
dispatcher_thread.start()
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

print("Submitting GitHub Goal...")
res, code = http_post("/goals", {
    "goal_text": "GitHub Proof",
    "workflow_plan": [
        {"task_id": "gh1", "target_agent": "linux_cloud", "task_type": "deterministic_transform", "input": "Hello Q14", "artifacts": ["courier_output.json"]}
    ]
})

if not res:
    print("Failed to create goal")
    sys.exit(1)

goal_id = res["goal_id"]
print(f"Goal created: {goal_id}")

for i in range(120):
    time.sleep(5)
    req = urllib.request.Request(f"http://127.0.0.1:8081/goals/{goal_id}", method="GET")
    req.add_header("Authorization", "Bearer test-key")
    try:
        with urllib.request.urlopen(req) as response:
            state = json.loads(response.read().decode("utf-8"))
            st = state.get("goal", {}).get("status")
            print(f"[{i}] Goal status: {st}")
            if st == "DONE":
                print("Q14 Proof successful: GitHub task finished automatically!")
                sys.exit(0)
    except Exception as e:
        pass

print("Timeout waiting for goal to finish!")
sys.exit(1)
