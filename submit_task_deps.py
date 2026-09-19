import urllib.request, json
url = "http://127.0.0.1:8080/goals"
headers = {"Content-Type": "application/json", "Authorization": "Bearer 321606503a874d39b50f6137e3321b7f"}
data = {
    "goal_text": "Mac Dependency Test",
    "workflow_plan": [
        {"task_id": "MACA", "target_agent": "mac", "instruction": "echo 'Mac A'"},
        {"task_id": "MACB", "target_agent": "mac", "instruction": "echo 'Mac B'", "depends_on": ["MACA"]}
    ]
}
req = urllib.request.Request(url, headers=headers, data=json.dumps(data).encode("utf-8"))
with urllib.request.urlopen(req) as response:
    print(response.read().decode())
