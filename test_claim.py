import requests
import time
start = time.time()
print("Claiming task...")
res = requests.post("http://localhost:8080/tasks/claim", json={"worker_id": "mac-worker-1"})
print(f"Result in {time.time() - start:.2f}s: {res.json()}")
