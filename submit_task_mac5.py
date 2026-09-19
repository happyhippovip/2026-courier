import urllib.request, json
url = "http://127.0.0.1:8080/goals"
headers = {"Content-Type": "application/json", "Authorization": "Bearer 321606503a874d39b50f6137e3321b7f"}
data = {
    "goal_text": "Mac Night Queue Test",
    "workflow_plan": [
        {"task_id": "A", "target_agent": "mac", "instruction": "echo 'Read-only analysis A'"},
        {"task_id": "B", "target_agent": "mac", "instruction": "echo 'Independent doc analysis B'"},
        {"task_id": "C", "target_agent": "mac", "instruction": "echo 'Depends on A'", "depends_on": ["A"]}
    ]
}
req = urllib.request.Request(url, headers=headers, data=json.dumps(data).encode("utf-8"))
with urllib.request.urlopen(req) as response:
    print(response.read().decode())
