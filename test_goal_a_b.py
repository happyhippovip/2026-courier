import requests
import json
import time

URL = "http://localhost:8080"
HEADERS = {"Authorization": "Bearer prod-secret-12345"}

def run():
    print("Submitting Goal...")
    resp = requests.post(f"{URL}/goals", json={"goal_text": "Clean room test A->B", "client_id": "clean-room-test", "cost_limit": 10}, headers=HEADERS)
    if resp.status_code != 200:
        print("Failed to submit goal:", resp.text)
        return
    goal = resp.json()["goal"]
    goal_id = goal["goal_id"]
    print(f"Goal ID: {goal_id}")
    
    # Check status
    while True:
        resp = requests.get(f"{URL}/goals", headers=HEADERS)
        goals = resp.json()
        if goal_id in goals:
            g = goals[goal_id]
            print(f"Goal status: {g['status']}")
            for t in g.get("workflow_plan", []):
                print(f"  Task {t['task_id']}: {t.get('status')} by {t.get('worker_id')}")
            if g["status"] in ["DONE", "FAILED", "BLOCKED"]:
                break
        time.sleep(5)
        
run()
