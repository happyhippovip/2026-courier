import requests
import json
import uuid
import time
import os

URL = "http://localhost:8080"
API_KEY = os.environ.get("COURIER_API_KEY")
if not API_KEY:
    try:
        import subprocess
        API_KEY = subprocess.check_output(["security", "find-generic-password", "-a", "courier_worker", "-s", "courier_api_key", "-w"]).decode().strip()
    except Exception:
        raise ValueError("Cannot find API key")

HEADERS = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}

goal_id = f"goal-ext-{uuid.uuid4().hex[:4]}"
task_a_id = f"task-ext-{uuid.uuid4().hex[:4]}"

plan = [
    {
        "task_id": task_a_id,
        "task_type": "metadata",
        "target_agent": "github",
        "target_capability": "github",
        "owner_scope": "TEST_EXT",
        "dependencies": [],
        "capabilities": ["github"]
    }
]

print("Submitting External Routing Goal...")
resp = requests.post(f"{URL}/goals", json={"goal_text": "Verify External Capability Routing", "client_id": "test", "workflow_plan": plan}, headers=HEADERS)
if resp.status_code != 200:
    print(f"Failed to submit: {resp.status_code} {resp.text}")
    exit(1)

server_goal_id = resp.json().get("goal_id", goal_id)
print(f"Goal ID: {server_goal_id}")

last_a = ""

while True:
    g = requests.get(f"{URL}/goals/{server_goal_id}", headers=HEADERS).json().get("goal")
    if not g:
        time.sleep(1)
        continue
    
    plan = g.get("workflow_plan", [])
    if not plan:
        continue
        
    a = plan[0]
    
    status_a = f"Ext Task: {a.get('status')} by {a.get('worker_id')}"
    
    if status_a != last_a:
        print(status_a)
        last_a = status_a
        
    if g.get("status") == "DONE":
        print("SUCCESS! External task reached DONE state automatically!")
        break
    if g.get("status") == "BLOCKED":
        print("FAILED! Goal reached BLOCKED state.")
        break
        
    time.sleep(2)
