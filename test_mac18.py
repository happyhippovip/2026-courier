import urllib.request, json
url = "http://127.0.0.1:8080/goals"
headers = {"Content-Type": "application/json", "Authorization": "Bearer 321606503a874d39b50f6137e3321b7f"}
data = {
    "goal_text": "Mac Human Gate Test",
    "workflow_plan": [
        {
            "task_id": "PURCHASE_TASK",
            "target_agent": "mac",
            "requested_action": "PURCHASE",
            "instruction": "echo 'Buy a domain'"
        },
        {
            "task_id": "CRED_TASK",
            "target_agent": "mac",
            "requested_action": "CREDENTIAL_EXPANSION",
            "instruction": "echo 'Get more permissions'"
        }
    ]
}
req = urllib.request.Request(url, headers=headers, data=json.dumps(data).encode("utf-8"))
with urllib.request.urlopen(req) as response:
    goal_id = json.loads(response.read().decode())["goal_id"]
    print("Submitted:", goal_id)
