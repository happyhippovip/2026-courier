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

goal_id = f"goal-queue-{uuid.uuid4().hex[:4]}"
t1_id = f"msg-1-{uuid.uuid4().hex[:4]}"
t2_id = f"msg-2-{uuid.uuid4().hex[:4]}"
t3_id = f"msg-3-{uuid.uuid4().hex[:4]}"

plan = [
    {
        "task_id": t1_id,
        "message_id": t1_id,
        "queue_order": 1,
        "task_type": "echo",
        "mode": "NATIVE",
        "instruction": f"echo MSG_1_DONE > courier_canary_{t1_id}.txt",
        "target_agent": "mac",
        "target_capability": "mac",
        "owner_scope": "QUEUE_TEST",
        "dependencies": [],
        "artifacts": [f"courier_canary_{t1_id}.txt"],
        "capabilities": ["macos"]
    },
    {
        "task_id": t2_id,
        "message_id": t2_id,
        "queue_order": 2,
        "task_type": "antigravity",
        "instruction": f"Wait 10 seconds. Then create file courier_canary_{t2_id}.txt with content 'MSG_2_DONE'",
        "target_agent": "mac",
        "target_capability": "mac",
        "owner_scope": "QUEUE_TEST",
        "dependencies": [t1_id],
        "artifacts": [f"courier_canary_{t2_id}.txt"],
        "capabilities": ["macos"]
    },
    {
        "task_id": t3_id,
        "message_id": t3_id,
        "queue_order": 3,
        "task_type": "echo",
        "mode": "NATIVE",
        "instruction": f"echo MSG_3_DONE > courier_canary_{t3_id}.txt",
        "target_agent": "mac",
        "target_capability": "mac",
        "owner_scope": "QUEUE_TEST",
        "dependencies": [t2_id],
        "artifacts": [f"courier_canary_{t3_id}.txt"],
        "capabilities": ["macos"]
    }
]

print("Submitting 3-Message Queue Goal...")
resp = requests.post(f"{URL}/goals", json={"goal_text": "Zero-Loss Queue Recovery", "client_id": "test", "workflow_plan": plan}, headers=HEADERS)
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
    
    current_state = f"M1: {s1} | M2: {s2} | M3: {s3}"
    
    if current_state != last_state:
        print(current_state)
        last_state = current_state
        
    if g.get("status") == "DONE":
        print("SUCCESS! All 3 messages successfully executed sequentially!")
        break
    if g.get("status") == "BLOCKED":
        print("FAILED! Goal reached BLOCKED state.")
        break
        
    time.sleep(2)
