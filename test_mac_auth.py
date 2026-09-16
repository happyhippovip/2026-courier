import urllib.request
import json

config = json.load(open("scripts/mac_worker/config.json"))
api_key = config.get("COURIER_API_KEY")
print(f"API_KEY: {api_key}")

req = urllib.request.Request("http://127.0.0.1:8080/workers/register", method="POST")
req.add_header("Authorization", f"Bearer {api_key}")
req.add_header("Content-Type", "application/json")
payload = json.dumps({"worker_id": "MAC-01"}).encode()
try:
    urllib.request.urlopen(req, data=payload)
    print("SUCCESS")
except Exception as e:
    print(f"ERROR: {e}")
