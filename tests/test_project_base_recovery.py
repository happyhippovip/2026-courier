import sys
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from project_base_backend import ProjectBaseBackend, ProjectBaseState

class DurableEvidenceEngine:
    """
    Mocks the engine recovering strictly from durable disk state,
    not from volatile memory.
    """
    def __init__(self, disk_state):
        self.disk = disk_state

    def get_raw_safe_state(self): return self.disk.get("safe_state", "unknown")
    def get_completed_workkeys(self): return self.disk.get("completed", [])
    
    def get_active_writers(self): 
        # Crucially: Even if the agent disappeared from memory, if it held a lock on disk,
        # it is technically still recorded as active/crashed until cleanly rolled back.
        return self.disk.get("locks", [])
        
    def get_raw_blockers(self): return self.disk.get("blockers", [])
    def get_recent_recoveries(self): return self.disk.get("recoveries", [])
    def get_next_executable_work(self): return self.disk.get("next_work", [])

def test_recovery_after_agent_crash_does_not_say_done():
    # Simulate: Agent was running "H1", but crashed/disappeared.
    # The disk state shows "H1" is NOT in completed, and the lock is still there or abandoned.
    disk_state_after_crash = {
        "safe_state": "sha:111",
        "completed": [], # NOT done!
        "locks": ["abandoned_agent_lock_for_H1"],
        "blockers": [],
        "next_work": ["H1"]
    }
    
    engine = DurableEvidenceEngine(disk_state_after_crash)
    backend = ProjectBaseBackend(engine)
    state = backend.get_project_base_state()
    
    # Assert it does NOT say "done"
    assert state.last_verified_progress == "No verified progress yet."
    assert "abandoned_agent_lock" not in state.last_verified_progress
    assert state.what_is_ready_next == ["H1"]
    
def test_recovery_after_windows_reboot_preserves_progress():
    disk_state_after_reboot = {
        "safe_state": "sha:222",
        "completed": ["H1", "H2"], # H1 and H2 safely made it to disk before reboot
        "locks": [],
        "blockers": [],
        "next_work": ["H3"]
    }
    
    engine = DurableEvidenceEngine(disk_state_after_reboot)
    backend = ProjectBaseBackend(engine)
    state = backend.get_project_base_state()
    
    assert "H1, H2" in state.last_verified_progress
    assert state.what_courier_is_doing == "Courier is idle."
    assert state.what_is_ready_next == ["H3"]

def test_recovery_after_network_interruption():
    # Simulate a network interruption that resulted in a blocker
    disk_state_after_network_drop = {
        "safe_state": "sha:333",
        "completed": ["H1"],
        "locks": [],
        "blockers": ["NETWORK_TIMEOUT"],
        "next_work": ["H2"]
    }
    
    engine = DurableEvidenceEngine(disk_state_after_network_drop)
    backend = ProjectBaseBackend(engine)
    state = backend.get_project_base_state()
    
    assert "NETWORK_TIMEOUT" in state.what_needs_the_user[0]
