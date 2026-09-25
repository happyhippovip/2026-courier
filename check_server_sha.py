import requests
import json

url = "http://127.0.0.1:8080/workers/register"
headers = {"Authorization": "Bearer 321606503a874d39b50f6137e3321b7f"}

for sha in ["2fe697ef2b0fbf71a5ce679bc5874e1bc4afa1a5", "a5087918d2a3db3aa873c780993241aca5d5de42", "24ab7d4b", "b459ff11249d4b164ca851c0b1c441131eb4ff6b", "unknown"]:
    payload = {
        "worker_id": "MAC-MACBOOK-PRO-VON-USER-EDEA96",
        "platform": "macos",
        "capabilities": ["mac", "bash"],
        "runtime_sha": sha
    }
    res = requests.post(url, json=payload, headers=headers)
    print(f"{sha}: {res.status_code} {res.text}")
