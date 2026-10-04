import sys
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from session_handoff import SessionHandoff, generate_handoff
from session_resumer import SessionResumer, EnvironmentContext

def test_successful_resume_no_duplicates():
    # SESSION A
    handoff = SessionHandoff(
        project_identity="Courier",
        current_gate="GATE_1",
        current_sha="a1b2c3d",
        completed_work=["Task1"],
        accepted_evidence=[],
        active_writers=[],
        dirty_worktrees=[],
        blocked_paths=[],
        human_decisions=[],
        next_executable_work=["Task2", "Task3"],
        artifacts=[],
        safe_continuation_instructions="Run next work"
    )
    handoff_json = generate_handoff(handoff)
    
    # Environment truth state when SESSION B starts
    # Task2 was completed outside by another process!
    env = EnvironmentContext(
        current_sha="a1b2c3d",
        dirty_worktrees=[],
        active_writers=[],
        completed_work=["Task1", "Task2"], # Task2 already done
        active_blockers=[]
    )
    
    # SESSION B
    resumer = SessionResumer(handoff_json, env)
    resumer.resume()
    
    assert not resumer.aborted
    # Verify no duplicate work (Task2 is skipped)
    assert resumer.executable_work == ["Task3"]

def test_no_lost_blocker():
    handoff = SessionHandoff(
        project_identity="Courier",
        current_gate="GATE_1",
        current_sha="a1b2c3d",
        completed_work=[],
        accepted_evidence=[],
        active_writers=[],
        dirty_worktrees=[],
        blocked_paths=["DB_DOWN"], # Blocker in handoff
        human_decisions=[],
        next_executable_work=["Task1"],
        artifacts=[],
        safe_continuation_instructions=""
    )
    handoff_json = generate_handoff(handoff)
    
    env = EnvironmentContext(
        current_sha="a1b2c3d",
        dirty_worktrees=[],
        active_writers=[],
        completed_work=[],
        active_blockers=["API_LIMIT"] # Additional blocker in env
    )
    
    resumer = SessionResumer(handoff_json, env)
    resumer.resume()
    
    assert resumer.aborted
    # Verify both blockers are retained
    assert "DB_DOWN" in resumer.active_blockers
    assert "API_LIMIT" in resumer.active_blockers

def test_no_writer_collision():
    handoff = SessionHandoff(
        project_identity="Courier",
        current_gate="GATE_1",
        current_sha="a1b2c3d",
        completed_work=[],
        accepted_evidence=[],
        active_writers=[],
        dirty_worktrees=[],
        blocked_paths=[],
        human_decisions=[],
        next_executable_work=["Task1"],
        artifacts=[],
        safe_continuation_instructions=""
    )
    handoff_json = generate_handoff(handoff)
    
    # Another writer is active!
    env = EnvironmentContext(
        current_sha="a1b2c3d",
        dirty_worktrees=[],
        active_writers=["Worker_B"],
        completed_work=[],
        active_blockers=[]
    )
    
    resumer = SessionResumer(handoff_json, env)
    resumer.resume()
    
    assert resumer.aborted
    assert "Writer collision detected" in resumer.abort_reason

def test_no_stale_readiness_credit():
    handoff = SessionHandoff(
        project_identity="Courier",
        current_gate="GATE_1",
        current_sha="a1b2c3d", # Handoff SHA
        completed_work=[],
        accepted_evidence=["Tests_Passed"],
        active_writers=[],
        dirty_worktrees=[],
        blocked_paths=[],
        human_decisions=[],
        next_executable_work=["Deploy"],
        artifacts=[],
        safe_continuation_instructions=""
    )
    handoff_json = generate_handoff(handoff)
    
    env = EnvironmentContext(
        current_sha="sha456", # ENV SHA CHANGED!
        dirty_worktrees=[],
        active_writers=[],
        completed_work=[],
        active_blockers=[]
    )
    
    resumer = SessionResumer(handoff_json, env)
    resumer.resume()
    
    assert len(resumer.stale_credits) > 0
    assert "Codebase SHA changed" in resumer.stale_credits[0]
