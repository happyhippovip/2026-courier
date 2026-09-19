import urllib.request, json
url = "http://127.0.0.1:8080/goals"
headers = {"Content-Type": "application/json", "Authorization": "Bearer 321606503a874d39b50f6137e3321b7f"}
data = {
    "goal_text": "Mac Fan-Out / Fan-In Test",
    "workflow_plan": [
        {
            "task_id": "ENV_ANALYSIS",
            "target_agent": "mac",
            "instruction": "echo 'Environment analysis'"
        },
        {
            "task_id": "DOC_ANALYSIS",
            "target_agent": "mac",
            "instruction": "echo 'Doc analysis'"
        },
        {
            "task_id": "COALESCE_WRITER",
            "target_agent": "mac",
            "instruction": "echo 'Combine and write'",
            "depends_on": ["ENV_ANALYSIS", "DOC_ANALYSIS"],
            "artifact_refs": ["ENV_ANALYSIS", "DOC_ANALYSIS"]
        }
    ]
}
req = urllib.request.Request(url, headers=headers, data=json.dumps(data).encode("utf-8"))
with urllib.request.urlopen(req) as response:
    goal_id = json.loads(response.read().decode())["goal_id"]
    print("Submitted:", goal_id)
