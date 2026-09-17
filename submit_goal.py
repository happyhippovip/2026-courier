import urllib.request
import json
import keyring
import os

API_KEY = os.environ.get('COURIER_API_KEY') or keyring.get_password('courier_worker', 'courier_api_key')

workflow_plan = []
for i in range(5):
    workflow_plan.append({
        'instruction': f'echo \"Windows Task {i}\" > windows_task_{i}.txt',
        'target_agent': 'windows',
        'artifacts': [f'windows_task_{i}.txt']
    })
    workflow_plan.append({
        'instruction': f'echo \"Mac Task {i}\" > mac_task_{i}.txt',
        'target_agent': 'mac',
        'artifacts': [f'mac_task_{i}.txt']
    })

data = {
    'goal_text': 'Zero-touch autonomy test with 10 tasks',
    'terminal': True,
    'workflow_plan': workflow_plan
}

req = urllib.request.Request('http://127.0.0.1:8081/goals', method='POST')
req.add_header('Authorization', f'Bearer {API_KEY}')
req.add_header('Content-Type', 'application/json')

try:
    res = urllib.request.urlopen(req, data=json.dumps(data).encode('utf-8'))
    print(res.read().decode())
except Exception as e:
    print(e)
    try:
        print(e.read().decode())
    except:
        pass
