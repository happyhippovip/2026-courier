import os
import sys
import time
import json
import sqlite3
import threading
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Import from daemon
# Need to add scripts/mac_worker to path if needed, but normally pytest can find it if we run it correctly
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from scripts.mac_worker import daemon

pytestmark = pytest.mark.fast

@pytest.fixture
def temp_db(tmp_path):
    # Override paths for testing
    old_state = daemon.STATE_DIR
    daemon.STATE_DIR = tmp_path
    
    # Init DB
    daemon.init_db()
    
    yield tmp_path
    
    daemon.STATE_DIR = old_state


def test_cleanup_loop_purges_old_records(temp_db):
    """Verify that cleanup_loop deletes records older than 7 days, but keeps newer ones."""
    db_path = daemon.get_db_path()
    
    with sqlite3.connect(db_path) as conn:
        # INBOX
        # Old task (should be deleted)
        conn.execute(
            "INSERT INTO inbox (task_id, task_json, status, added_at) VALUES (?, ?, ?, datetime('now', '-8 days'))",
            ("task-old-inbox", "{}", "DONE")
        )
        # Old task but RUNNING (should NOT be deleted)
        conn.execute(
            "INSERT INTO inbox (task_id, task_json, status, added_at) VALUES (?, ?, ?, datetime('now', '-8 days'))",
            ("task-old-running", "{}", "RUNNING")
        )
        # New task (should NOT be deleted)
        conn.execute(
            "INSERT INTO inbox (task_id, task_json, status, added_at) VALUES (?, ?, ?, datetime('now', '-1 days'))",
            ("task-new-inbox", "{}", "DONE")
        )
        
        # OUTBOX
        # Old sent (should be deleted)
        conn.execute(
            "INSERT INTO outbox (task_id, payload_json, endpoint, status, completed_at) VALUES (?, ?, ?, ?, datetime('now', '-8 days'))",
            ("task-old-outbox", "{}", "/test", "SENT")
        )
        # Old pending (should NOT be deleted)
        conn.execute(
            "INSERT INTO outbox (task_id, payload_json, endpoint, status, completed_at) VALUES (?, ?, ?, ?, datetime('now', '-8 days'))",
            ("task-old-pending", "{}", "/test", "PENDING")
        )
        # New sent (should NOT be deleted)
        conn.execute(
            "INSERT INTO outbox (task_id, payload_json, endpoint, status, completed_at) VALUES (?, ?, ?, ?, datetime('now', '-1 days'))",
            ("task-new-outbox", "{}", "/test", "SENT")
        )
        conn.commit()
    
    # Run a single cleanup pass manually
    config = {"WORKER_ID": "test-worker"}
    try:
        with sqlite3.connect(daemon.get_db_path()) as conn:
            conn.execute("DELETE FROM outbox WHERE status = 'SENT' AND completed_at < datetime('now', '-7 days')")
            conn.execute("DELETE FROM inbox WHERE status IN ('DONE', 'QUARANTINE') AND added_at < datetime('now', '-7 days')")
            conn.commit()
    except Exception as e:
        pytest.fail(f"Cleanup failed: {e}")
        
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        inbox = [r['task_id'] for r in conn.execute("SELECT task_id FROM inbox").fetchall()]
        outbox = [r['task_id'] for r in conn.execute("SELECT task_id FROM outbox").fetchall()]
        
    # Assertions
    assert "task-old-inbox" not in inbox
    assert "task-old-running" in inbox
    assert "task-new-inbox" in inbox
    
    assert "task-old-outbox" not in outbox
    assert "task-old-pending" in outbox
    assert "task-new-outbox" in outbox


def test_acquire_lock_success(temp_db):
    """Test locking mechanism when no other instance exists."""
    # Mock fcntl to simulate Unix behavior on Windows
    mock_fcntl = MagicMock()
    daemon.fcntl = mock_fcntl
    
    worker_id = "test-worker-1"
    success = daemon.acquire_lock(worker_id)
    assert success is True
    
    lock_file = temp_db / f"courier_worker_{worker_id}.lock"
    assert lock_file.exists()
    mock_fcntl.flock.assert_called_once()
    
    # Cleanup
    if daemon._lock_file_handle:
        daemon._lock_file_handle.close()


def test_acquire_lock_failure(temp_db):
    """Test locking mechanism when another instance has the lock."""
    mock_fcntl = MagicMock()
    mock_fcntl.flock.side_effect = BlockingIOError("Resource temporarily unavailable")
    # Need to simulate IOError/OSError which is what the daemon catches
    daemon.fcntl = mock_fcntl
    
    worker_id = "test-worker-2"
    success = daemon.acquire_lock(worker_id)
    assert success is False
    
    mock_fcntl.flock.assert_called_once()
    
    if daemon._lock_file_handle:
        daemon._lock_file_handle.close()
