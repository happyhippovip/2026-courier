import copy, os, json, re, uuid, time, threading
from functools import wraps
from flask import Flask, request, jsonify

from scripts.integration_contract import ContractError, prepare_task, validate_durable_result
import os
if os.environ.get("COURIER_MOCK_CHIEF"):
    class ChiefCommander:
        def formulate_workflow_plan(self, text, idea_type):
            import json
            try:
                plan = json.loads(text)
                if isinstance(plan, list) and plan:
                    return None, plan
            except:
                pass
            
            if "REPLENISHMENT_TEST" in text:
                import uuid
                # Read a counter from a file so we can return unique instructions
                count = 1
                counter_file = "/tmp/mock_replenish.txt"
                if os.path.exists(counter_file):
                    with open(counter_file, "r") as cf:
                        count = int(cf.read().strip()) + 1
                with open(counter_file, "w") as cf:
                    cf.write(str(count))
                    
                return None, [{
                    "task_id": f"task-{uuid.uuid4().hex[:8]}",
                    "target_agent": "linux",
                    "instruction": f"touch mock_replenish_{count}.txt",
                    "status": "QUEUED"
                }]
            return None, []
else:
    from scripts.run_chief_commander import ChiefCommander


import subprocess

try:
    SERVER_SHA = subprocess.check_output(["git", "rev-parse", "HEAD"]).decode("utf-8").strip()
except Exception:
    SERVER_SHA = "unknown"

app = Flask(__name__)


STATE_FILE = os.environ.get("COURIER_STATE_FILE", "server/state/central_state.json")
BATCH_QUEUE_DIR = "server/state/batches"
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

HUMAN_GATED_ACTIONS = frozenset({
    "SPEND",
    "PAYMENT",
    "BANKING",
    "PURCHASE",
    "UPGRADE",
    "MERGE",
    "RELEASE",
    "CREDENTIAL_EXPANSION",
    "PERMISSION_EXPANSION",
})

HUMAN_GATED_AUTHORITIES = frozenset({
    "SPEND",
    "PAYMENT",
    "BANKING",
    "MERGE",
    "RELEASE",
    "CREDENTIAL_EXPANSION",
    "PERMISSION_EXPANSION",
})

TASK_ELIGIBILITY_FIELDS = (
    "required_capabilities",
    "required_authorities",
    "exclusive_resources",
    "requires_spend",
    "estimated_cost_eur",
    "requires_human_approval",
    "human_gate_required",
    "requested_action",
    "merge_scope",
)

SECRET_MATERIAL_RE = re.compile(
    r"(?i)(?:bearer\s+\S+|-----BEGIN [A-Z ]*PRIVATE KEY-----|"
    r"\b(?:github_pat_|gh[pousr]_|sk-)[A-Za-z0-9_-]{12,})"
)


def _string_list(value):
    """Return a normalized list of non-empty strings, or None when malformed."""
    if value is None:
        return []
    if not isinstance(value, list):
        return None
    normalized = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            return None
        cleaned = item.strip()
        if cleaned not in normalized:
            normalized.append(cleaned)
    return normalized


def _safe_capacity_value(value):
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip() or len(value) > 256:
        return None
    cleaned = value.strip()
    if SECRET_MATERIAL_RE.search(cleaned):
        return None
    return cleaned


def _task_requires_human_gate(task):
    def is_required(value):
        return value is True or (
            isinstance(value, str) and value.strip().upper() in {"TRUE", "YES", "REQUIRED"}
        )

    if is_required(task.get("requires_spend")):
        return True
    try:
        if float(task.get("estimated_cost_eur", 0) or 0) > 0:
            return True
    except (TypeError, ValueError):
        return True
    if is_required(task.get("requires_human_approval")) or is_required(task.get("human_gate_required")):
        return True
    action = str(task.get("requested_action", "")).strip().upper().replace("-", "_").replace(" ", "_")
    if any(action == gated or action.startswith(f"{gated}_") for gated in HUMAN_GATED_ACTIONS):
        return True
    authorities = _string_list(task.get("required_authorities"))
    if authorities is None:
        return True
    normalized = {authority.upper().replace("-", "_").replace(" ", "_") for authority in authorities}
    return bool(normalized & HUMAN_GATED_AUTHORITIES)


