import urllib.request, json
url = "http://127.0.0.1:8080/goals"
headers = {"Content-Type": "application/json", "Authorization": "Bearer 321606503a874d39b50f6137e3321b7f"}
data = {
    "goal_text": "Mac 10 Task Torture",
    "workflow_plan": [
        {"task_id": f"T_TORTURE_{i}", "target_agent": "mac", "instruction": f"echo 'Torture Task {i}'"}
        for i in range(10)
    ]
}
req = urllib.request.Request(url, headers=headers, data=json.dumps(data).encode("utf-8"))
with urllib.request.urlopen(req) as response:
    print(response.read().decode())
