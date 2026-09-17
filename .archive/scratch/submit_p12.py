import requests
import json
import os
import uuid

API_URL = 'http://127.0.0.1:8081'
API_KEY = 'test-key-123'
HEADERS = {'Authorization': f'Bearer {API_KEY}', 'Content-Type': 'application/json'}

workflow_plan = []
for i in range(1, 11):
    agent = 'windows' if i <= 5 else 'mac'
    # Use powershell for Windows, bash for Mac (Wait, Mac native task uses echo or whatever)
    # The worker daemon executes 'instruction' directly.
    # To avoid missing artifacts error from the worker, we explicitly pass 'artifacts': []
    workflow_plan.append({
        'task_id': f'task-p12-{i}',
        'instruction': f'echo \"Hello from {agent} task {i}\"',
        'target_agent': agent,
        'artifacts': []
    })

goal_payload = {
    'goal_text': 'P12 Final Physical Release Run',
    'terminal': True,
    'workflow_plan': workflow_plan
}

r = requests.post(f"{API_URL}/goals", json=goal_payload, headers=HEADERS)
print("Response:", r.status_code)
print(r.text)
