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

goal_id = f"goal-motor-{uuid.uuid4().hex[:4]}"
t1_id = f"task-1-{uuid.uuid4().hex[:4]}"
t2_id = f"task-2-{uuid.uuid4().hex[:4]}"
t3_id = f"task-3-{uuid.uuid4().hex[:4]}"

plan = [
    {
        "task_id": t1_id,
        "task_type": "echo",
        "mode": "NATIVE",
        "instruction": f"echo T1_DONE > courier_canary_{t1_id}.txt",
        "target_agent": "mac",
        "target_capability": "mac",
        "owner_scope": "TEST_T1",
        "dependencies": [],
        "artifacts": [f"courier_canary_{t1_id}.txt"],
        "capabilities": ["macos"]
    },
    {
        "task_id": t2_id,
        "task_type": "metadata",
        "target_agent": "github",
        "target_capability": "github",
        "owner_scope": "TEST_T2",
        "dependencies": [],
        "capabilities": ["github"]
    },
    {
        "task_id": t3_id,
        "task_type": "echo",
        "mode": "NATIVE",
        "instruction": f"echo T3_DONE > courier_canary_{t3_id}.txt",
        "target_agent": "mac",
        "target_capability": "mac",
        "owner_scope": "TEST_T3",
        "dependencies": [t1_id],
        "artifacts": [f"courier_canary_{t3_id}.txt"],
        "capabilities": ["macos"]
    }
]

print("Submitting Autonomous Motor Goal...")
resp = requests.post(f"{URL}/goals", json={"goal_text": "Verify Autonomous Motor", "client_id": "test", "workflow_plan": plan}, headers=HEADERS)
if resp.status_code != 200:
    print(f"Failed to submit: {resp.status_code} {resp.text}")
    exit(1)

server_goal_id = resp.json().get("goal_id", goal_id)
print(f"Goal ID: {server_goal_id}")

last_state = ""

while True:
    g = requests.get(f"{URL}/goals/{server_goal_id}", headers=HEADERS).json().get("goal")
    if not g:
        time.sleep(1)
        continue
    
    plan = g.get("workflow_plan", [])
    if not plan:
        continue
        
    s1 = plan[0].get('status')
    s2 = plan[1].get('status')
    s3 = plan[2].get('status')
    
    current_state = f"T1(Mac): {s1} | T2(GH): {s2} | T3(Mac, deps on T1): {s3}"
    
    if current_state != last_state:
        print(current_state)
        last_state = current_state
        
    if g.get("status") == "DONE":
        print("SUCCESS! Autonomous motor resolved all branches sequentially and in parallel!")
        break
    if g.get("status") == "BLOCKED":
        print("FAILED! Goal reached BLOCKED state.")
        break
        
    time.sleep(2)
