import contextlib
import hashlib
import json
import sys
import time
import subprocess
import os
from datetime import datetime

# Marker recorded when no single run can be unambiguously bound to this
# dispatch. Downstream must treat it as "linkage pending reconcile",
# never as a run ID. (M05-Q1: take-latest `gh run list --limit 1` could
# attach a foreign run under concurrent dispatches.)
UNBOUND_EXECUTION_REF = "DISPATCHED_UNBOUND"

# Bounded wait for GitHub to register the dispatched run.
BIND_ATTEMPTS = 3
BIND_RETRY_DELAY_SECONDS = 2

# Freshness bound for a DISPATCHING admission marker: a fresh marker means
# "a dispatch may already be in flight, adopt it", a stale marker means
# "dispatch exactly once". (Pattern lifted from the adapter-side
# DISPATCHING marker with M06's blessing; intake key space is separate.)
INTAKE_DISPATCH_GRACE_SECONDS = 300

ADMISSION_DISPATCHING = "DISPATCHING"
ADMISSION_ADMITTED = "ADMITTED"
ADMISSION_BLOCKED = "BLOCKED"


def _evaluate_intake_admission(intake, checker=None):
    """Evaluates admission capacity and resource readiness for an intake.

    Returns a dict with 'decision' ('ADMIT' or 'BLOCKED'/'REJECT'),
    optional 'reason', and 'wakeup_condition'.
    """
    if checker is not None:
        if callable(checker):
            res = checker(intake)
        else:
            res = checker
        if isinstance(res, bool):
            if not res:
                return {
                    "decision": "BLOCKED",
                    "reason": "RESOURCE_ADMISSION_REJECTED",
                    "wakeup_condition": "RESOURCE_HEALTHY",
                }
            return {"decision": "ADMIT"}
        if isinstance(res, dict):
            return res
        decision = getattr(res, "decision", "ADMIT")
        reasons = getattr(res, "reasons", [])
        if decision != "ADMIT":
            return {
                "decision": "BLOCKED",
                "reason": "; ".join(reasons) if reasons else "RESOURCE_ADMISSION_REJECTED",
                "wakeup_condition": "RESOURCE_HEALTHY",
            }
        return {"decision": "ADMIT"}

    # Default checks when no custom checker is provided
    pause_path = os.environ.get("COURIER_RESOURCE_PAUSE_FILE")
    if not pause_path:
        local_pause = os.path.join(os.getcwd(), "RESOURCE_PAUSE")
        if os.path.exists(local_pause):
            pause_path = local_pause

    if pause_path and os.path.exists(pause_path):
        try:
            with open(pause_path, "r", encoding="utf-8") as f:
                content = f.read().strip()
        except Exception:
            content = "RESOURCE_PAUSE active"
        return {
            "decision": "BLOCKED",
            "reason": f"RESOURCE_PAUSE: {content}",
            "wakeup_condition": "RESOURCE_HEALTHY",
        }

    env_state = os.environ.get("COURIER_ADMISSION_STATE")
    if env_state in ("CLOSED", "BLOCKED", "RESOURCE_PAUSE"):
        return {
            "decision": "BLOCKED",
            "reason": f"COURIER_ADMISSION_STATE={env_state}",
            "wakeup_condition": "RESOURCE_HEALTHY",
        }

    # Pre-dispatch Cost & Spend Gate Check (Zero unauthorized spend enforcement)
    from scripts.resource_policy import CostGate
    resource_id = intake.get("resource_id", "google_antigravity_plus")
    cost_val = intake.get("estimated_cost_eur", 0.0)
    grant = intake.get("grant")
    already_spent = intake.get("already_spent_eur", 0.0)
    current_time = intake.get("current_time")
    cost_decision = CostGate.evaluate_spend_request(
        resource_id=resource_id,
        estimated_cost_eur=cost_val,
        requested_action=intake.get("requested_action", "EXECUTE_TASK"),
        grant=grant,
        already_spent_eur=already_spent,
        current_time=current_time,
    )
    if not cost_decision.get("allowed", False):
        return {
            "decision": "BLOCKED",
            "reason": f"COST_GATE_DENIAL: {cost_decision.get('reason')}",
            "blocked_reason": cost_decision.get("reason"),
            "cost_message": cost_decision.get("message"),
            "wakeup_condition": "COST_AUTHORIZED",
            "model_calls": 0,
        }

    return {"decision": "ADMIT"}


