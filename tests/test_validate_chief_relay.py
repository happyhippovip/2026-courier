#!/usr/bin/env python3
"""Tests for scripts/validate_chief_relay.py."""

import json
from pathlib import Path
import pytest
from scripts.validate_chief_relay import (
    canonical_hash,
    validate_event,
    RelayValidationError,
    main,
)


def _make_valid_command():
    payload = {
        "target_agent": "ANTIGRAVITY",
        "one_next_command": "Run Windows hardening",
        "allowed_scope": ["happyhippovip/2026-courier"],
        "human_gate_policy": "STOP_ON_HUMAN_GATE_ONLY",
        "cost_policy": "ZERO_COST_ONLY",
    }
    return {
        "schema_version": "2.0",
        "message_id": "cmd-101",
        "task_id": "task-101",
        "correlation_id": "corr-101",
        "parent_id": None,
        "source": "chief",
        "destination": "antigravity",
        "type": "COMMAND",
        "status": "NEW",
        "created_at": "2026-09-24T12:00:00Z",
        "payload": payload,
        "payload_hash": canonical_hash(payload),
        "max_iterations": 1,
    }


def _make_valid_result():
    payload = {
        "source_agent": "ANTIGRAVITY",
        "summary": "Completed tasks successfully",
        "verified_facts": ["fact1"],
        "files_changed": 1,
        "commits": ["sha1"],
        "test_results": "PASS",
        "cost": "0.00 EUR",
        "human_gate": "NONE",
        "safe_next_state": "WAITING_FOR_CHIEF_COMMAND",
    }
    return {
        "schema_version": "2.0",
        "message_id": "res-101",
        "task_id": "task-101",
        "correlation_id": "corr-101",
        "parent_id": "cmd-101",
        "source": "antigravity",
        "destination": "chief",
        "type": "RESULT",
        "status": "DONE",
        "created_at": "2026-09-24T12:01:00Z",
        "payload": payload,
        "payload_hash": canonical_hash(payload),
        "max_iterations": 1,
    }


def test_validate_event_command_success(tmp_path: Path):
    cmd_file = tmp_path / "cmd.json"
    cmd_file.write_text(json.dumps(_make_valid_command()), encoding="utf-8")
    data = validate_event(cmd_file)
    assert data["type"] == "COMMAND"
    assert data["message_id"] == "cmd-101"


def test_validate_event_result_success(tmp_path: Path):
    res_file = tmp_path / "res.json"
    res_file.write_text(json.dumps(_make_valid_result()), encoding="utf-8")
    data = validate_event(res_file)
    assert data["type"] == "RESULT"
    assert data["message_id"] == "res-101"


def test_validate_event_invalid_hash(tmp_path: Path):
    bad = _make_valid_command()
    bad["payload_hash"] = "tampered"
    bad_file = tmp_path / "bad.json"
    bad_file.write_text(json.dumps(bad), encoding="utf-8")

    with pytest.raises(RelayValidationError) as exc:
        validate_event(bad_file)
    assert "payload_hash mismatch" in str(exc.value)


def test_validate_event_dedupe_failure(tmp_path: Path):
    cmd = _make_valid_command()
    cmd_file = tmp_path / "incoming" / "cmd.json"
    cmd_file.parent.mkdir()
    cmd_file.write_text(json.dumps(cmd), encoding="utf-8")

    proc_dir = tmp_path / "processed"
    proc_dir.mkdir()
    existing_file = proc_dir / "old_cmd.json"
    existing_file.write_text(json.dumps({"message_id": "cmd-101"}), encoding="utf-8")

    with pytest.raises(RelayValidationError) as exc:
        validate_event(cmd_file, processed_dir=proc_dir)
    assert "duplicate message_id" in str(exc.value)


def test_main_cli_json(tmp_path: Path, capsys):
    cmd_file = tmp_path / "cmd.json"
    cmd_file.write_text(json.dumps(_make_valid_command()), encoding="utf-8")

    ret = main(["--file", str(cmd_file), "--json"])
    assert ret == 0
    captured = capsys.readouterr().out
    data = json.loads(captured)
    assert data["valid"] is True
