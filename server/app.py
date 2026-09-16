import os, json, uuid, time, threading
from functools import wraps
from flask import Flask, request, jsonify

from scripts.integration_contract import ContractError, prepare_task, validate_durable_result
from scripts.run_chief_commander import ChiefCommander

app = Flask(__name__)

CANONICAL_DIR = os.environ.get("COURIER_DATA_DIR", r"C:\ProgramData\Courier")
STATE_FILE = os.environ.get("COURIER_STATE_FILE", os.path.join(CANONICAL_DIR, "central_state.json"))
BATCH_QUEUE_DIR = os.path.join(CANONICAL_DIR, "batches")
try:
    import keyring
    API_KEY = os.environ.get("COURIER_API_KEY") or keyring.get_password("courier_worker", "courier_api_key")
    VERIFIER_API_KEY = os.environ.get("COURIER_VERIFIER_API_KEY") or keyring.get_password("courier_worker", "courier_verifier_api_key")
except ImportError:
    API_KEY = os.environ.get("COURIER_API_KEY")
    VERIFIER_API_KEY = os.environ.get("COURIER_VERIFIER_API_KEY")

if not API_KEY:
    raise SystemExit("Missing COURIER_API_KEY environment variable or keyring entry")
if not VERIFIER_API_KEY:
    raise SystemExit("Missing COURIER_VERIFIER_API_KEY environment variable or keyring entry")
INSECURE_API_KEYS = {"dev-secret-key"}

# Canonical task statuses — the ONLY valid values for task["status"].
# No code may invent status strings outside this set.
VALID_TASK_STATUSES = frozenset({
    "QUEUED",
    "DISPATCHED",
    "RESULT_RECEIVED",
    "RECONCILED",
    "RECONCILED_PENDING_MERGE",
    "FAILED_TERMINAL",
    "FAILED_VERIFICATION",
    "HUMAN_REQUIRED",
    "WAITING_PROVIDER",
    "BLOCKED_TRANSIENT",
})

def set_task_status(task, new_status):
    """Set task status with validation. Raises ValueError for invalid statuses."""
    if new_status not in VALID_TASK_STATUSES:
        raise ValueError(f"Invalid task status: {new_status!r}. Valid: {sorted(VALID_TASK_STATUSES)}")
    task["status"] = new_status

# P13 — Canonical cost ordering for cheapest-qualified routing.
COST_ORDER = {"free": 0, "low": 1, "medium": 2, "high": 3}

MAX_RETRIES = {
    "execution": 3,
    "transport": 5,
    "provider": 10,
    "verification": 2
}

def get_retry_state(task):
    if "retry_state" not in task:
        task["retry_state"] = {"execution": 0, "transport": 0, "provider": 0, "verification": 0}
    return task["retry_state"]

def calculate_backoff(attempt):
    return min(300, 2 ** attempt)  # Max 5 minutes backoff


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
        for i in range(20):
            try:
                with open(STATE_FILE, 'r') as f:
                    state = json.load(f)
                    
                schema_version_val = state.get("schema_version", 1)
                try:
                    schema_version = int(float(schema_version_val))
                except (ValueError, TypeError):
                    schema_version = 1
                
                if schema_version == 1:
                    # Migrate 1 -> 2 preserving task identity/state
                    state["schema_version"] = 2
                elif schema_version > 2:
                    # Fail closed on unknown future schema
                    print(f"FATAL: Unknown future schema_version {schema_version}. Failing closed to prevent destructive silent reset.")
                    sys.exit(1)
                    
                state.setdefault("goals", {})
                state.setdefault("tasks", {})
                state.setdefault("workers", {})
                return state
            except (PermissionError, IOError, json.JSONDecodeError) as e:
                if i == 19:
                    raise
                time.sleep(0.05)
    return {"schema_version": 2, "goals": {}, "tasks": {}, "workers": {}}

