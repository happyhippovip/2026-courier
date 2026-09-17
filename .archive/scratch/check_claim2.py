import requests
import json
import keyring

API_URL = 'http://127.0.0.1:8081'
API_KEY = keyring.get_password('courier_worker', 'courier_api_key')
HEADERS = {'Authorization': f'Bearer {API_KEY}', 'Content-Type': 'application/json'}

worker_id = "TEST-CLAIMER-01"
r_reg = requests.post(f"{API_URL}/workers/register", json={"worker_id": worker_id, "platform": "windows", "capabilities": ["windows"], "cost_class": "low"}, headers=HEADERS)
print("Reg:", r_reg.status_code)

r = requests.post(f"{API_URL}/tasks/claim", json={"worker_id": worker_id}, headers=HEADERS)
print(r.status_code)
print(r.text)
