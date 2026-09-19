import urllib.request, json, time, threading
url = "http://127.0.0.1:8080/tasks/claim"
headers = {"Content-Type": "application/json"}
data = {
    "worker_id": "FREE-MOCK-WORKER",
    "capabilities": ["linux"],
    "cost_class": "free",
    "provider": "mock",
    "platform": "mock-os"
}

def poll_worker():
    while True:
        try:
            req = urllib.request.Request(url, headers=headers, data=json.dumps(data).encode("utf-8"))
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
    "goal_text": "Mac Cannon Participation Test",
    "workflow_plan": [
        {
            "task_id": "CHEAP_LINUX_TASK",
            "target_agent": "auto",
            "required_capabilities": ["linux"],
            "instruction": "echo 'Run on cheap worker'"
        }
    ]
}
req = urllib.request.Request(url_goals, headers={"Content-Type": "application/json", "Authorization": "Bearer 321606503a874d39b50f6137e3321b7f"}, data=json.dumps(goal_data).encode("utf-8"))
with urllib.request.urlopen(req) as response:
    goal_id = json.loads(response.read().decode())["goal_id"]
    print("Submitted:", goal_id)

time.sleep(3) # Wait for claim
