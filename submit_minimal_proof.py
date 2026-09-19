import urllib.request
import json
import keyring
import os

API_KEY = os.environ.get('COURIER_API_KEY') or keyring.get_password('courier_worker', 'courier_api_key') or "test_key"

data = {
    'goal_text': 'Minimal ledger proof',
    'terminal': True,
    'workflow_plan': [{
        'instruction': 'echo "Minimal Proof" > minimal_proof.txt',
        'target_agent': 'linux',
        'artifacts': ['minimal_proof.txt']
    }]
}

req = urllib.request.Request('http://127.0.0.1:8080/goals', method='POST')
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