def _legacy_target_matches(task, worker):
    target = str(task.get("target_agent", "linux")).lower()
    capabilities = set(worker.get("capabilities", []))
    if "github" in target:
        return "github" in capabilities
    if "mac" in target:
        return "macos" in capabilities
    if "windows" in target:
        return "windows" in capabilities
    if "linux" in target:
        return "linux" in capabilities
    if "antigravity" in target:
        return "antigravity" in capabilities
    if "auto" in target:
        return bool({"windows", "macos"} & capabilities)
    return target in capabilities


def _resource_owner_is_active(state, owner):
    task = state.get("tasks", {}).get(owner.get("task_id"))
    if not task:
        # Missing canonical ownership evidence is ambiguous; fail closed.
        return True
    return task.get("status") not in {"RECONCILED", "FAILED_TERMINAL"}


def _prune_terminal_resource_owners(state):
    owners = state.setdefault("resource_owners", {})
    for resource, owner in list(owners.items()):
        if not isinstance(owner, dict) or not _resource_owner_is_active(state, owner):
            owners.pop(resource, None)


def _resources_available(state, task):
    resources = _string_list(task.get("exclusive_resources"))
    if resources is None:
        return False
    owners = state.setdefault("resource_owners", {})
    for resource in resources:
        owner = owners.get(resource)
        if owner and owner.get("task_id") != task.get("task_id"):
            return False
    return True


def _worker_is_eligible(state, task, worker_id):
    worker = state.get("workers", {}).get(worker_id)
    if not worker or not worker.get("available", False) or worker.get("current_task"):
        return False
    if (
        worker.get("provider_available", True) is not True
        or worker.get("capacity_available", True) is not True
    ):
        return False
    if _task_requires_human_gate(task):
        return False

    required_capabilities = _string_list(task.get("required_capabilities"))
    required_authorities = _string_list(task.get("required_authorities"))
    worker_capabilities = _string_list(worker.get("capabilities"))
    worker_authorities = _string_list(worker.get("authorities"))
    if None in (required_capabilities, required_authorities, worker_capabilities, worker_authorities):
        return False

    if required_capabilities:
        if not set(required_capabilities).issubset(set(worker_capabilities)):
            return False
    elif not _legacy_target_matches(task, worker):
        return False
    if not set(required_authorities).issubset(set(worker_authorities)):
        return False
    return _resources_available(state, task)


def _cheaper_eligible_worker_exists(state, task, worker_id):
    worker = state["workers"][worker_id]
    worker_cost = COST_ORDER.get(worker.get("cost_class", "high"), 3)
    if worker_cost <= COST_ORDER["free"]:
        return False
    now = time.time()
    for other_id, other in state.get("workers", {}).items():
        if other_id == worker_id or now - other.get("last_seen", 0) > 300:
            continue
        if COST_ORDER.get(other.get("cost_class", "high"), 3) >= worker_cost:
            continue
        if _worker_is_eligible(state, task, other_id):
            return True
    return False


def _canonical_target_capability(task, worker):
    required = _string_list(task.get("required_capabilities")) or []
    if required:
        return required[0]
    target = str(task.get("target_agent", "linux")).lower()
    if "github" in target:
        return "github"
    if "mac" in target:
        return "mac"
    if "windows" in target:
        return "windows"
    if "linux" in target:
        return "linux"
    if "antigravity" in target:
        return "antigravity"
    if target and target != "auto":
        return target
    capabilities = worker.get("capabilities", [])
    for known in ("windows", "macos", "github", "linux"):
        if known in capabilities:
            return "mac" if known == "macos" else known
    return capabilities[0] if capabilities else "unknown"


def _acquire_task_resources(state, task):
    owners = state.setdefault("resource_owners", {})
    for resource in _string_list(task.get("exclusive_resources")) or []:
        owners[resource] = {
            "resource": resource,
            "goal_id": task.get("goal_id"),
            "task_id": task.get("task_id"),
            "attempt_id": task.get("attempt_id"),
            "worker_id": task.get("worker_id"),
            "acquired_at": time.time(),
        }


def _release_task_resources(state, task):
    owners = state.setdefault("resource_owners", {})
    task_id = task.get("task_id")
    for resource, owner in list(owners.items()):
        if isinstance(owner, dict) and owner.get("task_id") == task_id:
            owners.pop(resource, None)


def _copy_task_eligibility_fields(source, target):
    for field in TASK_ELIGIBILITY_FIELDS:
        if field in source:
            target[field] = source[field]


