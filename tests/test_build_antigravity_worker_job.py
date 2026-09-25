import pytest
import os
import sys
import json
from unittest import mock

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from scripts import build_antigravity_worker_job

@pytest.fixture
def valid_command():
    payload = {
        "target_agent": "ANTIGRAVITY",
        "one_next_command": "Fix the thing",
        "allowed_scope": ["2026-courier"],
        "cost_policy": "ZERO_COST_ONLY",
        "human_gate_policy": "STOP_ON_HUMAN_GATE_ONLY"
    }
    return {
        "schema_version": "2.0",
        "message_id": "m1",
        "task_id": "t1",
        "correlation_id": "c1",
        "parent_id": "p1",
        "source": "chief",
        "destination": "antigravity",
        "type": "COMMAND",
        "status": "NEW",
        "created_at": "now",
        "payload": payload,
        "payload_hash": build_antigravity_worker_job.canonical_hash(payload),
        "max_iterations": 1
    }

def _valid_job(**changes):
    job = {
        "schema_version": "2.0",
        "job_id": "job-ag-t1-abc123de",
        "task_id": "t1",
        "correlation_id": "c1",
        "source_command_message_id": "m1",
        "target_agent": "ANTIGRAVITY",
        "instruction": "do it",
        "expected_output": "ANTIGRAVITY_RESULT",
        "created_at": "2026-09-24T12:00:00Z",
        "allowed_scope": ["2026-courier"],
        "forbidden_scope": [".gemini/"],
        "cost_policy": "ZERO_COST_ONLY",
        "human_gate_policy": "STOP_ON_HUMAN_GATE_ONLY",
        "max_iterations": 1,
    }
    job.update(changes)
    return job


@pytest.mark.parametrize("field", ["job_id", "task_id", "correlation_id", "source_command_message_id"])
def test_validate_job_rejects_trailing_newline_ids(field):
    valid, reason = build_antigravity_worker_job.validate_worker_job_against_schema(
        _valid_job(**{field: _valid_job()[field] + "\n"})
    )
    assert valid is False, f"{field} with trailing newline must not validate: {reason}"


def test_validate_command_success(valid_command):
    valid, reason = build_antigravity_worker_job.validate_command_for_job(valid_command)
    assert valid is True
    assert reason == "VALID"

def test_validate_command_invalid_cost_policy(valid_command):
    valid_command["payload"]["cost_policy"] = "UNLIMITED"
    valid_command["payload_hash"] = build_antigravity_worker_job.canonical_hash(valid_command["payload"])
    
    valid, reason = build_antigravity_worker_job.validate_command_for_job(valid_command)
    assert valid is False
    assert "Cost policy violation" in reason

def test_validate_command_forbidden_scope(valid_command):
    valid_command["payload"]["allowed_scope"] = ["2026-courier", ".gemini/"]
    valid_command["payload_hash"] = build_antigravity_worker_job.canonical_hash(valid_command["payload"])
    
    valid, reason = build_antigravity_worker_job.validate_command_for_job(valid_command)
    assert valid is False
    assert "Scope violation" in reason

def test_build_worker_job_no_schema(tmp_path, valid_command):
    cmd_file = tmp_path / "cmd.json"
    cmd_file.write_text(json.dumps(valid_command))
    
    out_dir = tmp_path / "out"
    
    job = build_antigravity_worker_job.build_worker_job(cmd_file, out_dir, schema_path=None, memory_repo_path=None)
    
    assert job["task_id"] == "t1"
    assert job["target_agent"] == "ANTIGRAVITY"
    assert job["cost_policy"] == "ZERO_COST_ONLY"
    
    out_file = out_dir / f"t1-worker-job.json"
    assert out_file.exists()

@mock.patch("scripts.build_antigravity_worker_job.build_worker_job")
def test_main_cli(mock_build, tmp_path, capsys):
    cmd_file = tmp_path / "cmd.json"
    cmd_file.write_text("{}")
    
    mock_build.return_value = {
        "job_id": "job-ag-t1-abc123de",
        "task_id": "t1",
        "source_command_message_id": "m1"
    }
    
    with mock.patch.object(sys, 'argv', ['prog', '--command', str(cmd_file), '--output-dir', str(tmp_path)]):
        build_antigravity_worker_job.main()
        
    captured = capsys.readouterr()
    assert "WORKER_JOB_CREATED: id=job-ag-t1-abc123de, task=t1, src_msg=m1" in captured.out

def test_main_validate_job(tmp_path, capsys):
    job = {
        "schema_version": "2.0",
        "job_id": "job-ag-t1-abc123de",
        "task_id": "t1",
        "correlation_id": "c1",
        "source_command_message_id": "m1",
        "target_agent": "ANTIGRAVITY",
        "instruction": "do it",
        "expected_output": "ANTIGRAVITY_RESULT",
        "created_at": "2026-09-24T12:00:00Z",
        "allowed_scope": ["2026-courier"],
        "forbidden_scope": [".gemini/"],
        "cost_policy": "ZERO_COST_ONLY",
        "human_gate_policy": "STOP_ON_HUMAN_GATE_ONLY",
        "max_iterations": 1
    }
    
    job_file = tmp_path / "job.json"
    job_file.write_text(json.dumps(job))
    
    with mock.patch.object(sys, 'argv', ['prog', '--validate-job', str(job_file)]):
        build_antigravity_worker_job.main()
        
    captured = capsys.readouterr()
    assert "WORKER_JOB_SCHEMA_VALID" in captured.out

