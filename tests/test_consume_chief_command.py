#!/usr/bin/env python3
"""Tests for scripts/consume_chief_command.py."""

import json
from pathlib import Path
import pytest
from scripts.consume_chief_command import (
    canonical_hash,
    validate_command,
    create_antigravity_result,
    process_command,
    ChiefConsumerError,
    main,
)


def _make_valid_command():
    payload = {
        "target_agent": "ANTIGRAVITY",
        "one_next_command": "Execute windows verification task",
        "allowed_scope": ["happyhippovip/2026-courier"],
        "human_gate_policy": "STOP_ON_HUMAN_GATE_ONLY",
        "cost_policy": "ZERO_COST_ONLY",
    }
    return {
        "schema_version": "2.0",
        "message_id": "cmd-consume-101",
        "task_id": "task-consume-101",
        "correlation_id": "corr-consume-101",
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


def test_validate_command_valid(tmp_path: Path):
    cmd = _make_valid_command()
    inc = tmp_path / "incoming"
    proc = tmp_path / "processed"
    inc.mkdir()
    proc.mkdir()

    valid, reason = validate_command(cmd, None, inc, proc)
    assert valid is True
    assert reason == "VALID"


def test_validate_command_scope_violation(tmp_path: Path):
    cmd = _make_valid_command()
    cmd["payload"]["allowed_scope"] = ["unauthorized/repo"]
    cmd["payload_hash"] = canonical_hash(cmd["payload"])
    inc = tmp_path / "incoming"
    proc = tmp_path / "processed"
    inc.mkdir()
    proc.mkdir()

    valid, reason = validate_command(cmd, None, inc, proc)
    assert valid is False
    assert "Scope violation" in reason


def test_process_command_success(tmp_path: Path):
    cmd_data = _make_valid_command()
    cmd_file = tmp_path / "incoming" / "cmd.json"
    cmd_file.parent.mkdir()
    cmd_file.write_text(json.dumps(cmd_data), encoding="utf-8")

    proc_dir = tmp_path / "processed"
    proc_dir.mkdir()

    res = process_command(cmd_file, cmd_file.parent, proc_dir)
    assert res["status"] == "DONE"
    assert res["type"] == "RESULT"
    assert res["parent_id"] == "cmd-consume-101"

    out_file = proc_dir / f"{cmd_data['task_id']}-result.json"
    assert out_file.exists()
    saved = json.loads(out_file.read_text(encoding="utf-8"))
    assert saved["message_id"] == res["message_id"]


def test_process_command_duplicate_refusal(tmp_path: Path):
    cmd_data = _make_valid_command()
    cmd_file = tmp_path / "incoming" / "cmd.json"
    cmd_file.parent.mkdir()
    cmd_file.write_text(json.dumps(cmd_data), encoding="utf-8")

    proc_dir = tmp_path / "processed"
    proc_dir.mkdir()
    (proc_dir / "existing.json").write_text(
        json.dumps({"message_id": "cmd-consume-101"}), encoding="utf-8"
    )

    with pytest.raises(ChiefConsumerError) as exc:
        process_command(cmd_file, cmd_file.parent, proc_dir)
    assert "Duplicate command" in str(exc.value)


def test_main_cli_json(tmp_path: Path, capsys):
    cmd_data = _make_valid_command()
    cmd_file = tmp_path / "cmd.json"
    cmd_file.write_text(json.dumps(cmd_data), encoding="utf-8")
    proc_dir = tmp_path / "processed"

    ret = main(["--command", str(cmd_file), "--processed-dir", str(proc_dir), "--json"])
    assert ret == 0
    captured = capsys.readouterr().out
    data = json.loads(captured)
    assert data["status"] == "DONE"
    assert data["source"] == "antigravity"
