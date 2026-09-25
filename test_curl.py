import subprocess
import os
import time
import urllib.request
env = os.environ.copy()
env["COURIER_API_KEY"] = "test-key-12345"
env["COURIER_VERIFIER_API_KEY"] = "test-key-12345"
env["PYTHONPATH"] = "."
p = subprocess.Popen(["python3", "server/app.py"], env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
time.sleep(2)
try:
    req = urllib.request.Request("http://127.0.0.1:8080/goals", headers={"Authorization": "Bearer test-key-12345", "Content-Type": "application/json"})
    res = urllib.request.urlopen(req)
    print(res.status)
except Exception as e:
    print("ERROR:", e)
p.kill()
print(p.communicate()[0])
