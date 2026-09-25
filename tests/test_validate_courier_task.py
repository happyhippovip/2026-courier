import pytest
import os
import sys
import json
from unittest import mock
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from scripts import validate_courier_task

@pytest.fixture
def valid_task():
    payload = {"result_request": "COURIER_CODEX_ACK"}
    return {
        "schema_version": "2.0",
        "message_id": "m1",
        "task_id": "t1",
        "correlation_id": "c1",
        "parent_id": None,
        "source": "github_courier",
        "destination": "codex",
        "type": "TASK",
        "status": "NEW",
        "created_at": "now",
        "payload": payload,
        "payload_hash": validate_courier_task.canonical_hash(payload),
        "max_iterations": 1
    }

def test_canonical_hash():
    h = validate_courier_task.canonical_hash({"a": 1})
    assert h == "015abd7f5cc57a2dd94b7590f04ad8084273905ee33ec5cebeae62276a97f862"

def test_main_success(tmp_path, valid_task, capsys):
    task_file = tmp_path / "task.json"
    task_file.write_text(json.dumps(valid_task))
    
    processed_dir = tmp_path / "processed"
    processed_dir.mkdir()
    
    with mock.patch.object(sys, 'argv', ['prog', '--task', str(task_file), '--processed-dir', str(processed_dir)]):
        validate_courier_task.main()
            
    captured = capsys.readouterr()
    assert str(task_file.as_posix()) in captured.out

def test_main_invalid_fields(tmp_path, valid_task):
    valid_task.pop("type")
    task_file = tmp_path / "task.json"
    task_file.write_text(json.dumps(valid_task))
    
    with mock.patch.object(sys, 'argv', ['prog', '--task', str(task_file), '--processed-dir', 'p']):
        with pytest.raises(SystemExit) as exc:
            validate_courier_task.main()
        assert "unexpected envelope fields" in str(exc.value)

def test_main_mismatched_hash(tmp_path, valid_task):
    valid_task["payload_hash"] = "badhash"
    task_file = tmp_path / "task.json"
    task_file.write_text(json.dumps(valid_task))
    
    with mock.patch.object(sys, 'argv', ['prog', '--task', str(task_file), '--processed-dir', 'p']):
        with pytest.raises(SystemExit) as exc:
            validate_courier_task.main()
        assert "payload_hash mismatch" in str(exc.value)

def test_main_duplicate_record(tmp_path, valid_task):
    task_file = tmp_path / "task.json"
    task_file.write_text(json.dumps(valid_task))
    
    processed_dir = tmp_path / "processed"
    processed_dir.mkdir()
    
    existing = processed_dir / "old.json"
    existing.write_text(json.dumps({"parent_id": valid_task["message_id"]}))
    
    with mock.patch.object(sys, 'argv', ['prog', '--task', str(task_file), '--processed-dir', str(processed_dir)]):
        with pytest.raises(SystemExit) as exc:
            validate_courier_task.main()
        assert "TASK already has a terminal record" in str(exc.value)

