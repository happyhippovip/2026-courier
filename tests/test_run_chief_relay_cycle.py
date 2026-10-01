import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from scripts.run_chief_relay_cycle import (
    fail,
    is_command_pending,
    discover_pending_command,
    run_cycle,
)

def test_fail():
    with pytest.raises(SystemExit) as excinfo:
        fail("Test error")
    assert "RELAY_CYCLE_ERROR: Test error" in str(excinfo.value)

def test_is_command_pending_invalid_json(tmp_path):
    cmd_file = tmp_path / "cmd.json"
    cmd_file.write_text("{invalid json", encoding="utf-8")
    assert is_command_pending(cmd_file, tmp_path) is False

def test_is_command_pending_not_pending(tmp_path):
    cmd_file = tmp_path / "cmd.json"
    cmd_file.write_text(json.dumps({
        "schema_version": "2.0",
        "type": "COMMAND",
        "status": "COMPLETED",
        "source": "chief",
        "destination": "antigravity",
        "message_id": "msg-123"
    }), encoding="utf-8")
    assert is_command_pending(cmd_file, tmp_path) is False

def test_is_command_pending_valid(tmp_path):
    processed_dir = tmp_path / "processed"
    processed_dir.mkdir()
    
    cmd_file = tmp_path / "cmd.json"
    cmd_file.write_text(json.dumps({
        "schema_version": "2.0",
        "type": "COMMAND",
        "status": "NEW",
        "source": "chief",
        "destination": "antigravity",
        "message_id": "msg-123"
    }), encoding="utf-8")
    assert is_command_pending(cmd_file, processed_dir) is True

def test_is_command_pending_already_processed(tmp_path):
    processed_dir = tmp_path / "processed"
    processed_dir.mkdir()
    proc_file = processed_dir / "proc.json"
    proc_file.write_text(json.dumps({"parent_id": "msg-123"}), encoding="utf-8")

    cmd_file = tmp_path / "cmd.json"
    cmd_file.write_text(json.dumps({
        "schema_version": "2.0",
        "type": "COMMAND",
        "status": "NEW",
        "source": "chief",
        "destination": "antigravity",
        "message_id": "msg-123"
    }), encoding="utf-8")
    assert is_command_pending(cmd_file, processed_dir) is False

def test_discover_pending_command_empty(tmp_path):
    incoming = tmp_path / "incoming"
    processed = tmp_path / "processed"
    assert discover_pending_command(incoming, processed) is None

def test_discover_pending_command_found(tmp_path):
    incoming = tmp_path / "incoming"
    incoming.mkdir()
    processed = tmp_path / "processed"
    processed.mkdir()

    cmd_file = incoming / "cmd.json"
    cmd_file.write_text(json.dumps({
        "schema_version": "2.0",
        "type": "COMMAND",
        "status": "NEW",
        "source": "chief",
        "destination": "antigravity",
        "message_id": "msg-123"
    }), encoding="utf-8")
    
    found = discover_pending_command(incoming, processed)
    assert found == cmd_file

@patch("scripts.run_chief_relay_cycle.subprocess.run")
def test_run_cycle_no_pending(mock_run, tmp_path):
    res = run_cycle(
        repo_dir=tmp_path,
        incoming_dir=tmp_path / "incoming",
        processed_dir=tmp_path / "processed",
        dispatch_dir=tmp_path / "dispatch",
        memory_repo=None,
    )
    assert res["status"] == "IDLE"

