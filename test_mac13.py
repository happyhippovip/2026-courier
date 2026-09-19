import urllib.request, json
url = "http://127.0.0.1:8080/goals"
headers = {"Content-Type": "application/json", "Authorization": "Bearer 321606503a874d39b50f6137e3321b7f"}
data = {
    "goal_text": "Mac Provider-Neutral Capability Test",
    "workflow_plan": [
        {
            "task_id": "WP_REPO",
            "target_agent": "auto",
            "required_capabilities": ["antigravity"],
            "instruction": "echo 'Repository verstehen'"
        },
        {
            "task_id": "WP_DOCS",
            "target_agent": "auto",
            "required_capabilities": ["antigravity"],
            "instruction": "echo 'Documentation'"
        },
        {
            "task_id": "WP_RESEARCH",
            "target_agent": "auto",
            "required_capabilities": ["antigravity"],
            "instruction": "echo 'Deep Research preparation'"
        },
        {
            "task_id": "WP_CI",
            "target_agent": "auto",
            "required_capabilities": ["antigravity"],
            "instruction": "echo 'CI/Test analysis preparation'"
        }
    ]
}
req = urllib.request.Request(url, headers=headers, data=json.dumps(data).encode("utf-8"))
with urllib.request.urlopen(req) as response:
    goal_id = json.loads(response.read().decode())["goal_id"]
    print("Submitted:", goal_id)
