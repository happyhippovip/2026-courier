from dataclasses import dataclass
from typing import List, Optional

@dataclass
class ProjectBaseState:
    current_safe_state: str
    last_verified_progress: str
    what_courier_is_doing: str
    what_needs_the_user: List[str]
    what_recovered_after_interruption: List[str]
    what_is_ready_next: List[str]

class ProjectBaseBackend:
    """
    Customer-facing API over Courier's internals. 
    Exposes high-level intent and progress without requiring the user
    to understand raw SHAs, PR states, or low-level handoff schemas.
    """
    
    def __init__(self, internal_engine_client):
        """
        internal_engine_client: A mock/dependency that queries the raw database/state.
        """
        self.engine = internal_engine_client

    def get_project_base_state(self) -> ProjectBaseState:
        # Translate low-level verified commit state into a human-readable safe state
        raw_state = self.engine.get_raw_safe_state() # e.g. "sha:a1b2c3d on master"
        current_safe_state = f"System is stable at the last known good configuration."
        
        # Translate internal workkeys to high-level progress
        completed_keys = self.engine.get_completed_workkeys()
        last_progress = "No verified progress yet."
        if completed_keys:
            last_progress = f"Successfully completed: {', '.join(completed_keys)}"
            
        # Determine what the agent is currently mutating
        active_writers = self.engine.get_active_writers()
        if active_writers:
            doing = f"Courier is currently executing tasks (Active writers: {len(active_writers)})."
        else:
            doing = "Courier is idle."
            
        # Translate blockers into user-actionable requests
        raw_blockers = self.engine.get_raw_blockers()
        needs_user = []
        for blocker in raw_blockers:
            if "QUOTA" in blocker:
                needs_user.append("Please approve a quota increase to continue.")
            elif "AUTH" in blocker:
                needs_user.append("Please re-authenticate the cloud provider.")
            elif "MANUAL_TEST" in blocker:
                needs_user.append("Please manually verify the latest deployment.")
            else:
                needs_user.append(f"Requires user input to resolve blocker: {blocker}")
                
        # Surface recent crash recoveries
        recoveries = self.engine.get_recent_recoveries()
        recovered_list = []
        for rec in recoveries:
            recovered_list.append(f"Safely recovered task {rec['workkey']} after unexpected interruption.")
            
        # Translate next executable work queue
        next_work = self.engine.get_next_executable_work()
        
        return ProjectBaseState(
            current_safe_state=current_safe_state,
            last_verified_progress=last_progress,
            what_courier_is_doing=doing,
            what_needs_the_user=needs_user,
            what_recovered_after_interruption=recovered_list,
            what_is_ready_next=next_work
        )
