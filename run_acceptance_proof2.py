import requests
import time
import uuid

SERVER_URL = "http://127.0.0.1:8080"
API_KEY = "321606503a874d39b50f6137e3321b7f"

def submit_goal():
    goal_id = f"ACCEPTANCE-PROOF-{uuid.uuid4().hex[:8]}"
    tasks = []
    for i in range(12):
        tasks.append({
            "task_id": f"task-proof-{i}-{goal_id}",
            "target_agent": "mac",
            "mode": "NATIVE",
            "instruction": "sleep 1",
            "artifacts": []
        })

    payload = {
        "goal_id": goal_id,
        "goal_text": "Physical Acceptance Proof",
        "workflow_plan": tasks,
        "terminal": True
    }
    
    res = requests.post(f"{SERVER_URL}/goals", json=payload, headers={"Authorization": f"Bearer {API_KEY}"})
    res.raise_for_status()
    print("Goal submitted: " + res.json()["goal_id"])
    return res.json()["goal_id"]

def wait_for_done(goal_id):
    start = time.time()
    while time.time() - start < 180:
        res = requests.get(f"{SERVER_URL}/goals/{goal_id}", headers={"Authorization": f"Bearer {API_KEY}"})
        if res.status_code == 200:
            data = res.json()
            if data.get("goal", {}).get("status") == "DONE":
                print(f"Goal {goal_id} reached DONE state!")
                return True
        time.sleep(1)
    print("Goal timed out!")
    return False

if __name__ == "__main__":
    gid = submit_goal()
    if wait_for_done(gid):
        print("ACCEPTANCE PROOF SUCCESS")
    else:
        print("ACCEPTANCE PROOF FAILED")
