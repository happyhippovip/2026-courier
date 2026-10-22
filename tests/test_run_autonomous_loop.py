import pytest
import os
import json
from pathlib import Path
from unittest import mock
import threading
import sys
import uuid

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from scripts.run_autonomous_loop import (
    AutonomousLevel6Loop,
    WorkflowLockedError,
    cached_result_is_reusable,
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

def test_cached_result_without_explicit_pass_is_not_reusable():
    assert cached_result_is_reusable({"payload": {"verdict": "PASS"}}) is True
    assert cached_result_is_reusable({"payload": {"verdict": "ACCEPTED"}}) is True
    assert cached_result_is_reusable({"payload": {}}) is False
    assert cached_result_is_reusable({"payload": {"verdict": True}}) is False
    assert cached_result_is_reusable({"payload": {"verdict": "FAILED"}}) is False
    assert cached_result_is_reusable({"payload": {"verdict": "PAUSED_PROVIDER_LIMIT"}}) is False
    assert cached_result_is_reusable({"payload": "PASS"}) is False
    assert cached_result_is_reusable(None) is False


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
        with mock.patch("psutil.Process") as mock_process:
            import psutil
            def process_mock_alive(pid):
                if pid == lock_data.get("pid"):
                    m = mock.MagicMock()
                    m.create_time.return_value = lock_data.get("process_create_time")
                    return m
                elif pid == 999999:
                    m = mock.MagicMock()
                    m.create_time.return_value = 12345.0
                    return m
                raise psutil.NoSuchProcess(pid)

            mock_process.side_effect = process_mock_alive
            with pytest.raises(WorkflowLockedError):
                loop.acquire_workflow_lock(wf_id, "corr-1", "task-1")
                
            # Now simulate process is dead
            def process_mock_dead(pid):
                if pid == lock_data.get("pid"):
                    raise psutil.NoSuchProcess(pid)
                elif pid == 999999:
                    m = mock.MagicMock()
                    m.create_time.return_value = 12345.0
                    return m
                raise psutil.NoSuchProcess(pid)

            mock_process.side_effect = process_mock_dead
            # Should succeed by reclaiming stale lock
            loop.acquire_workflow_lock(wf_id, "corr-1", "task-1")
    
    # 4. Release lock
    loop.release_workflow_lock(wf_id)
    assert not lock_file.exists()


def test_unreadable_workflow_lock_is_not_taken(repo_dir):
    loop = AutonomousLevel6Loop(repo_dir=repo_dir)
    lock_file = repo_dir / "events" / "locks" / "wf-torn.lock"
    original = "{not-json"
    lock_file.write_text(original, encoding="utf-8")

    with pytest.raises(WorkflowLockedError):
        loop.acquire_workflow_lock("wf-torn", "corr-1", "task-1")

    assert lock_file.read_text(encoding="utf-8") == original


def test_two_contenders_cannot_both_acquire_a_missing_lock(repo_dir):
    """Both runners observe a missing lock, then exclusive create admits one."""
    loop_a = AutonomousLevel6Loop(repo_dir=repo_dir)
    loop_b = AutonomousLevel6Loop(repo_dir=repo_dir)
    lock_file = repo_dir / "events" / "locks" / "wf-both.lock"
    both_saw_missing = threading.Barrier(2)
    real_exists = Path.exists
    ident_to_pid = {}

    def missing_until_both_look(self):
        if self == lock_file:
            both_saw_missing.wait(timeout=5)
            return False
        return real_exists(self)

    def fake_getpid():
        return ident_to_pid[threading.get_ident()]

    def fake_process(pid):
        proc = mock.MagicMock()
        proc.create_time.return_value = float(pid)
        return proc

    outcomes = []
    gate = threading.Lock()

    def run(loop, fake_pid):
        ident_to_pid[threading.get_ident()] = fake_pid
        try:
            loop.acquire_workflow_lock("wf-both", "corr", "task")
            status = "acquired"
        except WorkflowLockedError:
            status = "refused"
        with gate:
            outcomes.append((fake_pid, status))

    with mock.patch.object(Path, "exists", missing_until_both_look), \
         mock.patch("os.getpid", fake_getpid), \
         mock.patch("psutil.Process", fake_process):
        threads = [
            threading.Thread(target=run, args=(loop_a, 111111)),
            threading.Thread(target=run, args=(loop_b, 222222)),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)
            assert not thread.is_alive()

    assert sorted(status for _, status in outcomes) == ["acquired", "refused"]
    holder = json.loads(lock_file.read_text(encoding="utf-8"))["pid"]
    assert [pid for pid, status in outcomes if status == "acquired"] == [holder]


def test_workflow_lock_without_holder_is_not_taken(repo_dir):
    loop = AutonomousLevel6Loop(repo_dir=repo_dir)
    lock_file = repo_dir / "events" / "locks" / "wf-nopid.lock"
    original = "{}\n"
    lock_file.write_text(original, encoding="utf-8")

    with pytest.raises(WorkflowLockedError):
        loop.acquire_workflow_lock("wf-nopid", "corr-1", "task-1")

    assert lock_file.read_text(encoding="utf-8") == original


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


def test_save_and_load_workflow_state(repo_dir):
    loop = AutonomousLevel6Loop(repo_dir=repo_dir)
    state = {
        "workflow_id": "wf-persisted",
        "status": "RUNNING",
        "step": 2,
    }
    saved_path = loop.save_workflow_state("wf-persisted", state)
    assert saved_path.exists()

    loaded = loop.load_workflow_state("wf-persisted")
    assert loaded is not None
    assert loaded["workflow_id"] == "wf-persisted"
    assert loaded["status"] == "RUNNING"
    assert loaded["step"] == 2
    assert "updated_at" in loaded

    # Non-existent workflow state returns None
    assert loop.load_workflow_state("non-existent-wf") is None


def test_reconcile_workflow_progress(repo_dir):
    loop = AutonomousLevel6Loop(repo_dir=repo_dir)
    plan = [
        {"task_id": "step-1", "target_agent": "antigravity"},
        {"task_id": "step-2", "target_agent": "codex"},
        {"task_id": "step-3", "target_agent": "antigravity"},
    ]

    # No events on disk -> earliest uncompleted is index 0
    idx, hist = loop.reconcile_workflow_progress(plan)
    assert idx == 0
    assert hist == []

    # Create passed decision and result for step-1
    dec_dir = repo_dir / "events" / "chief-decisions"
    proc_dir = repo_dir / "events" / "processed"
    dec_dir.mkdir(parents=True, exist_ok=True)
    proc_dir.mkdir(parents=True, exist_ok=True)

    (dec_dir / "step-1-chief-decision.json").write_text(json.dumps({
        "verdict": "ACCEPTED",
        "action": "DISPATCH_NEXT_WORKFLOW_TASK",
        "correlation_id": "corr-123",
    }))
    (proc_dir / "step-1-result.json").write_text(json.dumps({"status": "SUCCESS"}))

    idx2, hist2 = loop.reconcile_workflow_progress(plan)
    assert idx2 == 1
    assert len(hist2) == 1
    assert hist2[0]["task_id"] == "step-1"
    assert hist2[0]["verdict"] == "ACCEPTED"
    assert hist2[0]["round"] == 1


def test_workflow_lock_authority_db_integration(repo_dir):
    from courier_runtime.lease import LeaseStore

    loop = AutonomousLevel6Loop(repo_dir=repo_dir)
    wf_id = "wf-auth-test"

    lock_file = loop.acquire_workflow_lock(wf_id, "corr-test", "task-init")
    assert lock_file.exists()
    data = json.loads(lock_file.read_text())
    assert "fencing_token" in data
    assert data["fencing_token"] >= 1

    # Verify authority.db lease
    authority_db = repo_dir / "events" / "locks" / "authority.db"
    assert authority_db.exists()
    store = LeaseStore(authority_db)
    lease = store.current(f"workflow:{wf_id}")
    assert lease is not None
    assert lease.token == data["fencing_token"]
    store.close()

    # Release and verify lease is cleared in authority.db
    loop.release_workflow_lock(wf_id)
    assert not lock_file.exists()
    store2 = LeaseStore(authority_db)
    assert store2.current(f"workflow:{wf_id}") is None
    store2.close()

