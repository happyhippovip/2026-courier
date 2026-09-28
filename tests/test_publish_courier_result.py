import pytest
import json
import os
import hashlib
from pathlib import Path

def payload_hash(payload: object) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

def test_publish_courier_result_success(tmp_path, monkeypatch):
    import scripts.publish_courier_result as script
    
    task_file = tmp_path / "task.json"
    task_data = {
        "task_id": "t-1",
        "correlation_id": "c-1",
        "message_id": "msg-task",
        "max_iterations": 1,
        "payload": {
            "result_request": "COURIER_CODEX_ACK"
        }
    }
    task_file.write_text(json.dumps(task_data))
    
    res_payload = {"result": "COURIER_CODEX_ACK"}
    res_data = {
        "schema_version": "2.0",
        "type": "RESULT",
        "status": "DONE",
        "source": "codex",
        "destination": "github_courier",
        "task_id": "t-1",
        "correlation_id": "c-1",
        "parent_id": "msg-task",
        "message_id": "msg-res",
        "max_iterations": 1,
        "payload": res_payload,
        "payload_hash": payload_hash(res_payload),
        "created_at": "now"
    }
    
    monkeypatch.setenv("CODEX_RESULT_JSON", json.dumps(res_data))
    
    processed_dir = tmp_path / "processed"
    processed_dir.mkdir()
    
    github_out = tmp_path / "github_out.txt"
    
    # Mock sys.argv
    monkeypatch.setattr("sys.argv", [
        "script",
        "--task", str(task_file),
        "--processed-dir", str(processed_dir),
        "--github-output", str(github_out)
    ])
    
    script.main()
    
    res_file = processed_dir / "msg-task.result.json"
    assert res_file.exists()
    assert "result_path=" in github_out.read_text()

def test_publish_courier_result_failure_hash(tmp_path, monkeypatch):
    import scripts.publish_courier_result as script
    
    task_file = tmp_path / "task.json"
    task_file.write_text(json.dumps({
        "task_id": "t-1",
        "correlation_id": "c-1",
        "message_id": "msg-task",
        "max_iterations": 1,
        "payload": {"result_request": "COURIER_CODEX_ACK"}
    }))
    
    res_data = {
        "schema_version": "2.0",
        "type": "RESULT",
        "status": "DONE",
        "source": "codex",
        "destination": "github_courier",
        "task_id": "t-1",
        "correlation_id": "c-1",
        "parent_id": "msg-task",
        "message_id": "msg-res",
        "max_iterations": 1,
        "payload": {"result": "COURIER_CODEX_ACK"},
        "payload_hash": "bad-hash",
        "created_at": "now"
    }
    monkeypatch.setenv("CODEX_RESULT_JSON", json.dumps(res_data))
    
    processed_dir = tmp_path / "processed"
    processed_dir.mkdir()
    github_out = tmp_path / "github_out.txt"
    
    monkeypatch.setattr("sys.argv", [
        "script", "--task", str(task_file),
        "--processed-dir", str(processed_dir), "--github-output", str(github_out)
    ])
    
    with pytest.raises(SystemExit, match="payload hash mismatch"):
        script.main()

