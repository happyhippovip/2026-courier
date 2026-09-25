import os
from pathlib import Path

app_file = Path("server/app.py")
content = app_file.read_text()

content = content.replace('def _worker_is_eligible(state, task, worker_id):', '''def _worker_is_eligible(state, task, worker_id):
    worker = state.get("workers", {}).get(worker_id)
    if not worker: print("DEBUG: no worker"); return False
    if not worker.get("available", False): print("DEBUG: not available"); return False
    if worker.get("current_task"): print("DEBUG: current task"); return False
    
    quota_resource_id = state.get("worker_quota_pools", {}).get(worker_id, worker_id)
    worker_provider = str(worker.get("provider") or "unknown")
    lock_key = f"{quota_resource_id}:{worker_provider}"
    if time.time() <= state.get("provider_locks", {}).get(lock_key, 0):
        print(f"DEBUG: provider lock {lock_key} active")
        return False
        
    if _task_requires_human_gate(task): return False
    
    required_capabilities = _string_list(task.get("required_capabilities"))
    required_authorities = _string_list(task.get("required_authorities"))
    worker_capabilities = _string_list(worker.get("capabilities"))
    worker_authorities = _string_list(worker.get("authorities"))
    
    if required_capabilities:
        if not set(required_capabilities).issubset(set(worker_capabilities)):
            print(f"DEBUG: cap mismatch req {required_capabilities} got {worker_capabilities}")
            return False
    elif not _legacy_target_matches(task, worker):
        print("DEBUG: legacy mismatch")
        return False
        
    return _resources_available(state, task)
    
def _worker_is_eligible_OLD(state, task, worker_id):''')
app_file.write_text(content)
