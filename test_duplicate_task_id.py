import urllib.request, json

def run():
    req = urllib.request.Request("http://127.0.0.1:8080/goals", method="POST")
    req.add_header("Authorization", "Bearer x")
    req.add_header("Content-Type", "application/json")
    req.data = json.dumps({
        "goal_text": "g1",
        "workflow_plan": [{"task_id": "same", "target_agent": "linux"}]
    }).encode()
    urllib.request.urlopen(req)

    req.data = json.dumps({
        "goal_text": "g2",
        "workflow_plan": [{"task_id": "same", "target_agent": "linux"}]
    }).encode()
    urllib.request.urlopen(req)

if __name__ == "__main__":
    run()