def save_state(state):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    temp_path = f"{STATE_FILE}.tmp"
    with open(temp_path, 'w') as f:
        json.dump(state, f, indent=2)
        f.flush()
        os.fsync(f.fileno())
    for i in range(20):
        try:
            os.replace(temp_path, STATE_FILE)
            break
        except PermissionError:
            if i == 19:
                raise
            time.sleep(0.05)

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
        "status": "ACTIVE",
        "terminal": data.get("terminal", True)
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
            new_task = {
                "task_id": step.get("task_id", f"task-{uuid.uuid4().hex[:8]}"),
                "goal_id": goal_id,
                "instruction": step.get("instruction", "Next bounded step"),
                "target_agent": target_agent,
                "status": "QUEUED",
                "attempts": 0,
            }
            if "artifacts" in step:
                new_task["artifacts"] = step["artifacts"]
            goal["workflow_plan"].append(new_task)
        
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
                set_task_status(task, "HUMAN_REQUIRED")
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
    
    # --- Reclaim DISPATCHED tasks (e.g. resumed from WAITING_PROVIDER) ---
    for task_id, task in state.get("tasks", {}).items():
        if task.get("status") == "DISPATCHED" and task.get("worker_id") == worker_id:
            worker["current_task"] = task_id
            worker["available"] = False
            save_state(state)
            return jsonify({"task": task})
    
    for goal_id, goal in state["goals"].items():
        if goal["status"] == "ACTIVE" and "workflow_plan" in goal:
            completed_tasks = {
                step.get("task_id") for step in goal["workflow_plan"] 
                if step.get("status") in ("RECONCILED", "RECONCILED_PENDING_MERGE")
            }
            blocked_targets = {
                step.get("target_agent", "linux").lower() for step in goal["workflow_plan"]
                if step.get("status") in ("WAITING_PROVIDER", "BLOCKED_TRANSIENT")
            }

            next_task = None
            for step in goal["workflow_plan"]:
                if step["status"] == "QUEUED":
                    if step.get("next_retry_at", 0) > time.time():
                        continue
                    
                    depends_on = step.get("depends_on")
                    if isinstance(depends_on, str):
                        depends_on = [depends_on]
                    
                    deps_met = True
                    if depends_on:
                        for dep in depends_on:
                            if dep not in completed_tasks:
                                deps_met = False
                                break
                                
                    if deps_met:
                        target = step.get("target_agent", "linux").lower()
                        if target not in blocked_targets:
                            next_task = step
                            break
                            
            if next_task is not None:
                    target = next_task.get("target_agent", "linux").lower()
                    
                    matched = False
                    if "github" in target and "github" in worker["capabilities"]: matched = True
                    elif "mac" in target and "macos" in worker["capabilities"]: matched = True
                    elif "windows" in target and "windows" in worker["capabilities"]: matched = True
                    elif "linux" in target and "linux" in worker["capabilities"]: matched = True
                    elif "antigravity" in target and "antigravity" in worker["capabilities"]: matched = True
                    elif target in worker.get("capabilities", []): matched = True
                    
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
                                # P13 — use COST_ORDER for clean comparison
                                is_cheaper = COST_ORDER.get(other_cost, 3) < COST_ORDER.get(worker_cost, 3)
                                    
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
                        next_task["execution_ref"] = f"exec-{uuid.uuid4().hex}"
                        next_task["run_id"] = None
                        next_task["result_id"] = None
                        next_task["target_capability"] = target
                        # Structured checkpoint fields (Prompt 2) — resume-safe, no CoT
                        next_task["last_completed_step"] = next_task.get("last_completed_step")
                        next_task["next_action"] = "EXECUTE"
                        next_task["blocker"] = None
                        next_task["artifact_refs"] = next_task.get("artifact_refs", [])
                        idx = goal["workflow_plan"].index(next_task)
                        try:
                            next_task = prepare_task(next_task)
                        except ContractError as exc:
                            return jsonify({"error": str(exc)}), 400
                        set_task_status(next_task, "DISPATCHED")
                        goal["workflow_plan"][idx] = next_task
                        
                        worker["current_task"] = next_task["task_id"]
                        worker["available"] = False
                        
                        state["tasks"][next_task["task_id"]] = next_task
                        save_state(state)
                        return jsonify({"task": next_task})
                        
    # --- INJECTED BATCH CLAIM LOGIC ---
    import glob
    if os.path.exists(BATCH_QUEUE_DIR):
        for path in glob.glob(os.path.join(BATCH_QUEUE_DIR, "*.json")):
            basename = os.path.basename(path)
            batch_id = basename[:-5]
            batch = load_batch(batch_id)
            if not batch: continue
            
            completed_seqs = {item.get("sequence") for item in batch.get("items", []) if item.get("status") == "COMPLETED"}
            blocked_targets = {item.get("target_agent", "linux").lower() for item in batch.get("items", []) if item.get("status") in ("WAITING_PROVIDER", "BLOCKED_TRANSIENT")}
            
            next_task = None
            for item in batch.get("items", []):
                if item.get("status") == "QUEUED":
                    if item.get("next_retry_at", 0) > time.time():
                        continue
                    depends_on = item.get("depends_on")
                    if depends_on is None or depends_on in completed_seqs:
                        target = item.get("target_agent", "linux").lower()
                        if target not in blocked_targets:
                            # Qualified check
                            matched = False
                            if "github" in target and "github" in worker["capabilities"]: matched = True
                            elif "mac" in target and "macos" in worker["capabilities"]: matched = True
                            elif "windows" in target and "windows" in worker["capabilities"]: matched = True
                            elif "linux" in target and "linux" in worker["capabilities"]: matched = True
                            elif "antigravity" in target and "antigravity" in worker["capabilities"]: matched = True
                            
                            if matched:
                                next_task = item
                                break
            
            if next_task:
                target = next_task.get("target_agent", "linux").lower()
                next_task["worker_id"] = worker_id
                next_task["attempts"] = next_task.get("attempts", 0) + 1
                next_task["task_id"] = next_task.get("task_id") or f"{batch_id}-seq-{next_task['sequence']}"
                next_task["attempt_id"] = f"{next_task['task_id']}:attempt:{next_task['attempts']}"
                next_task["dispatch_id"] = f"dispatch-{uuid.uuid4().hex}"
                next_task["execution_ref"] = f"exec-{uuid.uuid4().hex}"
                next_task["run_id"] = None
                next_task["result_id"] = None
                next_task["target_capability"] = target
                next_task["batch_id"] = batch_id
                if "prompt_id" in batch:
                    next_task["prompt_id"] = batch["prompt_id"]
                elif "prompt_id" in next_task:
                    pass # Keep existing
                next_task["goal_id"] = next_task.get("goal_id", batch_id)
                next_task["last_completed_step"] = next_task.get("last_completed_step")
                next_task["next_action"] = "EXECUTE"
                next_task["blocker"] = None
                next_task["artifact_refs"] = next_task.get("artifact_refs", [])
                next_task["instruction"] = next_task.get("description", "Batch item")
                
                try:
                    next_task = prepare_task(next_task)
                except ContractError as exc:
                    return jsonify({"error": str(exc)}), 400
                    
                set_task_status(next_task, "DISPATCHED")
                next_task["status"] = "DISPATCHED"
                
                for item in batch["items"]:
                    if item.get("sequence") == next_task.get("sequence"):
                        item.update(next_task)
                
                with open(path, "w") as bf:
                    json.dump(batch, bf, indent=2)
                
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
            set_task_status(task, "RESULT_RECEIVED")
            task["result"] = durable_result
            
            if durable_result.get("status") == "SUCCESS":
                set_task_status(task, "RESULT_RECEIVED")  # wait for independent /verify
                # Update checkpoint fields on success
                task["last_completed_step"] = task.get("task_id")
                task["next_action"] = "VERIFY"
                task["blocker"] = None
                task["artifact_refs"] = durable_result.get("artifacts", task.get("artifact_refs", []))
            else:
                failure_reason = durable_result.get("stderr", "unknown")
                retry_state = get_retry_state(task)
                if retry_state["execution"] < MAX_RETRIES["execution"] and "AMBIGUOUS_CRASH" not in failure_reason:
                    retry_state["execution"] += 1
                    set_task_status(task, "QUEUED")
                    task["worker_id"] = None
                    task["next_action"] = "RETRY"
                    task["blocker"] = failure_reason[:200] if failure_reason else None
                    task["next_retry_at"] = time.time() + calculate_backoff(retry_state["execution"])
                elif "AMBIGUOUS_CRASH" in failure_reason:
                    set_task_status(task, "HUMAN_REQUIRED")
                    task["next_action"] = "HUMAN_REVIEW"
                    task["recovery_reason"] = "AMBIGUOUS_EFFECT_CRASH"
                    task["blocker"] = "Worker crashed during external effect."
                else:
                    set_task_status(task, "FAILED_TERMINAL")
                    task["next_action"] = None
                    task["blocker"] = f"MAX_ATTEMPTS_REACHED: {failure_reason[:200]}" if failure_reason else "MAX_ATTEMPTS_REACHED"
                
            goal_id = task["goal_id"]
            if goal_id in state["goals"]:
                goal = state["goals"][goal_id]
                # Sync status back to workflow plan
                for step in goal.get("workflow_plan", []):
                    if step.get("task_id") == task_id:
                        step["status"] = task["status"]
                        step["worker_id"] = task.get("worker_id")
                        step["attempts"] = task.get("attempts")
                        if "retry_state" in task:
                            step["retry_state"] = task["retry_state"]
                        if "next_retry_at" in task:
                            step["next_retry_at"] = task["next_retry_at"]
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
                        set_task_status(task, "HUMAN_REQUIRED")
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
        "verified_at": time.time(),
    }
    goal = state["goals"][task["goal_id"]]
    if verdict == "PASS":
        # P8 — Human Gate split: protected code changes require merge approval
        if task.get("merge_scope") == "protected_code":
            set_task_status(task, "RECONCILED_PENDING_MERGE")
            task["next_action"] = "AWAIT_MERGE_APPROVAL"
            task["blocker"] = None
            # Do NOT advance goal step — merge gate must pass first
        else:
            set_task_status(task, "RECONCILED")
            task["next_action"] = None
            task["blocker"] = None
            
            # Sync status back to workflow_plan early for goal completion check
            for step in goal.get("workflow_plan", []):
                if step.get("task_id") == task_id:
                    step["status"] = task["status"]
            
            all_done = True
            for step in goal.get("workflow_plan", []):
                if step.get("status") not in ("RECONCILED", "RECONCILED_PENDING_MERGE"):
                    all_done = False
                    break
            
            if all_done:
                if goal.get("terminal") is False:
                    # Auto-Replenish!
                    goal["replenish_count"] = goal.get("replenish_count", 0) + 1
                    try:
                        _, planned_steps = ChiefCommander().formulate_workflow_plan(
                            goal["goal_text"], idea_type="GOAL"
                        )
                        if planned_steps:
                            added_any = False
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
                                    
                                instruction = step.get("instruction", "Next bounded step")
                                
                                # Deduplication logic
                                is_duplicate = False
                                for existing_step in goal.get("workflow_plan", []):
                                    if existing_step.get("instruction") == instruction and existing_step.get("target_agent") == target_agent:
                                        is_duplicate = True
                                        break
                                
                                if not is_duplicate:
                                    new_task = {
                                        "task_id": step.get("task_id", f"task-{uuid.uuid4().hex[:8]}"),
                                        "goal_id": goal["goal_id"],
                                        "instruction": instruction,
                                        "target_agent": target_agent,
                                        "status": "QUEUED",
                                        "attempts": 0,
                                    }
                                    if "artifacts" in step:
                                        new_task["artifacts"] = step["artifacts"]
                                    goal["workflow_plan"].append(new_task)
                                    added_any = True
                            
                            if not added_any:
                                goal["status"] = "DONE"
                        else:
                            goal["status"] = "DONE"
                    except Exception as exc:
                        goal["status"] = "BLOCKED"
                        goal["blocker"] = f"Replenish failed: {exc}"
                else:
                    goal["status"] = "DONE"
    else:
        retry_state = get_retry_state(task)
        if retry_state["verification"] < MAX_RETRIES["verification"]:
            retry_state["verification"] += 1
            set_task_status(task, "QUEUED")
            task["worker_id"] = None
            task["next_action"] = "RETRY"
            task["blocker"] = f"VERIFICATION_REJECTED: {data.get('reason', 'no reason')}"[:200]
            task["next_retry_at"] = time.time() + calculate_backoff(retry_state["verification"])
        else:
            set_task_status(task, "FAILED_VERIFICATION")
            task["next_action"] = "HUMAN_REVIEW"
            task["blocker"] = f"VERIFICATION_REJECTED_MAX_RETRIES: {data.get('reason', 'no reason')}"[:200]
            goal["status"] = "BLOCKED"

    # P6/P10 — Terminal cleanup: release worker ownership after verification
    assigned_worker_id = task.get("worker_id")
    if assigned_worker_id and assigned_worker_id in state["workers"]:
        state["workers"][assigned_worker_id]["current_task"] = None
        state["workers"][assigned_worker_id]["available"] = True

    # Sync status back to workflow_plan
    for step in goal.get("workflow_plan", []):
        if step.get("task_id") == task_id:
            step["status"] = task["status"]
            step["verification"] = task["verification"]
            if "retry_state" in task:
                step["retry_state"] = task["retry_state"]
            if "next_retry_at" in task:
                step["next_retry_at"] = task["next_retry_at"]

    save_state(state)
    return jsonify({"status": task["status"]})


