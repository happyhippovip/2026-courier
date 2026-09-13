import json
import os
from pathlib import Path
from typing import Optional

def is_single_flight_locked(workspace_dir: Path, bypass_for_goal: Optional[str] = None) -> bool:
    """
    Returns True if an external root goal is ACTIVE and we are not part of it.
    This is the SINGLE-FLIGHT invariant guard for Courier V1.
    """
    V1_CLOSED = os.environ.get("V1_CLOSED", "FALSE").upper() == "TRUE"
    if not V1_CLOSED and bypass_for_goal and ("v2" in bypass_for_goal.lower() or "company" in bypass_for_goal.lower()):
        return True # Block V2/company missions while V1 is not closed

    goals_path = Path(workspace_dir) / "events" / "founder-mode" / "goals.json"
    if not goals_path.exists():
        return False
    try:
        with open(goals_path, "r") as f:
            goals = json.load(f)
        active = [g for g in goals if g.get("status") == "ACTIVE"]
        if not active:
            return False
        
        active_goal = active[0]
        if bypass_for_goal and bypass_for_goal == active_goal.get("goal"):
            return False
            
        queue_path = Path(workspace_dir) / "events" / "mission-queue" / "queue.json"
        if queue_path.exists():
            with open(queue_path, "r") as f:
                q = json.load(f)
            missions = q.get("missions", [])
            has_live = any(
                m.get("goal") == active_goal["goal"] and 
                m.get("status") in ("PENDING", "RUNNING", "PENDING_VERIFY") 
                for m in missions
            )
            if has_live:
                return True
        return False
    except Exception:
        # UNCERTAIN CONTROL-PLANE STATE -> FAIL CLOSED
        return True
