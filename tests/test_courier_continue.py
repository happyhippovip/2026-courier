import sys
import pytest
import subprocess
import json
from pathlib import Path
import os

def setup_ledger(tmp_path, unproven_edges, blocker, proven_edges=None, active_writers=None, collision_scope=None, blocker_owner="Human"):
    record = {
        "PROJECT": "Courier",
        "GOAL": "TEST-GOAL",
        "CURRENT_SHA": "0000000000000000000000000000000000000000",
        "BRANCH": "test-branch",
        "RUNTIME_IDENTITY": "test",
        "RUNTIME_OWNER": "test",
        "STATUS": "TEST",
        "PROVEN_EDGES": proven_edges or [],
        "UNPROVEN_EDGES": unproven_edges,
        "FIRST_CAUSAL_BLOCKER": blocker,
        "BLOCKER_OWNER": blocker_owner,
        "NEXT_EXECUTABLE_ACTION": "test",
        "ACTIVE_WRITERS": active_writers or [],
        "COLLISION_SCOPE": collision_scope or [],
        "GOALS_SUBMITTED": 0,
        "TASKS_COMPLETED": 0,
        "WORKERS_USED": 0,
        "USER_CONTINUE_MESSAGES": 0,
        "MANUAL_PROCESS_RESTARTS": 0,
        "DUPLICATE_EXTERNAL_EFFECTS": 0,
        "TEMP_TASK_PROCESSES_AFTER_DONE": 0,
        "CLEAN_IDLE": "UNKNOWN",
        "QUEUE_INDEPENDENT": "YES",
        "LAST_EVIDENCE": [],
        "LAST_UPDATED_BY": "test",
        "CONTINUATION_CHECKPOINT": "none"
    }
    
    guard = {
        "acceptance_predicate": {
            "name": "Global-Stop",
            "version": "1.0",
            "required_results": ["ISSUE_STATE"],
            "results": {
                "ISSUE_STATE": {
                    "status": "UNKNOWN",
                    "observed_value": "NO_FURTHER_ACTION",
                    "evidence_urls": ["https://test.com"]
                }
            }
        },
        "binding": {
            "branch": "test-branch",
            "current_sha": "0000000000000000000000000000000000000000",
            "runtime_identity": "test"
        },
        "evidence": [{"source_url":"https://test.com","source_type":"MACHINE_ARTIFACT","observed_at":"2026-09-17T12:00:00Z","evidence_sha":"0000000000000000000000000000000000000000","runtime_binding":"test","validity":"UNKNOWN","reason":"test"}],
        "flow": [
            "EXECUTION",
            "EVIDENCE",
            "ACCEPTANCE_GUARD",
            "LEDGER_TRANSITION",
            "NEXT_EXECUTABLE_ACTION"
        ],
        "transition_state": "PROVISIONAL",
        "worker_state": "IDLE/YIELDED"
    }
    
    record_path = tmp_path / "record.json"
    guard_path = tmp_path / "guard.json"
    ledger_path = tmp_path / "agent_handoff_ledger.json"
    
    record_path.write_text(json.dumps(record))
    guard_path.write_text(json.dumps(guard))
    
    repo_dir = Path(__file__).parent.parent.resolve()
    script = repo_dir / "scripts" / "agent_handoff_ledger.py"
    
    subprocess.run([sys.executable, str(script), "init", str(ledger_path), "--record", str(record_path), "--guard", str(guard_path)], check=True)
    return ledger_path

def run_continue(ledger_path, mock_sha="0000000000000000000000000000000000000000", mock_branch="test-branch", run=False):
    repo_dir = Path(__file__).parent.parent.resolve()
    script = repo_dir / "scripts" / "courier_continue.py"
    
    env = os.environ.copy()
    env.update({"MOCK_SHA": mock_sha, "MOCK_BRANCH": mock_branch, "MOCK_LEDGER": str(ledger_path), "PYTHONPATH": str(repo_dir)})
    
    cmd = [sys.executable, str(script)]
    if run:
        cmd.append("--run")
        
    result = subprocess.run(cmd, env=env, capture_output=True, text=True)
    return result

def test_multiple_independent_tasks_concurrent_progress(tmp_path):
    ledger_path = setup_ledger(tmp_path, [], "HUMAN_REQUIRED", proven_edges=[])
    res = run_continue(ledger_path, run=True)
    
    assert "Executing/Delegating task: Prove edge: PILOT INTAKE" in res.stdout
    assert "Executing/Delegating task: Prove edge: SALES PACKAGE" in res.stdout
    assert "Executing/Delegating task: Prove edge: POST-PILOT HARDENING" in res.stdout

def test_busy_worker_independent_task_continues(tmp_path):
    ledger_path = setup_ledger(tmp_path, [], "NONE", collision_scope=["LEDGER/HANDOFF"])
    res = run_continue(ledger_path, run=False)
    
    assert "Prove edge: PILOT INTAKE" in res.stdout

def test_human_gate_independent_task_continues(tmp_path):
    ledger_path = setup_ledger(tmp_path, [], "HUMAN_REQUIRED", proven_edges=["LEDGER/HANDOFF"])
    res = run_continue(ledger_path, run=False)
    
    assert "Prove edge: PILOT INTAKE" in res.stdout

def test_money_gate_free_task_continues(tmp_path):
    ledger_path = setup_ledger(tmp_path, [], "MONEY_REQUIRED", proven_edges=["LEDGER/HANDOFF"])
    res = run_continue(ledger_path, run=False)
    
    assert "Prove edge: PR41 ACCEPTANCE" in res.stdout

def test_provider_unavailable_alternate_worker_continues(tmp_path):
    ledger_path = setup_ledger(tmp_path, [], "PROVIDER_QUOTA_EXHAUSTED", blocker_owner="other_worker")
    res = run_continue(ledger_path, run=False)
    
    assert "Prove edge: LEDGER/HANDOFF" in res.stdout

def test_writer_collision_serialize_colliding_scope(tmp_path):
    ledger_path = setup_ledger(tmp_path, [], "NONE", collision_scope=["LEDGER/HANDOFF"])
    res = run_continue(ledger_path, run=False)
    
    assert "Prove edge: PILOT INTAKE" in res.stdout

def test_stale_ledger_fail_closed(tmp_path):
    ledger_path = setup_ledger(tmp_path, [], "NONE")
    res = run_continue(ledger_path, mock_sha="1111111111111111111111111111111111111111")
    assert res.returncode == 3
    assert "Ledger is stale. Fail closed" in res.stdout

def test_all_scopes_blocked_true_global_stop(tmp_path):
    ledger_path = setup_ledger(tmp_path, [], "HUMAN_REQUIRED_PUBLIC_REPO_VISIBILITY", proven_edges=["LEDGER/HANDOFF", "PR41 ACCEPTANCE", "RELEASE", "PILOT INTAKE", "SALES PACKAGE", "FIRST PILOT", "POST-PILOT HARDENING"])
    res = run_continue(ledger_path)
    assert res.returncode == 0
    assert "GLOBAL STOP: CLEAN_IDLE" in res.stdout
