import requests
import json
import keyring

API_URL = 'http://127.0.0.1:8081'
API_KEY = keyring.get_password('courier_worker', 'courier_api_key')
HEADERS = {'Authorization': f'Bearer {API_KEY}'}

r = requests.get(f"{API_URL}/goals/goal-7125b706", headers=HEADERS)
data = r.json()
goal = data.get('goal', {})
workflow_plan = goal.get('workflow_plan', [])

completed = sum(1 for t in workflow_plan if t['status'] == 'RECONCILED' or t['status'] == 'COMPLETED')
failed = sum(1 for t in workflow_plan if t['status'] == 'FAILED' or t['status'] == 'HUMAN_REQUIRED')
queued = sum(1 for t in workflow_plan if t['status'] == 'QUEUED')
dispatched = sum(1 for t in workflow_plan if t['status'] == 'DISPATCHED')

print(f"Goal Status: {goal.get('status')}")
print(f"Total Tasks: {len(workflow_plan)}")
print(f"Completed: {completed}")
print(f"Failed: {failed}")
print(f"Queued: {queued}")
print(f"Dispatched: {dispatched}")
for t in workflow_plan:
    print(f"- {t['task_id']}: {t['target_agent']} -> {t['status']}")
