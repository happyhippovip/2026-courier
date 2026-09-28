import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
import json

def test_run_chief_relay_cycle_no_files(tmp_path, monkeypatch):
    import scripts.run_chief_relay_cycle as script
    
    incoming = tmp_path / "incoming"
    processed = tmp_path / "processed"
    incoming.mkdir()
    processed.mkdir()
    
    res = script.run_cycle(
        repo_dir=tmp_path,
        incoming_dir=incoming,
        processed_dir=processed,
        dispatch_dir=tmp_path / "dispatch",
        proposals_dir=tmp_path / "proposals",
        approvals_dir=tmp_path / "approvals",
        decisions_dir=tmp_path / "decisions",
        memory_repo=None,
        enable_auto_memory=False,
        memory_dry_run=False,
        pull=False,
        push=False
    )
    assert res["status"] == "IDLE"

def test_run_chief_relay_cycle_success(tmp_path, monkeypatch):
    import scripts.run_chief_relay_cycle as script
    
    incoming = tmp_path / "incoming"
    processed = tmp_path / "processed"
    dispatch = tmp_path / "dispatch"
    proposals = tmp_path / "proposals"
    approvals = tmp_path / "approvals"
    decisions = tmp_path / "decisions"
    
    for d in [incoming, processed, dispatch, proposals, approvals, decisions]:
        d.mkdir(exist_ok=True)
        
    cmd_file = incoming / "cmd-1.json"
    cmd_file.write_text(json.dumps({
        "schema_version": "2.0",
        "type": "COMMAND",
        "status": "NEW",
        "source": "chief",
        "destination": "antigravity",
        "message_id": "msg-1",
        "task_id": "t-1",
        "payload": {}
    }))
    
    def mock_run(*args, **kwargs):
        class MockProc:
            returncode = 0
            stdout = '{"status": "MOCK"}'
            stderr = ""
        
        args_str = str(args[0])
        
        # When worker job builder runs, create the worker job
        if "build_antigravity_worker_job.py" in args_str:
            job_file = dispatch / "t-1-worker-job.json"
            job_file.write_text(json.dumps({}))
            
        # When consumer runs, it should create result file
        if "consume_chief_command.py" in args_str:
            res_file = processed / "t-1-result.json"
            res_file.write_text(json.dumps({}))
            
        return MockProc()
        
    monkeypatch.setattr(script.subprocess, "run", mock_run)
    
    res = script.run_cycle(
        repo_dir=tmp_path,
        incoming_dir=incoming,
        processed_dir=processed,
        dispatch_dir=dispatch,
        proposals_dir=proposals,
        approvals_dir=approvals,
        decisions_dir=decisions,
        memory_repo=None,
        enable_auto_memory=False,
        memory_dry_run=False,
        pull=False,
        push=False
    )
    
    assert res["status"] == "COMPLETED"
    assert res["task_id"] == "t-1"