def validate_task_result_submission(task_id, state_file="central_state.json") -> tuple[bool, str]:
    """Ensures that execution results are rejected for tasks that were cost-blocked or unadmitted."""
    with _central_state_locked(state_file):
        state = _load_or_exit(state_file)
        task = state["tasks"].get(task_id)
        if task is None:
            return False, "UNKNOWN_TASK: task does not exist in central state"
        if task.get("admission") == ADMISSION_BLOCKED or task.get("state") == "BLOCKED":
            return False, f"TASK_BLOCKED_UNAUTHORIZED: task '{task_id}' is BLOCKED ({task.get('blocked_reason')}); results cannot be accepted for unauthorized work"
        return True, "SUBMISSION_PERMITTED"


def unblock_task(task_id, state_file="central_state.json", reason="OPERATOR_UNBLOCK"):
    """Explicitly unblocks a BLOCKED task, clearing the resource hold."""
    with _central_state_locked(state_file):
        state = _load_or_exit(state_file)
        task = state["tasks"].get(task_id)
        if task and task.get("admission") == ADMISSION_BLOCKED:
            task["admission"] = "UNBLOCKED"
            task["state"] = "READY"
            task["last_transition"] = f"UNBLOCKED:{reason}"
            save_central_state(state_file, state)
            return True
        return False


@contextlib.contextmanager
def _central_state_locked(state_file):
    """Exclusive cross-process lock for one central-state read-modify-write.

    save_central_state is atomic (tmp+replace) but two interleaved writers
    still lose updates: each saves a stale base. Hold this across
    load -> mutate -> save, and re-load under it before a final save that
    follows a slow external call. Blocking acquire: a crashed holder's OS
    lock dies with it, and dispatches are rare enough that waiting beats
    dropping a record. Same fcntl/msvcrt pattern as the worker home lock.
    """
    lock_path = state_file + ".lock"
    fd = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(fd, msvcrt.LK_LOCK, 1)
        else:
            import fcntl
            fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)


def _load_or_exit(state_file):
    """Load or fail closed (never reset-and-overwrite)."""
    try:
        return load_central_state(state_file)
    except (ValueError, OSError) as e:
        # Never silently wipe every recorded task; queue_processor treats
        # SystemExit as retryable, so the intake stays pending.
        print(f"Refusing dispatch record: unreadable {state_file}: {e}")
        sys.exit(1)


def _parse_created_at(value):
    try:
        text = str(value).strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        return datetime.fromisoformat(text).timestamp()
    except (ValueError, TypeError):
        return None


def resolve_execution_ref(workflow, since_epoch, attempts=BIND_ATTEMPTS,
                          delay=BIND_RETRY_DELAY_SECONDS):
    """Return the databaseId of the single run created after since_epoch.

    Returns None when zero or more than one candidate run exists
    (ambiguous: concurrent dispatch or API lag) or when `gh` fails.
    Callers must fail closed on None, never fall back to take-latest.
    """
    for attempt in range(max(1, attempts)):
        try:
            run_info = subprocess.run(
                ["gh", "run", "list", f"--workflow={workflow}",
                 "--limit=10", "--json", "databaseId,createdAt"],
                capture_output=True, text=True)
            runs = json.loads(run_info.stdout or "[]")
        except (subprocess.CalledProcessError, ValueError):
            runs = []
        candidates = []
        if isinstance(runs, list):
            for run in runs:
                if not isinstance(run, dict):
                    continue
                created = _parse_created_at(run.get("createdAt"))
                if created is not None and created >= since_epoch:
                    candidates.append(str(run.get("databaseId")))
        if len(candidates) == 1:
            return candidates[0]
        if attempt < max(1, attempts) - 1:
            time.sleep(delay)
    return None


def fingerprint_task_id(intake):
    """Stable id for an intake so recovery re-dispatch is idempotent.

    Same intake content -> same task id: a crash between dispatch and the
    queue move re-records under the same id instead of minting a duplicate
    task (and the queue pre-check skips the second external dispatch).
    """
    canonical = json.dumps(
        {k: intake[k] for k in (
            "customer_reference", "target_owner", "target_repo", "target_sha")},
        sort_keys=True, separators=(",", ":"))
    return f"task-revenue-{hashlib.sha1(canonical.encode()).hexdigest()[:8]}"


