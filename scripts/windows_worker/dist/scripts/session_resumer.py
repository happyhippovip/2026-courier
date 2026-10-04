from typing import List, Dict, Any
from session_handoff import SessionHandoff, validate_handoff
import json

class EnvironmentContext:
    """Mock for retrieving the current ground truth state"""
    def __init__(self, current_sha: str, dirty_worktrees: List[str], active_writers: List[str], completed_work: List[str], active_blockers: List[str]):
        self.current_sha = current_sha
        self.dirty_worktrees = dirty_worktrees
        self.active_writers = active_writers
        self.completed_work = completed_work
        self.active_blockers = active_blockers

class SessionResumer:
    def __init__(self, handoff_json: str, env_context: EnvironmentContext):
        data = json.loads(handoff_json)
        validate_handoff(data)
        self.handoff = SessionHandoff(**data)
        self.env = env_context
        
        self.executable_work = []
        self.stale_credits = []
        self.active_blockers = []
        self.aborted = False
        self.abort_reason = ""
        
    def resume(self):
        # 1. Check for writer collision
        if self.env.active_writers:
            self.aborted = True
            self.abort_reason = f"Writer collision detected: {self.env.active_writers} are currently active."
            return
            
        # 2. Check for stale readiness (SHA mismatch)
        if self.handoff.current_sha != self.env.current_sha:
            self.stale_credits.append("Codebase SHA changed. Readiness credits from previous SHA are invalidated.")
            # Depending on policy, we might abort or just re-evaluate, but for now we flag it
            
        # 3. Check for lost blockers (combine handoff blockers with current env blockers)
        combined_blockers = set(self.handoff.blocked_paths + self.env.active_blockers)
        self.active_blockers = list(combined_blockers)
        if self.active_blockers:
            self.aborted = True
            self.abort_reason = f"Cannot continue. Active blockers: {self.active_blockers}"
            return
            
        # 4. Filter duplicate work
        # Work from handoff next_executable_work that is already in env.completed_work should be skipped
        for work in self.handoff.next_executable_work:
            if work not in self.env.completed_work:
                self.executable_work.append(work)

        # If everything passes, session is ready to continue
