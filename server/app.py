import os, json, uuid, time
from flask import Flask, request, jsonify

from scripts.integration_contract import ContractError, prepare_task, validate_durable_result

app = Flask(__name__)

STATE_FILE = os.environ.get("COURIER_STATE_FILE", "server/state/central_state.json")
API_KEY = os.environ.get("COURIER_API_KEY", "dev-secret-key")
INSECURE_API_KEYS = {"", "dev-secret-key", "your_secure_api_key_here"}

def require_auth(f):
    def wrapper(*args, **kwargs):
        if API_KEY in INSECURE_API_KEYS:
            return jsonify({"error": "Courier API key is not configured"}), 503
        auth_header = request.headers.get("Authorization")
        if not auth_header or auth_header != f"Bearer {API_KEY}":
            return jsonify({"error": "Unauthorized"}), 401
        return f(*args, **kwargs)
    wrapper.__name__ = f.__name__
    return wrapper

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r') as f:
            state = json.load(f)
            state.setdefault("goals", {})
            state.setdefault("tasks", {})
            state.setdefault("workers", {})
            return state
    return {"goals": {}, "tasks": {}, "workers": {}}

def save_state(state):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    temp_path = f"{STATE_FILE}.tmp"
    with open(temp_path, 'w') as f:
        json.dump(state, f, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(temp_path, STATE_FILE)

@app.route("/goals", methods=["POST"])
@require_auth
def submit_goal():
    data = request.get_json(silent=True) or {}
    if not isinstance(data.get("goal_text"), str) or not data["goal_text"].strip():
        return jsonify({"error": "goal_text is required"}), 400
    goal_id = f"goal-{uuid.uuid4().hex[:8]}"
    state = load_state()
    
    goal = {
        "goal_id": goal_id,
        "goal_text": data.get("goal_text"),
        "status": "ACTIVE"
    }
    
    # If the user explicitly provided a workflow plan (for canary)
    if "workflow_plan" in data:
        goal["workflow_plan"] = data["workflow_plan"]
        goal["current_step_index"] = 0
        for step in goal["workflow_plan"]:
            step["goal_id"] = goal_id
            step["status"] = "QUEUED"
            if "task_id" not in step:
                step["task_id"] = f"task-{uuid.uuid4().hex[:8]}"
    else:
        # Here we'd call ChiefCommander to formulate a plan
        # but for this server boundary simulation, we'll just queue a generic task if none provided.
        pass
        
    state["goals"][goal_id] = goal
    save_state(state)
    return jsonify({"goal_id": goal_id, "status": "ACTIVE"})

@app.route("/workers/register", methods=["POST"])
@require_auth
def register_worker():
    data = request.get_json(silent=True) or {}
    worker_id = data.get("worker_id")
    if not isinstance(worker_id, str) or not worker_id:
        return jsonify({"error": "worker_id is required"}), 400
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
    data = request.get_json(silent=True) or {}
    worker_id = data.get("worker_id")
    state = load_state()
    
    if worker_id in state["workers"]:
        state["workers"][worker_id]["last_seen"] = time.time()
        state["workers"][worker_id]["available"] = True
        save_state(state)
        return jsonify({"status": "OK"})
    else:
        return jsonify({"error": "Unknown worker"}), 404

@app.route("/tasks/claim", methods=["POST"])
@require_auth
def claim_task():
    data = request.get_json(silent=True) or {}
    worker_id = data.get("worker_id")
    state = load_state()
    
    if worker_id not in state["workers"]:
        return jsonify({"error": "Unknown worker"}), 404
        
    worker = state["workers"][worker_id]
    worker["last_seen"] = time.time()
    
    # Find next eligible task
    for goal_id, goal in state["goals"].items():
        if goal["status"] == "ACTIVE" and "workflow_plan" in goal:
            idx = goal.get("current_step_index", 0)
            if idx < len(goal["workflow_plan"]):
                next_task = goal["workflow_plan"][idx]
                if next_task["status"] == "QUEUED":
                    # Check routing capability
                    target = next_task.get("target_agent", "linux")
                    
                    # Routing logic
                    matched = False
                    if target == "github" and "github" in worker["capabilities"]:
                        matched = True
                    elif target == "mac" and "macos" in worker["capabilities"]:
                        matched = True
                    elif target == "windows" and "windows" in worker["capabilities"]:
                        matched = True
                    elif target == "linux" and "linux" in worker["capabilities"]:
                        matched = True
                    
                    if matched:
                        next_task["worker_id"] = worker_id
                        next_task["target_capability"] = target
                        try:
                            next_task = prepare_task(next_task)
                        except ContractError as exc:
                            return jsonify({"error": str(exc)}), 400
                        next_task["status"] = "DISPATCHED"
                        goal["workflow_plan"][idx] = next_task
                        
                        worker["current_task"] = next_task["task_id"]
                        worker["available"] = False
                        
                        state["tasks"][next_task["task_id"]] = next_task
                        save_state(state)
                        return jsonify({"task": next_task})
                        
    save_state(state)
    return jsonify({"task": None})

@app.route("/tasks/result", methods=["POST"])
@require_auth
def task_result():
    data = request.get_json(silent=True) or {}
    task_id = data.get("task_id")
    worker_id = data.get("worker_id")
    state = load_state()
    
    if task_id in state["tasks"]:
        task = state["tasks"][task_id]
        if task.get("worker_id") == worker_id:
            if task.get("status") == "RESULT_RECEIVED" and task.get("result", {}).get("result_id") == data.get("result_id"):
                return jsonify({"status": "ACK_DUPLICATE"})
            if task.get("status") != "DISPATCHED":
                return jsonify({"error": "Task is not awaiting a result"}), 409
            try:
                durable_result = validate_durable_result(task, data)
            except ContractError as exc:
                return jsonify({"error": str(exc)}), 400
            task["status"] = "RESULT_RECEIVED"
            task["result"] = durable_result

            if worker_id in state["workers"]:
                state["workers"][worker_id]["current_task"] = None
                state["workers"][worker_id]["available"] = True

            if durable_result["status"] == "FAILED":
                task["status"] = "FAILED_TERMINAL"
                state["goals"][task["goal_id"]]["status"] = "BLOCKED"

            save_state(state)
            return jsonify({"status": "ACK_RESULT_RECEIVED"})
            
    return jsonify({"error": "Invalid task or worker"}), 400


@app.route("/tasks/verify", methods=["POST"])
@require_auth
def verify_task_result():
    data = request.get_json(silent=True) or {}
    task_id = data.get("task_id")
    state = load_state()
    task = state["tasks"].get(task_id)
    if not task:
        return jsonify({"error": "Unknown task"}), 404
    if task.get("status") == "RECONCILED":
        verification = task.get("verification", {})
        if verification.get("result_id") == data.get("result_id"):
            return jsonify({"status": "ACK_DUPLICATE"})
        return jsonify({"error": "Task already reconciled"}), 409
    if task.get("status") != "RESULT_RECEIVED":
        return jsonify({"error": "Task has no result awaiting verification"}), 409

    verifier_id = data.get("verifier_id")
    if not isinstance(verifier_id, str) or not verifier_id or verifier_id == task.get("worker_id"):
        return jsonify({"error": "independent verifier_id is required"}), 400
    result = task["result"]
    if data.get("result_id") != result.get("result_id"):
        return jsonify({"error": "result_id mismatch"}), 400
    if data.get("artifacts") != result.get("artifacts"):
        return jsonify({"error": "artifact evidence mismatch"}), 400
    verdict = data.get("verdict")
    if verdict not in {"PASS", "FAIL"}:
        return jsonify({"error": "verdict must be PASS or FAIL"}), 400

    task["verification"] = {
        "verifier_id": verifier_id,
        "result_id": result["result_id"],
        "verdict": verdict,
        "artifacts": result["artifacts"],
    }
    goal = state["goals"][task["goal_id"]]
    if verdict == "PASS":
        task["status"] = "RECONCILED"
        goal["current_step_index"] = goal.get("current_step_index", 0) + 1
        if goal["current_step_index"] >= len(goal["workflow_plan"]):
            goal["status"] = "DONE"
    else:
        task["status"] = "FAILED_VERIFICATION"
        goal["status"] = "BLOCKED"
    save_state(state)
    return jsonify({"status": task["status"]})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
