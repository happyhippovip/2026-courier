import pytest
import json
from pathlib import Path
from unittest.mock import patch

from scripts.build_antigravity_worker_job import (
    validate_worker_job_against_schema,
    validate_command_for_job,
    build_worker_job,
    main,
    REQUIRED_ENVELOPE,
    REQUIRED_COMMAND_PAYLOAD,
    ALLOWED_COST_POLICIES,
    ALLOWED_HUMAN_GATE_POLICIES,
    canonical_hash
)

def _valid_job():
    return {
        "schema_version": "2.0",
        "job_id": "job-ag-123-abc",
        "source_command_message_id": "msg-123",
        "task_id": "task-123",
        "correlation_id": "corr-123",
        "target_agent": "ANTIGRAVITY",
        "instruction": "do something",
        "allowed_scope": ["2026-courier"],
        "forbidden_scope": ["04-Wellnesskoenig-Website"],
        "cost_policy": "ZERO_COST_ONLY",
        "human_gate_policy": "STOP_ON_HUMAN_GATE_ONLY",
        "max_iterations": 1,
        "expected_output": "ANTIGRAVITY_RESULT",
        "created_at": "2026-01-01T00:00:00Z"
    }

def _valid_cmd():
    payload = {
        "target_agent": "ANTIGRAVITY",
        "one_next_command": "do something",
        "allowed_scope": ["2026-courier"],
        "cost_policy": "ZERO_COST_ONLY",
        "human_gate_policy": "STOP_ON_HUMAN_GATE_ONLY"
    }
    return {
        "message_id": "msg-1",
        "correlation_id": "corr-1",
        "parent_id": "parent-1",
        "created_at": "2026-01-01",
        "source": "chief",
        "destination": "antigravity",
        "type": "COMMAND",
        "status": "NEW",
        "schema_version": "2.0",
        "task_id": "task-1",
        "max_iterations": 1,
        "payload": payload,
        "payload_hash": canonical_hash(payload)
    }

def test_validate_worker_job_against_schema_missing_coverage(tmp_path):
    schema_path = tmp_path / "schema.json"
    schema_path.write_text("invalid json")
    
    # 78-79: schema load error
    valid, msg = validate_worker_job_against_schema({}, schema_path)
    assert not valid and "Failed to load schema file" in msg

    # 89: not dict
    valid, msg = validate_worker_job_against_schema([], None)
    assert not valid and "must be a JSON object" in msg
    
    # 93: missing req fields
    job = _valid_job()
    del job["instruction"]
    valid, msg = validate_worker_job_against_schema(job, None)
    assert not valid and "Missing required fields" in msg
    
    # 98: extra fields
    job = _valid_job()
    job["extra_field"] = 123
    valid, msg = validate_worker_job_against_schema(job, None)
    assert not valid and "Unexpected extra fields" in msg
    
    # 102: schema_version invalid
    job = _valid_job()
    job["schema_version"] = "1.0"
    valid, msg = validate_worker_job_against_schema(job, None)
    assert not valid and "Invalid schema_version" in msg
    
    # 117: target_agent != ANTIGRAVITY
    job = _valid_job()
    job["target_agent"] = "OTHER"
    valid, msg = validate_worker_job_against_schema(job, None)
    assert not valid and "Invalid target_agent" in msg
    
    # 121: instruction not non-empty str
    job = _valid_job()
    job["instruction"] = ""
    valid, msg = validate_worker_job_against_schema(job, None)
    assert not valid and "instruction must be a non-empty string" in msg
    
    # 125: allowed_scope invalid
    job = _valid_job()
    job["allowed_scope"] = "not a list"
    valid, msg = validate_worker_job_against_schema(job, None)
    assert not valid and "allowed_scope must be a non-empty list of strings" in msg
    
    # 129: forbidden_scope invalid
    job = _valid_job()
    job["forbidden_scope"] = [123]
    valid, msg = validate_worker_job_against_schema(job, None)
    assert not valid and "forbidden_scope must be a list of strings" in msg
    
    # 132: cost_policy invalid
    job = _valid_job()
    job["cost_policy"] = "UNLIMITED"
    valid, msg = validate_worker_job_against_schema(job, None)
    assert not valid and "Invalid cost_policy" in msg
    
    # 135: human_gate_policy invalid
    job = _valid_job()
    job["human_gate_policy"] = "NEVER"
    valid, msg = validate_worker_job_against_schema(job, None)
    assert not valid and "Invalid human_gate_policy" in msg
    
    # 138: max_iterations != 1
    job = _valid_job()
    job["max_iterations"] = 5
    valid, msg = validate_worker_job_against_schema(job, None)
    assert not valid and "Invalid max_iterations" in msg
    
    # 141: expected_output != ANTIGRAVITY_RESULT
    job = _valid_job()
    job["expected_output"] = "OTHER"
    valid, msg = validate_worker_job_against_schema(job, None)
    assert not valid and "Invalid expected_output" in msg
    
    # 145: created_at invalid
    job = _valid_job()
    job["created_at"] = ""
    valid, msg = validate_worker_job_against_schema(job, None)
    assert not valid and "created_at must be a non-empty" in msg

    # Regex tests
    job = _valid_job()
    job["job_id"] = "inv@lid"
    valid, msg = validate_worker_job_against_schema(job, None)
    assert not valid and "Invalid job_id pattern" in msg

    job = _valid_job()
    job["source_command_message_id"] = "inv@lid"
    valid, msg = validate_worker_job_against_schema(job, None)
    assert not valid and "Invalid source_command_message_id pattern" in msg

    job = _valid_job()
    job["task_id"] = "inv@lid"
    valid, msg = validate_worker_job_against_schema(job, None)
    assert not valid and "Invalid task_id pattern" in msg

    job = _valid_job()
    job["correlation_id"] = "inv@lid"
    valid, msg = validate_worker_job_against_schema(job, None)
    assert not valid and "Invalid correlation_id pattern" in msg


    # Memory context checks
    job = _valid_job()
    job["memory_context"] = "not a dict"
    valid, msg = validate_worker_job_against_schema(job, None)
    assert not valid and "memory_context must be a JSON object" in msg
    
    job = _valid_job()
    job["memory_context"] = {"memory_repo": "foo"}
    valid, msg = validate_worker_job_against_schema(job, None)
    assert not valid and "memory_context fields mismatch" in msg
    
    job = _valid_job()
    job["memory_context"] = {
        "memory_repo": "repo",
        "memory_commit": "short",
        "files_consulted": ["f1"],
        "relevant_context": "x",
        "status_labels": [],
        "source_references": [],
        "generated_at": "time"
    }
    valid, msg = validate_worker_job_against_schema(job, None)
    assert not valid and "Invalid memory_commit hash" in msg
    
    job = _valid_job()
    mctx = job["memory_context"] = {
        "memory_repo": "repo",
        "memory_commit": "12345678",
        "files_consulted": [],
        "relevant_context": "x",
        "status_labels": [],
        "source_references": [],
        "generated_at": "time"
    }
    valid, msg = validate_worker_job_against_schema(job, None)
    assert not valid and "files_consulted must be a non-empty list of strings" in msg

