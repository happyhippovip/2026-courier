import os
from pathlib import Path

app_file = Path("server/app.py")
content = app_file.read_text()

# 1. str(None) to "unknown"
content = content.replace('worker_provider = str(worker.get("provider", "unknown"))', 'worker_provider = str(worker.get("provider") or "unknown")')
content = content.replace('worker_provider = str(state["workers"][worker_id].get("provider", "unknown"))', 'worker_provider = str(state["workers"][worker_id].get("provider") or "unknown")')

# 2. claim_task auto-resume next_retry_at check
content = content.replace(
'''    for task_id, task in state.get("tasks", {}).items():
        if task.get("status") in ("WAITING_PROVIDER", "BLOCKED_TRANSIENT") and task.get("worker_id") == worker_id:
            if time.time() > state.get("provider_locks", {}).get(lock_key, 0):''',
'''    for task_id, task in state.get("tasks", {}).items():
        if task.get("status") in ("WAITING_PROVIDER", "BLOCKED_TRANSIENT") and task.get("worker_id") == worker_id:
            if time.time() > state.get("provider_locks", {}).get(lock_key, 0) and time.time() >= task.get("next_retry_at", 0):''')

# 3. provider_wait fallback to per-task backoff if "unknown"
content = content.replace(
'''        quota_resource_id = state.setdefault("worker_quota_pools", {}).get(worker_id, worker_id)
        worker_provider = str(state["workers"][worker_id].get("provider") or "unknown")
        lock_key = f"{quota_resource_id}:{worker_provider}"
        
        new_backoff = time.time() + calculate_backoff(retry_state["provider"])
        existing_backoff = state.setdefault("provider_locks", {}).get(lock_key, 0)
        state["provider_locks"][lock_key] = max(existing_backoff, new_backoff)
        task["next_retry_at"] = state["provider_locks"][lock_key]''',
'''        quota_resource_id = state.setdefault("worker_quota_pools", {}).get(worker_id, worker_id)
        worker_provider = str(state["workers"][worker_id].get("provider") or "unknown")
        
        new_backoff = time.time() + calculate_backoff(retry_state["provider"])
        if worker_provider != "unknown":
            lock_key = f"{quota_resource_id}:{worker_provider}"
            existing_backoff = state.setdefault("provider_locks", {}).get(lock_key, 0)
            state["provider_locks"][lock_key] = max(existing_backoff, new_backoff)
            task["next_retry_at"] = state["provider_locks"][lock_key]
        else:
            task["next_retry_at"] = new_backoff''')

app_file.write_text(content)

test_file = Path("tests/test_provider_wait_isolation.py")
test_content = test_file.read_text()
test_content = test_content.replace(
'''                # manually push next_retry_at into the past for task-1 to test lock expiry
                state["provider_locks"]["pool-A:openai"] = time.time() - 10''',
'''                # manually push next_retry_at into the past for task-1 to test lock expiry
                state["provider_locks"]["pool-A:openai"] = time.time() - 10
                state["tasks"]["task-1"]["next_retry_at"] = time.time() - 10''')
test_file.write_text(test_content)
