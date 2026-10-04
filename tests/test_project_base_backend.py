import sys
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from project_base_backend import ProjectBaseBackend, ProjectBaseState

class MockEngine:
    def __init__(self):
        self.raw_safe_state = "sha:a1b2c3d on master"
        self.completed = []
        self.writers = []
        self.blockers = []
        self.recoveries = []
        self.next_work = []
        
    def get_raw_safe_state(self): return self.raw_safe_state
    def get_completed_workkeys(self): return self.completed
    def get_active_writers(self): return self.writers
    def get_raw_blockers(self): return self.blockers
    def get_recent_recoveries(self): return self.recoveries
    def get_next_executable_work(self): return self.next_work

def test_project_base_empty_state():
    engine = MockEngine()
    backend = ProjectBaseBackend(engine)
    state = backend.get_project_base_state()
    
    # Asserting we don't expose SHAs to normal users directly in the high-level string
    assert "a1b2c3d" not in state.current_safe_state
    assert state.current_safe_state == "System is stable at the last known good configuration."
    assert state.last_verified_progress == "No verified progress yet."
    assert state.what_courier_is_doing == "Courier is idle."
    assert state.what_needs_the_user == []

def test_project_base_active_state():
    engine = MockEngine()
    engine.completed = ["Install Setup", "Database Config"]
    engine.writers = ["Worker-1"]
    engine.blockers = ["AUTH_FAILURE", "UNKNOWN_ERROR"]
    engine.recoveries = [{"workkey": "Migration"}]
    engine.next_work = ["Run Integration Tests"]
    
    backend = ProjectBaseBackend(engine)
    state = backend.get_project_base_state()
    
    assert "Install Setup, Database Config" in state.last_verified_progress
    assert "Courier is currently executing tasks" in state.what_courier_is_doing
    
    assert len(state.what_needs_the_user) == 2
    assert "re-authenticate" in state.what_needs_the_user[0]
    assert "UNKNOWN_ERROR" in state.what_needs_the_user[1]
    
    assert "Safely recovered task Migration" in state.what_recovered_after_interruption[0]
    assert state.what_is_ready_next == ["Run Integration Tests"]
