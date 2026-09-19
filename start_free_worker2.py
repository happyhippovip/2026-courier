import urllib.request, json, time, threading

url_reg = "http://127.0.0.1:8080/workers/register"
headers = {"Content-Type": "application/json", "Authorization": "Bearer 321606503a874d39b50f6137e3321b7f"}
data = {
    "worker_id": "FREE-MOCK-WORKER",
    "capabilities": ["linux"],
    "cost_class": "free",
    "provider": "mock",
    "platform": "mock-os"
}

req = urllib.request.Request(url_reg, headers=headers, data=json.dumps(data).encode("utf-8"))
with urllib.request.urlopen(req) as response:
    print("Registered:", response.read().decode())

url_claim = "http://127.0.0.1:8080/tasks/claim"
def poll_worker():
    while True:
        try:
            req = urllib.request.Request(url_claim, headers=headers, data=json.dumps({"worker_id": "FREE-MOCK-WORKER"}).encode("utf-8"))
            with urllib.request.urlopen(req) as response:
                pass
        except Exception:
            pass
        time.sleep(1)

t = threading.Thread(target=poll_worker, daemon=True)
t.start()

import urllib.request
url_goals = "http://127.0.0.1:8080/goals"
goal_data = {
    "goal_text": "Mac Cannon Participation Test 2",
    "workflow_plan": [
        {
            "task_id": "CHEAP_LINUX_TASK_2",
            "target_agent": "auto",
            "required_capabilities": ["linux"],
            "instruction": "echo 'Run on cheap worker'"
        }
    ]
}
req = urllib.request.Request(url_goals, headers={"Content-Type": "application/json", "Authorization": "Bearer 321606503a874d39b50f6137e3321b7f"}, data=json.dumps(goal_data).encode("utf-8"))
with urllib.request.urlopen(req) as response:
    goal_id = json.loads(response.read().decode())["goal_id"]
    print("Submitted Goal:", goal_id)

time.sleep(4) # Wait for claim
