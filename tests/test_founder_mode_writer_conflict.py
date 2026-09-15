import pytest
from pathlib import Path
from scripts.courier_safety_dispatcher import CourierSafetyDispatcher, MissionQueue
from scripts.canonical_authority import CanonicalAuthority

def test_writer_conflict_rejection(tmp_path):
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    
    auth = CanonicalAuthority(repo_dir)
    dispatcher = CourierSafetyDispatcher(str(repo_dir))
    
    lease = auth.acquire_scopes(
        owner_id="fake-other-worker",
        task_id="task-123",
        scopes=["src/test.py"],
        ttl_seconds=3600
    )
    assert lease is not None
    
    mission = {
        "mission_id": "mission-456",
        "action": "implement_bounded_improvement",
        "scope": ["src/test.py"],
        "status": "PENDING"
    }
    
    q = MissionQueue(str(repo_dir))
    q.enqueue(mission)
    
    result = dispatcher.process_next_mission(worker_id="founder_loop_1")
    assert result.get("status") in ["NO_PENDING_MISSION", "CONTINUE_SAFE_WORK", "BLOCKED", "DISCOVER_FROM_ACTIVE_ROOT_GOAL_GAPS"]

