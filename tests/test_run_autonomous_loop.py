import pytest
import os
import json
from pathlib import Path
from unittest import mock
import sys
import uuid

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from scripts.run_autonomous_loop import (
    AutonomousLevel6Loop,
    WorkflowLockedError
)

@pytest.fixture
def repo_dir(tmp_path):
    # Setup necessary folder structure
    (tmp_path / "events" / "locks").mkdir(parents=True)
    (tmp_path / "events" / "policies").mkdir(parents=True)
    (tmp_path / "events" / "processed").mkdir(parents=True)
    (tmp_path / "events" / "approvals").mkdir(parents=True)
    (tmp_path / "events" / "chief-decisions").mkdir(parents=True)
    return tmp_path

def test_workflow_lock(repo_dir):
    loop = AutonomousLevel6Loop(repo_dir=repo_dir)
    wf_id = "wf-test-1"
    
    # 1. Acquire lock
    lock_file = loop.acquire_workflow_lock(wf_id, "corr-1", "task-1")
    assert lock_file.exists()
    
    # 2. Re-acquire by SAME pid should work (overwrites or updates)
    lock_file2 = loop.acquire_workflow_lock(wf_id, "corr-1", "task-1")
    assert lock_file2.exists()
    
    # 3. Simulate another process holding the lock
    lock_data = json.loads(lock_file.read_text())
    # Choose a PID that is likely running but not us (e.g. 1 on linux, or our own pid but mock os.kill)
    # Since we can't easily guess a running PID on windows, we'll mock os.kill and os.getpid
    with mock.patch("os.getpid", return_value=999999):
        with mock.patch("os.kill") as mock_kill:
            # os.kill doesn't throw -> process is "alive"
            mock_kill.return_value = None
            with pytest.raises(WorkflowLockedError):
                loop.acquire_workflow_lock(wf_id, "corr-1", "task-1")
                
            # Now simulate process is dead (os.kill throws OSError)
            mock_kill.side_effect = OSError("No such process")
            # Should succeed by reclaiming stale lock
            loop.acquire_workflow_lock(wf_id, "corr-1", "task-1")
    
    # 4. Release lock
    loop.release_workflow_lock(wf_id)
    assert not lock_file.exists()


def test_check_human_approval(repo_dir):
    loop = AutonomousLevel6Loop(repo_dir=repo_dir)
    
    appr_file = repo_dir / "events" / "approvals" / "appr1.json"
    appr_file.write_text(json.dumps({
        "workflow_id": "wf-1",
        "correlation_id": "corr-1",
        "decision": "APPROVE"
    }))
    
    # Exact match
    res = loop.check_human_approval("wf-1", "corr-1")
    assert res is not None
    assert res["decision"] == "APPROVE"
    
    # Wrong correlation
    res = loop.check_human_approval("wf-1", "corr-wrong")
    assert res is None


def test_evaluate_chief_decision_needs_fix(repo_dir):
    loop = AutonomousLevel6Loop(repo_dir=repo_dir)
    
    res_file = repo_dir / "test_res.json"
    res_file.write_text(json.dumps({
        "source": "antigravity",
        "payload": {
            "verdict": "NEEDS_FIX",
            "target_file": ["file.py"]
        }
    }))
    
    decision = loop.evaluate_chief_decision(
        task_id="task-1",
        correlation_id="corr-1",
        result_file=res_file,
        workflow_id="wf-1",
        round_index=0
    )
    
    assert decision["verdict"] == "NEEDS_FIX"
    assert decision["action"] == "QUEUE_SCOPED_REPAIR_TASK"
    assert decision["next_task"]["task_id"] == "repair-task-1"
    assert decision["next_task"]["allowed_scope"] == ["file.py"]


def test_evaluate_chief_decision_human_gate_approval(repo_dir):
    loop = AutonomousLevel6Loop(repo_dir=repo_dir)
    
    # 1. Payload requires human gate, but no approval exists -> STOP_AT_HUMAN_GATE
    res_file = repo_dir / "test_res.json"
    res_file.write_text(json.dumps({
        "source": "antigravity",
        "payload": {
            "verdict": "PASS",
            "requires_human_approval": True
        }
    }))
    
    dec1 = loop.evaluate_chief_decision("t1", "c1", res_file, "wf-1", 0)
    assert dec1["verdict"] == "HUMAN_APPROVAL_REQUIRED"
    assert dec1["action"] == "STOP_AT_HUMAN_GATE"
    
    # 2. Add an approval event for this workflow/correlation
    appr_file = repo_dir / "events" / "approvals" / "appr1.json"
    appr_file.write_text(json.dumps({
        "workflow_id": "wf-1",
        "correlation_id": "c1",
        "action": "APPROVE"
    }))
    
    dec2 = loop.evaluate_chief_decision("t1", "c1", res_file, "wf-1", 0, workflow_plan=[{"task_id":"t1"}])
    # The verdict becomes ACCEPTED since it was approved, and it advances or completes
    assert dec2["verdict"] == "ACCEPTED"
    assert dec2["action"] == "COMPLETE_WORKFLOW"


def test_evaluate_chief_decision_pass_advances_plan(repo_dir):
    loop = AutonomousLevel6Loop(repo_dir=repo_dir)
    
    res_file = repo_dir / "test_res.json"
    res_file.write_text(json.dumps({
        "source": "antigravity",
        "payload": {
            "verdict": "PASS"
        }
    }))
    
    plan = [
        {"task_id": "t1"},
        {"task_id": "t2", "target_agent": "codex"}
    ]
    
    dec = loop.evaluate_chief_decision("t1", "c1", res_file, "wf-1", 0, workflow_plan=plan)
    
    assert dec["verdict"] == "ACCEPTED"
    assert dec["action"] == "DISPATCH_NEXT_WORKFLOW_TASK"
    assert dec["next_task"]["task_id"] == "t2"
    assert dec["next_task"]["target_agent"] == "codex"


def test_resume_workflow_blocked(repo_dir):
    loop = AutonomousLevel6Loop(repo_dir=repo_dir)
    # Missing approval -> stays blocked
    res = loop.resume_workflow("wf-1", "c1", [])
    assert res["status"] == "BLOCKED_HUMAN_GATE"

def test_resume_workflow_rejected(repo_dir):
    loop = AutonomousLevel6Loop(repo_dir=repo_dir)
    appr_file = repo_dir / "events" / "approvals" / "appr1.json"
    appr_file.write_text(json.dumps({
        "workflow_id": "wf-1",
        "correlation_id": "c1",
        "action": "REJECT"
    }))
    res = loop.resume_workflow("wf-1", "c1", [])
    assert res["status"] == "REJECTED_BY_HUMAN"
