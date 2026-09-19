import urllib.request, json
url = "http://127.0.0.1:8080/goals"
headers = {"Content-Type": "application/json", "Authorization": "Bearer 321606503a874d39b50f6137e3321b7f"}
data = {
    "goal_text": "Mac Context Shard Test",
    "workflow_plan": [
        {
            "task_id": "CONTEXT_SHARD_TASK",
            "target_agent": "mac",
            "instruction": "sleep 1",
            "constraints": ["must be fast"],
            "acceptance_criteria": "completed",
            "artifacts": [{"path": "/tmp/dummy", "sha256": "fake"}],
            "irrelevant_past_history": ["chat 1", "chat 2", "chat 3"]
        }
    ]
}
req = urllib.request.Request(url, headers=headers, data=json.dumps(data).encode("utf-8"))
with urllib.request.urlopen(req) as response:
    print("Submitted Goal:", json.loads(response.read().decode())["goal_id"])

# We wait 1 second and then read what the worker state holds for the current task.
import time
time.sleep(1)