@app.route('/tasks/<task_id>/resume', methods=['POST'])
@require_auth
@serialize_state_mutation
def resume_task(task_id):
    data = request.get_json(silent=True) or {}
    action = data.get("action", "retry")
    state = load_state()
    
    for goal_id, goal in state["goals"].items():
        if "workflow_plan" not in goal: continue
        for step in goal["workflow_plan"]:
            if step["task_id"] == task_id:
                if step["status"] not in ["HUMAN_REQUIRED", "FAILED_VERIFICATION", "FAILED_TERMINAL", "WAITING_PROVIDER", "BLOCKED_TRANSIENT"]:
                    return jsonify({"error": f"Task cannot be resumed from status {step['status']}"}), 400
                
                # Also update the canonical task in state["tasks"]
                task = state["tasks"].get(task_id, step)
                prior_status = task.get("status", step["status"])

                if action == "retry":
                    # P11/P14 — Transport-retry vs real re-execution:
                    # WAITING_PROVIDER / BLOCKED_TRANSIENT = same attempt, preserve identity
                    # HUMAN_REQUIRED / FAILED_* = real re-execution, new attempt via claim
                    if prior_status in ("WAITING_PROVIDER", "BLOCKED_TRANSIENT"):
                        retry_state = get_retry_state(task)
                        can_resume = True
                        if prior_status == "BLOCKED_TRANSIENT":
                            if retry_state["transport"] < MAX_RETRIES["transport"]:
                                retry_state["transport"] += 1
                            else:
                                can_resume = False
                        
                        if can_resume:
                            set_task_status(task, "DISPATCHED")
                            step["status"] = "DISPATCHED"
                            task["next_action"] = "EXECUTE"
                            task["blocker"] = None
                            task.pop("provider_wait_since", None)
                            if "retry_state" in task:
                                step["retry_state"] = task["retry_state"]
                            if "next_retry_at" in task:
                                step["next_retry_at"] = task["next_retry_at"]
                        else:
                            set_task_status(task, "FAILED_TERMINAL")
                            step["status"] = "FAILED_TERMINAL"
                            task["blocker"] = "MAX_TRANSPORT_RETRIES_REACHED"
                            goal["status"] = "BLOCKED"
                            save_state(state)
                            return jsonify({"error": "Max transport retries reached"}), 400
                    else:
                        # Real re-execution: clear identity, will get new attempt on claim
                        set_task_status(task, "QUEUED")
                        step["status"] = "QUEUED"
                        task["worker_id"] = None
                        step["worker_id"] = None
                        task["next_action"] = "DISPATCH"
                        task["blocker"] = None
                        # Release previous worker ownership
                        prev_worker = task.get("worker_id")
                        if prev_worker and prev_worker in state["workers"]:
                            w = state["workers"][prev_worker]
                            if w.get("current_task") == task_id:
                                w["current_task"] = None
                                w["available"] = True

                    goal["status"] = "ACTIVE"
                    if "instruction_override" in data:
                        step["instruction"] = data["instruction_override"]
                        task["instruction"] = data["instruction_override"]
                    save_state(state)
                    return jsonify({
                        "status": "RESUMED",
                        "task_id": task_id,
                        "goal_id": goal_id,
                        "attempt_id": task.get("attempt_id"),
                        "dispatch_id": task.get("dispatch_id"),
                        "resume_type": "TRANSPORT_RETRY" if prior_status in ("WAITING_PROVIDER", "BLOCKED_TRANSIENT") else "RE_EXECUTION",
                    })
                elif action == "force_success":
                    set_task_status(task, "RESULT_RECEIVED")
                    step["status"] = "RESULT_RECEIVED"
                    goal["status"] = "ACTIVE"
                    task["result_id"] = "manual-resume-" + task_id
                    step["result_id"] = "manual-resume-" + task_id
                    save_state(state)
                    return jsonify({"status": "FORCED_SUCCESS_PENDING_VERIFICATION", "task_id": task_id})
                else:
                    return jsonify({"error": "Unknown action"}), 400
                    
    return jsonify({"error": "Task not found"}), 404

