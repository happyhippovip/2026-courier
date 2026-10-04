import pytest
import json
import hashlib
from pathlib import Path
from scripts.validate_chief_relay import validate_event, canonical_hash, fail

def create_base_event(event_type="RESULT"):
    payload = {}
    if event_type == "RESULT":
        payload = {
            "source_agent": "ANTIGRAVITY",
            "summary": "done",
            "verified_facts": [],
            "files_changed": [],
            "commits": [],
            "test_results": [],
            "cost": 0,
            "human_gate": False,
            "safe_next_state": "NEW"
        }
    elif event_type == "COMMAND":
        payload = {
            "target_agent": "ANTIGRAVITY",
            "one_next_command": "do it",
            "allowed_scope": "all",
            "human_gate_policy": "none",
            "cost_policy": "zero"
        }
        
    event = {
        "schema_version": "2.0",
        "message_id": "msg-123",
        "task_id": "task-abc",
        "correlation_id": "corr-456",
        "parent_id": None,
        "source": "antigravity" if event_type == "RESULT" else "chief",
        "destination": "chief" if event_type == "RESULT" else "antigravity",
        "type": event_type,
        "status": "DONE" if event_type == "RESULT" else "NEW",
        "created_at": "2026-09-30T00:00:00Z",
        "payload": payload,
        "payload_hash": canonical_hash(payload),
        "max_iterations": 1
    }
    return event

def write_json(path, data):
    path.write_text(json.dumps(data), encoding="utf-8")

def test_validate_chief_relay_success_result(tmp_path):
    event = create_base_event("RESULT")
    f = tmp_path / "event.json"
    write_json(f, event)
    
    res = validate_event(f)
    assert res["message_id"] == "msg-123"

def test_validate_chief_relay_success_command(tmp_path):
    event = create_base_event("COMMAND")
    f = tmp_path / "event.json"
    write_json(f, event)
    
    res = validate_event(f)
    assert res["message_id"] == "msg-123"

def test_validate_chief_relay_missing_file(tmp_path):
    with pytest.raises(SystemExit, match="VALIDATION_ERROR: File does not exist"):
        validate_event(tmp_path / "nonexistent.json")

def test_validate_chief_relay_invalid_json(tmp_path):
    f = tmp_path / "event.json"
    f.write_text("invalid json")
    with pytest.raises(SystemExit, match="VALIDATION_ERROR: Invalid JSON"):
        validate_event(f)

def test_validate_chief_relay_envelope_mismatch(tmp_path):
    event = create_base_event("RESULT")
    del event["task_id"]
    f = tmp_path / "event.json"
    write_json(f, event)
    
    with pytest.raises(SystemExit, match="VALIDATION_ERROR: Envelope fields mismatch"):
        validate_event(f)

def test_validate_chief_relay_unsupported_version(tmp_path):
    event = create_base_event("RESULT")
    event["schema_version"] = "1.0"
    f = tmp_path / "event.json"
    write_json(f, event)
    
    with pytest.raises(SystemExit, match="VALIDATION_ERROR: Unsupported schema_version: 1.0"):
        validate_event(f)

def test_validate_chief_relay_bad_payload_hash(tmp_path):
    event = create_base_event("RESULT")
    event["payload_hash"] = "badhash"
    f = tmp_path / "event.json"
    write_json(f, event)
    
    with pytest.raises(SystemExit, match="VALIDATION_ERROR: payload_hash mismatch"):
        validate_event(f)

def test_validate_chief_relay_duplicate_message_id(tmp_path):
    event = create_base_event("RESULT")
    f = tmp_path / "event.json"
    write_json(f, event)
    
    incoming = tmp_path / "incoming"
    incoming.mkdir()
    existing = incoming / "old.json"
    write_json(existing, event) # Same message_id
    
    with pytest.raises(SystemExit, match="VALIDATION_ERROR: duplicate message_id 'msg-123' already exists"):
        validate_event(f, incoming_dir=incoming)

def test_validate_chief_relay_invalid_route(tmp_path):
    event = create_base_event("RESULT")
    event["source"] = "chief" # Invalid for RESULT
    f = tmp_path / "event.json"
    write_json(f, event)
    
    with pytest.raises(SystemExit, match="VALIDATION_ERROR: Invalid route for RESULT"):
        validate_event(f)
