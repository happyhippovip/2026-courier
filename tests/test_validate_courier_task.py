import pytest
import json
import sys
from pathlib import Path
from unittest.mock import patch
from scripts.validate_courier_task import main, canonical_hash

def create_base_task():
    payload = {
        "result_request": "COURIER_CODEX_ACK"
    }
    
    task = {
        "schema_version": "2.0",
        "message_id": "msg-123",
        "task_id": "task-abc",
        "correlation_id": "corr-456",
        "parent_id": None,
        "source": "github_courier",
        "destination": "codex",
        "type": "TASK",
        "status": "NEW",
        "created_at": "2026-09-30T00:00:00Z",
        "payload": payload,
        "payload_hash": canonical_hash(payload),
        "max_iterations": 1
    }
    return task

def run_main(task_path, processed_dir):
    with patch("sys.argv", ["script.py", "--task", str(task_path), "--processed-dir", str(processed_dir)]):
        try:
            main()
            return None
        except SystemExit as e:
            return str(e)

def test_validate_courier_task_success(tmp_path, capsys):
    task = create_base_task()
    task_file = tmp_path / "task.json"
    task_file.write_text(json.dumps(task), encoding="utf-8")
    
    processed_dir = tmp_path / "processed"
    processed_dir.mkdir()
    
    err = run_main(task_file, processed_dir)
    assert err is None
    assert task_file.as_posix() in capsys.readouterr().out

def test_validate_courier_task_invalid_fields(tmp_path):
    task = create_base_task()
    del task["schema_version"]
    task_file = tmp_path / "task.json"
    task_file.write_text(json.dumps(task), encoding="utf-8")
    
    err = run_main(task_file, tmp_path)
    assert err == "invalid courier task: unexpected envelope fields"

def test_validate_courier_task_invalid_version(tmp_path):
    task = create_base_task()
    task["schema_version"] = "1.0"
    task_file = tmp_path / "task.json"
    task_file.write_text(json.dumps(task), encoding="utf-8")
    
    err = run_main(task_file, tmp_path)
    assert err == "invalid courier task: unsupported schema_version"

def test_validate_courier_task_invalid_type(tmp_path):
    task = create_base_task()
    task["type"] = "RESULT"
    task_file = tmp_path / "task.json"
    task_file.write_text(json.dumps(task), encoding="utf-8")
    
    err = run_main(task_file, tmp_path)
    assert err == "invalid courier task: message is not a new TASK"

def test_validate_courier_task_invalid_route(tmp_path):
    task = create_base_task()
    task["source"] = "chief"
    task_file = tmp_path / "task.json"
    task_file.write_text(json.dumps(task), encoding="utf-8")
    
    err = run_main(task_file, tmp_path)
    assert err == "invalid courier task: unexpected route"

def test_validate_courier_task_missing_identity(tmp_path):
    task = create_base_task()
    task["message_id"] = None
    task_file = tmp_path / "task.json"
    task_file.write_text(json.dumps(task), encoding="utf-8")
    
    err = run_main(task_file, tmp_path)
    assert err == "invalid courier task: missing identity field"

def test_validate_courier_task_parent_not_null(tmp_path):
    task = create_base_task()
    task["parent_id"] = "some-parent"
    task_file = tmp_path / "task.json"
    task_file.write_text(json.dumps(task), encoding="utf-8")
    
    err = run_main(task_file, tmp_path)
    assert err == "invalid courier task: TASK parent_id must be null"

def test_validate_courier_task_invalid_iterations(tmp_path):
    task = create_base_task()
    task["max_iterations"] = 5
    task_file = tmp_path / "task.json"
    task_file.write_text(json.dumps(task), encoding="utf-8")
    
    err = run_main(task_file, tmp_path)
    assert err == "invalid courier task: max_iterations must be exactly 1"

def test_validate_courier_task_hash_mismatch(tmp_path):
    task = create_base_task()
    task["payload_hash"] = "bad"
    task_file = tmp_path / "task.json"
    task_file.write_text(json.dumps(task), encoding="utf-8")
    
    err = run_main(task_file, tmp_path)
    assert err == "invalid courier task: payload_hash mismatch"

def test_validate_courier_task_invalid_result_request(tmp_path):
    task = create_base_task()
    task["payload"]["result_request"] = "INVALID_ACK"
    task["payload_hash"] = canonical_hash(task["payload"])
    task_file = tmp_path / "task.json"
    task_file.write_text(json.dumps(task), encoding="utf-8")
    
    err = run_main(task_file, tmp_path)
    assert err == "invalid courier task: unsupported result_request"

def test_validate_courier_task_already_processed(tmp_path):
    task = create_base_task()
    task_file = tmp_path / "task.json"
    task_file.write_text(json.dumps(task), encoding="utf-8")
    
    processed_dir = tmp_path / "processed"
    processed_dir.mkdir()
    
    processed_file = processed_dir / "old.json"
    processed_file.write_text(json.dumps({"message_id": "msg-123"}), encoding="utf-8")
    
    err = run_main(task_file, processed_dir)
    assert err == "invalid courier task: TASK already has a terminal record"
