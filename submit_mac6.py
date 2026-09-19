import urllib.request, json
url = "http://127.0.0.1:8080/goals"
headers = {"Content-Type": "application/json", "Authorization": "Bearer 321606503a874d39b50f6137e3321b7f"}
data = {
    "goal_text": "Mac Circuit Breaker Parallel Test",
    "workflow_plan": [
        {
            "task_id": "FAIL_TASK_6",
            "target_agent": "mac",
            "instruction": "echo 'This will fail'",
            "artifacts": [{"path": "/tmp/nonexistent6.txt", "sha256": "fake"}]
        },
        {
            "task_id": "SAFE_TASK_6",
            "target_agent": "mac",
            "instruction": "echo 'This is safe independent work'"
        }
    ]
}
req = urllib.request.Request(url, headers=headers, data=json.dumps(data).encode("utf-8"))
with urllib.request.urlopen(req) as response:
    print(response.read().decode())
