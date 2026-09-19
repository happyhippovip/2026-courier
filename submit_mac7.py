import urllib.request, json
url = "http://127.0.0.1:8080/goals"
headers = {"Content-Type": "application/json", "Authorization": "Bearer 321606503a874d39b50f6137e3321b7f"}
data = {
    "goal_text": "Mac Scope Lock Test",
    "workflow_plan": [
        {
            "task_id": "WRITER_A",
            "target_agent": "mac",
            "instruction": "sleep 10",
            "exclusive_resources": ["SCOPE_X"]
        },
        {
            "task_id": "WRITER_B",
            "target_agent": "mac",
            "instruction": "echo 'Second writer'",
            "exclusive_resources": ["SCOPE_X"]
        },
        {
            "task_id": "READONLY_C",
            "target_agent": "mac",
            "instruction": "echo 'Read-only inspect'",
            "exclusive_resources": []
        },
        {
            "task_id": "WRITER_Y",
            "target_agent": "mac",
            "instruction": "echo 'Independent scope'",
            "exclusive_resources": ["SCOPE_Y"]
        }
    ]
}
req = urllib.request.Request(url, headers=headers, data=json.dumps(data).encode("utf-8"))
with urllib.request.urlopen(req) as response:
    print(response.read().decode())