def dispatch_intake(intake_file, admission_checker=None, force_wakeup=False, state_file='central_state.json'):
    with open(intake_file, 'r') as f:
        intake = json.load(f)

    task_id = fingerprint_task_id(intake)
    print(f"Admitting intake {intake.get('customer_reference')} as {task_id}")

    # 1. State check under lock: already admitted or already blocked
    with _central_state_locked(state_file):
        state = _load_or_exit(state_file)
        existing = state["tasks"].get(task_id)
        if existing is not None and existing.get(
                "admission", ADMISSION_ADMITTED) == ADMISSION_ADMITTED:
            print(f"Task {task_id} already admitted; skipping re-dispatch")
            return task_id
        if existing is not None and existing.get("admission") == ADMISSION_BLOCKED:
            if not force_wakeup:
                print(f"Task {task_id} is BLOCKED ({existing.get('blocked_reason')}); skipping re-dispatch without model calls")
                return task_id
            print(f"Task {task_id} unblock requested; re-evaluating admission")

    # 2. Pre-dispatch admission check (Host pressure / resource gate)
    adm_decision = _evaluate_intake_admission(intake, admission_checker)
    if adm_decision.get("decision") in ("REJECT", "BLOCKED"):
        block_reason = adm_decision.get("reason", "RESOURCE_ADMISSION_REJECTED")
        wakeup_cond = adm_decision.get("wakeup_condition", "RESOURCE_HEALTHY")
        max_retries = adm_decision.get("max_retries", 4)
        with _central_state_locked(state_file):
            state = _load_or_exit(state_file)
            existing = state["tasks"].get(task_id)
            retry_count = (existing.get("retry_count", 0) + 1) if existing else 1
            state["tasks"][task_id] = {
                "task_id": task_id,
                "customer_reference": intake.get('customer_reference'),
                "admission": ADMISSION_BLOCKED,
                "state": "BLOCKED",
                "blocked_reason": block_reason,
                "retry_count": retry_count,
                "max_retries": max_retries,
                "dispatched_at": time.time(),
                "last_transition": "RESOURCE_BLOCKED",
                "wakeup_condition": wakeup_cond,
                "model_calls": 0,
            }
            save_central_state(state_file, state)
        print(f"Task {task_id} BLOCKED: {block_reason}. Dispatcher decision: BLOCKED. MODEL_CALLS=0.")
        return task_id

    # Revenue V1 uses GitHub Actions as the primary qualified lane
    cmd = [
        "gh", "workflow", "run", "revenue_v1_baseline.yml",
        "-f", f"target_owner={intake['target_owner']}",
        "-f", f"target_repo={intake['target_repo']}",
        "-f", f"target_sha={intake['target_sha']}",
        "-f", f"customer_reference={intake['customer_reference']}",
        "-f", f"price_currency={intake.get('price_currency', 'EUR_99')}",
        "-f", f"delivery_destination={intake.get('delivery_destination', 'none')}"
    ]

    # Update Central State. Every load -> mutate -> save runs under the
    # central-state lock: concurrent writers otherwise save stale bases and
    # lose each other's records (and share one tmp name). Slow external
    # calls stay outside the lock; the final save re-loads under it and
    # verifies our marker is still current before merging.
    with _central_state_locked(state_file):
        state = _load_or_exit(state_file)
        existing = state["tasks"].get(task_id)
        if existing is not None and existing.get(
                "admission", ADMISSION_ADMITTED) == ADMISSION_ADMITTED:
            print(f"Task {task_id} already admitted; skipping re-dispatch")
            return task_id
        if (existing is not None
                and existing.get("admission") == ADMISSION_DISPATCHING
                and time.time() - existing.get("dispatched_at", 0)
                < INTAKE_DISPATCH_GRACE_SECONDS):
            # Fresh marker: a dispatch may already be in flight. Adopt its run
            # if exactly one is visible, else stay pending for a later retry.
            # The (slow) resolve runs outside the lock; the marker snapshot
            # is re-verified before the adopt is recorded.
            snapshot = dict(existing)
            decision = "adopt"
        else:
            # Fresh admission or stale marker: record DISPATCHING *before* the
            # external call so recovery can adopt instead of blind re-dispatch.
            # A stale marker means the old attempt is dead; exactly one new
            # dispatch replaces it.
            dispatch_start = time.time()
            state["tasks"][task_id] = {
                "task_id": task_id,
                "customer_reference": intake.get('customer_reference'),
                "admission": ADMISSION_DISPATCHING,
                "dispatched_at": dispatch_start,
            }
            save_central_state(state_file, state)
            decision = "dispatch"

    if decision == "adopt":
        adopted = resolve_execution_ref(
            "revenue_v1_baseline.yml", snapshot["dispatched_at"])
        if adopted is None:
            print(f"No run yet for {task_id}; leaving DISPATCHING for retry")
            sys.exit(1)
        with _central_state_locked(state_file):
            state = _load_or_exit(state_file)
            current = state["tasks"].get(task_id)
            if current is not None and current.get(
                    "admission", ADMISSION_ADMITTED) == ADMISSION_ADMITTED:
                print(f"Task {task_id} admitted while adopting; skipping re-dispatch")
                return task_id
            if (current is None or current.get("admission") != ADMISSION_DISPATCHING
                    or current.get("dispatched_at") != snapshot["dispatched_at"]):
                print(f"Marker for {task_id} changed during adopt; leaving for retry")
                sys.exit(1)
            current["execution_ref"] = adopted
            current["admission"] = ADMISSION_ADMITTED
            current["last_transition"] = "AUTOMATIC_ADOPT"
            save_central_state(state_file, state)
        print(f"Adopted run {adopted} for {task_id}")
        return task_id

    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        print(f"Successfully dispatched to GitHub Actions worker.")
    except subprocess.CalledProcessError as e:
        # Marker stays DISPATCHING: adopt on retry, re-dispatch once stale.
        print(f"Failed to dispatch: {e.stderr}")
        sys.exit(1)

    # Bind the execution_ref (the GitHub run ID) to THIS dispatch only:
    # exactly one run created after dispatch_start binds, anything else
    # (zero, several, gh failure) fails closed to UNBOUND.
    execution_ref = resolve_execution_ref(
        "revenue_v1_baseline.yml", dispatch_start) or UNBOUND_EXECUTION_REF

    with _central_state_locked(state_file):
        state = _load_or_exit(state_file)
        current = state["tasks"].get(task_id)
        if current is not None and current.get(
                "admission", ADMISSION_ADMITTED) == ADMISSION_ADMITTED \
                and current.get("dispatched_at") != dispatch_start:
            print(f"Task {task_id} admitted by a concurrent actor; keeping its record")
            return task_id
        if current is None or current.get("dispatched_at") != dispatch_start:
            # Defensive: only this call writes our marker, so a mismatch means
            # an unexpected writer. Never clobber it; stay pending for retry.
            print(f"Marker for {task_id} superseded during dispatch; leaving for retry")
            sys.exit(1)
        state["tasks"][task_id] = {
            "task_id": task_id,
            "customer_reference": intake['customer_reference'],
            "worker_id": "github-actions-revenue-v1",
            "platform": "github",
            "dispatch_ref": "intake_dispatcher_local",
            "execution_ref": execution_ref,
            "admission": ADMISSION_ADMITTED,
            "dispatched_at": dispatch_start,
            "state": "DISPATCHED_TO_EXTERNAL",
            "last_transition": "AUTOMATIC_DISPATCH",
            "next_explicit_transition": "WAIT_FOR_GITHUB_PR",
            "real_wall": "HUMAN_REVIEW_REQUIRED_ON_PR"
        }
        save_central_state(state_file, state)

    print(f"Central state updated. System chain fully connected for intake -> execution -> PR.")
    return task_id


def load_central_state(state_file):
    """Load state, validating shape. Missing file -> fresh state.

    Raises ValueError on corrupt JSON or wrong shape, OSError on IO
    problems. Callers must fail closed, never reset-and-overwrite.
    """
    if not os.path.exists(state_file):
        return {"tasks": {}}
    with open(state_file, 'r') as f:
        try:
            state = json.load(f)
        except ValueError as e:
            raise ValueError(f"corrupt JSON: {e}")
    if not isinstance(state, dict) or not isinstance(state.get("tasks"), dict):
        raise ValueError("missing 'tasks' object")
    return state


def save_central_state(state_file, state):
    """Atomically persist state (tmp + fsync + replace).

    A crash mid-write leaves either the old or the new complete file,
    never a torn one that the next reader would have to discard.
    """
    tmp_file = state_file + ".tmp"
    with open(tmp_file, 'w') as f:
        json.dump(state, f, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp_file, state_file)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/intake_dispatcher.py <intake_file.json>")
        sys.exit(1)
    dispatch_intake(sys.argv[1])
