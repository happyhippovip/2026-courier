"""Tests for the pure-logic functions in scripts/run_chief_relay_cycle.py.

Covers:
  - is_command_pending(): valid command file
  - is_command_pending(): schema_version != 2.0 rejected
  - is_command_pending(): wrong type or status rejected
  - is_command_pending(): wrong source/destination rejected
  - is_command_pending(): missing message_id rejected
  - is_command_pending(): already-processed commands are not pending
  - is_command_pending(): corrupt JSON is not pending
  - discover_pending_command(): returns oldest unprocessed command
  - discover_pending_command(): returns None when all processed
  - discover_pending_command(): returns None for missing incoming dir
"""

import json
import sys
import time
from pathlib import Path

import pytest

REPO = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(REPO / "scripts"))

from run_chief_relay_cycle import is_command_pending, discover_pending_command


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _valid_command(msg_id="msg-001", task_id="task-001"):
    return {
        "schema_version": "2.0",
        "message_id": msg_id,
        "task_id": task_id,
        "correlation_id": "corr-001",
        "parent_id": None,
        "source": "chief",
        "destination": "antigravity",
        "type": "COMMAND",
        "status": "NEW",
        "created_at": "2026-09-01T00:00:00Z",
        "payload": {
            "target_agent": "ANTIGRAVITY",
            "one_next_command": "run tests",
            "allowed_scope": ["2026-courier"],
            "human_gate_policy": "STOP_ON_HUMAN_GATE_ONLY",
            "cost_policy": "ZERO_COST_ONLY",
        },
        "payload_hash": "placeholder",
        "max_iterations": 1,
    }


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


# ─── is_command_pending() ──────────────────────────────────────────────────

def test_is_command_pending_valid_returns_true(tmp_path):
    cmd_file = tmp_path / "incoming" / "cmd.json"
    _write_json(cmd_file, _valid_command())
    processed_dir = tmp_path / "processed"
    assert is_command_pending(cmd_file, processed_dir) is True


def test_is_command_pending_wrong_schema_version(tmp_path):
    cmd = _valid_command()
    cmd["schema_version"] = "1.0"
    cmd_file = tmp_path / "incoming" / "cmd.json"
    _write_json(cmd_file, cmd)
    assert is_command_pending(cmd_file, tmp_path / "processed") is False


def test_is_command_pending_wrong_type(tmp_path):
    cmd = _valid_command()
    cmd["type"] = "RESULT"
    cmd_file = tmp_path / "incoming" / "cmd.json"
    _write_json(cmd_file, cmd)
    assert is_command_pending(cmd_file, tmp_path / "processed") is False


def test_is_command_pending_wrong_status(tmp_path):
    cmd = _valid_command()
    cmd["status"] = "PROCESSED"
    cmd_file = tmp_path / "incoming" / "cmd.json"
    _write_json(cmd_file, cmd)
    assert is_command_pending(cmd_file, tmp_path / "processed") is False


def test_is_command_pending_wrong_source(tmp_path):
    cmd = _valid_command()
    cmd["source"] = "unknown"
    cmd_file = tmp_path / "incoming" / "cmd.json"
    _write_json(cmd_file, cmd)
    assert is_command_pending(cmd_file, tmp_path / "processed") is False


def test_is_command_pending_wrong_destination(tmp_path):
    cmd = _valid_command()
    cmd["destination"] = "codex"
    cmd_file = tmp_path / "incoming" / "cmd.json"
    _write_json(cmd_file, cmd)
    assert is_command_pending(cmd_file, tmp_path / "processed") is False


def test_is_command_pending_missing_message_id(tmp_path):
    cmd = _valid_command()
    cmd["message_id"] = ""
    cmd_file = tmp_path / "incoming" / "cmd.json"
    _write_json(cmd_file, cmd)
    assert is_command_pending(cmd_file, tmp_path / "processed") is False


def test_is_command_pending_corrupt_json(tmp_path):
    cmd_file = tmp_path / "incoming" / "corrupt.json"
    cmd_file.parent.mkdir(parents=True, exist_ok=True)
    cmd_file.write_text("{not valid json}", encoding="utf-8")
    assert is_command_pending(cmd_file, tmp_path / "processed") is False


