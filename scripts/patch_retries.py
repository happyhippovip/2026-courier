import os
import re

app_file = "server/app.py"
with open(app_file, "r") as f:
    content = f.read()

# 1. Add MAX_RETRIES dictionary
max_retries_code = """
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
"""
content = content.replace("COST_ORDER = {\"free\": 0, \"low\": 1, \"medium\": 2, \"high\": 3}", "COST_ORDER = {\"free\": 0, \"low\": 1, \"medium\": 2, \"high\": 3}\n" + max_retries_code)

# 2. task_result: replace execution retry
exec_retry_orig = """                if task.get("attempts", 1) < 3 and "AMBIGUOUS_CRASH" not in failure_reason:
                    set_task_status(task, "QUEUED")  # Retry
                    task["worker_id"] = None
                    task["next_action"] = "RETRY"
                    task["blocker"] = failure_reason[:200] if failure_reason else None"""

exec_retry_new = """                retry_state = get_retry_state(task)
                if retry_state["execution"] < MAX_RETRIES["execution"] and "AMBIGUOUS_CRASH" not in failure_reason:
                    retry_state["execution"] += 1
                    set_task_status(task, "QUEUED")
                    task["worker_id"] = None
                    task["next_action"] = "RETRY"
                    task["blocker"] = failure_reason[:200] if failure_reason else None
                    task["next_retry_at"] = time.time() + calculate_backoff(retry_state["execution"])"""
content = content.replace(exec_retry_orig, exec_retry_new)

# 3. verify_task_result: replace verification rejection
ver_orig = """    else:
        set_task_status(task, "FAILED_VERIFICATION")
        task["next_action"] = "HUMAN_REVIEW"
        task["blocker"] = f"VERIFICATION_REJECTED: {data.get('reason', 'no reason')}"[:200]
        goal["status"] = "BLOCKED" """

ver_new = """    else:
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
            goal["status"] = "BLOCKED" """
content = content.replace(ver_orig, ver_new)

# 4. provider_wait: handle provider wait bounds
prov_orig = """    set_task_status(task, wait_type)
    task["blocker"] = reason[:200] if reason else "PROVIDER_UNAVAILABLE"
    task["next_action"] = "WAIT_THEN_RESUME"
    # Preserve attempt_id and dispatch_id — no new attempt
    task["provider_wait_since"] = time.time()"""

prov_new = """    retry_state = get_retry_state(task)
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
        state["goals"][task["goal_id"]]["status"] = "BLOCKED\"\"\"
        # Wait, the string was just replaced inside a function, no need to triple quote here. Let's fix the string.
"""

prov_new = """    retry_state = get_retry_state(task)
    if retry_state["provider"] < MAX_RETRIES["provider"]:
        retry_state["provider"] += 1
        set_task_status(task, wait_type)
        task["blocker"] = reason[:200] if reason else "PROVIDER_UNAVAILABLE"
        task["next_action"] = "WAIT_THEN_RESUME"
        task["provider_wait_since"] = time.time()
        task["next_retry_at"] = time.time() + calculate_backoff(retry_state["provider"])
    else:
        set_task_status(task, "FAILED_TERMINAL")
        task["blocker"] = "MAX_PROVIDER_WAITS_REACHED"
        task["next_action"] = None
        if task["goal_id"] in state.get("goals", {}):
            state["goals"][task["goal_id"]]["status"] = "BLOCKED" """
content = content.replace(prov_orig, prov_new)

# 5. resume_task: handle transport retry bound
trans_orig = """                    if prior_status in ("WAITING_PROVIDER", "BLOCKED_TRANSIENT"):
                        # Transport retry: same attempt_id, same dispatch_id
                        # Go back to DISPATCHED so the same worker (or another) can resume
                        set_task_status(task, "DISPATCHED")
                        step["status"] = "DISPATCHED"
                        task["next_action"] = "EXECUTE"
                        task["blocker"] = None
                        task.pop("provider_wait_since", None)"""

trans_new = """                    if prior_status in ("WAITING_PROVIDER", "BLOCKED_TRANSIENT"):
                        retry_state = get_retry_state(task)
                        if retry_state["transport"] < MAX_RETRIES["transport"]:
                            retry_state["transport"] += 1
                            set_task_status(task, "DISPATCHED")
                            step["status"] = "DISPATCHED"
                            task["next_action"] = "EXECUTE"
                            task["blocker"] = None
                            task.pop("provider_wait_since", None)
                        else:
                            set_task_status(task, "FAILED_TERMINAL")
                            step["status"] = "FAILED_TERMINAL"
                            task["blocker"] = "MAX_TRANSPORT_RETRIES_REACHED"
                            goal["status"] = "BLOCKED"
                            save_state(state)
                            return jsonify({"error": "Max transport retries reached"}), 400"""
content = content.replace(trans_orig, trans_new)

# 6. claim_task: enforce backoff by skipping tasks that are queued but next_retry_at is in the future
claim_orig = """                if candidate["status"] == "QUEUED":
                    cand_target = candidate.get("target_agent", "linux").lower()
                    if blocked_target is None or cand_target != blocked_target:
                        next_task = candidate
                        idx = scan_idx
                        break"""

claim_new = """                if candidate["status"] == "QUEUED":
                    if candidate.get("next_retry_at", 0) > time.time():
                        scan_idx += 1
                        continue
                    cand_target = candidate.get("target_agent", "linux").lower()
                    if blocked_target is None or cand_target != blocked_target:
                        next_task = candidate
                        idx = scan_idx
                        break"""
content = content.replace(claim_orig, claim_new)

# 7. batch claim_task: enforce backoff
batch_claim_orig = """            for item in batch.get("items", []):
                if item.get("status") == "QUEUED":
                    depends_on = item.get("depends_on")
                    if depends_on is None or depends_on in completed_seqs:
                        target = item.get("target_agent", "linux").lower()"""
batch_claim_new = """            for item in batch.get("items", []):
                if item.get("status") == "QUEUED":
                    if item.get("next_retry_at", 0) > time.time():
                        continue
                    depends_on = item.get("depends_on")
                    if depends_on is None or depends_on in completed_seqs:
                        target = item.get("target_agent", "linux").lower()"""
content = content.replace(batch_claim_orig, batch_claim_new)


with open(app_file, "w") as f:
    f.write(content)
print("Patched app.py")
