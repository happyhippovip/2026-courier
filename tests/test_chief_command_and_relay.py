import hashlib
import json
import pytest
from pathlib import Path

import scripts.consume_chief_command as consumer
import scripts.validate_chief_relay as validator


def _canonical_hash(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _make_command_envelope(msg_id="cmd-1", task_id="task-1", scope="happyhippovip/2026-courier"):
    payload = {
        "target_agent": "ANTIGRAVITY",
        "one_next_command": "Run unit test suite",
        "allowed_scope": [scope],
        "human_gate_policy": "AUTO_IF_SAFE",
        "cost_policy": "ZERO_COST_ONLY",
    }
    return {
        "schema_version": "2.0",
        "message_id": msg_id,
        "task_id": task_id,
        "correlation_id": "corr-1",
        "parent_id": None,
        "source": "chief",
        "destination": "antigravity",
        "type": "COMMAND",
        "status": "NEW",
        "created_at": "2026-09-23T05:00:00Z",
        "payload": payload,
        "payload_hash": _canonical_hash(payload),
        "max_iterations": 1,
    }


def test_validate_command_valid(tmp_path):
    cmd = _make_command_envelope()
    incoming = tmp_path / "incoming"
    processed = tmp_path / "processed"
    incoming.mkdir()
    processed.mkdir()

    cmd_file = incoming / "cmd1.json"
    cmd_file.write_text(json.dumps(cmd), encoding="utf-8")

    is_valid, reason = consumer.validate_command(cmd, cmd_file, incoming, processed)
    assert is_valid is True
    assert reason == "VALID"


def test_validate_command_hash_mismatch(tmp_path):
    cmd = _make_command_envelope()
    cmd["payload_hash"] = "0" * 64
    incoming = tmp_path / "incoming"
    processed = tmp_path / "processed"

    is_valid, reason = consumer.validate_command(cmd, None, incoming, processed)
    assert is_valid is False
    assert "payload_hash mismatch" in reason


def test_validate_command_scope_violation(tmp_path):
    cmd = _make_command_envelope(scope="unauthorized/repo")
    incoming = tmp_path / "incoming"
    processed = tmp_path / "processed"

    is_valid, reason = consumer.validate_command(cmd, None, incoming, processed)
    assert is_valid is False
    assert "Scope violation" in reason


def test_validate_command_duplicate_detection(tmp_path):
    cmd = _make_command_envelope(msg_id="cmd-duplicate")
    incoming = tmp_path / "incoming"
    processed = tmp_path / "processed"
    incoming.mkdir()
    processed.mkdir()

    # Pre-populate processed dir with existing result referencing parent_id = cmd-duplicate
    (processed / "existing.json").write_text(
        json.dumps({"message_id": "res-1", "parent_id": "cmd-duplicate"}),
        encoding="utf-8",
    )

    is_valid, reason = consumer.validate_command(cmd, None, incoming, processed)
    assert is_valid is False
    assert "Duplicate command" in reason


def test_process_command_produces_atomic_result(tmp_path):
    cmd = _make_command_envelope(msg_id="cmd-exec-1", task_id="task-exec-1")
    incoming = tmp_path / "incoming"
    processed = tmp_path / "processed"
    incoming.mkdir()
    processed.mkdir()

    cmd_file = incoming / "cmd.json"
    cmd_file.write_text(json.dumps(cmd), encoding="utf-8")

    result = consumer.process_command(cmd_file, incoming, processed)
    assert result["type"] == "RESULT"
    assert result["status"] == "DONE"
    assert result["task_id"] == "task-exec-1"
    assert result["parent_id"] == "cmd-exec-1"

    # Verify result file was created on disk
    res_file = processed / "task-exec-1-result.json"
    assert res_file.exists()
    disk_data = json.loads(res_file.read_text(encoding="utf-8"))
    assert disk_data["message_id"] == result["message_id"]


def test_validator_validate_result_event(tmp_path):
    cmd = _make_command_envelope()
    result = consumer.create_antigravity_result(
        command_data=cmd,
        status="DONE",
        summary="Summary of work",
        verified_facts=["fact 1"],
        files_changed=1,
        commits=["c1"],
        test_results="PASS",
    )
    res_file = tmp_path / "result.json"
    res_file.write_text(json.dumps(result), encoding="utf-8")

    validated = validator.validate_event(res_file)
    assert validated["type"] == "RESULT"
    assert validated["status"] == "DONE"


def test_validator_detects_hash_mismatch(tmp_path):
    cmd = _make_command_envelope()
    cmd_file = tmp_path / "bad_cmd.json"
    cmd["payload_hash"] = "0" * 64
    cmd_file.write_text(json.dumps(cmd), encoding="utf-8")

    with pytest.raises(SystemExit, match="payload_hash mismatch"):
        validator.validate_event(cmd_file)


def test_validator_detects_duplicate_message_id(tmp_path):
    cmd = _make_command_envelope(msg_id="dup-msg")
    cmd_file = tmp_path / "incoming" / "cmd.json"
    cmd_file.parent.mkdir()
    cmd_file.write_text(json.dumps(cmd), encoding="utf-8")

    proc_dir = tmp_path / "processed"
    proc_dir.mkdir()
    (proc_dir / "old.json").write_text(json.dumps({"message_id": "dup-msg"}), encoding="utf-8")

    with pytest.raises(SystemExit, match="duplicate message_id"):
        validator.validate_event(cmd_file, processed_dir=proc_dir)
