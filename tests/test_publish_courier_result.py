import pytest
import json
import os
from pathlib import Path
from unittest.mock import patch
from scripts.publish_courier_result import main, payload_hash

def create_task():
    return {
        "message_id": "msg-123",
        "task_id": "task-abc",
        "correlation_id": "corr-456",
        "max_iterations": 1,
        "payload": {
            "result_request": "COURIER_CODEX_ACK"
        }
    }

def create_result(task):
    payload = {"result": task["payload"]["result_request"]}
    return {
        "schema_version": "2.0",
        "message_id": "res-123",
        "task_id": task["task_id"],
        "correlation_id": task["correlation_id"],
        "parent_id": task["message_id"],
        "source": "codex",
        "destination": "github_courier",
        "type": "RESULT",
        "status": "DONE",
        "created_at": "2026-09-30T00:00:00Z",
        "payload": payload,
        "payload_hash": payload_hash(payload),
        "max_iterations": 1
    }

def run_main(task_path, processed_dir, github_output, codex_result):
    with patch("sys.argv", ["script.py", "--task", str(task_path), "--processed-dir", str(processed_dir), "--github-output", str(github_output)]):
        with patch.dict(os.environ, {"CODEX_RESULT_JSON": json.dumps(codex_result) if not isinstance(codex_result, str) else codex_result}):
            try:
                main()
                return None
            except SystemExit as e:
                return str(e)

def setup_files(tmp_path):
    task = create_task()
    task_file = tmp_path / "task.json"
    task_file.write_text(json.dumps(task), encoding="utf-8")
    
    processed_dir = tmp_path / "processed"
    processed_dir.mkdir()
    
    github_output = tmp_path / "github_output.txt"
    
    return task, task_file, processed_dir, github_output

def test_publish_courier_result_success(tmp_path):
    task, task_file, processed_dir, github_output = setup_files(tmp_path)
    result = create_result(task)
    
    err = run_main(task_file, processed_dir, github_output, result)
    assert err is None
    
    out_content = github_output.read_text(encoding="utf-8")
    expected_path = processed_dir / f"{task['message_id']}.result.json"
    assert f"result_path={expected_path.as_posix()}" in out_content
    assert expected_path.exists()
    assert json.loads(expected_path.read_text(encoding="utf-8")) == result

def test_publish_courier_result_not_json(tmp_path):
    task, task_file, processed_dir, github_output = setup_files(tmp_path)
    
    err = run_main(task_file, processed_dir, github_output, "NOT JSON")
    assert "Codex output is not JSON" in err

def test_publish_courier_result_unexpected_fields(tmp_path):
    task, task_file, processed_dir, github_output = setup_files(tmp_path)
    result = create_result(task)
    del result["schema_version"]
    
    err = run_main(task_file, processed_dir, github_output, result)
    assert err == "invalid Codex courier result: unexpected envelope fields"

def test_publish_courier_result_unexpected_lifecycle(tmp_path):
    task, task_file, processed_dir, github_output = setup_files(tmp_path)
    result = create_result(task)
    result["status"] = "NEW"
    
    err = run_main(task_file, processed_dir, github_output, result)
    assert err == "invalid Codex courier result: unexpected result lifecycle"

def test_publish_courier_result_unexpected_route(tmp_path):
    task, task_file, processed_dir, github_output = setup_files(tmp_path)
    result = create_result(task)
    result["source"] = "github_courier"
    
    err = run_main(task_file, processed_dir, github_output, result)
    assert err == "invalid Codex courier result: unexpected route"

def test_publish_courier_result_correlation_mismatch(tmp_path):
    task, task_file, processed_dir, github_output = setup_files(tmp_path)
    result = create_result(task)
    result["correlation_id"] = "wrong"
    
    err = run_main(task_file, processed_dir, github_output, result)
    assert err == "invalid Codex courier result: task or correlation mismatch"

def test_publish_courier_result_identity_mismatch(tmp_path):
    task, task_file, processed_dir, github_output = setup_files(tmp_path)
    result = create_result(task)
    result["parent_id"] = "wrong"
    
    err = run_main(task_file, processed_dir, github_output, result)
    assert err == "invalid Codex courier result: parent or message identity mismatch"

def test_publish_courier_result_iteration_mismatch(tmp_path):
    task, task_file, processed_dir, github_output = setup_files(tmp_path)
    result = create_result(task)
    result["max_iterations"] = 2
    
    err = run_main(task_file, processed_dir, github_output, result)
    assert err == "invalid Codex courier result: iteration bound mismatch"