@patch("scripts.run_chief_relay_cycle.subprocess.run")
def test_run_cycle_full_success(mock_run, tmp_path):
    incoming = tmp_path / "incoming"
    incoming.mkdir()
    processed = tmp_path / "processed"
    processed.mkdir()
    dispatch = tmp_path / "dispatch"
    dispatch.mkdir()
    proposals = tmp_path / "proposals"
    proposals.mkdir()
    approvals = tmp_path / "approvals"
    approvals.mkdir()
    decisions = tmp_path / "decisions"
    decisions.mkdir()
    
    memory_repo = tmp_path / "memory_repo"
    memory_repo.mkdir()

    # Create pending command
    cmd_file = incoming / "cmd.json"
    cmd_file.write_text(json.dumps({
        "schema_version": "2.0",
        "type": "COMMAND",
        "status": "NEW",
        "source": "chief",
        "destination": "antigravity",
        "message_id": "msg-123",
        "task_id": "task-1"
    }), encoding="utf-8")

    def mock_subprocess_run(args, **kwargs):
        cmd_str = " ".join(args)
        if "build_antigravity_worker_job.py" in cmd_str and "--validate" not in cmd_str:
            (dispatch / "task-1-worker-job.json").write_text("{}")
            return MagicMock(returncode=0)
        if "build_antigravity_worker_job.py" in cmd_str and "--validate" in cmd_str:
            return MagicMock(returncode=0)
        if "consume_chief_command.py" in cmd_str:
            (processed / "task-1-result.json").write_text("{}")
            return MagicMock(returncode=0)
        if "validate_chief_relay.py" in cmd_str:
            return MagicMock(returncode=0)
        if "build_memory_update_proposal.py" in cmd_str:
            (proposals / "task-1-memory-proposal.json").write_text("{}")
            return MagicMock(returncode=0)
        if "evaluate_memory_proposal_for_auto_approval.py" in cmd_str:
            (decisions / "task-1-chief-decision.json").write_text(json.dumps({"decision": "AUTO_APPROVE", "reason_codes": []}))
            (approvals / "task-1-auto-approval.json").write_text("{}")
            return MagicMock(returncode=0)
        if "apply_memory_update_proposal.py" in cmd_str:
            return MagicMock(returncode=0, stdout='{"success": true}')
        if "git" in cmd_str:
            return MagicMock(returncode=0, stdout='abcdef123')
        return MagicMock(returncode=0) # default

    mock_run.side_effect = mock_subprocess_run

    res = run_cycle(
        repo_dir=tmp_path,
        incoming_dir=incoming,
        processed_dir=processed,
        dispatch_dir=dispatch,
        proposals_dir=proposals,
        approvals_dir=approvals,
        decisions_dir=decisions,
        memory_repo=memory_repo,
        pull=True,
        push=True,
    )
    
    assert res["status"] == "COMPLETED"
    assert res["task_id"] == "task-1"
    assert res["memory_cycle"]["decision"] == "AUTO_APPROVE"
    assert res["commit_sha"] == "abcdef123"

