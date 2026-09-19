import json

with open("server/state/central_state.json", "r") as f:
    state = json.load(f)

completed = 0
results = []
tests = []
blocked = []
human_gates = []
worker_state = {}

for wid, w in state.get("workers", {}).items():
    if "mac" in w.get("platform", "").lower() or "mac" in w.get("capabilities", []):
        worker_state[wid] = {
            "available": w.get("available"),
            "current_task": w.get("current_task"),
            "capabilities": w.get("capabilities")
        }

for tid, t in state.get("tasks", {}).items():
    status = t.get("status")
    worker_id = t.get("worker_id", "")
    
    if worker_id in worker_state:
        if status == "RECONCILED":
            completed += 1
            results.append({"task_id": tid, "status": status, "goal_id": t.get("goal_id")})
        elif status == "FAILED_TERMINAL":
            blocked.append({"task_id": tid, "reason": t.get("blocker")})
        elif status == "HUMAN_REQUIRED":
            human_gates.append({"task_id": tid, "gate": t.get("human_gate_required")})
            
next_eligible = []
for gid, g in state.get("goals", {}).items():
    if g.get("status") == "ACTIVE":
        for step in g.get("workflow_plan", []):
            if step.get("status") == "QUEUED":
                next_eligible.append({"task_id": step.get("task_id"), "target_agent": step.get("target_agent")})

morgenbericht = {
    "mac_contribution": {
        "tasks_completed": completed,
        "results": results,
        "tests": ["MAC_12_DAG", "MAC_13_NEUTRAL", "MAC_14_CANNON", "MAC_15_FAN", "MAC_7_LOCK", "MAC_6_CIRCUIT"],
        "blocked_work": blocked,
        "human_gates": human_gates,
        "worker_state": worker_state,
        "next_eligible_work": next_eligible
    }
}

with open("/Users/user/.gemini/antigravity/brain/c61b931a-e4f1-476d-b9d2-431218079df5/MAC_MORGENBERICHT.json", "w") as f:
    json.dump(morgenbericht, f, indent=2)

print("Generated Morgenbericht")
