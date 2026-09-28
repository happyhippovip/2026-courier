import pytest
import json
from pathlib import Path
from scripts.consume_chief_command import validate_command, REQUIRED_ENVELOPE

def test_validate_command_valid(tmp_path):
    incoming = tmp_path / "incoming"
    processed = tmp_path / "processed"
    incoming.mkdir()
    processed.mkdir()
    
    cmd_file = incoming / "cmd.json"
    
    payload = {
        "target_agent": "ANTIGRAVITY",
        "one_next_command": "echo test",
        "allowed_scope": ["2026-courier"],
        "human_gate_policy": "AUTO_IF_SAFE",
        "cost_policy": "ZERO_COST_ONLY"
    }
    
    import hashlib
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    payload_hash = hashlib.sha256(encoded).hexdigest()
    
    cmd_data = {
        "schema_version": "2.0",
        "message_id": "msg-1",
        "task_id": "task-1",
        "correlation_id": "corr-1",
        "parent_id": None,
        "source": "chief",
        "destination": "antigravity",
        "type": "COMMAND",
        "status": "NEW",
        "created_at": "2026-09-01T00:00:00Z",
        "payload": payload,
        "payload_hash": payload_hash,
        "max_iterations": 1
    }
    
    # Fill remaining fields
    for r in REQUIRED_ENVELOPE:
        if r not in cmd_data:
            cmd_data[r] = "dummy"
            
    valid, reason = validate_command(cmd_data, cmd_file, incoming, processed)
    assert valid, reason

def test_validate_command_invalid_scope(tmp_path):
    incoming = tmp_path / "incoming"
    processed = tmp_path / "processed"
    cmd_file = incoming / "cmd.json"
    
    payload = {
        "target_agent": "ANTIGRAVITY",
        "one_next_command": "echo test",
        "allowed_scope": ["UNAUTHORIZED_REPO"],
        "human_gate_policy": "AUTO_IF_SAFE",
        "cost_policy": "ZERO_COST_ONLY"
    }
    
    import hashlib
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    payload_hash = hashlib.sha256(encoded).hexdigest()
    
    cmd_data = {
        "schema_version": "2.0",
        "message_id": "msg-1",
        "task_id": "task-1",
        "correlation_id": "corr-1",
        "parent_id": None,
        "source": "chief",
        "destination": "antigravity",
        "type": "COMMAND",
        "status": "NEW",
        "created_at": "2026-09-01T00:00:00Z",
        "payload": payload,
        "payload_hash": payload_hash,
        "max_iterations": 1
    }
    
    valid, reason = validate_command(cmd_data, cmd_file, incoming, processed)
    assert not valid
    assert "Scope violation" in reason