@patch("scripts.run_chief_relay_cycle.subprocess.run")
def test_run_cycle_subprocess_failure(mock_run, tmp_path):
    incoming = tmp_path / "incoming"
    incoming.mkdir()
    processed = tmp_path / "processed"
    processed.mkdir()
    dispatch = tmp_path / "dispatch"
    dispatch.mkdir()

    cmd_file = incoming / "cmd.json"
    cmd_file.write_text(json.dumps({
        "schema_version": "2.0",
        "type": "COMMAND",
        "status": "NEW",
        "source": "chief",
        "destination": "antigravity",
        "message_id": "msg-123",
        "task_id": "task-1"
    }), encoding="utf-8")

    # Mock builder failure
    mock_run.return_value = MagicMock(returncode=1, stderr="Boom")
    with pytest.raises(SystemExit) as excinfo:
        run_cycle(
            repo_dir=tmp_path,
            incoming_dir=incoming,
            processed_dir=processed,
            dispatch_dir=dispatch,
        )
    assert "Worker job builder failed: Boom" in str(excinfo.value)
    
    # Mock validate job failure
    def mock_val_job(args, **kwargs):
        cmd_str = " ".join(args)
        if "build_antigravity_worker_job.py" in cmd_str and "--validate" not in cmd_str:
            (dispatch / "task-1-worker-job.json").write_text("{}")
            return MagicMock(returncode=0)
        return MagicMock(returncode=1, stderr="Val error")
    mock_run.side_effect = mock_val_job
    with pytest.raises(SystemExit) as excinfo:
        run_cycle(
            repo_dir=tmp_path,
            incoming_dir=incoming,
            processed_dir=processed,
            dispatch_dir=dispatch,
        )
    assert "Worker job JSON Schema validation failed: Val error" in str(excinfo.value)

    # Mock consumer failure
    def mock_consumer(args, **kwargs):
        cmd_str = " ".join(args)
        if "build_antigravity_worker_job.py" in cmd_str:
            (dispatch / "task-1-worker-job.json").write_text("{}")
            return MagicMock(returncode=0)
        return MagicMock(returncode=1, stderr="Consume error")
    mock_run.side_effect = mock_consumer
    with pytest.raises(SystemExit) as excinfo:
        run_cycle(
            repo_dir=tmp_path,
            incoming_dir=incoming,
            processed_dir=processed,
            dispatch_dir=dispatch,
        )
    assert "Consumer failed: Consume error" in str(excinfo.value)

    # Mock val failure
    def mock_val_relay(args, **kwargs):
        cmd_str = " ".join(args)
        if "build_antigravity_worker_job.py" in cmd_str:
            (dispatch / "task-1-worker-job.json").write_text("{}")
            return MagicMock(returncode=0)
        if "consume_chief_command.py" in cmd_str:
            (processed / "task-1-result.json").write_text("{}")
            return MagicMock(returncode=0)
        return MagicMock(returncode=1, stderr="Relay error")
    mock_run.side_effect = mock_val_relay
    with pytest.raises(SystemExit) as excinfo:
        run_cycle(
            repo_dir=tmp_path,
            incoming_dir=incoming,
            processed_dir=processed,
            dispatch_dir=dispatch,
        )
    assert "Result validation failed: Relay error" in str(excinfo.value)

    # Mock proposal builder failure
    def mock_prop_builder(args, **kwargs):
        cmd_str = " ".join(args)
        if "build_antigravity_worker_job.py" in cmd_str:
            (dispatch / "task-1-worker-job.json").write_text("{}")
            return MagicMock(returncode=0)
        if "consume_chief_command.py" in cmd_str:
            (processed / "task-1-result.json").write_text("{}")
            return MagicMock(returncode=0)
        if "validate_chief_relay.py" in cmd_str:
            return MagicMock(returncode=0)
        return MagicMock(returncode=1, stderr="Prop error")
    mock_run.side_effect = mock_prop_builder
    memory_repo = tmp_path / "memory"
    memory_repo.mkdir()
    with pytest.raises(SystemExit) as excinfo:
        run_cycle(
            repo_dir=tmp_path,
            incoming_dir=incoming,
            processed_dir=processed,
            dispatch_dir=dispatch,
            memory_repo=memory_repo
        )
    assert "Memory proposal builder failed: Prop error" in str(excinfo.value)

    # Mock evaluate memory proposal failure
    proposals = tmp_path / "proposals"
    proposals.mkdir()
    def mock_evaluate_memory(args, **kwargs):
        cmd_str = " ".join(args)
        if "build_antigravity_worker_job.py" in cmd_str:
            (dispatch / "task-1-worker-job.json").write_text("{}")
            return MagicMock(returncode=0)
        if "consume_chief_command.py" in cmd_str:
            (processed / "task-1-result.json").write_text("{}")
            return MagicMock(returncode=0)
        if "validate_chief_relay.py" in cmd_str:
            return MagicMock(returncode=0)
        if "build_memory_update_proposal.py" in cmd_str:
            (proposals / "task-1-memory-proposal.json").write_text("{}")
            return MagicMock(returncode=0)
        return MagicMock(returncode=1, stderr="Eval error")
    mock_run.side_effect = mock_evaluate_memory
    with pytest.raises(SystemExit) as excinfo:
        run_cycle(
            repo_dir=tmp_path,
            incoming_dir=incoming,
            processed_dir=processed,
            dispatch_dir=dispatch,
            proposals_dir=proposals,
            memory_repo=memory_repo
        )
    assert "Autonomous Chief Policy evaluation failed: Eval error" in str(excinfo.value)

    # Mock apply memory update proposal failure
    decisions = tmp_path / "decisions"
    decisions.mkdir()
    approvals = tmp_path / "approvals"
    approvals.mkdir()
    def mock_apply_memory(args, **kwargs):
        cmd_str = " ".join(args)
        if "build_antigravity_worker_job.py" in cmd_str:
            (dispatch / "task-1-worker-job.json").write_text("{}")
            return MagicMock(returncode=0)
        if "consume_chief_command.py" in cmd_str:
            (processed / "task-1-result.json").write_text("{}")
            return MagicMock(returncode=0)
        if "validate_chief_relay.py" in cmd_str:
            return MagicMock(returncode=0)
        if "build_memory_update_proposal.py" in cmd_str:
            (proposals / "task-1-memory-proposal.json").write_text("{}")
            return MagicMock(returncode=0)
        if "evaluate_memory_proposal_for_auto_approval.py" in cmd_str:
            (decisions / "task-1-chief-decision.json").write_text(json.dumps({"decision": "AUTO_APPROVE", "reason_codes": []}))
            (approvals / "task-1-auto-approval.json").write_text("{}")
            return MagicMock(returncode=0)
        if "apply_memory_update_proposal.py" in cmd_str:
            return MagicMock(returncode=1, stderr="Apply error")
        return MagicMock(returncode=0)
    mock_run.side_effect = mock_apply_memory
    with pytest.raises(SystemExit) as excinfo:
        run_cycle(
            repo_dir=tmp_path,
            incoming_dir=incoming,
            processed_dir=processed,
            dispatch_dir=dispatch,
            proposals_dir=proposals,
            decisions_dir=decisions,
            approvals_dir=approvals,
            memory_repo=memory_repo
        )
    assert "Memory write handler failed: Apply error" in str(excinfo.value)



    # Mock git push failure
    def mock_git_push(args, **kwargs):
        cmd_str = " ".join(args)
        if "build_antigravity_worker_job.py" in cmd_str:
            (dispatch / "task-1-worker-job.json").write_text("{}")
            return MagicMock(returncode=0)
        if "consume_chief_command.py" in cmd_str:
            (processed / "task-1-result.json").write_text("{}")
            return MagicMock(returncode=0)
        if "validate_chief_relay.py" in cmd_str:
            return MagicMock(returncode=0)
        if "build_memory_update_proposal.py" in cmd_str:
            (proposals / "task-1-memory-proposal.json").write_text("{}")
            return MagicMock(returncode=0)
        if "evaluate_memory_proposal_for_auto_approval.py" in cmd_str:
            (decisions / "task-1-chief-decision.json").write_text(json.dumps({"decision": "AUTO_APPROVE", "reason_codes": []}))
            (approvals / "task-1-auto-approval.json").write_text("{}")
            return MagicMock(returncode=0)
        if "apply_memory_update_proposal.py" in cmd_str:
            return MagicMock(returncode=0, stdout='{"success": true}')
        if "git" in cmd_str and "push" in cmd_str:
            return MagicMock(returncode=1, stderr="Git Push Error")
        return MagicMock(returncode=0)
    mock_run.side_effect = mock_git_push
    with pytest.raises(SystemExit) as excinfo:
        run_cycle(
            repo_dir=tmp_path,
            incoming_dir=incoming,
            processed_dir=processed,
            dispatch_dir=dispatch,
            proposals_dir=proposals,
            decisions_dir=decisions,
            approvals_dir=approvals,
            memory_repo=memory_repo,
            push=True
        )
    assert "Git push failed: Git Push Error" in str(excinfo.value)

