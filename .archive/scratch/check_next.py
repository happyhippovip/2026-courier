import requests
import json
import keyring

API_URL = 'http://127.0.0.1:8081'
API_KEY = keyring.get_password('courier_worker', 'courier_api_key')
HEADERS = {'Authorization': f'Bearer {API_KEY}'}

r = requests.post(f"{API_URL}/tasks/next", json={"worker_id": "WINDOWS-TEST-WORKER", "target_capability": "windows"}, headers=HEADERS)
print(r.status_code)
print(r.text)