def test_publish_courier_result_unsupported_request(tmp_path):
    task, task_file, processed_dir, github_output = setup_files(tmp_path)
    task["payload"]["result_request"] = "INVALID"
    task_file.write_text(json.dumps(task), encoding="utf-8")
    result = create_result(task)
    
    err = run_main(task_file, processed_dir, github_output, result)
    assert err == "invalid Codex courier result: unsupported task result_request"

def test_publish_courier_result_unexpected_payload(tmp_path):
    task, task_file, processed_dir, github_output = setup_files(tmp_path)
    result = create_result(task)
    result["payload"] = {"result": "WRONG"}
    result["payload_hash"] = payload_hash(result["payload"])
    
    err = run_main(task_file, processed_dir, github_output, result)
    assert err == "invalid Codex courier result: unexpected payload"

def test_publish_courier_result_payload_hash(tmp_path):
    task, task_file, processed_dir, github_output = setup_files(tmp_path)
    result = create_result(task)
    result["payload_hash"] = "bad"
    
    err = run_main(task_file, processed_dir, github_output, result)
    assert err == "invalid Codex courier result: payload hash mismatch"

def test_publish_courier_result_unsafe_message_id(tmp_path):
    task, task_file, processed_dir, github_output = setup_files(tmp_path)
    result = create_result(task)
    result["message_id"] = "res/123"
    
    err = run_main(task_file, processed_dir, github_output, result)
    assert err == "invalid Codex courier result: unsafe result message_id"

def test_publish_courier_result_duplicate_terminal_parent(tmp_path):
    task, task_file, processed_dir, github_output = setup_files(tmp_path)
    result = create_result(task)
    
    existing = processed_dir / "old.json"
    existing.write_text(json.dumps({"parent_id": task["message_id"]}), encoding="utf-8")
    
    err = run_main(task_file, processed_dir, github_output, result)
    assert err == "invalid Codex courier result: duplicate terminal result"

def test_publish_courier_result_duplicate_terminal_message(tmp_path):
    task, task_file, processed_dir, github_output = setup_files(tmp_path)
    result = create_result(task)
    
    existing = processed_dir / "old.json"
    existing.write_text(json.dumps({"message_id": result["message_id"]}), encoding="utf-8")
    
    err = run_main(task_file, processed_dir, github_output, result)
    assert err == "invalid Codex courier result: duplicate terminal result"

def test_publish_courier_result_target_exists(tmp_path):
    task, task_file, processed_dir, github_output = setup_files(tmp_path)
    result = create_result(task)
    
    target = processed_dir / f"{task['message_id']}.result.json"
    # Create the file with unrelated contents to hit the exists() check without
    # tripping the duplicate terminal check (which ignores non-matching ids)
    target.write_text(json.dumps({"something": "else"}), encoding="utf-8")
    
    err = run_main(task_file, processed_dir, github_output, result)
    assert err == "invalid Codex courier result: terminal result path already exists"


def _result_files(root):
    return [path for path in root.rglob("*") if path.is_file() and path.name.endswith(".result.json")]


def test_p1_corrupt_history_entry_rejects(tmp_path):
    task, task_file, processed_dir, github_output = setup_files(tmp_path)
    (processed_dir / "broken.json").write_text("{not-json", encoding="utf-8")

    err = run_main(task_file, processed_dir, github_output, create_result(task))
    assert err == "invalid Codex courier result: unreadable history entry broken.json"
    assert _result_files(tmp_path) == []


def test_p1_non_object_history_entry_rejects(tmp_path):
    task, task_file, processed_dir, github_output = setup_files(tmp_path)
    (processed_dir / "broken.json").write_text("[]", encoding="utf-8")

    err = run_main(task_file, processed_dir, github_output, create_result(task))
    assert err == "invalid Codex courier result: unreadable history entry broken.json"
    assert _result_files(tmp_path) == []


def test_p1_undecodable_history_entry_rejects(tmp_path):
    task, task_file, processed_dir, github_output = setup_files(tmp_path)
    (processed_dir / "broken.json").write_bytes(b"\xff\xfe{")

    err = run_main(task_file, processed_dir, github_output, create_result(task))
    assert err == "invalid Codex courier result: unreadable history entry broken.json"
    assert _result_files(tmp_path) == []


def test_p1_unreadable_history_directory_rejects(tmp_path):
    task, task_file, processed_dir, github_output = setup_files(tmp_path)
    (processed_dir / "broken.json").mkdir()

    err = run_main(task_file, processed_dir, github_output, create_result(task))
    assert err == "invalid Codex courier result: unreadable history entry broken.json"
    assert _result_files(tmp_path) == []


