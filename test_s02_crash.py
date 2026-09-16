import requests, json, time, uuid

URL = "http://localhost:8080"
HEADERS = {"Authorization": "Bearer prod-secret-12345", "Content-Type": "application/json"}

tid = f"task_crash_{uuid.uuid4().hex[:8]}"
plan = [
    {
        "task_id": tid,
        "task_type": "echo",
        "instruction": "pkill -f daemon.py",
        "target_agent": "mac",
        "owner_scope": "TEST_CRASH",
        "dependencies": [],
        "artifacts": [],
        "capabilities": ["linux"]
    }
]

print("Submitting Crash Goal...")
resp = requests.post(f"{URL}/goals", json={"goal_text": "Crash Test", "client_id": "test", "workflow_plan": plan}, headers=HEADERS)
goal_id = resp.json()["goal_id"]
print(f"Goal ID: {goal_id}")

while True:
    g = requests.get(f"{URL}/goals/{goal_id}", headers=HEADERS).json().get("goal")
    if not g:
        time.sleep(1)
        continue
    
    t = g.get("workflow_plan", [])[0]
    status = t.get("status")
    worker = t.get("worker_id")
    target = t.get("target_agent")
    print(f"Status: {status} by {worker} (Target: {target})")
    
    if status == "QUEUED" and target == "linux":
        print("SUCCESS! Task was routed to linux/github after crashing locally!")
        break
    if status in ["FAILED_TERMINAL", "DONE", "RECONCILED", "RESULT_RECEIVED"] and target == "linux":
        print("SUCCESS! Task was routed to linux/github after crashing locally!")
        break
        
    time.sleep(2)
