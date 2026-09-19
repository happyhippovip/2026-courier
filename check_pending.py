import urllib.request
import json
req = urllib.request.Request("http://127.0.0.1:8111/tasks/pending_verification", method="GET")
req.add_header("Authorization", "Bearer verifier-secret")
resp = urllib.request.urlopen(req)
print(resp.read().decode())
