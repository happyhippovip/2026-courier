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


def test_publish_does_not_follow_a_symlink(tmp_path):
    task, task_file, _processed, _output = setup_files(tmp_path)
    result = create_result(task)
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "keep.txt").write_text("keep", encoding="utf-8")
    linked = tmp_path / "linked-processed"
    linked.symlink_to(outside)
    secret = tmp_path / "secret-output.txt"
    secret.write_text("keep-output", encoding="utf-8")
    out_link = tmp_path / "github-out"
    out_link.symlink_to(secret)
    err = run_main(task_file, linked, out_link, result)
    leaked = sorted(p.name for p in outside.iterdir())
    body = secret.read_text(encoding="utf-8")
    assert err == "invalid Codex courier result: refusing to follow a symlink" and leaked == ["keep.txt"] and body == "keep-output" and linked.is_symlink() and out_link.is_symlink(), (
        err, leaked, body, linked.is_symlink(), out_link.is_symlink(),
    )


def test_bool_max_iterations_is_not_published(tmp_path):
    task, task_file, processed_dir, github_output = setup_files(tmp_path)
    task["max_iterations"] = True
    task_file.write_text(json.dumps(task), encoding="utf-8")
    result = create_result(task)
    result["max_iterations"] = True
    err_both = run_main(task_file, processed_dir, github_output, result)
    names = sorted(p.name for p in processed_dir.iterdir())

    task_one = create_task()
    task_one_file = tmp_path / "task-one.json"
    task_one_file.write_text(json.dumps(task_one), encoding="utf-8")
    processed_one = tmp_path / "processed-one"
    processed_one.mkdir()
    output_one = tmp_path / "out-one.txt"
    result_true = create_result(task_one)
    result_true["max_iterations"] = True
    err_true = run_main(task_one_file, processed_one, output_one, result_true)
    names_one = sorted(p.name for p in processed_one.iterdir())

    task_bool = create_task()
    task_bool["max_iterations"] = True
    task_bool_file = tmp_path / "task-bool.json"
    task_bool_file.write_text(json.dumps(task_bool), encoding="utf-8")
    processed_bool = tmp_path / "processed-bool"
    processed_bool.mkdir()
    output_bool = tmp_path / "out-bool.txt"
    result_one = create_result(task_bool)
    err_task = run_main(task_bool_file, processed_bool, output_bool, result_one)
    names_task = sorted(p.name for p in processed_bool.iterdir())

    mismatch = "invalid Codex courier result: iteration bound mismatch"
    assert err_both == mismatch and names == [] and err_true == mismatch and names_one == [] and err_task == mismatch and names_task == [], (
        err_both, names, err_true, names_one, err_task, names_task,
    )


def test_float_max_iterations_is_not_published(tmp_path):
    mismatch = "invalid Codex courier result: iteration bound mismatch"

    def case(name, task_iterations, result_iterations):
        task = create_task()
        task["max_iterations"] = task_iterations
        task_file = tmp_path / f"{name}-task.json"
        task_file.write_text(json.dumps(task), encoding="utf-8")
        processed = tmp_path / name
        processed.mkdir()
        output = tmp_path / f"{name}.txt"
        result = create_result(task)
        result["max_iterations"] = result_iterations
        err = run_main(task_file, processed, output, result)
        names = sorted(p.name for p in processed.iterdir())
        return err, names

    both = case("both", 1.0, 1.0)
    result_float = case("result", 1, 1.0)
    task_float = case("task", 1.0, 1)
    integer = case("integer", 1, 1)
    assert (both, result_float, task_float, integer) == (
        (mismatch, []),
        (mismatch, []),
        (mismatch, []),
        (None, ["msg-123.result.json"]),
    )