def test_is_command_pending_invalid_fields(tmp_path):
    processed_dir = tmp_path / "processed"
    processed_dir.mkdir()
    cmd_file = tmp_path / "cmd.json"

    # wrong schema_version
    cmd_file.write_text(json.dumps({"schema_version": "1.0", "type": "COMMAND", "status": "NEW", "source": "chief", "destination": "antigravity", "message_id": "123"}), encoding="utf-8")
    assert is_command_pending(cmd_file, processed_dir) is False

    # wrong type
    cmd_file.write_text(json.dumps({"schema_version": "2.0", "type": "RESULT", "status": "NEW", "source": "chief", "destination": "antigravity", "message_id": "123"}), encoding="utf-8")
    assert is_command_pending(cmd_file, processed_dir) is False

    # wrong source
    cmd_file.write_text(json.dumps({"schema_version": "2.0", "type": "COMMAND", "status": "NEW", "source": "other", "destination": "antigravity", "message_id": "123"}), encoding="utf-8")
    assert is_command_pending(cmd_file, processed_dir) is False

    # missing message_id
    cmd_file.write_text(json.dumps({"schema_version": "2.0", "type": "COMMAND", "status": "NEW", "source": "chief", "destination": "antigravity"}), encoding="utf-8")
    assert is_command_pending(cmd_file, processed_dir) is False

