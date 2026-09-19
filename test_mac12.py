import urllib.request, json
url = "http://127.0.0.1:8080/goals"
headers = {"Content-Type": "application/json", "Authorization": "Bearer 321606503a874d39b50f6137e3321b7f"}
data = {
    "goal_text": "Mac Website Package Readiness Test",
    "workflow_plan": [
        {
            "task_id": "READ_ASSETS",
            "target_agent": "mac",
            "instruction": "echo 'Asset discovery completed'",
            "exclusive_resources": []
        },
        {
            "task_id": "READ_CONSTRAINTS",
            "target_agent": "mac",
            "instruction": "echo 'Technical constraints discovered'",
            "exclusive_resources": []
        },
        {
            "task_id": "WRITE_WEBSITE",
            "target_agent": "mac",
            "instruction": "echo 'One writer updating website scope'",
            "depends_on": ["READ_ASSETS", "READ_CONSTRAINTS"],
            "exclusive_resources": ["WEBSITE_SCOPE"]
        },
        {
            "task_id": "TEST_WEBSITE",
            "target_agent": "mac",
            "instruction": "echo 'Tests completed successfully'",
            "depends_on": ["WRITE_WEBSITE"],
            "exclusive_resources": ["WEBSITE_SCOPE"]
        }
    ]
}
req = urllib.request.Request(url, headers=headers, data=json.dumps(data).encode("utf-8"))
with urllib.request.urlopen(req) as response:
    goal_id = json.loads(response.read().decode())["goal_id"]
    print("Submitted:", goal_id)
