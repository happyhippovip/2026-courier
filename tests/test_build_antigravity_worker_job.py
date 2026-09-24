#!/usr/bin/env python3
"""Tests for scripts/build_antigravity_worker_job.py."""

import json
from pathlib import Path
import pytest
from scripts.build_antigravity_worker_job import (
    canonical_hash,
    validate_command_for_job,
    validate_worker_job_against_schema,
    build_worker_job,
    WorkerJobBuilderError,
    main,
)


def _make_valid_chief_command():
    payload = {
        "target_agent": "ANTIGRAVITY",
        "one_next_command": "Execute unit test verification",
        "allowed_scope": ["happyhippovip/2026-courier"],
        "human_gate_policy": "STOP_ON_HUMAN_GATE_ONLY",
        "cost_policy": "ZERO_COST_ONLY",
    }
    return {
        "schema_version": "2.0",
        "message_id": "cmd-job-101",
        "task_id": "task-job-101",
        "correlation_id": "corr-job-101",
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


def test_validate_command_for_job_valid():
    cmd = _make_valid_chief_command()
    valid, reason = validate_command_for_job(cmd)
    assert valid is True
    assert reason == "VALID"


def test_validate_command_for_job_forbidden_scope():
    cmd = _make_valid_chief_command()
    cmd["payload"]["allowed_scope"] = ["FruitKI"]
    cmd["payload_hash"] = canonical_hash(cmd["payload"])
    valid, reason = validate_command_for_job(cmd)
    assert valid is False
    assert "Forbidden scope" in reason


def test_build_worker_job_success(tmp_path: Path):
    cmd_data = _make_valid_chief_command()
    cmd_file = tmp_path / "cmd.json"
    cmd_file.write_text(json.dumps(cmd_data), encoding="utf-8")

    out_dir = tmp_path / "dispatch"
    job = build_worker_job(cmd_file, output_dir=out_dir)

    assert job["target_agent"] == "ANTIGRAVITY"
    assert job["task_id"] == "task-job-101"
    assert job["source_command_message_id"] == "cmd-job-101"
    assert job["cost_policy"] == "ZERO_COST_ONLY"

    saved_file = out_dir / f"{cmd_data['task_id']}-worker-job.json"
    assert saved_file.exists()
    saved = json.loads(saved_file.read_text(encoding="utf-8"))
    assert saved["job_id"] == job["job_id"]


def test_main_cli_build_and_validate(tmp_path: Path, capsys):
    cmd_data = _make_valid_chief_command()
    cmd_file = tmp_path / "cmd.json"
    cmd_file.write_text(json.dumps(cmd_data), encoding="utf-8")
    out_dir = tmp_path / "dispatch"

    ret_build = main(["--command", str(cmd_file), "--output-dir", str(out_dir), "--json"])
    assert ret_build == 0
    captured = capsys.readouterr().out
    data = json.loads(captured)
    assert data["target_agent"] == "ANTIGRAVITY"

    job_file = out_dir / f"{cmd_data['task_id']}-worker-job.json"
    ret_val = main(["--validate-job", str(job_file), "--json"])
    assert ret_val == 0
    cap_val = capsys.readouterr().out
    val_data = json.loads(cap_val)
    assert val_data["valid"] is True
