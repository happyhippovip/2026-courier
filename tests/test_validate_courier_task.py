import pytest
import json
from pathlib import Path

def test_validate_courier_task_success(tmp_path, monkeypatch):
    import scripts.validate_courier_task as script
    
    task_file = tmp_path / "task.json"
    processed_dir = tmp_path / "processed"
    processed_dir.mkdir()
    
    payload = {"result_request": "COURIER_CODEX_ACK"}
    payload_hash = script.canonical_hash(payload)
    
    task_data = {
        "schema_version": "2.0",
        "message_id": "msg-123",
        "task_id": "t-123",
        "correlation_id": "c-123",
        "parent_id": None,
        "source": "github_courier",
        "destination": "codex",
        "type": "TASK",
        "status": "NEW",
        "created_at": "now",
        "payload": payload,
        "payload_hash": payload_hash,
        "max_iterations": 1
    }
    
    task_file.write_text(json.dumps(task_data))
    
    monkeypatch.setattr("sys.argv", ["script", "--task", str(task_file), "--processed-dir", str(processed_dir)])
    
    # Should not raise
    script.main()

def test_validate_courier_task_duplicate(tmp_path, monkeypatch):
    import scripts.validate_courier_task as script
    
    task_file = tmp_path / "task.json"
    processed_dir = tmp_path / "processed"
    processed_dir.mkdir()
    
    payload = {"result_request": "COURIER_CODEX_ACK"}
    task_data = {
        "schema_version": "2.0",
        "message_id": "msg-123",
        "task_id": "t-123",
        "correlation_id": "c-123",
        "parent_id": None,
        "source": "github_courier",
        "destination": "codex",
        "type": "TASK",
        "status": "NEW",
        "created_at": "now",
        "payload": payload,
        "payload_hash": script.canonical_hash(payload),
        "max_iterations": 1
    }
    task_file.write_text(json.dumps(task_data))
    
    # Put a processed file in there
    processed_file = processed_dir / "old.json"
    processed_file.write_text(json.dumps({"message_id": "msg-123"}))
    
    monkeypatch.setattr("sys.argv", ["script", "--task", str(task_file), "--processed-dir", str(processed_dir)])
    
    with pytest.raises(SystemExit, match="TASK already has a terminal record"):
        script.main()