def test_is_command_pending_corrupt_processed(tmp_path):
    processed_dir = tmp_path / "processed"
    processed_dir.mkdir()
    proc_file = processed_dir / "proc.json"
    proc_file.write_text("{bad json", encoding="utf-8")

    cmd_file = tmp_path / "cmd.json"
    cmd_file.write_text(json.dumps({
        "schema_version": "2.0",
        "type": "COMMAND",
        "status": "NEW",
        "source": "chief",
        "destination": "antigravity",
        "message_id": "msg-123"
    }), encoding="utf-8")
    assert is_command_pending(cmd_file, processed_dir) is True

@patch("scripts.run_chief_relay_cycle.subprocess.run")
def test_run_cycle_pull_warning(mock_run, tmp_path):
    mock_run.return_value = MagicMock(returncode=1, stderr="Pull warning")
    res = run_cycle(
        repo_dir=tmp_path,
        incoming_dir=tmp_path / "incoming",
        processed_dir=tmp_path / "processed",
        dispatch_dir=tmp_path / "dispatch",
        pull=True
    )
    assert res["status"] == "IDLE"

@patch("scripts.run_chief_relay_cycle.subprocess.run")
def test_run_cycle_dry_run(mock_run, tmp_path):
    incoming = tmp_path / "incoming"
    incoming.mkdir()
    processed = tmp_path / "processed"
    processed.mkdir()
    dispatch = tmp_path / "dispatch"
    dispatch.mkdir()
    proposals = tmp_path / "proposals"
    proposals.mkdir()
    approvals = tmp_path / "approvals"
    approvals.mkdir()
    decisions = tmp_path / "decisions"
    decisions.mkdir()
    memory_repo = tmp_path / "memory_repo"
    memory_repo.mkdir()

    cmd_file = incoming / "cmd.json"
    cmd_file.write_text(json.dumps({
        "schema_version": "2.0",
        "type": "COMMAND",
        "status": "NEW",
        "source": "chief",
        "destination": "antigravity",
        "message_id": "msg-123",
        "task_id": "task-1"
    }), encoding="utf-8")

    def mock_subprocess_run(args, **kwargs):
        cmd_str = " ".join(args)
        if "build_antigravity_worker_job.py" in cmd_str and "--validate" not in cmd_str:
            (dispatch / "task-1-worker-job.json").write_text("{}")
            return MagicMock(returncode=0)
        if "build_antigravity_worker_job.py" in cmd_str and "--validate" in cmd_str:
            return MagicMock(returncode=0)
        if "consume_chief_command.py" in cmd_str:
            (processed / "task-1-result.json").write_text("{}")
            return MagicMock(returncode=0)
        if "validate_chief_relay.py" in cmd_str:
            return MagicMock(returncode=0)
        if "build_memory_update_proposal.py" in cmd_str:
            (proposals / "task-1-memory-proposal.json").write_text("{}")
            return MagicMock(returncode=0)
        if "evaluate_memory_proposal_for_auto_approval.py" in cmd_str:
            (decisions / "task-1-chief-decision.json").write_text(json.dumps({"decision": "AUTO_APPROVE", "reason_codes": []}))
            (approvals / "task-1-auto-approval.json").write_text("{}")
            return MagicMock(returncode=0)
        if "apply_memory_update_proposal.py" in cmd_str:
            assert "--dry-run" in args
            return MagicMock(returncode=0, stdout='{"success": true, "dry_run": true}')
        return MagicMock(returncode=0)

    mock_run.side_effect = mock_subprocess_run

    res = run_cycle(
        repo_dir=tmp_path,
        incoming_dir=incoming,
        processed_dir=processed,
        dispatch_dir=dispatch,
        proposals_dir=proposals,
        approvals_dir=approvals,
        decisions_dir=decisions,
        memory_repo=memory_repo,
        memory_dry_run=True,
    )
    assert res["memory_cycle"]["write_result"] == {"success": True, "dry_run": True}