@app.route('/tasks/<task_id>/approve_merge', methods=['POST'])
@require_auth
@serialize_state_mutation
def approve_merge(task_id):
    """P8 — Human Gate: approve merge for protected-code tasks.

    Only tasks in RECONCILED_PENDING_MERGE can be approved.
    On approval the task transitions to RECONCILED and the goal step advances.
    """
    data = request.get_json(silent=True) or {}
    approver = data.get("approver")
    if not isinstance(approver, str) or not approver:
        return jsonify({"error": "approver identity is required"}), 400
    state = load_state()

    task = state["tasks"].get(task_id)
    if not task:
        return jsonify({"error": "Task not found"}), 404
    if task.get("status") != "RECONCILED_PENDING_MERGE":
        return jsonify({"error": f"Task is not pending merge (status={task.get('status')})"}), 409

    set_task_status(task, "RECONCILED")
    task["next_action"] = None
    task["merge_approval"] = {
        "approver": approver,
        "approved_at": time.time(),
        "merge_ref": data.get("merge_ref"),
    }

    goal = state["goals"].get(task.get("goal_id"))
    if goal:
        goal["current_step_index"] = goal.get("current_step_index", 0) + 1
        if goal["current_step_index"] >= len(goal.get("workflow_plan", [])):
            goal["status"] = "DONE"
        # Sync to workflow_plan
        for step in goal.get("workflow_plan", []):
            if step.get("task_id") == task_id:
                step["status"] = "RECONCILED"
                step["merge_approval"] = task["merge_approval"]

    save_state(state)
    return jsonify({"status": "RECONCILED", "task_id": task_id})

