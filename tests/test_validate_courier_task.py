#!/usr/bin/env python3
"""Tests for scripts/validate_courier_task.py."""

import json
from pathlib import Path
import pytest
from scripts.validate_courier_task import (
    canonical_hash,
    validate_task,
    validate_task_dict,
    main,
)


def _make_valid_task() -> dict:
    payload = {
        "instruction": "Test instruction",
        "result_request": "COURIER_CODEX_ACK",
    }
    return {
        "schema_version": "2.0",
        "message_id": "msg-101",
        "task_id": "task-101",
        "correlation_id": "corr-101",
        "parent_id": None,
        "source": "github_courier",
        "destination": "codex",
        "type": "TASK",
        "status": "NEW",
        "created_at": "2026-09-24T12:00:00Z",
        "payload": payload,
        "payload_hash": canonical_hash(payload),
        "max_iterations": 1,
    }


def test_validate_task_dict_valid():
    task = _make_valid_task()
    valid, reason = validate_task_dict(task)
    assert valid is True
    assert reason == "VALID"


def test_validate_task_dict_invalid_hash():
    task = _make_valid_task()
    task["payload_hash"] = "invalid_hash"
    valid, reason = validate_task_dict(task)
    assert valid is False
    assert "payload_hash mismatch" in reason


def test_validate_task_dict_invalid_result_request():
    task = _make_valid_task()
    task["payload"]["result_request"] = "INVALID_ACK"
    task["payload_hash"] = canonical_hash(task["payload"])
    valid, reason = validate_task_dict(task)
    assert valid is False
    assert "unsupported result_request" in reason


def test_validate_task_dedupe(tmp_path: Path):
    task = _make_valid_task()
    task_file = tmp_path / "task.json"
    task_file.write_text(json.dumps(task), encoding="utf-8")

    proc_dir = tmp_path / "processed"
    proc_dir.mkdir()

    # Before processed record exists
    valid, _ = validate_task(task_file, processed_dir=proc_dir)
    assert valid is True

    # Add terminal record matching message_id
    term_file = proc_dir / "term_1.json"
    term_file.write_text(json.dumps({"parent_id": "msg-101", "status": "TERMINAL"}), encoding="utf-8")

    valid_after, reason = validate_task(task_file, processed_dir=proc_dir)
    assert valid_after is False
    assert "already has a terminal record" in reason


def test_main_cli_json(tmp_path: Path, capsys):
    task = _make_valid_task()
    task_file = tmp_path / "task.json"
    task_file.write_text(json.dumps(task), encoding="utf-8")

    ret = main(["--task", str(task_file), "--json"])
    assert ret == 0
    captured = capsys.readouterr().out
    data = json.loads(captured)
    assert data["valid"] is True
