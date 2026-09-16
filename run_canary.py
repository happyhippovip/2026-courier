import requests, json, time, sys

URL = "http://localhost:8080"
HEADERS = {"Authorization": "Bearer prod-secret-12345", "Content-Type": "application/json"}

plan = [
    {
        "task_id": "task_A2",
        "task_type": "deterministic_transform",
        "input": "nonce_A2",
        "target_agent": "github",
        "owner_scope": "TEST_A2",
        "dependencies": []
    },
    {
        "task_id": "task_B2",
        "task_type": "deterministic_transform",
        "input": "nonce_B2",
        "target_agent": "github",
        "owner_scope": "TEST_B2",
        "dependencies": ["task_A2"]
    }
]

print("Submitting A->B Goal...")
resp = requests.post(f"{URL}/goals", json={"goal_text": "Clean room A2->B2", "client_id": "test", "workflow_plan": plan}, headers=HEADERS)
goal_id = resp.json()["goal_id"]
print(f"Goal ID: {goal_id}")

while True:
    g = requests.get(f"{URL}/goals/{goal_id}", headers=HEADERS).json().get("goal")
    print(f"Goal status: {g['status']}")
    for t in g.get("workflow_plan", []):
        print(f"  Task {t['task_id']}: {t.get('status')} by {t.get('worker_id')}")
    if g["status"] in ["DONE", "FAILED", "BLOCKED"]:
        break
    time.sleep(5)
