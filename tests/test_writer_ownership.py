import sys
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from writer_ownership import WriterOwnershipRecord, WriterOwnershipManager

def test_writer_acquire_and_heartbeat():
    manager = WriterOwnershipManager(stale_timeout_seconds=300)
    
    # Writer A acquires
    assert manager.acquire_ownership("build", "writer_A", "/src/project", "sha-1", 1000) is True
    
    # Writer B attempts to acquire, but A is active (not stale)
    assert manager.acquire_ownership("build", "writer_B", "/src/project", "sha-1", 1100) is False
    
    # Writer A updates heartbeat and dirty files
    manager.update_heartbeat("/src/project", "writer_A", 1200, ["src/main.py"])
    assert manager._records["/src/project"].dirty_files == ["src/main.py"]

def test_stale_writer_is_stolen():
    manager = WriterOwnershipManager(stale_timeout_seconds=300)
    
    # Writer A acquires at time 1000
    assert manager.acquire_ownership("build", "writer_A", "/src/project", "sha-1", 1000) is True
    
    # Writer B attempts to acquire at time 1400 (400 seconds later). A is now STALE.
    # Therefore, B is allowed to steal the lock.
    assert manager.acquire_ownership("build", "writer_B", "/src/project", "sha-1", 1400) is True
    
    # Verify B holds it
    assert manager._records["/src/project"].writer_id == "writer_B"

def test_released_writer_is_acquired():
    manager = WriterOwnershipManager(stale_timeout_seconds=300)
    
    assert manager.acquire_ownership("build", "writer_A", "/src/project", "sha-1", 1000) is True
    manager.release_ownership("/src/project", "writer_A")
    
    # Writer B acquires immediately (time 1001), no need to wait for stale timeout because it was explicitly released
    assert manager.acquire_ownership("build", "writer_B", "/src/project", "sha-1", 1001) is True
    assert manager._records["/src/project"].writer_id == "writer_B"

def test_unauthorized_heartbeat_fails():
    manager = WriterOwnershipManager(stale_timeout_seconds=300)
    manager.acquire_ownership("build", "writer_A", "/src/project", "sha-1", 1000)
    
    with pytest.raises(ValueError, match="does not own"):
        manager.update_heartbeat("/src/project", "writer_B", 1100, [])
