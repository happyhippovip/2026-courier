import hashlib
import json
import pytest
from pathlib import Path

from scripts.validate_courier_task import validate_task, canonical_hash
from scripts.publish_courier_result import publish_result, payload_hash


def _make_task_dict(msg_id="task-msg-1", task_id="t-1", req="COURIER_CODEX_ACK"):
    payload = {"result_request": req}
    p_hash = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return {
        "schema_version": "2.0",
        "message_id": msg_id,
        "task_id": task_id,
        "correlation_id": "corr-1",
        "parent_id": None,
        "source": "github_courier",
        "destination": "codex",
        "type": "TASK",
        "status": "NEW",
        "created_at": "2026-09-23T05:00:00Z",
        "payload": payload,
        "payload_hash": p_hash,
        "max_iterations": 1,
    }


def _make_result_dict(task_dict, msg_id="res-msg-1"):
    payload = {"result": task_dict["payload"]["result_request"]}
    p_hash = payload_hash(payload)
    return {
        "schema_version": "2.0",
        "message_id": msg_id,
        "task_id": task_dict["task_id"],
        "correlation_id": task_dict["correlation_id"],
        "parent_id": task_dict["message_id"],
        "source": "codex",
        "destination": "github_courier",
        "type": "RESULT",
        "status": "DONE",
        "created_at": "2026-09-23T05:01:00Z",
        "payload": payload,
        "payload_hash": p_hash,
        "max_iterations": 1,
    }


def test_validate_task_valid(tmp_path):
    task = _make_task_dict()
    task_file = tmp_path / "task.json"
    task_file.write_text(json.dumps(task), encoding="utf-8")
    proc_dir = tmp_path / "processed"
    proc_dir.mkdir()

    res = validate_task(task_file, proc_dir)
    assert res["message_id"] == "task-msg-1"
    assert res["status"] == "NEW"


def test_validate_task_missing_file(tmp_path):
    proc_dir = tmp_path / "processed"
    with pytest.raises(SystemExit, match="task file does not exist"):
        validate_task(tmp_path / "nonexistent.json", proc_dir)


def test_validate_task_hash_mismatch(tmp_path):
    task = _make_task_dict()
    task["payload_hash"] = "0" * 64
    task_file = tmp_path / "task.json"
    task_file.write_text(json.dumps(task), encoding="utf-8")
    proc_dir = tmp_path / "processed"

    with pytest.raises(SystemExit, match="payload_hash mismatch"):
        validate_task(task_file, proc_dir)


def test_validate_task_duplicate_in_processed(tmp_path):
    task = _make_task_dict(msg_id="dup-task-1")
    task_file = tmp_path / "task.json"
    task_file.write_text(json.dumps(task), encoding="utf-8")
    proc_dir = tmp_path / "processed"
    proc_dir.mkdir()

    # Create processed result with parent_id = dup-task-1
    (proc_dir / "res.json").write_text(
        json.dumps({"message_id": "r-1", "parent_id": "dup-task-1"}),
        encoding="utf-8",
    )

    with pytest.raises(SystemExit, match="already has a terminal record"):
        validate_task(task_file, proc_dir)


def test_publish_result_success(tmp_path):
    task = _make_task_dict()
    task_file = tmp_path / "task.json"
    task_file.write_text(json.dumps(task), encoding="utf-8")
    proc_dir = tmp_path / "processed"
    proc_dir.mkdir()
    gh_output = tmp_path / "github_output.txt"

    result_dict = _make_result_dict(task)
    raw_result = json.dumps(result_dict)

    target = publish_result(
        task_path=task_file,
        processed_dir=proc_dir,
        github_output=gh_output,
        raw_result=raw_result,
    )

    assert target.exists()
    assert target.name == f"{task['message_id']}.result.json"

    disk_data = json.loads(target.read_text(encoding="utf-8"))
    assert disk_data["status"] == "DONE"
    assert disk_data["parent_id"] == task["message_id"]

    assert gh_output.exists()
    assert f"result_path={target.as_posix()}" in gh_output.read_text(encoding="utf-8")


def test_publish_result_hash_mismatch(tmp_path):
    task = _make_task_dict()
    task_file = tmp_path / "task.json"
    task_file.write_text(json.dumps(task), encoding="utf-8")
    proc_dir = tmp_path / "processed"

    result_dict = _make_result_dict(task)
    result_dict["payload_hash"] = "0" * 64
    raw_result = json.dumps(result_dict)

    with pytest.raises(SystemExit, match="payload hash mismatch"):
        publish_result(task_file, proc_dir, raw_result=raw_result)


def test_publish_result_invalid_json(tmp_path):
    task = _make_task_dict()
    task_file = tmp_path / "task.json"
    task_file.write_text(json.dumps(task), encoding="utf-8")
    proc_dir = tmp_path / "processed"

    with pytest.raises(SystemExit, match="Codex output is not JSON"):
        publish_result(task_file, proc_dir, raw_result="{ invalid json ...")