@app.route('/tasks/<task_id>/provider_wait', methods=['POST'])
@require_auth
@serialize_state_mutation
def provider_wait(task_id):
    """Worker reports a provider/rate-limit interruption.

    Maps to WAITING_PROVIDER (transient, auto-resumable) or BLOCKED_TRANSIENT.
    Does NOT increment attempt_id — the same dispatch resumes when provider returns.
    """
    data = request.get_json(silent=True) or {}
    reason = data.get("reason", "PROVIDER_UNAVAILABLE")
    wait_type = data.get("wait_type", "WAITING_PROVIDER")
    worker_id = data.get("worker_id")
    state = load_state()

    task = state["tasks"].get(task_id)
    if not task:
        return jsonify({"error": "Task not found"}), 404
    if task.get("status") != "DISPATCHED":
        return jsonify({"error": f"Task not in DISPATCHED state (is {task.get('status')})"}), 409
    if task.get("worker_id") != worker_id:
        return jsonify({"error": "Worker mismatch"}), 403

    # Only allow canonical transient wait states
    if wait_type not in ("WAITING_PROVIDER", "BLOCKED_TRANSIENT"):
        wait_type = "WAITING_PROVIDER"

    retry_state = get_retry_state(task)
    if retry_state["provider"] < MAX_RETRIES["provider"]:
        retry_state["provider"] += 1
        set_task_status(task, wait_type)
        task["blocker"] = reason[:200] if reason else "PROVIDER_UNAVAILABLE"
        task["next_action"] = "WAIT_THEN_RESUME"
        # Preserve attempt_id and dispatch_id — no new attempt
        task["provider_wait_since"] = time.time()
        task["next_retry_at"] = time.time() + calculate_backoff(retry_state["provider"])
    else:
        set_task_status(task, "FAILED_TERMINAL")
        task["blocker"] = "MAX_PROVIDER_WAITS_REACHED"
        task["next_action"] = None
        if task.get("goal_id") in state.get("goals", {}):
            state["goals"][task["goal_id"]]["status"] = "BLOCKED"

    # Sync to workflow_plan
    goal = state["goals"].get(task.get("goal_id"))
    if goal and "workflow_plan" in goal:
        for step in goal["workflow_plan"]:
            if step.get("task_id") == task_id:
                step["status"] = task["status"]
                step["blocker"] = task["blocker"]
                if "retry_state" in task:
                    step["retry_state"] = task["retry_state"]
                if "next_retry_at" in task:
                    step["next_retry_at"] = task["next_retry_at"]

    # Release worker so other tasks can proceed
    if worker_id in state["workers"]:
        state["workers"][worker_id]["current_task"] = None
        state["workers"][worker_id]["available"] = True

    save_state(state)
    return jsonify({
        "status": task["status"],
        "task_id": task_id,
        "attempt_id": task.get("attempt_id"),
        "dispatch_id": task.get("dispatch_id"),
        "blocker": task["blocker"],
    })
