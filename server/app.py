import os, json, uuid, time, threading
from flask import Flask, request, jsonify

app = Flask(__name__)

STATE_FILE = os.environ.get("COURIER_STATE_FILE", "server/state/central_state.json")
API_KEY = os.environ.get("COURIER_API_KEY", "dev-secret-key")

def require_auth(f):
    def wrapper(*args, **kwargs):
        auth_header = request.headers.get("Authorization")
        if not auth_header or auth_header != f"Bearer {API_KEY}":
            return jsonify({"error": "Unauthorized"}), 401
        return f(*args, **kwargs)
    wrapper.__name__ = f.__name__
    return wrapper

def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r') as f:
                state = json.load(f)
                state.setdefault("goals", {})
                state.setdefault("tasks", {})
                state.setdefault("workers", {})
                return state
        except json.JSONDecodeError:
            pass
    return {"goals": {}, "tasks": {}, "workers": {}}

def save_state(state):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "healthy", "time": time.time()})

@app.route("/status", methods=["GET"])
@require_auth
def status():
    state = load_state()
    return jsonify({
        "goals": len(state["goals"]),
        "active_goals": len([g for g in state["goals"].values() if g["status"] == "ACTIVE"]),
        "tasks": len(state["tasks"]),
        "workers": len(state["workers"])
    })

@app.route("/goals", methods=["POST"])
@require_auth
def submit_goal():
    data = request.json
    goal_id = f"goal-{uuid.uuid4().hex[:8]}"
    state = load_state()
    
    goal = {
        "goal_id": goal_id,
        "goal_text": data.get("goal_text"),
        "status": "ACTIVE"
    }
    
    if "workflow_plan" in data:
        goal["workflow_plan"] = data["workflow_plan"]
        goal["current_step_index"] = 0
        for step in goal["workflow_plan"]:
            step["goal_id"] = goal_id
            step["status"] = "QUEUED"
            step["attempts"] = 0
            if "task_id" not in step:
                step["task_id"] = f"task-{uuid.uuid4().hex[:8]}"
    else:
        # Without ChiefCommander directly linked, we create a single generic task
        # Ideally, we'd dispatch a PLANNING task, but for the deterministic server router:
        task_id = f"task-{uuid.uuid4().hex[:8]}"
        goal["workflow_plan"] = [{
            "task_id": task_id,
            "goal_id": goal_id,
            "instruction": data.get("goal_text"),
            "target_agent": "linux",
            "status": "QUEUED",
            "attempts": 0
        }]
        goal["current_step_index"] = 0
        
    state["goals"][goal_id] = goal
    save_state(state)
    return jsonify({"goal_id": goal_id, "status": "ACTIVE"})

@app.route("/workers/register", methods=["POST"])
@require_auth
def register_worker():
    data = request.json
    worker_id = data.get("worker_id")
    state = load_state()
    
    state["workers"][worker_id] = {
        "worker_id": worker_id,
        "platform": data.get("platform", "unknown"),
        "capabilities": data.get("capabilities", []),
        "last_seen": time.time(),
        "available": True,
        "current_task": None,
        "cost_class": data.get("cost_class", "unknown")
    }
    
    save_state(state)
    return jsonify({"status": "REGISTERED"})

@app.route("/workers/heartbeat", methods=["POST"])
@require_auth
def heartbeat():
    data = request.json
    worker_id = data.get("worker_id")
    state = load_state()
    
    if worker_id in state["workers"]:
        state["workers"][worker_id]["last_seen"] = time.time()
        # Only mark available if not currently working
        if not state["workers"][worker_id].get("current_task"):
            state["workers"][worker_id]["available"] = True
        save_state(state)
        return jsonify({"status": "OK"})
    else:
        return jsonify({"error": "Unknown worker"}), 404

