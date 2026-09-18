import os
import sys
import time
import requests
import uuid
import threading
from concurrent.futures import ThreadPoolExecutor

API_KEY = "test-key-123"
os.environ["COURIER_API_KEY"] = API_KEY
HEADERS = {"Authorization": f"Bearer {API_KEY}"}

from server.app import app, load_state

def run_server():
    app.run(port=5001, debug=False, use_reloader=False)

threading.Thread(target=run_server, daemon=True).start()
time.sleep(2)

BASE_URL = "http://localhost:5001"

# 1. Register 10 workers
workers = [f"w10-worker-{uuid.uuid4().hex}" for _ in range(10)]
for w in workers:
    res = requests.post(f"{BASE_URL}/workers/register", json={"worker_id": w, "capabilities": ["windows"]}, headers=HEADERS)
    assert res.status_code == 200

# 2. Submit Goal with 1 Task
res = requests.post(f"{BASE_URL}/goals", json={"goal_text": "W10 Test", "workflow_plan": [{"instruction": "W10 Test Task", "target_agent": "windows"}]}, headers=HEADERS)
assert res.status_code == 200
goal_id = res.json()["goal_id"]

# 3. Concurrent claim
claims = []
def claim_task(worker_id):
    res = requests.post(f"{BASE_URL}/tasks/claim", json={"worker_id": worker_id}, headers=HEADERS)
    if res.status_code == 200 and res.json().get("task"):
        task = res.json()["task"]
        if task.get("goal_id") == goal_id:
            claims.append(task)

with ThreadPoolExecutor(max_workers=10) as executor:
    executor.map(claim_task, workers)

if len(claims) == 1:
    print("W10: QUALIFIED CLAIM / SINGLE-FLIGHT proven. Exactly one worker claimed the task.")
    sys.exit(0)
else:
    print(f"W10 FAILED: Expected 1 claim, got {len(claims)} claims.")
    for c in claims:
        print(c["worker_id"], c["task_id"])
    sys.exit(1)


