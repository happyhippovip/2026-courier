import requests
import keyring

API_URL = 'http://127.0.0.1:8081'
API_KEY = keyring.get_password('courier_worker', 'courier_api_key')
HEADERS = {'Authorization': f'Bearer {API_KEY}'}

r = requests.get(f"{API_URL}/status", headers=HEADERS)
print(r.text)
