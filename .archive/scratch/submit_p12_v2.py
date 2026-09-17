import requests
import json
import os
import uuid
import keyring

API_URL = 'http://127.0.0.1:8081'
API_KEY = keyring.get_password('courier_worker', 'courier_api_key') or os.environ.get('COURIER_API_KEY')
HEADERS = {'Authorization': f'Bearer {API_KEY}', 'Content-Type': 'application/json'}

workflow_plan = []
for i in range(1, 11):
    agent = 'windows' if i <= 5 else 'mac'
    task_id = f'task-p12-{i}-v2'
    if agent == 'windows':
        instruction = f'echo \"Hello from {agent} task {i}\" > courier_canary_{task_id}.txt'
    else:
        instruction = f'echo \"Hello from {agent} task {i}\" > courier_canary_{task_id}.txt'
        
    workflow_plan.append({
        'task_id': task_id,
        'instruction': instruction,
        'target_agent': agent,
        'artifacts': [f'courier_canary_{task_id}.txt']
    })

goal_payload = {
    'goal_text': 'P12 Final Physical Release Run V2',
    'terminal': True,
    'workflow_plan': workflow_plan
}

r = requests.post(f"{API_URL}/goals", json=goal_payload, headers=HEADERS)
print("Response:", r.status_code)
print(r.text)
