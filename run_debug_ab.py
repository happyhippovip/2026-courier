import subprocess
with open("tests/test_ab_reconcile_unlock.py", "r") as f:
    c = f.read()

c = c.replace('assert http.post("/tasks/result", headers=auth(), json=result).status_code == 200', 'res = http.post("/tasks/result", headers=auth(), json=result)\n    print("RESPONSE:", res.get_json())\n    assert res.status_code == 200')

with open("tests/test_ab_reconcile_unlock.py", "w") as f:
    f.write(c)

print(subprocess.run(["python3", "-m", "pytest", "tests/test_ab_reconcile_unlock.py", "-s", "-v"], capture_output=True, text=True).stdout)
