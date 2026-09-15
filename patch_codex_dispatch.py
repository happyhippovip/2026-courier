import sys
import re

with open('scripts/router_dispatch_codex.py', 'r') as f:
    code = f.read()

# We need to replace the `if r_payload.get("verdict") == "BLOCKED_RATE_LIMIT":` block
old_block = """    if r_payload.get("verdict") == "BLOCKED_RATE_LIMIT":
        print("[FAIL] Codex rate limited!")
        sys.exit(3)"""

new_block = """    if r_payload.get("verdict") == "BLOCKED_RATE_LIMIT":
        print("[FAIL] Codex rate limited!")
        authority.release_scopes(owner_id=owner_id, task_id=task_id, scopes=[scope_str], generation=gen)
        print("[STEP 8] Released scope after rate limit.")
        
        # Mark Codex unavailable
        try:
            from scripts.live_worker_registry import LiveWorkerRegistry, WorkerState
            from pathlib import Path
            reg = LiveWorkerRegistry(Path('.'))
            w = reg.get_worker('CODEX')
            if w:
                w.state = WorkerState.PROVIDER_ERROR.value
                reg._save_worker_record(w)
                print("Marked CODEX unavailable (PROVIDER_ERROR).")
        except Exception as e:
            print(f"Failed to mark CODEX unavailable: {e}")
            
        sys.exit(3)"""

code = code.replace(old_block, new_block)

# And make sure scope is released on any bridge failure
old_bridge_fail = """    if bridge_result.returncode != 0:
        print(f"[FAIL] Bridge exited with code {bridge_result.returncode}")
        if bridge_result.stderr:
            print(bridge_result.stderr)
        sys.exit(1)"""

new_bridge_fail = """    if bridge_result.returncode != 0:
        print(f"[FAIL] Bridge exited with code {bridge_result.returncode}")
        if bridge_result.stderr:
            print(bridge_result.stderr)
        authority.release_scopes(owner_id=owner_id, task_id=task_id, scopes=[scope_str], generation=gen)
        # Check if rate limited from stderr
        if "rate limit" in str(bridge_result.stderr).lower():
            try:
                from scripts.live_worker_registry import LiveWorkerRegistry, WorkerState
                from pathlib import Path
                reg = LiveWorkerRegistry(Path('.'))
                w = reg.get_worker('CODEX')
                if w:
                    w.state = WorkerState.PROVIDER_ERROR.value
                    reg._save_worker_record(w)
            except: pass
            sys.exit(3)
        sys.exit(1)"""

code = code.replace(old_bridge_fail, new_bridge_fail)

with open('scripts/router_dispatch_codex.py', 'w') as f:
    f.write(code)
