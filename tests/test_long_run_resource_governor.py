import pytest
import os
import subprocess
from pathlib import Path
from scripts.useful_work_selection_engine import UsefulWorkSelectionEngine, AutonomyLifecycleState
from scripts.resource_policy import TaskLeaseManager

def test_resource_limits_and_quiescence(tmp_path):
    engine = UsefulWorkSelectionEngine(repo_dir=tmp_path)
    engine.completed_fps_file = tmp_path / "completed.json"
    
    lease_mgr = TaskLeaseManager(repo_dir=tmp_path)
    
    # 1. Assert no unbounded queue growth on empty queue
    result = engine.select_next_task([])
    assert result["lifecycle_state"] == AutonomyLifecycleState.QUEUE_EMPTY.value
    
    # 2. Acquire a lease to simulate MAX_MUTATING_WRITERS_PER_SCOPE=1
    acquired, reason, data = lease_mgr.acquire_lease("test_task", "hash1", "worker_1")
    assert acquired is True
    
    # Second acquisition fails (enforcing WRITER_LIMIT_VIOLATIONS=0)
    acquired2, reason2, data2 = lease_mgr.acquire_lease("test_task", "hash2", "worker_2")
    assert acquired2 is False
    
    # 3. Process check: ensure no runaway watchers in our control plane
    pid = os.getpid()
    out = subprocess.check_output(f"ps -o ppid= | grep -w {pid} || true", shell=True)
    children_count = len(out.strip().split(b'\n')) if out.strip() else 0
    assert children_count < 5
    
    # Cleanup
    lease_mgr.release_lease("test_task", "worker_1")