def test_validate_command_for_job_missing_coverage():
    # 165: envelope mismatch
    cmd = _valid_cmd()
    del cmd["message_id"]
    valid, msg = validate_command_for_job(cmd)
    assert not valid and "Envelope mismatch" in msg

    # 168: schema_version != 2.0
    cmd = _valid_cmd()
    cmd["schema_version"] = "1.0"
    valid, msg = validate_command_for_job(cmd)
    assert not valid and "Unsupported schema_version" in msg
    
    # 171: type != COMMAND
    cmd = _valid_cmd()
    cmd["type"] = "EVENT"
    valid, msg = validate_command_for_job(cmd)
    assert not valid and "Event type must be COMMAND" in msg
    
    # 174: status != NEW
    cmd = _valid_cmd()
    cmd["status"] = "IN_PROGRESS"
    valid, msg = validate_command_for_job(cmd)
    assert not valid and "Event status must be NEW" in msg
    
    # 177: source/destination invalid
    cmd = _valid_cmd()
    cmd["source"] = "other"
    valid, msg = validate_command_for_job(cmd)
    assert not valid and "Invalid route" in msg
    
    # 180: max_iterations != 1
    cmd = _valid_cmd()
    cmd["max_iterations"] = 2
    valid, msg = validate_command_for_job(cmd)
    assert not valid and "max_iterations must be 1" in msg
    
    # 184: payload fields mismatch
    cmd = _valid_cmd()
    cmd["payload"]["extra"] = 1
    valid, msg = validate_command_for_job(cmd)
    assert not valid and "Payload fields mismatch" in msg
    
    # 187: target_agent != ANTIGRAVITY
    cmd = _valid_cmd()
    cmd["payload"]["target_agent"] = "OTHER"
    # Need to re-hash because hash mismatch happens later, wait, target_agent is checked before payload_hash!
    valid, msg = validate_command_for_job(cmd)
    assert not valid and "target_agent must be ANTIGRAVITY" in msg
    
    # 190: payload_hash mismatch
    cmd = _valid_cmd()
    cmd["payload_hash"] = "wrong"
    valid, msg = validate_command_for_job(cmd)
    assert not valid and "payload_hash mismatch" in msg
    
    # 193: Strict cost policy check
    cmd = _valid_cmd()
    cmd["payload"]["cost_policy"] = "UNLIMITED"
    cmd["payload_hash"] = canonical_hash(cmd["payload"])
    valid, msg = validate_command_for_job(cmd)
    assert not valid and "Cost policy violation" in msg
    
    # 198: human gate policy invalid
    cmd = _valid_cmd()
    cmd["payload"]["human_gate_policy"] = "NEVER"
    cmd["payload_hash"] = canonical_hash(cmd["payload"])
    valid, msg = validate_command_for_job(cmd)
    assert not valid and "Human gate policy violation" in msg
    
    # 203: allowed_scope must be list
    cmd = _valid_cmd()
    cmd["payload"]["allowed_scope"] = "not a list"
    cmd["payload_hash"] = canonical_hash(cmd["payload"])
    valid, msg = validate_command_for_job(cmd)
    assert not valid and "allowed_scope must be a non-empty list" in msg

    # 209: forbidden scope requested
    cmd = _valid_cmd()
    cmd["payload"]["allowed_scope"] = ["03-Wellnesskoenig-Website-Memory"]
    cmd["payload_hash"] = canonical_hash(cmd["payload"])
    valid, msg = validate_command_for_job(cmd)
    assert not valid and "Scope violation" in msg

    # 211: scope violation
    cmd = _valid_cmd()
    cmd["payload"]["allowed_scope"] = ["unknown-scope"]
    cmd["payload_hash"] = canonical_hash(cmd["payload"])
    valid, msg = validate_command_for_job(cmd)
    assert not valid and "Scope violation" in msg



