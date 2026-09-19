import urllib.request, json
url = "http://127.0.0.1:8080/goals"
headers = {"Content-Type": "application/json", "Authorization": "Bearer 321606503a874d39b50f6137e3321b7f"}
data = {
    "goal_text": "Mac Duplicate Work Test",
    "workflow_plan": [
        {
            "task_id": "REUSE_TASK",
            "target_agent": "mac",
            "instruction": "echo 'This will run'"
        }
    ]
}
req = urllib.request.Request(url, headers=headers, data=json.dumps(data).encode("utf-8"))
with urllib.request.urlopen(req) as response:
    goal_id1 = json.loads(response.read().decode())["goal_id"]

print("Submitted:", goal_id1)
import time; time.sleep(2)