@app.route("/tasks/claim", methods=["POST"])
@require_auth
def claim_task():
    data = request.json
    worker_id = data.get("worker_id")
    state = load_state()
    
    if worker_id not in state["workers"]:
        return jsonify({"error": "Unknown worker"}), 404
        
    worker = state["workers"][worker_id]
    worker["last_seen"] = time.time()
    
    for goal_id, goal in state["goals"].items():
        if goal["status"] == "ACTIVE" and "workflow_plan" in goal:
            idx = goal.get("current_step_index", 0)
            if idx < len(goal["workflow_plan"]):
                next_task = goal["workflow_plan"][idx]
                if next_task["status"] == "QUEUED":
                    target = next_task.get("target_agent", "linux").lower()
                    
                    matched = False
                    if "github" in target and "github" in worker["capabilities"]: matched = True
                    elif "mac" in target and "macos" in worker["capabilities"]: matched = True
                    elif "windows" in target and "windows" in worker["capabilities"]: matched = True
                    elif "linux" in target and "linux" in worker["capabilities"]: matched = True
                    elif "antigravity" in target and "antigravity" in worker["capabilities"]: matched = True
                    
                    if matched:
                        next_task["status"] = "DISPATCHED"
                        next_task["worker_id"] = worker_id
                        next_task["dispatch_id"] = str(uuid.uuid4())
                        next_task["attempts"] = next_task.get("attempts", 0) + 1
                        
                        worker["current_task"] = next_task["task_id"]
                        worker["available"] = False
                        
                        state["tasks"][next_task["task_id"]] = next_task
                        # If target is github, trigger the adapter locally
                        if "github" in target:
                            import subprocess, os
                            task_file = f"server/state/dispatched_{next_task['task_id']}.json"
                            with open(task_file, 'w') as tf:
                                json.dump(next_task, tf)
                            subprocess.Popen(["python3", "scripts/github_worker_adapter.py", task_file])
                        save_state(state)
                        return jsonify({"task": next_task})
                        
    save_state(state)
    return jsonify({"task": None})

@app.route("/tasks/result", methods=["POST"])
@require_auth
def task_result():
    data = request.json
    task_id = data.get("task_id")
    worker_id = data.get("worker_id")
    state = load_state()
    
    if task_id in state["tasks"]:
        task = state["tasks"][task_id]
        
        # Duplicate protection
        if task["status"] in ["RECONCILED", "FAILED_TERMINAL", "RESULT_RECEIVED"]:
            return jsonify({"status": "IGNORED", "reason": "DUPLICATE_OR_ALREADY_PROCESSED"})
            
        if task.get("worker_id") == worker_id:
            task["status"] = "RESULT_RECEIVED"
            task["result"] = data
            
            # bounded retry logic handled by a background loop or next request, 
            # but for now we reconcile immediately based on worker success (simulating causal verification).
            # True causal verification would happen via a separate VERIFY task or explicit evidence.
            if data.get("status") == "SUCCESS":
                task["status"] = "RECONCILED"
            else:
                if task.get("attempts", 1) < 3:
                    task["status"] = "QUEUED" # Retry
                    task["worker_id"] = None
                else:
                    task["status"] = "FAILED_TERMINAL"
                
            goal_id = task["goal_id"]
            if goal_id in state["goals"]:
                goal = state["goals"][goal_id]
                # Sync status back to workflow plan
                for step in goal.get("workflow_plan", []):
                    if step.get("task_id") == task_id:
                        step["status"] = task["status"]
                        step["worker_id"] = task.get("worker_id")
                        step["attempts"] = task.get("attempts")
                if task["status"] == "RECONCILED":
                    goal["current_step_index"] = goal.get("current_step_index", 0) + 1
                    if goal["current_step_index"] >= len(goal["workflow_plan"]):
                        goal["status"] = "DONE"
                elif task["status"] == "FAILED_TERMINAL":
                    goal["status"] = "FAILED"
                    
            if worker_id in state["workers"]:
                state["workers"][worker_id]["current_task"] = None
                state["workers"][worker_id]["available"] = True
                
            save_state(state)
            return jsonify({"status": "ACK"})
            
    return jsonify({"error": "Invalid task or worker"}), 400

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