import os
import glob
import json

BATCH_QUEUE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "events", "queue")

def load_batch(batch_id):
    path = os.path.join(BATCH_QUEUE_DIR, f"{batch_id}.json")
    if os.path.exists(path):
        with open(path, "r") as f:
            return json.load(f)
    return None

@app.route("/batches", methods=["GET"])
@require_auth
def list_batches():
    batches = []
    if os.path.exists(BATCH_QUEUE_DIR):
        for path in glob.glob(os.path.join(BATCH_QUEUE_DIR, "*.json")):
            basename = os.path.basename(path)
            batch_id = basename[:-5]
            batch_data = load_batch(batch_id)
            if batch_data:
                batches.append({
                    "batch_id": batch_data.get("batch_id"),
                    "status": batch_data.get("status"),
                    "created_at": batch_data.get("created_at"),
                })
    return jsonify({"batches": batches})

@app.route("/batches/<batch_id>", methods=["GET"])
@require_auth
def get_batch(batch_id):
    batch = load_batch(batch_id)
    if not batch:
        return jsonify({"error": "Batch not found"}), 404
    return jsonify(batch)

@app.route("/batches/<batch_id>/active", methods=["GET"])
@require_auth
def get_batch_active(batch_id):
    batch = load_batch(batch_id)
    if not batch:
        return jsonify({"error": "Batch not found"}), 404
    
    active_items = [item for item in batch.get("items", []) if item.get("status") in ("IN_PROGRESS", "DISPATCHED")]
    if active_items:
        return jsonify({"active_item": active_items[0]})
    return jsonify({"active_item": None})

