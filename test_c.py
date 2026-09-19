import sys, json
sys.path.insert(0, ".")
import app.cannon.web as web

class MockChild:
    def __init__(self, code):
        self.code = code
        self.stdin = None
    def poll(self):
        return self.code

web.CHILD = MockChild(1)

with open("/Users/user/.courier/motor/motor.json", "r") as f:
    m = json.load(f)
m["state"] = "RUNNING"
m["error"] = None
with open("/Users/user/.courier/motor/motor.json", "w") as f:
    json.dump(m, f)

st = web.status()
print(st["state"]["status"])