def _prepare_claimed_task(task, worker_id, worker):
    claimed = copy.deepcopy(task)
    claimed["worker_id"] = worker_id
    claimed["attempts"] = claimed.get("attempts", 0) + 1
    claimed["attempt_id"] = f"{claimed['task_id']}:attempt:{claimed['attempts']}"
    claimed["dispatch_id"] = f"dispatch-{uuid.uuid4().hex}"
    claimed["execution_ref"] = f"exec-{uuid.uuid4().hex}"
    claimed["run_id"] = None
    claimed["result_id"] = None
    claimed["target_capability"] = _canonical_target_capability(claimed, worker)
    claimed["last_completed_step"] = claimed.get("last_completed_step")
    claimed["next_action"] = "EXECUTE"
    claimed["blocker"] = None
    claimed["artifact_refs"] = claimed.get("artifact_refs", [])
    claimed = prepare_task(claimed)
    set_task_status(claimed, "DISPATCHED")
    return claimed

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
        expected = f"Bearer {API_KEY}"
        if not auth_header or auth_header != expected:
            try:
                import time
                with open("C:/Users/lol/2026-workspace/courier/debug_auth2.txt", "a") as f2:
                    f2.write(f"[{time.time()}] AUTH FAIL: Invalid token provided\n")
            except Exception as e:
                pass
            print("Auth fail: Invalid token provided"); return jsonify({"error": "Unauthorized"}), 401
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
                state.setdefault("resource_owners", {})
                return state
            except (PermissionError, IOError, json.JSONDecodeError) as e:
                if i == 19:
                    raise
                time.sleep(0.05)
    return {
        "schema_version": 2,
        "goals": {},
        "tasks": {},
        "workers": {},
        "resource_owners": {},
    }

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