@app.route("/batches/<batch_id>/next", methods=["GET"])
@require_auth
def get_batch_next(batch_id):
    batch = load_batch(batch_id)
    if not batch:
        return jsonify({"error": "Batch not found"}), 404
    
    completed_seqs = {item.get("sequence") for item in batch.get("items", []) if item.get("status") == "COMPLETED"}
    
    for item in batch.get("items", []):
        if item.get("status") == "QUEUED":
            depends_on = item.get("depends_on")
            if depends_on is None or depends_on in completed_seqs:
                return jsonify({"next_item": item})
    
    return jsonify({"next_item": None})

@app.route("/batches/<batch_id>/blocked", methods=["GET"])
@require_auth
def get_batch_blocked(batch_id):
    batch = load_batch(batch_id)
    if not batch:
        return jsonify({"error": "Batch not found"}), 404
    
    blocked_items = [item for item in batch.get("items", []) if item.get("status") in ("WAITING_PROVIDER", "BLOCKED", "BLOCKED_TRANSIENT", "HUMAN_REQUIRED")]
    return jsonify({"blocked_items": blocked_items})


# --- OVERRIDE SAVE_STATE TO SYNC BATCHES ---
original_save_state = save_state
def custom_save_state(state):
    original_save_state(state)
    
    import os, json
    batches_to_sync = {}
    for task_id, task in state.get("tasks", {}).items():
        batch_id = task.get("batch_id")
        if batch_id:
            if batch_id not in batches_to_sync:
                batches_to_sync[batch_id] = load_batch(batch_id)
            
            batch = batches_to_sync[batch_id]
            if not batch: continue
            
            for item in batch.get("items", []):
                if item.get("sequence") == task.get("sequence"):
                    st = task.get("status")
                    if st == "RECONCILED":
                        item["status"] = "COMPLETED"
                    elif st in ("WAITING_PROVIDER", "BLOCKED_TRANSIENT", "HUMAN_REQUIRED", "FAILED_VERIFICATION", "FAILED_TERMINAL"):
                        item["status"] = "WAITING_PROVIDER"
                    elif st in ("DISPATCHED", "RESULT_RECEIVED", "RECONCILED_PENDING_MERGE"):
                        item["status"] = "IN_PROGRESS"
                    else:
                        item["status"] = st
                        
                    item["worker_id"] = task.get("worker_id")
                    item["result"] = task.get("result")
                    item["verification"] = task.get("verification")
                    item["blocker"] = task.get("blocker")
                    item["attempts"] = task.get("attempts")
                    item["attempt_id"] = task.get("attempt_id")

    for batch_id, batch in batches_to_sync.items():
        if batch:
            path = os.path.join(BATCH_QUEUE_DIR, f"{batch_id}.json")
            with open(path, "w") as bf:
                json.dump(batch, bf, indent=2)

save_state = custom_save_state

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
