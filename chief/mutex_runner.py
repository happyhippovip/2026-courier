"""
mutex_runner.py - Stdin/Stdout CLI Runner for Fenced Mutex Operations
Invoked by Node.js Studio Server or external workers via JSON input.
"""

import sys
import json
from courier.chief.fenced_mutex import FencedMutexManager

def main():
    try:
        raw_in = sys.stdin.read()
        payload = json.loads(raw_in) if raw_in.strip() else {}
        action = payload.get("action", "acquire")
        resource_id = payload.get("resource_id")

        if not resource_id:
            print(json.dumps({"success": False, "error": "Missing resource_id"}))
            sys.exit(1)

        mgr = FencedMutexManager()
        if action == "acquire":
            res = mgr.acquire(
                resource_id=resource_id,
                holder_id=payload.get("holder_id", "WORKER_DEFAULT"),
                holder_host=payload.get("holder_host", "WINDOWS"),
                holder_pid=payload.get("holder_pid"),
                ttl_seconds=int(payload.get("ttl_seconds", 30))
            )
        elif action == "renew":
            res = mgr.renew(
                resource_id=resource_id,
                holder_id=payload.get("holder_id", ""),
                lease_token=payload.get("lease_token", ""),
                ttl_seconds=int(payload.get("ttl_seconds", 30))
            )
        elif action == "release":
            res = mgr.release(
                resource_id=resource_id,
                holder_id=payload.get("holder_id", ""),
                lease_token=payload.get("lease_token", "")
            )
        elif action == "validate":
            res = mgr.validate_fencing_token(
                resource_id=resource_id,
                holder_id=payload.get("holder_id", ""),
                lease_token=payload.get("lease_token", ""),
                epoch=int(payload.get("epoch", 1))
            )
        elif action == "steal":
            res = mgr.attempt_steal(
                resource_id=resource_id,
                candidate_id=payload.get("candidate_id", "STEALER"),
                candidate_host=payload.get("candidate_host", "WINDOWS"),
                candidate_pid=payload.get("candidate_pid"),
                ttl_seconds=int(payload.get("ttl_seconds", 30)),
                grace_period_sec=float(payload.get("grace_period_sec", 2.0))
            )
        elif action == "inspect":
            lock = mgr.get_lock(resource_id)
            res = {"success": True, "lock": lock}
        else:
            res = {"success": False, "error": f"Unknown action {action}"}

        print(json.dumps({"success": True, "result": res}))
        sys.exit(0)
    except Exception as e:
        print(json.dumps({"success": False, "error": str(e)}))
        sys.exit(2)

if __name__ == "__main__":
    main()
