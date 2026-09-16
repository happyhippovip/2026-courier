import requests, json, time, sys

URL = "http://localhost:8080"
HEADERS = {"Authorization": "Bearer prod-secret-12345", "Content-Type": "application/json"}

goal_id = "goal-10f2ce1d"
for i in range(20):
    g = requests.get(f"{URL}/goals/{goal_id}", headers=HEADERS).json().get("goal")
    print(f"Goal status: {g['status']}")
    for t in g.get("workflow_plan", []):
        print(f"  Task {t['task_id']}: {t.get('status')} by {t.get('worker_id')}")
    if g["status"] in ["DONE", "FAILED", "BLOCKED"]:
        break
    time.sleep(5)