def test_build_worker_job_missing_coverage(tmp_path):
    output_dir = tmp_path / "out"
    cmd_file = tmp_path / "cmd.json"
    
    # 222: command file not found
    with pytest.raises(SystemExit):
        build_worker_job(tmp_path / "nonexistent.json", output_dir)
        
    # 232: command validation failed
    cmd = _valid_cmd()
    cmd["schema_version"] = "1.0"
    cmd_file.write_text(json.dumps(cmd))
    with pytest.raises(SystemExit):
        build_worker_job(cmd_file, output_dir)
        
    # 269: memory_context logic
    # Mock build_memory_context_package to return something
    cmd = _valid_cmd()
    cmd_file.write_text(json.dumps(cmd))
    with patch("scripts.build_antigravity_worker_job.build_memory_context_package", return_value={"memory_repo": "r", "memory_commit": "12345678", "files_consulted": ["x"], "relevant_context": "x", "status_labels": [], "source_references": [], "generated_at": "x"}):
        repo_path = tmp_path / "memory_repo"
        repo_path.mkdir()
        job = build_worker_job(cmd_file, output_dir, memory_repo_path=repo_path)
        assert "memory_context" in job

    # 274: schema validation failed
    with patch("scripts.build_antigravity_worker_job.validate_worker_job_against_schema", return_value=(False, "error")):
        with pytest.raises(SystemExit):
            build_worker_job(cmd_file, output_dir)
            
    # 227-228: JSON parse failure
    cmd_file.write_text("invalid json {")
    with pytest.raises(SystemExit):
        build_worker_job(cmd_file, output_dir)
        
    # 248-249: Memory context resolve exception
    cmd = _valid_cmd()
    cmd_file.write_text(json.dumps(cmd))
    with patch("scripts.build_antigravity_worker_job.build_memory_context_package", side_effect=Exception("mock memory warning")):
        repo_path = tmp_path / "memory_repo2"
        repo_path.mkdir()
        job = build_worker_job(cmd_file, output_dir, memory_repo_path=repo_path)
        assert job.get("memory_context") is None



def test_main_missing_coverage(tmp_path, capsys):
    job_file = tmp_path / "job.json"
    
    # 297: validate_job file not found
    with patch("sys.argv", ["scripts/build_antigravity_worker_job.py", "--validate-job", str(job_file)]):
        with pytest.raises(SystemExit):
            main()
            
    # 300-301: validate_job json loads error
    job_file.write_text("invalid json")
    with patch("sys.argv", ["scripts/build_antigravity_worker_job.py", "--validate-job", str(job_file)]):
        with pytest.raises(SystemExit):
            main()
            
    # 304: validate_job validation failed
    job_file.write_text(json.dumps(_valid_job()))
    with patch("sys.argv", ["scripts/build_antigravity_worker_job.py", "--validate-job", str(job_file)]):
        with patch("scripts.build_antigravity_worker_job.validate_worker_job_against_schema", return_value=(False, "err")):
            with pytest.raises(SystemExit):
                main()
                
    # 305: validate_job valid
    with patch("sys.argv", ["scripts/build_antigravity_worker_job.py", "--validate-job", str(job_file)]):
        with patch("scripts.build_antigravity_worker_job.validate_worker_job_against_schema", return_value=(True, "ok")):
            main()
            assert "WORKER_JOB_SCHEMA_VALID" in capsys.readouterr().out
            
    # 309: command arg missing
    with patch("sys.argv", ["scripts/build_antigravity_worker_job.py"]):
        with pytest.raises(SystemExit):
            main()

    # 311-316: main execution with --command
    with patch("sys.argv", ["scripts/build_antigravity_worker_job.py", "--command", str(tmp_path / "cmd.json"), "--output-dir", str(tmp_path)]):
        with patch("scripts.build_antigravity_worker_job.build_worker_job", return_value=_valid_job()):
            main()
            assert "WORKER_JOB_CREATED" in capsys.readouterr().out
            
def test_main_execution():
    with patch("scripts.build_antigravity_worker_job.main") as mock_main:
        with patch("sys.argv", ["scripts/build_antigravity_worker_job.py"]):
            import scripts.build_antigravity_worker_job
            # to hit line 320 it has to be run as __main__, which is covered by runpy in other tests.

