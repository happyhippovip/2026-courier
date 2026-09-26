#!/usr/bin/env python3
"""Targeted unit tests for publish_courier_result.py idempotency and atomic publishing."""

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
import pytest

SCRIPT_PATH = Path(__file__).resolve().parent.parent / "scripts" / "publish_courier_result.py"


def payload_hash(payload: object) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def test_publish_result_success(tmp_path):
    task = {
        "message_id": "msg-task-1",
        "task_id": "T-1",
        "correlation_id": "corr-1",
        "max_iterations": 1,
        "payload": {"result_request": "COURIER_CODEX_ACK"}
    }
    task_file = tmp_path / "task.json"
    task_file.write_text(json.dumps(task), encoding="utf-8")

    result = {
        "schema_version": "2.0",
        "message_id": "msg-result-1",
        "task_id": "T-1",
        "correlation_id": "corr-1",
        "parent_id": "msg-task-1",
        "source": "codex",
        "destination": "github_courier",
        "type": "RESULT",
        "status": "DONE",
        "created_at": "2026-09-26T08:00:00Z",
        "payload": {"result": "COURIER_CODEX_ACK"},
        "payload_hash": payload_hash({"result": "COURIER_CODEX_ACK"}),
        "max_iterations": 1
    }

    processed_dir = tmp_path / "processed"
    processed_dir.mkdir()
    github_output = tmp_path / "github_output.txt"

    env = os.environ.copy()
    env["CODEX_RESULT_JSON"] = json.dumps(result)

    cmd = [
        sys.executable, str(SCRIPT_PATH),
        "--task", str(task_file),
        "--processed-dir", str(processed_dir),
        "--github-output", str(github_output)
    ]
    subprocess.check_call(cmd, env=env)

    target = processed_dir / "msg-task-1.result.json"
    assert target.exists()
    assert json.loads(target.read_text(encoding="utf-8")) == result
    assert f"result_path={target.as_posix()}\n" in github_output.read_text(encoding="utf-8")


def test_publish_result_idempotent(tmp_path):
    task = {
        "message_id": "msg-task-2",
        "task_id": "T-2",
        "correlation_id": "corr-2",
        "max_iterations": 1,
        "payload": {"result_request": "COURIER_CODEX_ACK"}
    }
    task_file = tmp_path / "task2.json"
    task_file.write_text(json.dumps(task), encoding="utf-8")

    result = {
        "schema_version": "2.0",
        "message_id": "msg-result-2",
        "task_id": "T-2",
        "correlation_id": "corr-2",
        "parent_id": "msg-task-2",
        "source": "codex",
        "destination": "github_courier",
        "type": "RESULT",
        "status": "DONE",
        "created_at": "2026-09-26T08:00:00Z",
        "payload": {"result": "COURIER_CODEX_ACK"},
        "payload_hash": payload_hash({"result": "COURIER_CODEX_ACK"}),
        "max_iterations": 1
    }

    processed_dir = tmp_path / "processed"
    processed_dir.mkdir()
    github_output = tmp_path / "github_output.txt"

    env = os.environ.copy()
    env["CODEX_RESULT_JSON"] = json.dumps(result)

    cmd = [
        sys.executable, str(SCRIPT_PATH),
        "--task", str(task_file),
        "--processed-dir", str(processed_dir),
        "--github-output", str(github_output)
    ]
    # First call
    subprocess.check_call(cmd, env=env)
    # Second call (idempotent duplicate)
    subprocess.check_call(cmd, env=env)

    target = processed_dir / "msg-task-2.result.json"
    assert target.exists()
