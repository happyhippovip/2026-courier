from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import scripts.run_chief_relay_cycle as rcrc


def test_is_command_pending(tmp_path: Path):
    incoming = tmp_path / "incoming"
    processed = tmp_path / "processed"
    incoming.mkdir(parents=True)
    processed.mkdir(parents=True)

    cmd_file = incoming / "cmd1.json"
    cmd_data = {
        "schema_version": "2.0",
        "type": "COMMAND",
        "status": "NEW",
        "source": "chief",
        "destination": "antigravity",
        "message_id": "msg-001",
        "task_id": "task-001",
    }
    cmd_file.write_text(json.dumps(cmd_data), encoding="utf-8")

    assert rcrc.is_command_pending(cmd_file, processed) is True

    # Mark as already processed
    proc_file = processed / "res1.json"
    proc_file.write_text(json.dumps({"message_id": "res-001", "parent_id": "msg-001"}), encoding="utf-8")
    assert rcrc.is_command_pending(cmd_file, processed) is False


def test_discover_pending_command(tmp_path: Path):
    incoming = tmp_path / "incoming"
    processed = tmp_path / "processed"
    incoming.mkdir(parents=True)
    processed.mkdir(parents=True)

    # Empty incoming
    assert rcrc.discover_pending_command(incoming, processed) is None

    # Add command
    cmd_file = incoming / "cmd1.json"
    cmd_data = {
        "schema_version": "2.0",
        "type": "COMMAND",
        "status": "NEW",
        "source": "chief",
        "destination": "antigravity",
        "message_id": "msg-123",
        "task_id": "task-123",
    }
    cmd_file.write_text(json.dumps(cmd_data), encoding="utf-8")
    found = rcrc.discover_pending_command(incoming, processed)
    assert found == cmd_file


def test_run_cycle_idle(tmp_path: Path):
    incoming = tmp_path / "incoming"
    processed = tmp_path / "processed"
    dispatch = tmp_path / "dispatch"

    res = rcrc.run_cycle(
        repo_dir=tmp_path,
        incoming_dir=incoming,
        processed_dir=processed,
        dispatch_dir=dispatch,
        enable_auto_memory=False,
    )
    assert res["status"] == "IDLE"
    assert res["command_processed"] is None


def test_main_cli(tmp_path: Path, capsys):
    incoming = tmp_path / "incoming"
    incoming.mkdir(parents=True)
    code = rcrc.main(["--repo-dir", str(tmp_path), "--incoming-dir", "incoming", "--disable-auto-memory", "--json"])
    assert code == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["status"] == "IDLE"
