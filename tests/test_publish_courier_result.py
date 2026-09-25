import pytest
import os
import sys
import json
from unittest import mock

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from scripts import publish_courier_result

@pytest.fixture
def valid_task():
    return {
        "task_id": "t1",
        "correlation_id": "c1",
        "message_id": "m1",
        "max_iterations": 1,
        "payload": {"result_request": "COURIER_CODEX_ACK"}
    }

@pytest.fixture
def valid_result():
    payload = {"result": "COURIER_CODEX_ACK"}
    return {
        "schema_version": "2.0",
        "message_id": "res1",
        "task_id": "t1",
        "correlation_id": "c1",
        "parent_id": "m1",
        "source": "codex",
        "destination": "github_courier",
        "type": "RESULT",
        "status": "DONE",
        "created_at": "now",
        "payload": payload,
        "payload_hash": publish_courier_result.payload_hash(payload),
        "max_iterations": 1
    }

def test_payload_hash():
    h = publish_courier_result.payload_hash({"a": 1})
    assert h == "015abd7f5cc57a2dd94b7590f04ad8084273905ee33ec5cebeae62276a97f862"

def test_main_success(tmp_path, valid_task, valid_result):
    task_file = tmp_path / "task.json"
    task_file.write_text(json.dumps(valid_task))
    
    processed_dir = tmp_path / "processed"
    processed_dir.mkdir()
    
    github_out = tmp_path / "github.txt"
    
    with mock.patch.dict(os.environ, {"CODEX_RESULT_JSON": json.dumps(valid_result)}):
        with mock.patch.object(sys, 'argv', ['prog', '--task', str(task_file), '--processed-dir', str(processed_dir), '--github-output', str(github_out)]):
            publish_courier_result.main()
            
    # Check output file exists
    target = processed_dir / f"{valid_task['message_id']}.result.json"
    assert target.exists()
    
    # Check github output
    out = github_out.read_text()
    assert target.as_posix() in out

def test_main_invalid_json(tmp_path, valid_task):
    task_file = tmp_path / "task.json"
    task_file.write_text(json.dumps(valid_task))
    
    with mock.patch.dict(os.environ, {"CODEX_RESULT_JSON": "bad"}):
        with mock.patch.object(sys, 'argv', ['prog', '--task', str(task_file), '--processed-dir', 'p', '--github-output', 'g']):
            with pytest.raises(SystemExit) as exc:
                publish_courier_result.main()
            assert "Codex output is not JSON" in str(exc.value)

def test_main_mismatched_hash(tmp_path, valid_task, valid_result):
    task_file = tmp_path / "task.json"
    task_file.write_text(json.dumps(valid_task))
    
    valid_result["payload_hash"] = "badhash"
    
    with mock.patch.dict(os.environ, {"CODEX_RESULT_JSON": json.dumps(valid_result)}):
        with mock.patch.object(sys, 'argv', ['prog', '--task', str(task_file), '--processed-dir', 'p', '--github-output', 'g']):
            with pytest.raises(SystemExit) as exc:
                publish_courier_result.main()
            assert "payload hash mismatch" in str(exc.value)

def test_main_duplicate_terminal_result(tmp_path, valid_task, valid_result):
    task_file = tmp_path / "task.json"
    task_file.write_text(json.dumps(valid_task))
    
    processed_dir = tmp_path / "processed"
    processed_dir.mkdir()
    
    # Create an existing result that matches parent_id
    existing_result = processed_dir / "old.json"
    existing_result.write_text(json.dumps({"parent_id": valid_task["message_id"]}))
    
    with mock.patch.dict(os.environ, {"CODEX_RESULT_JSON": json.dumps(valid_result)}):
        with mock.patch.object(sys, 'argv', ['prog', '--task', str(task_file), '--processed-dir', str(processed_dir), '--github-output', 'g']):
            with pytest.raises(SystemExit) as exc:
                publish_courier_result.main()
            assert "duplicate terminal result" in str(exc.value)

