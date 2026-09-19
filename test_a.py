import sys, json
sys.path.insert(0, ".")
import app.cannon.web as web

# Test A: helper_exit=0 + error=null + remaining>0 => READY, not ERROR
with open("/Users/user/.courier/motor/motor.json", "r") as f:
    m = json.load(f)
m["state"] = "RUNNING"
m["error"] = None
m["start_limit"] = 1000
m["started_count"] = 10
with open("/Users/user/.courier/motor/motor.json", "w") as f:
    json.dump(m, f)

st = web.status()
print(json.dumps(st, indent=2))
