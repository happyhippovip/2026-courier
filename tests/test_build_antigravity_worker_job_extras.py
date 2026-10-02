import pytest
import os
import sys
import json
from unittest import mock
from pathlib import Path

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
        "forbidden_scope": ["04-Wellnesskoenig-Website"],
        "cost_policy": "ZERO_COST_ONLY",
        "human_gate_policy": "STOP_ON_HUMAN_GATE_ONLY",
        "max_iterations": 1,
    }
    job.update(changes)
    return job

def test_validate_job_with_memory_context_valid():
    job = _valid_job(memory_context={
        "memory_repo": "test",
        "memory_commit": "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2",
        "files_consulted": ["f1.txt"],
        "relevant_context": "x",
        "status_labels": [],
        "source_references": [],
        "generated_at": "now"
    })
    valid, msg = build_antigravity_worker_job.validate_worker_job_against_schema(job)
    assert valid is True

def test_validate_job_with_memory_context_invalid_fields():
    job = _valid_job(memory_context={
        "memory_repo": "test",
        "files_consulted": ["f1.txt"],
        # Missing other fields
    })
    valid, msg = build_antigravity_worker_job.validate_worker_job_against_schema(job)
    assert valid is False
    assert "memory_context fields mismatch" in msg

def test_validate_command_forbidden_pattern(valid_command):
    # Test one of the explicit forbidden scope patterns
    valid_command["payload"]["allowed_scope"] = ["FruitKI-backend"]
    valid_command["payload_hash"] = build_antigravity_worker_job.canonical_hash(valid_command["payload"])
    
    valid, msg = build_antigravity_worker_job.validate_command_for_job(valid_command)
    assert valid is False
    assert "violates protection of" in msg

def test_build_worker_job_file_not_found():
    with pytest.raises(SystemExit, match="WORKER_JOB_BUILDER_ERROR: Command file not found"):
        build_antigravity_worker_job.build_worker_job(Path("does_not_exist.json"), Path("out"))

def test_build_worker_job_invalid_json(tmp_path):
    f = tmp_path / "cmd.json"
    f.write_text("not json")
    with pytest.raises(SystemExit, match="Invalid JSON in command file"):
        build_antigravity_worker_job.build_worker_job(f, tmp_path / "out")

@mock.patch("scripts.build_antigravity_worker_job.build_memory_context_package")
def test_build_worker_job_memory_resolve_exception(mock_build, tmp_path, valid_command, capsys):
    f = tmp_path / "cmd.json"
    f.write_text(json.dumps(valid_command))
    mock_build.side_effect = Exception("Memory failed")
    
    # Needs a mock memory repo path that exists
    repo = tmp_path / "memory_repo"
    repo.mkdir()
    
    job = build_antigravity_worker_job.build_worker_job(f, tmp_path / "out", memory_repo_path=repo)
    assert "memory_context" not in job
    captured = capsys.readouterr()
    assert "MEMORY_RESOLVE_WARNING" in captured.err

def test_validate_job_against_schema_file(tmp_path):
    schema_file = tmp_path / "schema.json"
    job = _valid_job()
    schema_file.write_text(json.dumps({
        "required": list(job.keys())
    }))
    
    valid, msg = build_antigravity_worker_job.validate_worker_job_against_schema(job, schema_path=schema_file)
    assert valid is True