def test_is_command_pending_already_processed_by_parent_id(tmp_path):
    """If processed_dir has a file with parent_id matching the command's message_id, it's NOT pending."""
    cmd = _valid_command(msg_id="msg-unique-123")
    cmd_file = tmp_path / "incoming" / "cmd.json"
    _write_json(cmd_file, cmd)

    # A processed result referencing this command
    processed_dir = tmp_path / "processed"
    result = {"parent_id": "msg-unique-123", "message_id": "msg-result-456", "type": "RESULT"}
    _write_json(processed_dir / "result.json", result)

    assert is_command_pending(cmd_file, processed_dir) is False


def test_is_command_pending_already_processed_by_message_id(tmp_path):
    """If processed_dir has a file with message_id matching the command's message_id, it's NOT pending."""
    cmd = _valid_command(msg_id="msg-dupe-789")
    cmd_file = tmp_path / "incoming" / "cmd.json"
    _write_json(cmd_file, cmd)

    processed_dir = tmp_path / "processed"
    # Same message_id already in processed (e.g., re-delivery of same command)
    existing = {"message_id": "msg-dupe-789", "type": "COMMAND"}
    _write_json(processed_dir / "existing.json", existing)

    assert is_command_pending(cmd_file, processed_dir) is False


def test_is_command_pending_different_message_id_stays_pending(tmp_path):
    """A processed result for a different command should not affect this one."""
    cmd = _valid_command(msg_id="msg-A")
    cmd_file = tmp_path / "incoming" / "cmd.json"
    _write_json(cmd_file, cmd)

    processed_dir = tmp_path / "processed"
    other_result = {"parent_id": "msg-B", "message_id": "msg-result-B"}
    _write_json(processed_dir / "result_b.json", other_result)

    assert is_command_pending(cmd_file, processed_dir) is True


def test_is_command_pending_corrupt_processed_file_is_skipped(tmp_path):
    """Corrupt files in processed_dir should be skipped, not crash."""
    cmd = _valid_command(msg_id="msg-safe")
    cmd_file = tmp_path / "incoming" / "cmd.json"
    _write_json(cmd_file, cmd)

    processed_dir = tmp_path / "processed"
    processed_dir.mkdir()
    (processed_dir / "corrupt.json").write_text("{bad}", encoding="utf-8")

    assert is_command_pending(cmd_file, processed_dir) is True


# ─── discover_pending_command() ────────────────────────────────────────────

def test_discover_returns_none_for_missing_incoming_dir(tmp_path):
    missing = tmp_path / "no_such_dir"
    assert discover_pending_command(missing, tmp_path / "processed") is None


def test_discover_returns_oldest_unprocessed_command(tmp_path):
    incoming = tmp_path / "incoming"
    incoming.mkdir()
    processed = tmp_path / "processed"

    # Create two valid commands with different mtimes
    cmd_a = incoming / "cmd_a.json"
    _write_json(cmd_a, _valid_command(msg_id="msg-older", task_id="task-a"))
    time.sleep(0.05)
    cmd_b = incoming / "cmd_b.json"
    _write_json(cmd_b, _valid_command(msg_id="msg-newer", task_id="task-b"))

    found = discover_pending_command(incoming, processed)
    assert found is not None
    assert found.name == "cmd_a.json"  # oldest first


def test_discover_returns_none_when_all_processed(tmp_path):
    incoming = tmp_path / "incoming"
    incoming.mkdir()
    processed = tmp_path / "processed"
    processed.mkdir()

    cmd_file = incoming / "cmd.json"
    _write_json(cmd_file, _valid_command(msg_id="msg-done"))

    # Mark as already processed
    result = {"parent_id": "msg-done", "type": "RESULT"}
    _write_json(processed / "result.json", result)

    assert discover_pending_command(incoming, processed) is None


def test_discover_returns_none_for_invalid_json_files(tmp_path):
    incoming = tmp_path / "incoming"
    incoming.mkdir()
    (incoming / "garbage.json").write_text("{not json}", encoding="utf-8")
    assert discover_pending_command(incoming, tmp_path / "processed") is None


def test_discover_skips_non_json_files(tmp_path):
    incoming = tmp_path / "incoming"
    incoming.mkdir()
    (incoming / "notes.txt").write_text("not a command", encoding="utf-8")
    (incoming / "cmd.json").write_text(
        json.dumps(_valid_command(msg_id="msg-ok")), encoding="utf-8"
    )
    found = discover_pending_command(incoming, tmp_path / "processed")
    assert found is not None
    assert found.name == "cmd.json"