@app.route("/health2", methods=["GET"])
def health2():
    return jsonify({"status": "I AM THE RIGHT FILE"})


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
            _copy_task_eligibility_fields(step, new_task)
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
        
    worker_sha = data.get("runtime_sha")
    if worker_sha and SERVER_SHA != "unknown" and worker_sha != "unknown" and worker_sha != SERVER_SHA:
        return jsonify({"error": "wrong SHA rejected: worker runtime_sha does not match server SHA"}), 426
        
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

    capabilities = _string_list(data.get("capabilities", existing.get("capabilities", [])))
    authorities = _string_list(data.get("authorities", existing.get("authorities", [])))
    if capabilities is None or authorities is None:
        return jsonify({"error": "capabilities and authorities must be lists of strings"}), 400

    provider = existing.get("provider")
    if "provider" in data:
        provider = _safe_capacity_value(data.get("provider"))
        if provider is None:
            return jsonify({"error": "provider must be safe non-secret metadata"}), 400

    capacity_identity = existing.get("capacity_identity")
    capacity_key = "capacity_identity" if "capacity_identity" in data else "account_id"
    if capacity_key in data:
        capacity_identity = _safe_capacity_value(data.get(capacity_key))
        if capacity_identity is None:
            return jsonify({"error": "capacity identity must be safe non-secret metadata"}), 400

    provider_available = data.get("provider_available", existing.get("provider_available", True))
    capacity_available = data.get("capacity_available", existing.get("capacity_available", True))
    if not isinstance(provider_available, bool) or not isinstance(capacity_available, bool):
        return jsonify({"error": "provider/capacity availability must be boolean"}), 400

    state["workers"][worker_id] = {
        "worker_id": worker_id,
        "platform": data.get("platform", "unknown"),
        "capabilities": capabilities,
        "authorities": authorities,
        "provider": provider,
        "capacity_identity": capacity_identity,
        "provider_available": provider_available,
        "capacity_available": capacity_available,
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
        task_id = state["workers"][worker_id].get("current_task")
        if task_id:
            task = state.get("tasks", {}).get(task_id)
            if not task or task.get("status") != "DISPATCHED":
                state["workers"][worker_id]["current_task"] = None
                state["workers"][worker_id]["available"] = True
        else:
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
        task_id = worker.get("current_task")
        if task_id:
            task = state.get("tasks", {}).get(task_id)
            if not task or task.get("status") != "DISPATCHED":
                worker["current_task"] = None
                worker["available"] = True
            else:
                save_state(state)
                return jsonify({"task": None, "reason": "WORKER_BUSY"})
        else:
            worker["available"] = True
    
    # --- Reclaim DISPATCHED tasks (e.g. resumed from WAITING_PROVIDER) ---
    for task_id, task in state.get("tasks", {}).items():
        if task.get("status") == "DISPATCHED" and task.get("worker_id") == worker_id:
            worker["current_task"] = task_id
            worker["available"] = False
            save_state(state)
            return jsonify({"task": task})

    # --- Auto-resume WAITING_PROVIDER tasks if backoff elapsed ---
    quota_resource_id = state.get("worker_quota_pools", {}).get(worker_id, worker_id)
    worker_provider = str(worker.get("provider", "unknown"))
    lock_key = f"{quota_resource_id}:{worker_provider}"

    for task_id, task in state.get("tasks", {}).items():
        if task.get("status") in ("WAITING_PROVIDER", "BLOCKED_TRANSIENT") and task.get("worker_id") == worker_id:
            if time.time() > state.get("provider_locks", {}).get(lock_key, 0):
                task["status"] = "DISPATCHED"
                
                # Sync back to goal
                if task.get("goal_id") in state.get("goals", {}):
                    goal = state["goals"][task["goal_id"]]
                    if "workflow_plan" in goal:
                        for step in goal["workflow_plan"]:
                            if step.get("task_id") == task_id:
                                step["status"] = "DISPATCHED"

                worker["current_task"] = task_id
                worker["available"] = False
                save_state(state)
                return jsonify({"task": task})

    _prune_terminal_resource_owners(state)
    if (
        worker.get("provider_available", True) is not True
        or worker.get("capacity_available", True) is not True
    ):
        save_state(state)
        return jsonify({"task": None, "reason": "PROVIDER_UNAVAILABLE"})
        
    if time.time() < state.get("provider_locks", {}).get(lock_key, 0):
        save_state(state)
        return jsonify({"task": None, "reason": "PROVIDER_QUOTA_LOCKED"})

    for goal_id, goal in state["goals"].items():
        if goal["status"] == "ACTIVE" and "workflow_plan" in goal:
            completed_tasks = {
                step.get("task_id") for step in goal["workflow_plan"]
                if step.get("status") == "RECONCILED"
            }

            # Scan every dependency-ready task until eligible work is found.
            # A capability/provider/resource mismatch is local to that task and
            # must not hide later independent READY work.
            for index, candidate in enumerate(goal["workflow_plan"]):
                if candidate.get("status") != "QUEUED":
                    continue
                if candidate.get("next_retry_at", 0) > time.time():
                    continue
                depends_on = candidate.get("depends_on", [])
                if isinstance(depends_on, str):
                    depends_on = [depends_on]
                if not all(dependency in completed_tasks for dependency in depends_on):
                    continue
                if not _worker_is_eligible(state, candidate, worker_id):
                    continue
                if _cheaper_eligible_worker_exists(state, candidate, worker_id):
                    continue
                try:
                    claimed = _prepare_claimed_task(candidate, worker_id, worker)
                except ContractError as exc:
                    print(f"ContractError in prepare_task: {exc}", flush=True)
                    return jsonify({"error": str(exc)}), 400

                goal["workflow_plan"][index] = claimed
                state["tasks"][claimed["task_id"]] = claimed
                _acquire_task_resources(state, claimed)
                worker["current_task"] = claimed["task_id"]
                worker["available"] = False
                save_state(state)
                return jsonify({"task": claimed})
                        
    # --- INJECTED BATCH CLAIM LOGIC ---
    import glob
    if os.path.exists(BATCH_QUEUE_DIR):
        for path in glob.glob(os.path.join(BATCH_QUEUE_DIR, "*.json")):
            basename = os.path.basename(path)
            batch_id = basename[:-5]
            batch = load_batch(batch_id)
            if not batch: continue
            
            completed_seqs = {item.get("sequence") for item in batch.get("items", []) if item.get("status") == "COMPLETED"}
            
            next_task = None
            for item in batch.get("items", []):
                if item.get("status") == "QUEUED":
                    if item.get("next_retry_at", 0) > time.time():
                        continue
                    depends_on = item.get("depends_on")
                    if depends_on is None or depends_on in completed_seqs:
                        item.setdefault("task_id", f"{batch_id}-seq-{item['sequence']}")
                        item.setdefault("goal_id", batch_id)
                        if not _worker_is_eligible(state, item, worker_id):
                            continue
                        if _cheaper_eligible_worker_exists(state, item, worker_id):
                            continue
                        next_task = item
                        break
            
            if next_task:
                batch_task = copy.deepcopy(next_task)
                batch_task["batch_id"] = batch_id
                if "prompt_id" in batch:
                    batch_task["prompt_id"] = batch["prompt_id"]
                elif "prompt_id" in batch_task:
                    pass # Keep existing
                batch_task["instruction"] = batch_task.get("instruction", batch_task.get("description", "Batch item"))
                
                try:
                    claimed = _prepare_claimed_task(batch_task, worker_id, worker)
                except ContractError as exc:
                    return jsonify({"error": str(exc)}), 400
                
                for item in batch["items"]:
                    if item.get("sequence") == claimed.get("sequence"):
                        item.update(claimed)
                
                with open(path, "w") as bf:
                    json.dump(batch, bf, indent=2)
                
                worker["current_task"] = claimed["task_id"]
                worker["available"] = False
                state["tasks"][claimed["task_id"]] = claimed
                _acquire_task_resources(state, claimed)
                save_state(state)
                return jsonify({"task": claimed})

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
            is_identical = (
                task.get("result", {}).get("result_id") == data.get("result_id") and
                task.get("result", {}).get("worker_id") == data.get("worker_id")
            )
            if is_identical:
                return jsonify({"status": "ACK_DUPLICATE"})
            return jsonify({"status": "CONFLICT", "reason": "CONTRADICTORY_DUPLICATE"}), 409
            
        if task.get("worker_id") == worker_id:
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
                failure_reason = durable_result.get("stderr") or "unknown"
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
                    task["next_action"] = "ABORT"
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
            
    return jsonify({"status": "IGNORED", "reason": "UNKNOWN_TASK"}), 200


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
            _release_task_resources(state, task)
            
            # Sync status back to workflow_plan early for goal completion check
            for step in goal.get("workflow_plan", []):
                if step.get("task_id") == task_id:
                    step["status"] = task["status"]
            
            all_done = True
            ready_work_exists = False
            completed_tasks = {
                step.get("task_id")
                for step in goal.get("workflow_plan", [])
                if step.get("status") == "RECONCILED"
            }
            for step in goal.get("workflow_plan", []):
                st = step.get("status")
                if st != "RECONCILED":
                    all_done = False
                if st in ("QUEUED", "FAILED_TRANSIENT", "PROVIDER_WAIT"):
                    deps = step.get("depends_on", [])
                    if isinstance(deps, str): deps = [deps]
                    if all(d in completed_tasks for d in deps):
                        ready_work_exists = True
            
            if all_done or (not ready_work_exists and goal.get("terminal") is False):
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
                                    _copy_task_eligibility_fields(step, new_task)
                                    goal["workflow_plan"].append(new_task)
                                    added_any = True
                            
                            if not added_any:
                                goal["status"] = "BLOCKED"
                                goal["blocker"] = "Replenish returned no new steps for nonterminal goal"
                        else:
                            goal["status"] = "BLOCKED"
                            goal["blocker"] = "Replenish returned empty plan for nonterminal goal"
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
            set_task_status(task, "FAILED_TERMINAL")
            task["next_action"] = "ABORT"
            task["blocker"] = f"VERIFICATION_REJECTED_MAX_RETRIES: {data.get('reason', 'no reason')}"[:200]
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
                            _release_task_resources(state, task)
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

                else:
                    return jsonify({"error": "Unknown action"}), 400
                    
    return jsonify({"error": "Task not found"}), 404

@app.route('/tasks/<task_id>/approve_merge', methods=['POST'])
@require_verifier_auth
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
    _release_task_resources(state, task)
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
        quota_resource_id = state.setdefault("worker_quota_pools", {}).get(worker_id, worker_id)
        worker_provider = str(state["workers"][worker_id].get("provider", "unknown"))
        lock_key = f"{quota_resource_id}:{worker_provider}"
        
        new_backoff = time.time() + calculate_backoff(retry_state["provider"])
        existing_backoff = state.setdefault("provider_locks", {}).get(lock_key, 0)
        state["provider_locks"][lock_key] = max(existing_backoff, new_backoff)
        
        task["provider_wait_since"] = time.time()
        task["next_retry_at"] = state["provider_locks"][lock_key]
    else:
        set_task_status(task, "FAILED_TERMINAL")
        task["blocker"] = "MAX_PROVIDER_WAITS_REACHED"
        task["next_action"] = None
        _release_task_resources(state, task)
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
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", 8080)))
