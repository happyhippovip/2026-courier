import pytest
import sys
import os
import json
import tempfile
import hashlib
from pathlib import Path
from unittest import mock

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from scripts import courier_github_dispatcher

def test_task_file_path():
    task = {"dispatch_id": "dispatch-123"}
    expected_digest = hashlib.sha256("dispatch-123".encode("utf-8")).hexdigest()
    expected_path = str(Path(tempfile.gettempdir()) / f"courier-github-{expected_digest}.json")
    assert courier_github_dispatcher.task_file_path(task) == expected_path

def test_task_file_path_missing_id():
    with pytest.raises(ValueError, match="missing dispatch_id"):
        courier_github_dispatcher.task_file_path({"some": "task"})

def test_persist_and_cleanup_task_file(tmp_path):
    with mock.patch("tempfile.gettempdir", return_value=str(tmp_path)):
        task = {"dispatch_id": "dispatch-abc", "info": "test"}
        file_path = courier_github_dispatcher.persist_task_file(task)
        
        # Verify it was written correctly
        assert os.path.exists(file_path)
        with open(file_path, "r") as f:
            written_task = json.load(f)
            assert written_task == task
            
        # Test file conflict with same task
        file_path2 = courier_github_dispatcher.persist_task_file(task)
        assert file_path == file_path2
        
        # Test cleanup
        state_path = Path(file_path).with_name(f"{Path(file_path).stem}.github-worker-state.json")
        state_path.write_text("{}")
        assert state_path.exists()
        
        courier_github_dispatcher.cleanup_task_files(file_path)
        assert not os.path.exists(file_path)
        assert not os.path.exists(state_path)

def test_persist_conflict_different_task(tmp_path):
    with mock.patch("tempfile.gettempdir", return_value=str(tmp_path)):
        task1 = {"dispatch_id": "dispatch-conflict", "info": "A"}
        task2 = {"dispatch_id": "dispatch-conflict", "info": "B"}
        courier_github_dispatcher.persist_task_file(task1)
        
        with pytest.raises(RuntimeError, match="conflicting TaskPacket already exists"):
            courier_github_dispatcher.persist_task_file(task2)

