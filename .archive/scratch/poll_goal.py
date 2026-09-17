import urllib.request
import json
import keyring
import os
import time

API_KEY = os.environ.get('COURIER_API_KEY') or keyring.get_password('courier_worker', 'courier_api_key')
goal_id = 'goal-22a392f8'

req = urllib.request.Request(f'http://127.0.0.1:8081/goals/{goal_id}')
req.add_header('Authorization', f'Bearer {API_KEY}')

for _ in range(30):
    try:
        res = urllib.request.urlopen(req)
        data = json.loads(res.read().decode())
        goal = data['goal']
        print(f"Goal status: {goal['status']}")
        if goal['status'] in ('DONE', 'BLOCKED'):
            for step in goal.get('workflow_plan', []):
                print(f"Task {step.get('task_id')} - Agent: {step.get('target_agent')} - Status: {step.get('status')}")
            break
        time.sleep(5)
    except Exception as e:
        print(e)
        time.sleep(5)
