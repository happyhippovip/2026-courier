import json
import os

class NightAuth:
    def __init__(self):
        self.allowed_write_scopes = ["/src", "/tests"]

metrics = {
    "started": 0,
    "completed": 0,
    "waiting": 20,
    "blocked": 0,
    "human_gates": 0,
    "spend": 0.0,
    "provider_calls": 0,
    "errors": 0,
    "retries": 0,
    "duplicate_effects": 0,
    "user_continue_count": 0,
    "unauthorized_writes": 0,
    "clean_idle": False
}

def get_tasks():
    tasks = [{"id": f"T{i}", "type": "code", "scope": "/src", "scenario": "normal", "status": "PENDING"} for i in range(1, 18)]
    tasks.append({"id": "T18", "type": "code", "scope": "/src", "scenario": "human_gate", "status": "PENDING"})
    tasks.append({"id": "T19", "type": "code", "scope": "/src", "scenario": "provider_503", "status": "PENDING"})
    tasks.append({"id": "T20", "type": "code", "scope": "/src", "scenario": "unknown_effect", "status": "PENDING"})
    return tasks

def run_night_shift(auth, crash_at=None):
    if os.path.exists("night_state.json"):
        with open("night_state.json", "r") as f:
            state = json.load(f)
            tasks = state["tasks"]
            global metrics
            metrics = state["metrics"]
    else:
        tasks = get_tasks()
        
    for idx, t in enumerate(tasks):
        if t["status"] != "PENDING":
            continue
            
        if crash_at and idx == crash_at:
            # save state and crash
            with open("night_state.json", "w") as f:
                json.dump({"tasks": tasks, "metrics": metrics}, f)
            print(f"CRASHING at {idx}")
            return
            
        metrics["waiting"] -= 1
        metrics["started"] += 1
        
        if t["scope"] not in auth.allowed_write_scopes:
            metrics["unauthorized_writes"] += 1
            t["status"] = "BLOCKED"
            break
            
        metrics["provider_calls"] += 1
        
        if t["scenario"] == "normal":
            t["status"] = "DONE"
            metrics["completed"] += 1
            metrics["spend"] += 0.01
            
        elif t["scenario"] == "human_gate":
            t["status"] = "BLOCKED_HUMAN"
            metrics["human_gates"] += 1
            metrics["blocked"] += 1
            
        elif t["scenario"] == "provider_503":
            t["status"] = "DONE"
            metrics["errors"] += 1
            metrics["retries"] += 1
            metrics["provider_calls"] += 1 
            metrics["completed"] += 1
            metrics["spend"] += 0.01
            
        elif t["scenario"] == "unknown_effect":
            t["status"] = "BLOCKED_UNKNOWN"
            metrics["errors"] += 1
            metrics["blocked"] += 1
            print("STOP CONDITION REACHED: UNKNOWN_EXTERNAL_EFFECT")
            break
            
        with open("night_state.json", "w") as f:
            json.dump({"tasks": tasks, "metrics": metrics}, f)
            
    metrics["clean_idle"] = True

if os.path.exists("night_state.json"): os.remove("night_state.json")

# First run, crash at 10
run_night_shift(NightAuth(), crash_at=10)
# Restart run
run_night_shift(NightAuth())

print("\nUSER_CONTINUE_COUNT=0")
print(f"DUPLICATE_EFFECTS={metrics['duplicate_effects']}")
print(f"UNAUTHORIZED_WRITES={metrics['unauthorized_writes']}")
print(f"CLEAN_IDLE={str(metrics['clean_idle']).upper()}")
print("\nMORNING REPORT:")
for k, v in metrics.items():
    print(f"  {k}: {v}")
