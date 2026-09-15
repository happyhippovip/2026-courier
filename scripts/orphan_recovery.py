from typing import Dict, Any, List
from pathlib import Path
import json
import os
import datetime

from scripts.canonical_authority import is_pid_alive
from scripts.resource_policy import TaskLeaseManager
from scripts.courier_safety_dispatcher import CourierSafetyDispatcher, MissionQueue

def recover_orphans(workspace_dir: Path):
    dispatcher = CourierSafetyDispatcher(workspace_dir)
    queue = dispatcher.mission_queue
    lease_mgr = dispatcher.lease_manager

    # 1. Inspect existing leases
    reclaimed_leases = []
    for lock_file in lease_mgr.locks_dir.glob("*.lease"):
        with open(lock_file, "r") as f:
            try:
                lease_data = json.load(f)
            except:
                continue

        pid = lease_data.get("owner_pid")
        if not pid:
            continue
            
        if not is_pid_alive(pid):
            # HOLDER IS DEAD
            # Check if this task hash exists in missions
            task_hash = lease_data.get("task_hash")
            
            # Find the mission
            all_missions = queue.read_all()
            mission = next((m for m in all_missions if m.get("task_hash") == task_hash and m.get("status") == "CLAIMED"), None)
            
            if mission:
                # Determine EFFECT STATE
                # We can check if result_reference exists or if task envelope has a result
                target_agent = mission.get("preferred_agent", "UNKNOWN").lower()
                result_file = workspace_dir / "events" / "task-envelopes" / f"result_{target_agent}_{task_hash}.json"
                
                if not result_file.exists():
                    # DEAD HOLDER + NO EFFECT
                    # -> reclaim old lease
                    lock_file.unlink(missing_ok=True)
                    # -> resume SAME logical task (set back to PENDING)
                    queue.transition(mission["mission_id"], "PENDING", claimed_by=None)
                    
                else:
                    try:
                        with open(result_file, "r") as rf:
                            result_data = json.load(rf)
                        payload = result_data.get("payload", {})
                        if payload.get("status") == "COMPLETED" or payload.get("verdict"):
                            # DEAD HOLDER + CONFIRMED EFFECT
                            # -> reclaim for reconciliation
                            lock_file.unlink(missing_ok=True)
                            # -> NO replay -> Verify/Customs (set to PENDING_VERIFY)
                            # Wait, the result exists, so we should transition to PENDING_VERIFY or just inject the result
                            # Actually, we can just transition to PENDING_VERIFY
                            queue.transition(mission["mission_id"], "PENDING_VERIFY", result_reference=str(result_file))
                        else:
                            # AMBIGUOUS EFFECT
                            lock_file.unlink(missing_ok=True)
                            queue.transition(mission["mission_id"], "FAILED", result_reference="AMBIGUOUS_EFFECT_QUARANTINE")
                    except Exception:
                        # AMBIGUOUS EFFECT
                        lock_file.unlink(missing_ok=True)
                        queue.transition(mission["mission_id"], "FAILED", result_reference="AMBIGUOUS_EFFECT_QUARANTINE")
            else:
                # No mission, just stale lease
                lock_file.unlink(missing_ok=True)

