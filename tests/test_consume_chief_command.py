import json
import os
import pytest
from pathlib import Path
from unittest import mock

from scripts import consume_chief_command


def test_canonical_hash():
    payload = {"a": 1, "b": "test"}
    # Expected: '{"a":1,"b":"test"}' -> sha256
    expected_str = '{"a":1,"b":"test"}'.encode('utf-8')
    import hashlib
    expected_hash = hashlib.sha256(expected_str).hexdigest()
    assert consume_chief_command.canonical_hash(payload) == expected_hash


def test_check_dedupe(tmp_path):
    proc_dir = tmp_path / "processed"
    proc_dir.mkdir()
    
    # 1. No files -> True
    assert consume_chief_command.check_dedupe("msg-1", [proc_dir]) is True
    
    # 2. Add irrelevant file -> True
    (proc_dir / "irrelevant.json").write_text(json.dumps({"message_id": "other"}))
    assert consume_chief_command.check_dedupe("msg-1", [proc_dir]) is True
    
    # 3. Add file with msg-1 -> False
    (proc_dir / "match_msg.json").write_text(json.dumps({"message_id": "msg-1"}))
    assert consume_chief_command.check_dedupe("msg-1", [proc_dir]) is False
    
    # 4. Add file with parent_id msg-2 -> False for msg-2
    (proc_dir / "match_parent.json").write_text(json.dumps({"parent_id": "msg-2"}))
    assert consume_chief_command.check_dedupe("msg-2", [proc_dir]) is False
    
    # 5. Exclude path -> True
    exclude_file = proc_dir / "exclude.json"
    exclude_file.write_text(json.dumps({"message_id": "msg-3"}))
    assert consume_chief_command.check_dedupe("msg-3", [proc_dir]) is False
    assert consume_chief_command.check_dedupe("msg-3", [proc_dir], exclude_path=exclude_file) is True
    
    # 6. Malformed JSON -> ignores and continues
    (proc_dir / "malformed.json").write_text("not json")
    assert consume_chief_command.check_dedupe("msg-4", [proc_dir]) is True


def generate_valid_command():
    payload = {
        "target_agent": "ANTIGRAVITY",
        "one_next_command": "echo test",
        "allowed_scope": ["2026-courier"],
        "human_gate_policy": "AUTO_IF_SAFE",
        "cost_policy": "ZERO_COST_ONLY"
    }
    return {
        "schema_version": "2.0",
        "message_id": "cmd-1",
        "task_id": "task-1",
        "correlation_id": "corr-1",
        "parent_id": "parent-1",
        "source": "chief",
        "destination": "antigravity",
        "type": "COMMAND",
        "status": "NEW",
        "created_at": "2026-09-30T00:00:00Z",
        "payload": payload,
        "payload_hash": consume_chief_command.canonical_hash(payload),
        "max_iterations": 1,
    }


def test_validate_command_success(tmp_path):
    cmd = generate_valid_command()
    cmd_file = tmp_path / "cmd.json"
    cmd_file.write_text(json.dumps(cmd))
    
    valid, reason = consume_chief_command.validate_command(cmd, cmd_file, tmp_path, tmp_path)
    assert valid is True
    assert reason == "VALID"


def test_validate_command_envelope_mismatch(tmp_path):
    cmd = generate_valid_command()
    del cmd["schema_version"]
    valid, reason = consume_chief_command.validate_command(cmd, None, tmp_path, tmp_path)
    assert valid is False
    assert "Envelope mismatch" in reason


