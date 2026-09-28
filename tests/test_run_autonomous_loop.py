import pytest
from pathlib import Path
import json

def test_resume_workflow_no_approval(tmp_path, monkeypatch):
    import scripts.run_autonomous_loop as script
    
    approvals_dir = tmp_path / "events/approvals"
    approvals_dir.mkdir(parents=True)
    
    loop = script.AutonomousLevel6Loop(repo_dir=tmp_path)
    
    res = loop.resume_workflow("wf-1", "c-1", [], from_round_index=0)
    assert res["status"] == "BLOCKED_HUMAN_GATE"

def test_resume_workflow_rejected(tmp_path, monkeypatch):
    import scripts.run_autonomous_loop as script
    
    approvals_dir = tmp_path / "events/approvals"
    approvals_dir.mkdir(parents=True)
    
    appr_file = approvals_dir / "wf-1-human-approval.json"
    appr_file.write_text(json.dumps({
        "workflow_id": "wf-1",
        "correlation_id": "c-1",
        "decision": "REJECT"
    }))
    
    loop = script.AutonomousLevel6Loop(repo_dir=tmp_path)
    
    res = loop.resume_workflow("wf-1", "c-1", [], from_round_index=0)
    assert res["status"] == "REJECTED_BY_HUMAN"

def test_resume_workflow_approved_no_steps(tmp_path, monkeypatch):
    import scripts.run_autonomous_loop as script
    
    approvals_dir = tmp_path / "events/approvals"
    approvals_dir.mkdir(parents=True)
    
    appr_file = approvals_dir / "wf-1-human-approval.json"
    appr_file.write_text(json.dumps({
        "workflow_id": "wf-1",
        "correlation_id": "c-1",
        "decision": "APPROVE"
    }))
    
    loop = script.AutonomousLevel6Loop(repo_dir=tmp_path)
    
    res = loop.resume_workflow("wf-1", "c-1", [{"task": "t1"}], from_round_index=1)
    assert res["status"] == "COMPLETED"
    assert res["stop_reason"] == "NO_REMAINING_STEPS"

