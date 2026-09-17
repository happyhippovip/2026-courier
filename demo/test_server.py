import requests

SERVER_URL = "http://192.168.178.87:8080"
API_KEY = "win-central-secret"
HEADERS = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}

goal = {
    "goal_text": "Demo: Market Research Pipeline",
    "workflow_plan": [
        {"task_id": "demo-test-1", "target_agent": "mac", "instruction": "echo Extracting data...", "mode": "NATIVE"}
    ]
}
resp = requests.post(f"{SERVER_URL}/goals", json=goal, headers=HEADERS)
print("POST STATUS:", resp.status_code)
print("POST RESPONSE:", resp.json())

goal_id = resp.json().get("goal_id")
resp = requests.get(f"{SERVER_URL}/goals/{goal_id}", headers=HEADERS)
print("GET STATUS:", resp.status_code)
print("GET RESPONSE:", resp.json())
