import requests
import json
import keyring

API_URL = 'http://127.0.0.1:8081'
API_KEY = keyring.get_password('courier_worker', 'courier_api_key')
HEADERS = {'Authorization': f'Bearer {API_KEY}', 'Content-Type': 'application/json'}

r = requests.post(f"{API_URL}/tasks/claim", json={"worker_id": "TEST-CLAIMER-01", "capabilities": ["windows"]}, headers=HEADERS)
print(r.status_code)
print(r.text)
