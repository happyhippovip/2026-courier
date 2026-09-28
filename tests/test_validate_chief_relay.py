import pytest
import json
from pathlib import Path

def test_validate_chief_relay_result(tmp_path):
    import scripts.validate_chief_relay as script
    
    file_path = tmp_path / "result.json"
    
    payload = {
        "source_agent": "ANTIGRAVITY",
        "summary": "OK",
        "verified_facts": [],
        "files_changed": [],
        "commits": [],
        "test_results": [],
        "cost": 0,
        "human_gate": None,
        "safe_next_state": "DONE"
    }
    
    data = {
        "schema_version": "2.0",
        "message_id": "msg-123",
        "task_id": "t-123",
        "correlation_id": "c-123",
        "parent_id": None,
        "source": "antigravity",
        "destination": "chief",
        "type": "RESULT",
        "status": "DONE",
        "created_at": "now",
        "payload": payload,
        "payload_hash": script.canonical_hash(payload),
        "max_iterations": 1
    }
    
    file_path.write_text(json.dumps(data))
    
    # Should not raise
    validated = script.validate_event(file_path)
    assert validated["message_id"] == "msg-123"

def test_validate_chief_relay_command(tmp_path):
    import scripts.validate_chief_relay as script
    
    file_path = tmp_path / "command.json"
    
    payload = {
        "target_agent": "ANTIGRAVITY",
        "one_next_command": "Run tests",
        "allowed_scope": [],
        "human_gate_policy": "NONE",
        "cost_policy": "DEFAULT"
    }
    
    data = {
        "schema_version": "2.0",
        "message_id": "cmd-123",
        "task_id": "t-123",
        "correlation_id": "c-123",
        "parent_id": None,
        "source": "chief",
        "destination": "antigravity",
        "type": "COMMAND",
        "status": "NEW",
        "created_at": "now",
        "payload": payload,
        "payload_hash": script.canonical_hash(payload),
        "max_iterations": 1
    }
    
    file_path.write_text(json.dumps(data))
    
    # Should not raise
    validated = script.validate_event(file_path)
    assert validated["type"] == "COMMAND"

def test_validate_chief_relay_invalid_hash(tmp_path):
    import scripts.validate_chief_relay as script
    
    file_path = tmp_path / "command.json"
    
    payload = {
        "target_agent": "ANTIGRAVITY",
        "one_next_command": "Run tests",
        "allowed_scope": [],
        "human_gate_policy": "NONE",
        "cost_policy": "DEFAULT"
    }
    
    data = {
        "schema_version": "2.0",
        "message_id": "cmd-123",
        "task_id": "t-123",
        "correlation_id": "c-123",
        "parent_id": None,
        "source": "chief",
        "destination": "antigravity",
        "type": "COMMAND",
        "status": "NEW",
        "created_at": "now",
        "payload": payload,
        "payload_hash": "bad-hash",
        "max_iterations": 1
    }
    
    file_path.write_text(json.dumps(data))
    
    with pytest.raises(SystemExit, match="payload_hash mismatch"):
        script.validate_event(file_path)

