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

goal_id = f"goal-final-{uuid.uuid4().hex[:4]}"
t1_id = f"task-a-{uuid.uuid4().hex[:4]}"
t2_id = f"task-b-{uuid.uuid4().hex[:4]}"

plan = [
    {
        "task_id": t1_id,
        "task_type": "antigravity",
        "instruction": f"Wait 10 seconds. Then create file courier_canary_{t1_id}.txt with content 'TASK_A_DONE'",
        "target_agent": "mac",
        "target_capability": "mac",
        "owner_scope": "FINAL_TEST",
        "dependencies": [],
        "artifacts": [f"courier_canary_{t1_id}.txt"],
        "capabilities": ["macos"]
    },
    {
        "task_id": t2_id,
        "task_type": "metadata",
        "target_agent": "github",
        "target_capability": "github",
        "owner_scope": "FINAL_TEST",
        "dependencies": [t1_id],
        "capabilities": ["github"]
    }
]

print("Submitting Final Physical A-to-B Canary...")
resp = requests.post(f"{URL}/goals", json={"goal_text": "ONE HUMAN GOAL", "client_id": "test", "workflow_plan": plan}, headers=HEADERS)
if resp.status_code != 200:
    print(f"Failed to submit: {resp.status_code} {resp.text}")
    exit(1)

server_goal_id = resp.json().get("goal_id", goal_id)
print(f"Goal ID: {server_goal_id}")

last_state = ""
killed_daemon = False

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
    
    current_state = f"Task A (Mac AI): {s1} | Task B (GitHub): {s2}"
    
    if current_state != last_state:
        print(current_state)
        last_state = current_state
        
    # Simulate Account/Session Replacement mid-flight
    if s1 == "DISPATCHED" and not killed_daemon:
        print(">>> Task A is DISPATCHED. Wait 5s then simulate Provider/Session Loss! <<<")
        time.sleep(5)
        print(">>> Triggering pkill -f daemon.py <<<")
        os.system("pkill -f daemon.py")
        killed_daemon = True

    if g.get("status") == "DONE":
        print("SUCCESS! Final Physical Operator-Level Vollautomatik Verified!")
        break
    if g.get("status") == "BLOCKED":
        print("FAILED! Goal reached BLOCKED state.")
        break
        
    time.sleep(2)
