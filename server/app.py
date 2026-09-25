import os, json, uuid, time, threading
from functools import wraps
from flask import Flask, request, jsonify

from scripts.integration_contract import ContractError, prepare_task, validate_durable_result
from scripts.run_chief_commander import ChiefCommander

app = Flask(__name__)

STATE_FILE = os.environ.get("COURIER_STATE_FILE", "server/state/central_state.json")
API_KEY = os.environ.get("COURIER_API_KEY")
if not API_KEY:
    raise SystemExit("Missing COURIER_API_KEY environment variable")
VERIFIER_API_KEY = os.environ.get("COURIER_VERIFIER_API_KEY")
if not VERIFIER_API_KEY:
    raise SystemExit("Missing COURIER_VERIFIER_API_KEY environment variable")
INSECURE_API_KEYS = {"", "dev-secret-key", "your_secure_api_key_here"}
STATE_LOCK = threading.RLock()

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


def require_verifier_auth(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if (
            VERIFIER_API_KEY in INSECURE_API_KEYS
            or VERIFIER_API_KEY == API_KEY
        ):
            return jsonify({"error": "Courier verifier authority is not configured"}), 503
        if request.headers.get("Authorization") != f"Bearer {VERIFIER_API_KEY}":
            return jsonify({"error": "Verifier authority required"}), 401
        return f(*args, **kwargs)
    return wrapper


def serialize_state_mutation(f):
    """Keep each JSON-state read/check/write transition atomic in this process."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        with STATE_LOCK:
            return f(*args, **kwargs)
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
@serialize_state_mutation
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
        try:
            _, planned_steps = ChiefCommander().formulate_workflow_plan(
                data["goal_text"], idea_type="GOAL"
            )
        except Exception as exc:
            return jsonify({"error": f"planner failed: {exc}"}), 503
        if not isinstance(planned_steps, list) or not planned_steps:
            return jsonify({"error": "planner returned no actionable tasks"}), 503
        goal["workflow_plan"] = []
        goal["current_step_index"] = 0
        for step in planned_steps:
            target_agent = str(step.get("target_agent", "linux")).lower()
            if "github" in target_agent:
                target_agent = "github"
            elif "windows" in target_agent or "codex" in target_agent:
                target_agent = "windows"
            elif "mac" in target_agent or "antigravity" in target_agent or "gemini" in target_agent:
                target_agent = "mac"
            else:
                target_agent = "linux"
            goal["workflow_plan"].append({
                "task_id": step.get("task_id", f"task-{uuid.uuid4().hex[:8]}"),
                "goal_id": goal_id,
                "instruction": step.get("instruction", "Next bounded step"),
                "target_agent": target_agent,
                "status": "QUEUED",
                "attempts": 0,
            })
        
    state["goals"][goal_id] = goal
    save_state(state)
    return jsonify({"goal_id": goal_id, "status": "ACTIVE"})


@app.route("/goals/<goal_id>", methods=["GET"])
@require_auth
def get_goal(goal_id):
    state = load_state()
    goal = state["goals"].get(goal_id)
    if not goal:
        return jsonify({"error": "Unknown goal"}), 404
    tasks = [task for task in state["tasks"].values() if task.get("goal_id") == goal_id]
    return jsonify({"goal": goal, "tasks": tasks})

@app.route("/workers", methods=["GET"])
@require_auth
def list_workers():
    state = load_state()
    # Mask API keys if they exist, but they shouldn't be in worker definitions
    return jsonify(state.get("workers", {}))

@app.route("/walls", methods=["GET"])
@require_auth
def list_walls():
    state = load_state()
    walls = {}
    for gid, goal in state.get("goals", {}).items():
        if goal.get("status") == "BLOCKED":
            walls[gid] = goal
    return jsonify(walls)

@app.route("/workers/register", methods=["POST"])
@require_auth
@serialize_state_mutation
def register_worker():
    data = request.get_json(silent=True) or {}
    worker_id = data.get("worker_id")
    if not isinstance(worker_id, str) or not worker_id:
        return jsonify({"error": "worker_id is required"}), 400
    state = load_state()
    
    existing = state["workers"].get(worker_id, {})
    server_task = existing.get("current_task")
    worker_task = data.get("current_task")
    
    if "current_task" in data:
        current_task = worker_task
        if server_task and worker_task != server_task:
            task = state.get("tasks", {}).get(server_task)
            if task:
                task["status"] = "HUMAN_REQUIRED"
                task["recovery_reason"] = "WORKER_RESTARTED_AND_LOST_STATE"
            for goal in state.get("goals", {}).values():
                if goal.get("status") == "ACTIVE" and "workflow_plan" in goal:
                    for step in goal["workflow_plan"]:
                        if step.get("task_id") == server_task:
                            step["status"] = "HUMAN_REQUIRED"
                            step["recovery_reason"] = "WORKER_RESTARTED_AND_LOST_STATE"
                            goal["status"] = "BLOCKED"
    else:
        current_task = server_task

    state["workers"][worker_id] = {
        "worker_id": worker_id,
        "platform": data.get("platform", "unknown"),
        "capabilities": data.get("capabilities", []),
        "last_seen": time.time(),
        "available": current_task is None,
        "current_task": current_task,
        "cost_class": data.get("cost_class", "unknown")
    }
    
    save_state(state)
    return jsonify({"status": "REGISTERED"})

@app.route("/workers/unregister", methods=["POST"])
@require_auth
@serialize_state_mutation
def unregister_worker():
    data = request.get_json(silent=True) or {}
    worker_id = data.get("worker_id")
    state = load_state()
    
    if worker_id in state["workers"]:
        state["workers"][worker_id]["available"] = False
        save_state(state)
        return jsonify({"status": "UNREGISTERED"})
    return jsonify({"error": "Unknown worker"}), 404

@app.route("/workers/heartbeat", methods=["POST"])
@require_auth
@serialize_state_mutation
def heartbeat():
    data = request.get_json(silent=True) or {}
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
@serialize_state_mutation
def claim_task():
    data = request.get_json(silent=True) or {}
    worker_id = data.get("worker_id")
    state = load_state()
    
    if worker_id not in state["workers"]:
        return jsonify({"error": "Unknown worker"}), 404
        
    worker = state["workers"][worker_id]
    worker["last_seen"] = time.time()
    if worker.get("current_task") or not worker.get("available", False):
        save_state(state)
        return jsonify({"task": None, "reason": "WORKER_BUSY"})
    
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
                        # Cost-based routing check:
                        # If this worker is expensive, and a cheaper qualified worker is currently active and available,
                        # decline this claim so the cheaper worker can grab it.
                        worker_cost = worker.get("cost_class", "high")
                        if worker_cost in ("high", "medium"):
                            cheaper_available = False
                            now = time.time()
                            for other_id, other_w in state["workers"].items():
                                if other_id == worker_id: continue
                                if not other_w.get("available", False): continue
                                if now - other_w.get("last_seen", 0) > 300: continue
                                
                                other_cost = other_w.get("cost_class", "high")
                                # is other cheaper?
                                if worker_cost == "high" and other_cost in ("free", "low", "medium"):
                                    is_cheaper = True
                                elif worker_cost == "medium" and other_cost in ("free", "low"):
                                    is_cheaper = True
                                else:
                                    is_cheaper = False
                                    
                                if is_cheaper:
                                    # Is other qualified?
                                    if "github" in target and "github" in other_w["capabilities"]: cheaper_available = True
                                    elif "mac" in target and "macos" in other_w["capabilities"]: cheaper_available = True
                                    elif "windows" in target and "windows" in other_w["capabilities"]: cheaper_available = True
                                    elif "linux" in target and "linux" in other_w["capabilities"]: cheaper_available = True
                                    elif "antigravity" in target and "antigravity" in other_w["capabilities"]: cheaper_available = True
                                
                            if cheaper_available:
                                # We decline this claim to let the cheaper worker grab it.
                                # But we can't return error, we just skip this task and let it return empty.
                                matched = False

                    if matched:
                        next_task["worker_id"] = worker_id
                        next_task["attempts"] = next_task.get("attempts", 0) + 1
                        next_task["attempt_id"] = f"{next_task['task_id']}:attempt:{next_task['attempts']}"
                        next_task["dispatch_id"] = f"dispatch-{uuid.uuid4().hex}"
                        next_task["run_id"] = None
                        next_task["result_id"] = None
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
@serialize_state_mutation
def task_result():
    data = request.get_json(silent=True) or {}
    task_id = data.get("task_id")
    worker_id = data.get("worker_id")
    state = load_state()
    
    if task_id in state["tasks"]:
        task = state["tasks"][task_id]
        
        # Duplicate protection
        if task["status"] in ["RECONCILED", "FAILED_TERMINAL", "RESULT_RECEIVED"]:
            return jsonify({"status": "IGNORED", "reason": "DUPLICATE_OR_ALREADY_PROCESSED"})
            
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
            
            if durable_result.get("status") == "SUCCESS":
                task["status"] = "RESULT_RECEIVED" # wait for independent /verify
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
                if task["status"] == "FAILED_TERMINAL":
                    goal["status"] = "BLOCKED"

            if worker_id in state["workers"]:
                state["workers"][worker_id]["current_task"] = None
                state["workers"][worker_id]["available"] = True

            save_state(state)
            return jsonify({"status": "ACK_RESULT_RECEIVED"})
            
    return jsonify({"error": "Invalid task or worker"}), 400


@app.route("/tasks/reclaim_stale", methods=["POST"])
@require_auth
@serialize_state_mutation
def reclaim_stale():
    state = load_state()
    now = time.time()
    stale_threshold = 300  # 5 minutes
    
    stale_workers = set()
    for w_id, w in state.get("workers", {}).items():
        if now - w.get("last_seen", 0) > stale_threshold:
            stale_workers.add(w_id)
            w["available"] = False
            
    quarantined_count = 0
    # A claimed task may already have produced an effect. Without durable proof
    # that execution never started, replaying it would risk a duplicate effect.
    for goal in state.get("goals", {}).values():
        if goal.get("status") == "ACTIVE" and "workflow_plan" in goal:
            for step in goal["workflow_plan"]:
                if step.get("status") == "DISPATCHED" and step.get("worker_id") in stale_workers:
                    step["status"] = "HUMAN_REQUIRED"
                    step["recovery_reason"] = "STALE_WORKER_EFFECT_AMBIGUOUS"
                    quarantined_count += 1

                    task = state.get("tasks", {}).get(step.get("task_id"))
                    if task:
                        task["status"] = "HUMAN_REQUIRED"
                        task["recovery_reason"] = step["recovery_reason"]
                    worker = state.get("workers", {}).get(step.get("worker_id"))
                    if worker and worker.get("current_task") == step.get("task_id"):
                        worker["current_task"] = None
                        worker["available"] = False
                    goal["status"] = "BLOCKED"

    if stale_workers or quarantined_count > 0:
        save_state(state)

    return jsonify({"reclaimed_tasks": 0, "quarantined_tasks": quarantined_count})

@app.route("/tasks/pending_verification", methods=["GET"])
@require_verifier_auth
def pending_verification():
    state = load_state()
    pending = []
    for task in state.get("tasks", {}).values():
        if task.get("status") == "RESULT_RECEIVED":
            pending.append(task)
    return jsonify({"tasks": pending})

@app.route("/tasks/verify", methods=["POST"])
@require_verifier_auth
@serialize_state_mutation
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
    _, step = _find_workflow_step(state, task_id)
    if step is not None:
        step["status"] = task["status"]
    save_state(state)
    return jsonify({"status": task["status"]})


@app.route('/tasks/<task_id>/resume', methods=['POST'])
@require_auth
@serialize_state_mutation
def resume_task(task_id):
    data = request.get_json(silent=True) or {}
    action = data.get("action", "retry")
    state = load_state()
    task = state["tasks"].get(task_id)
    goal, step = _find_workflow_step(state, task_id)
    if step is None:
        return jsonify({"error": "Task not found"}), 404

    status = task["status"] if task else step["status"]
    if status not in ["HUMAN_REQUIRED", "FAILED_VERIFICATION", "FAILED_TERMINAL"]:
        return jsonify({"error": f"Task cannot be resumed from status {status}"}), 400

    if action == "retry":
        # Requeue only; the next claim mints a fresh attempt_id/dispatch_id so
        # results of the superseded attempt can no longer bind to this task.
        for record in filter(None, (task, step)):
            record["resumed_from"] = status
            record["status"] = "QUEUED"
            record["worker_id"] = None
        if "instruction_override" in data:
            step["instruction"] = data["instruction_override"]
        goal["status"] = "ACTIVE"
        save_state(state)
        return jsonify({"status": "RESUMED", "task_id": task_id, "goal_id": goal["goal_id"]})
    if action == "force_success":
        # Success must come from a DurableResult bound to a dispatch and an
        # independent verifier; a manual marker cannot provide either.
        return jsonify({"error": "force_success is not supported; retry and verify instead"}), 400
    return jsonify({"error": "Unknown action"}), 400


def _find_workflow_step(state, task_id):
    for goal in state["goals"].values():
        for step in goal.get("workflow_plan", []):
            if step.get("task_id") == task_id:
                return goal, step
    return None, None


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
