#!/usr/bin/env python3
"""Comprehensive tests for consume_chief_command.py covering validation, path containment, deduplication, and atomic publishing."""

import hashlib
import json
from pathlib import Path
import pytest

from scripts.consume_chief_command import (
    validate_command,
    process_command,
    canonical_hash,
)


def make_valid_command(task_id="task-001", message_id="msg-chief-001"):
    payload = {
        "target_agent": "ANTIGRAVITY",
        "one_next_command": "Run deterministic suite",
        "allowed_scope": ["2026-courier"],
        "human_gate_policy": "STOP_ON_HUMAN_GATE_ONLY",
        "cost_policy": "ZERO_COST_ONLY",
    }
    payload_hash = canonical_hash(payload)
    return {
        "schema_version": "2.0",
        "message_id": message_id,
        "task_id": task_id,
        "correlation_id": "corr-001",
        "parent_id": "parent-001",
        "source": "chief",
        "destination": "antigravity",
        "type": "COMMAND",
        "status": "NEW",
        "created_at": "2026-09-26T08:00:00Z",
        "payload": payload,
        "payload_hash": payload_hash,
        "max_iterations": 1,
    }


def test_validate_valid_command(tmp_path):
    cmd = make_valid_command()
    incoming = tmp_path / "incoming"
    processed = tmp_path / "processed"
    incoming.mkdir()
    processed.mkdir()

    ok, reason = validate_command(cmd, None, incoming, processed)
    assert ok is True
    assert reason == "VALID"


def test_validate_rejects_task_id_path_traversal(tmp_path):
    cmd = make_valid_command(task_id="../../../etc/passwd")
    incoming = tmp_path / "incoming"
    processed = tmp_path / "processed"
    incoming.mkdir()
    processed.mkdir()

    ok, reason = validate_command(cmd, None, incoming, processed)
    assert ok is False
    assert "Invalid task_id pattern" in reason


def test_validate_rejects_message_id_path_traversal(tmp_path):
    cmd = make_valid_command(message_id="../../evil-msg")
    incoming = tmp_path / "incoming"
    processed = tmp_path / "processed"
    incoming.mkdir()
    processed.mkdir()

    ok, reason = validate_command(cmd, None, incoming, processed)
    assert ok is False
    assert "Invalid message_id pattern" in reason


def test_validate_rejects_unharmonized_cost_policy(tmp_path):
    cmd = make_valid_command()
    cmd["payload"]["cost_policy"] = "FREE_TIER_ONLY"
    cmd["payload_hash"] = canonical_hash(cmd["payload"])
    incoming = tmp_path / "incoming"
    processed = tmp_path / "processed"
    incoming.mkdir()
    processed.mkdir()

    ok, reason = validate_command(cmd, None, incoming, processed)
    assert ok is False
    assert "Cost policy violation" in reason


def test_validate_rejects_unharmonized_human_gate_policy(tmp_path):
    cmd = make_valid_command()
    cmd["payload"]["human_gate_policy"] = "AUTO_IF_SAFE"
    cmd["payload_hash"] = canonical_hash(cmd["payload"])
    incoming = tmp_path / "incoming"
    processed = tmp_path / "processed"
    incoming.mkdir()
    processed.mkdir()

    ok, reason = validate_command(cmd, None, incoming, processed)
    assert ok is False
    assert "Human gate policy violation" in reason


def test_validate_rejects_duplicate_message_id(tmp_path):
    cmd = make_valid_command(message_id="msg-dup-001")
    incoming = tmp_path / "incoming"
    processed = tmp_path / "processed"
    incoming.mkdir()
    processed.mkdir()

    # Create existing processed file with this message_id
    existing = processed / "other-result.json"
    existing.write_text(json.dumps({"message_id": "msg-dup-001"}), encoding="utf-8")

    ok, reason = validate_command(cmd, None, incoming, processed)
    assert ok is False
    assert "Duplicate command" in reason


def test_validate_rejects_task_id_result_overwrite(tmp_path):
    cmd = make_valid_command(task_id="task-existing")
    incoming = tmp_path / "incoming"
    processed = tmp_path / "processed"
    incoming.mkdir()
    processed.mkdir()

    # Pre-create result file
    res_file = processed / "task-existing-result.json"
    res_file.write_text(json.dumps({"message_id": "different-msg-id"}), encoding="utf-8")

    ok, reason = validate_command(cmd, None, incoming, processed)
    assert ok is False
    assert "Duplicate task: task_id 'task-existing' already has a processed result" in reason


def test_process_command_atomic_publish(tmp_path):
    cmd = make_valid_command(task_id="task-atomic-01")
    incoming = tmp_path / "incoming"
    processed = tmp_path / "processed"
    incoming.mkdir()
    processed.mkdir()

    cmd_file = incoming / "cmd.json"
    cmd_file.write_text(json.dumps(cmd), encoding="utf-8")

    result = process_command(cmd_file, incoming, processed)
    assert result["status"] == "DONE"
    assert result["task_id"] == "task-atomic-01"

    out_file = processed / "task-atomic-01-result.json"
    assert out_file.exists()
    loaded = json.loads(out_file.read_text(encoding="utf-8"))
    assert loaded["task_id"] == "task-atomic-01"
    assert loaded["payload"]["source_agent"] == "ANTIGRAVITY"
