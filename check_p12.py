import requests
import json
import time
import keyring

API_URL = 'http://127.0.0.1:8081'
API_KEY = keyring.get_password('courier_worker', 'courier_api_key')
HEADERS = {'Authorization': f'Bearer {API_KEY}'}

for _ in range(10):
    r = requests.get(f"{API_URL}/goals/goal-f1819558", headers=HEADERS)
    if r.status_code == 200:
        data = r.json()
        tasks = data.get('tasks', [])
        completed = sum(1 for t in tasks if t['status'] == 'COMPLETED')
        failed = sum(1 for t in tasks if t['status'] == 'FAILED')
        queued = sum(1 for t in tasks if t['status'] == 'QUEUED')
        dispatched = sum(1 for t in tasks if t['status'] == 'DISPATCHED')
        print(f"Goal: {data['goal']['status']} | Tasks: {len(tasks)} (C: {completed}, F: {failed}, Q: {queued}, D: {dispatched})")
        if completed == len(tasks):
            break
    time.sleep(2)
