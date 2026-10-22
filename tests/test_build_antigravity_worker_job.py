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

def test_output_dir_does_not_follow_a_symlink(tmp_path, valid_command):
    cmd_file = tmp_path / "cmd.json"
    cmd_file.write_text(json.dumps(valid_command), encoding="utf-8")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "keep.txt").write_text("keep", encoding="utf-8")
    linked = tmp_path / "linked-out"
    linked.symlink_to(outside)
    via = tmp_path / "via"
    via.symlink_to(tmp_path)
    nested = via / "jobs"
    errors = []
    for dest in (linked, nested):
        try:
            build_antigravity_worker_job.build_worker_job(
                cmd_file, dest, schema_path=None, memory_repo_path=None,
            )
        except SystemExit as exc:
            errors.append(str(exc))
        else:
            errors.append("wrote")
    leaked = sorted(p.name for p in outside.iterdir())
    assert errors == [
        "WORKER_JOB_BUILDER_ERROR: refusing to follow a symlink",
        "WORKER_JOB_BUILDER_ERROR: refusing to follow a symlink",
    ] and leaked == ["keep.txt"] and linked.is_symlink(), (errors, leaked, linked.is_symlink())

def test_bool_max_iterations_is_not_one(valid_command):
    command = json.loads(json.dumps(valid_command))
    command["max_iterations"] = True
    command_ok, command_reason = build_antigravity_worker_job.validate_command_for_job(command)
    job = _valid_job()
    job["max_iterations"] = True
    job_ok, job_reason = build_antigravity_worker_job.validate_worker_job_against_schema(job, None)
    numeric_ok, numeric_reason = build_antigravity_worker_job.validate_command_for_job(valid_command)
    assert command_ok is False and job_ok is False and numeric_ok is True, (
        command_ok, command_reason, job_ok, job_reason, numeric_ok, numeric_reason,
    )


def test_float_max_iterations_is_not_one(valid_command):
    command = json.loads(json.dumps(valid_command))
    command["max_iterations"] = 1.0
    command_ok, command_reason = build_antigravity_worker_job.validate_command_for_job(command)
    job = _valid_job()
    job["max_iterations"] = 1.0
    job_ok, job_reason = build_antigravity_worker_job.validate_worker_job_against_schema(job, None)
    numeric = json.loads(json.dumps(valid_command))
    numeric["max_iterations"] = 1
    numeric_ok, numeric_reason = build_antigravity_worker_job.validate_command_for_job(numeric)
    two = json.loads(json.dumps(valid_command))
    two["max_iterations"] = 2
    two_ok, two_reason = build_antigravity_worker_job.validate_command_for_job(two)
    assert (command_ok, command_reason, job_ok, job_reason, numeric_ok, numeric_reason, two_ok, two_reason) == (
        False,
        "max_iterations must be 1, got 1.0",
        False,
        "Invalid max_iterations: 1.0 (strictly 1 required)",
        True,
        "VALID",
        False,
        "max_iterations must be 1, got 2",
    )


def test_memory_repo_cli_does_not_follow_a_symlink(tmp_path, valid_command):
    def run(mem: Path):
        cmd = tmp_path / f"cmd-{mem.name}.json"
        cmd.write_text(json.dumps(valid_command), encoding="utf-8")
        out = tmp_path / f"out-{mem.name}"
        argv = [
            "prog",
            "--command", str(cmd),
            "--output-dir", str(out),
            "--memory-repo", str(mem),
        ]
        with mock.patch.object(sys, "argv", argv):
            try:
                build_antigravity_worker_job.main()
                err = None
            except SystemExit as exc:
                err = str(exc)
        names = sorted(p.name for p in out.iterdir()) if out.exists() else []
        body = (out / names[0]).read_text(encoding="utf-8") if names else ""
        return err, names, body

    real = tmp_path / "real-memory"
    real.mkdir()
    (real / "PROJECT_STATE.md").write_text("SECRET-MEMORY-BODY\n", encoding="utf-8")
    linked = tmp_path / "linked-memory"
    linked.symlink_to(real)

    parent_real = tmp_path / "parent-real"
    nested = parent_real / "repo"
    nested.mkdir(parents=True)
    (nested / "PROJECT_STATE.md").write_text("SECRET-PARENT-BODY\n", encoding="utf-8")
    parent_link = tmp_path / "parent-link"
    parent_link.symlink_to(parent_real)

    plain = tmp_path / "plain-memory"
    plain.mkdir()
    (plain / "PROJECT_STATE.md").write_text("PLAIN-MEMORY-BODY\n", encoding="utf-8")

    err_link, names_link, body_link = run(linked)
    err_parent, names_parent, body_parent = run(parent_link / "repo")
    err_plain, names_plain, body_plain = run(plain)
    refused = "WORKER_JOB_BUILDER_ERROR: refusing to follow a symlink"
    assert (
        err_link == refused
        and names_link == []
        and "SECRET-MEMORY-BODY" not in body_link
        and err_parent == refused
        and names_parent == []
        and "SECRET-PARENT-BODY" not in body_parent
        and err_plain is None
        and names_plain == ["t1-worker-job.json"]
        and "PLAIN-MEMORY-BODY" in body_plain
        and linked.is_symlink()
        and parent_link.is_symlink()
    ), (
        err_link, names_link, "SECRET-MEMORY-BODY" in body_link,
        err_parent, names_parent, "SECRET-PARENT-BODY" in body_parent,
        err_plain, names_plain, "PLAIN-MEMORY-BODY" in body_plain,
    )

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

