import hashlib
import json
import os
import sys
from pathlib import Path
import pytest

from scripts.publish_courier_result import main, payload_hash


def test_payload_hash():
    payload = {"result": "COURIER_CODEX_ACK"}
    h = payload_hash(payload)
    assert len(h) == 64
    assert h == hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def test_publish_courier_result_success(tmp_path: Path, monkeypatch):
    task_file = tmp_path / "task.json"
    task_data = {
        "schema_version": "2.0",
        "message_id": "msg-task-001",
        "task_id": "task-001",
        "correlation_id": "corr-001",
        "max_iterations": 1,
        "payload": {
            "result_request": "COURIER_CODEX_ACK",
        },
    }
    task_file.write_text(json.dumps(task_data), encoding="utf-8")

    processed_dir = tmp_path / "processed"
    processed_dir.mkdir()
    github_output = tmp_path / "github" / "output.txt"

    result_payload = {"result": "COURIER_CODEX_ACK"}
    result_data = {
        "schema_version": "2.0",
        "message_id": "res-001",
        "task_id": "task-001",
        "correlation_id": "corr-001",
        "parent_id": "msg-task-001",
        "source": "codex",
        "destination": "github_courier",
        "type": "RESULT",
        "status": "DONE",
        "created_at": "2026-09-24T12:00:00Z",
        "payload": result_payload,
        "payload_hash": payload_hash(result_payload),
        "max_iterations": 1,
    }

    monkeypatch.setenv("CODEX_RESULT_JSON", json.dumps(result_data))
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "publish_courier_result.py",
            "--task", str(task_file),
            "--processed-dir", str(processed_dir),
            "--github-output", str(github_output),
        ],
    )
    main()

    # Verify result file written atomically
    target_result = processed_dir / "msg-task-001.result.json"
    assert target_result.is_file()
    written = json.loads(target_result.read_text(encoding="utf-8"))
    assert written["message_id"] == "res-001"
    assert written["status"] == "DONE"

    # Verify github output appended
    assert github_output.is_file()
    gh_content = github_output.read_text(encoding="utf-8")
    assert f"result_path={target_result.as_posix()}" in gh_content


def test_publish_courier_result_invalid_result_rejects(tmp_path: Path, monkeypatch):
    task_file = tmp_path / "task.json"
    task_data = {
        "message_id": "msg-002",
        "task_id": "task-002",
        "correlation_id": "corr-002",
        "max_iterations": 1,
        "payload": {"result_request": "COURIER_CODEX_ACK"},
    }
    task_file.write_text(json.dumps(task_data), encoding="utf-8")

    processed_dir = tmp_path / "processed"
    processed_dir.mkdir()
    github_output = tmp_path / "output.txt"

    # Malformed / mismatched json
    monkeypatch.setenv("CODEX_RESULT_JSON", "{\"bad\": true}")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "publish_courier_result.py",
            "--task", str(task_file),
            "--processed-dir", str(processed_dir),
            "--github-output", str(github_output),
        ],
    )
    with pytest.raises(SystemExit) as exc:
        main()
    assert "invalid Codex courier result" in str(exc.value)