def test_p2_duplicate_result_same_parent_different_filename(tmp_path):
    task, task_file, processed_dir, github_output = setup_files(tmp_path)
    result = create_result(task)
    (processed_dir / "legacy-other-name.json").write_text(
        json.dumps({
            "type": "RESULT",
            "status": "DONE",
            "task_id": "different-task",
            "parent_id": task["message_id"],
            "message_id": "older-result",
        }),
        encoding="utf-8",
    )

    err = run_main(task_file, processed_dir, github_output, result)
    assert err == "invalid Codex courier result: duplicate terminal result"
    assert not (processed_dir / f"{task['message_id']}.result.json").exists()


def test_p2_duplicate_result_same_task_different_filename(tmp_path):
    task, task_file, processed_dir, github_output = setup_files(tmp_path)
    result = create_result(task)
    (processed_dir / "task-abc-result.json").write_text(
        json.dumps({
            "type": "RESULT",
            "status": "DONE",
            "task_id": task["task_id"],
            "parent_id": "older-parent",
            "message_id": "older-result",
        }),
        encoding="utf-8",
    )

    err = run_main(task_file, processed_dir, github_output, result)
    assert err == "invalid Codex courier result: duplicate terminal result"
    assert not (processed_dir / f"{task['message_id']}.result.json").exists()


@pytest.mark.parametrize("message_id", [
    "../escaped",
    "..",
    "foo/bar",
    "foo\\bar",
    "a..b",
    "bad id",
    "",
    ".hidden",
])
def test_p3_unsafe_task_message_id_rejects(tmp_path, message_id):
    task, task_file, processed_dir, github_output = setup_files(tmp_path)
    task["message_id"] = message_id
    task_file.write_text(json.dumps(task), encoding="utf-8")

    err = run_main(task_file, processed_dir, github_output, create_result(task))
    assert err == "invalid Codex courier result: unsafe task message_id"
    assert _result_files(tmp_path) == []
    assert not (tmp_path / "escaped.result.json").exists()


def test_p3_result_message_id_dotdot_rejects(tmp_path):
    task, task_file, processed_dir, github_output = setup_files(tmp_path)
    result = create_result(task)
    result["message_id"] = "a..b"

    err = run_main(task_file, processed_dir, github_output, result)
    assert err == "invalid Codex courier result: unsafe result message_id"
    assert _result_files(tmp_path) == []


def test_p4_exclusive_create_does_not_overwrite(tmp_path, monkeypatch):
    task, task_file, processed_dir, github_output = setup_files(tmp_path)
    target = processed_dir / f"{task['message_id']}.result.json"
    original = '{"preserved": true}\n'
    target.write_text(original, encoding="utf-8")
    # The exists-then-write window: a raced exists() reports the target free.
    monkeypatch.setattr(Path, "exists", lambda self: False)

    err = run_main(task_file, processed_dir, github_output, create_result(task))
    assert err == "invalid Codex courier result: terminal result path already exists"
    assert target.read_text(encoding="utf-8") == original


def test_p5_missing_results_directory_rejects(tmp_path):
    task, task_file, processed_dir, github_output = setup_files(tmp_path)
    processed_dir.rmdir()

    err = run_main(task_file, processed_dir, github_output, create_result(task))
    assert err == "invalid Codex courier result: results directory does not exist"
    assert not processed_dir.exists()
    assert _result_files(tmp_path) == []


def test_p6_valid_publish_is_byte_identical(tmp_path):
    task, task_file, processed_dir, github_output = setup_files(tmp_path)
    (processed_dir / "unrelated.json").write_text(
        json.dumps({
            "type": "RESULT",
            "status": "DONE",
            "task_id": "other-task",
            "parent_id": "other-parent",
            "message_id": "other-result",
        }),
        encoding="utf-8",
    )
    result = create_result(task)

    err = run_main(task_file, processed_dir, github_output, result)
    assert err is None

    expected_path = processed_dir / f"{task['message_id']}.result.json"
    expected_body = json.dumps(result, sort_keys=True, indent=2) + "\n"
    expected_output = f"result_path={expected_path.as_posix()}\n"
    if os.linesep != "\n":
        expected_body = expected_body.replace("\n", os.linesep)
        expected_output = expected_output.replace("\n", os.linesep)
    assert expected_path.read_bytes() == expected_body.encode("utf-8")
    assert github_output.read_bytes() == expected_output.encode("utf-8")
