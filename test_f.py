import sys, json
sys.path.insert(0, ".")
import app.cannon.web as web

with open("/Users/user/.courier/motor/motor.json", "r") as f:
    m = json.load(f)
m["state"] = "BLOCKED"
m["error"] = "result_not_reconciled"
with open("/Users/user/.courier/motor/motor.json", "w") as f:
    json.dump(m, f)

st = web.status()
print(f"Status: {st['state']['status']}, Error: {st['error']}")