def test_validate_command_invalid_fields(tmp_path):
    # Schema version
    cmd = generate_valid_command()
    cmd["schema_version"] = "1.0"
    assert consume_chief_command.validate_command(cmd, None, tmp_path, tmp_path)[0] is False
    
    # Type
    cmd = generate_valid_command()
    cmd["type"] = "RESULT"
    assert consume_chief_command.validate_command(cmd, None, tmp_path, tmp_path)[0] is False
    
    # Status
    cmd = generate_valid_command()
    cmd["status"] = "DONE"
    assert consume_chief_command.validate_command(cmd, None, tmp_path, tmp_path)[0] is False
    
    # Route
    cmd = generate_valid_command()
    cmd["source"] = "wrong"
    assert consume_chief_command.validate_command(cmd, None, tmp_path, tmp_path)[0] is False
    
    # max_iterations
    cmd = generate_valid_command()
    cmd["max_iterations"] = 2
    assert consume_chief_command.validate_command(cmd, None, tmp_path, tmp_path)[0] is False
    
    # Payload type
    cmd = generate_valid_command()
    cmd["payload"] = "string"
    assert consume_chief_command.validate_command(cmd, None, tmp_path, tmp_path)[0] is False
    
    # Target agent
    cmd = generate_valid_command()
    cmd["payload"]["target_agent"] = "OTHER"
    # Need to update hash
    cmd["payload_hash"] = consume_chief_command.canonical_hash(cmd["payload"])
    assert consume_chief_command.validate_command(cmd, None, tmp_path, tmp_path)[0] is False
    
    # Payload hash mismatch
    cmd = generate_valid_command()
    cmd["payload_hash"] = "wronghash"
    assert consume_chief_command.validate_command(cmd, None, tmp_path, tmp_path)[0] is False
    
    # Scope
    cmd = generate_valid_command()
    cmd["payload"]["allowed_scope"] = ["unknown_scope"]
    cmd["payload_hash"] = consume_chief_command.canonical_hash(cmd["payload"])
    assert consume_chief_command.validate_command(cmd, None, tmp_path, tmp_path)[0] is False
    
    # Cost
    cmd = generate_valid_command()
    cmd["payload"]["cost_policy"] = "UNLIMITED"
    cmd["payload_hash"] = consume_chief_command.canonical_hash(cmd["payload"])
    assert consume_chief_command.validate_command(cmd, None, tmp_path, tmp_path)[0] is False
    
    # Human gate
    cmd = generate_valid_command()
    cmd["payload"]["human_gate_policy"] = "NO_HUMAN"
    cmd["payload_hash"] = consume_chief_command.canonical_hash(cmd["payload"])
    assert consume_chief_command.validate_command(cmd, None, tmp_path, tmp_path)[0] is False
    
    # Dedupe
    cmd = generate_valid_command()
    (tmp_path / "exist.json").write_text(json.dumps({"message_id": cmd["message_id"]}))
    assert consume_chief_command.validate_command(cmd, None, tmp_path, tmp_path)[0] is False


def test_process_command(tmp_path):
    cmd = generate_valid_command()
    cmd_file = tmp_path / "cmd.json"
    cmd_file.write_text(json.dumps(cmd))
    
    processed_dir = tmp_path / "processed"
    
    res = consume_chief_command.process_command(cmd_file, tmp_path, processed_dir)
    assert res["status"] == "DONE"
    assert res["task_id"] == "task-1"
    
    res_file = processed_dir / "task-1-result.json"
    assert res_file.exists()


def test_process_command_missing_file(tmp_path):
    with pytest.raises(SystemExit) as exc:
        consume_chief_command.process_command(tmp_path / "missing.json", tmp_path, tmp_path)
    assert "Command file does not exist" in str(exc.value)


def test_process_command_invalid_json(tmp_path):
    bad_file = tmp_path / "bad.json"
    bad_file.write_text("{bad")
    with pytest.raises(SystemExit) as exc:
        consume_chief_command.process_command(bad_file, tmp_path, tmp_path)
    assert "Invalid JSON" in str(exc.value)


def test_process_command_validation_failed(tmp_path):
    cmd = generate_valid_command()
    cmd["schema_version"] = "9.9"
    cmd_file = tmp_path / "cmd.json"
    cmd_file.write_text(json.dumps(cmd))
    
    with pytest.raises(SystemExit) as exc:
        consume_chief_command.process_command(cmd_file, tmp_path, tmp_path)
    assert "Validation failed" in str(exc.value)


def test_main(tmp_path, monkeypatch):
    cmd = generate_valid_command()
    cmd_file = tmp_path / "cmd.json"
    cmd_file.write_text(json.dumps(cmd))
    
    processed_dir = tmp_path / "processed"
    
    import sys
    monkeypatch.setattr(sys, "argv", [
        "consume_chief_command.py", 
        "--command", str(cmd_file),
        "--incoming-dir", str(tmp_path),
        "--processed-dir", str(processed_dir)
    ])
    
    import runpy
    # Prevent SystemExit due to script reaching the end successfully
    runpy.run_path(str(__import__("pathlib").Path(__file__).resolve().parents[1] / "scripts" / "consume_chief_command.py"), run_name="__main__")
    
    assert (processed_dir / "task-1-result.json").exists()

