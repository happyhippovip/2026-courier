import urllib.request, json, os, urllib.error
try:
    req = urllib.request.Request("http://127.0.0.1:8111/goals", method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", "Bearer test-secret")
    data = {
        "goal_text": "real worker prep",
        "workflow_plan": [
            {
                "task_id": "T1",
                "target_agent": "mac",
                "instruction": "echo 'hello real worker'",
                "payload": {"command": "echo 'hello real worker'"}
            }
        ]
    }
    with urllib.request.urlopen(req, data=json.dumps(data).encode("utf-8")) as response:
        print(response.read())
except urllib.error.HTTPError as e:
    print(e.read())
