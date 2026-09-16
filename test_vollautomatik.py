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

goal_id = f"goal-voll-{uuid.uuid4().hex[:4]}"
task_a_id = f"task-a-{uuid.uuid4().hex[:4]}"
task_b_id = f"task-b-{uuid.uuid4().hex[:4]}"

plan = [
    {
        "task_id": task_a_id,
        "task_type": "verify_file",
        "instruction": "echo GITHUB_SUCCESS > courier_canary_voll_a.txt",
        "target_agent": "github",
        "target_capability": "github",
        "owner_scope": "TEST_A",
        "dependencies": [],
        "artifacts": ["courier_canary_voll_a.txt"],
        "capabilities": ["github"]
    },
    {
        "task_id": task_b_id,
        "task_type": "verify_file",
        "instruction": "echo MAC_SUCCESS > courier_canary_voll_b.txt",
        "target_agent": "mac",
        "target_capability": "mac",
        "owner_scope": "TEST_B",
        "dependencies": [task_a_id],
        "artifacts": ["courier_canary_voll_b.txt"],
        "capabilities": ["macos"]
    }
]

print("Submitting Vollautomatik Goal...")
resp = requests.post(f"{URL}/goals", json={"goal_text": "Cross-worker verification", "client_id": "test", "workflow_plan": plan}, headers=HEADERS)
if resp.status_code != 200:
    print(f"Failed to submit: {resp.status_code} {resp.text}")
    exit(1)

server_goal_id = resp.json().get("goal_id", goal_id)
print(f"Goal ID: {server_goal_id}")

last_a = ""
last_b = ""

while True:
    g = requests.get(f"{URL}/goals/{server_goal_id}", headers=HEADERS).json().get("goal")
    if not g:
        time.sleep(1)
        continue
    
    plan = g.get("workflow_plan", [])
    if not plan:
        continue
        
    a = plan[0]
    b = plan[1]
    
    status_a = f"A: {a.get('status')} by {a.get('worker_id')}"
    status_b = f"B: {b.get('status')} by {b.get('worker_id')}"
    
    if status_a != last_a or status_b != last_b:
        print(f"{status_a} | {status_b}")
        last_a = status_a
        last_b = status_b
        
    if g.get("status") == "DONE":
        print("SUCCESS! Goal reached DONE state automatically!")
        break
    if g.get("status") == "BLOCKED":
        print("FAILED! Goal reached BLOCKED state.")
        break
        
    time.sleep(2)
