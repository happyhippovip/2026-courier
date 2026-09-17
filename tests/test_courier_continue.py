import pytest
import subprocess
import json
from pathlib import Path

def setup_ledger(tmp_path, unproven_edges, blocker):
    record = {
        "PROJECT": "Courier",
        "GOAL": "TEST-GOAL",
        "CURRENT_SHA": "0000000000000000000000000000000000000000",
        "BRANCH": "test-branch",
        "RUNTIME_IDENTITY": "test",
        "RUNTIME_OWNER": "test",
        "STATUS": "TEST",
        "PROVEN_EDGES": [],
        "UNPROVEN_EDGES": unproven_edges,
        "FIRST_CAUSAL_BLOCKER": blocker,
        "BLOCKER_OWNER": "Human",
        "NEXT_EXECUTABLE_ACTION": "test",
        "ACTIVE_WRITERS": [],
        "COLLISION_SCOPE": [],
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
        "evidence": [
            {
                "source_url": "https://test.com",
                "source_type": "MACHINE_ARTIFACT",
                "observed_at": "2026-09-17T12:00:00Z",
                "evidence_sha": "0000000000000000000000000000000000000000",
                "runtime_binding": "test",
                "validity": "UNKNOWN",
                "reason": "test"
            }
        ],
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
    
    # Write temp files
    record_path = tmp_path / "record.json"
    guard_path = tmp_path / "guard.json"
    ledger_path = tmp_path / "agent_handoff_ledger.json"
    
    record_path.write_text(json.dumps(record))
    guard_path.write_text(json.dumps(guard))
    
    repo_dir = Path(__file__).parent.parent.resolve()
    script = repo_dir / "scripts" / "agent_handoff_ledger.py"
    
    subprocess.run(["python3", str(script), "init", str(ledger_path), "--record", str(record_path), "--guard", str(guard_path)], check=True)
    return ledger_path

def run_continue(ledger_path, mock_sha="0000000000000000000000000000000000000000", mock_branch="test-branch"):
    repo_dir = Path(__file__).parent.parent.resolve()
    script = repo_dir / "scripts" / "courier_continue.py"
    
    env = {"MOCK_SHA": mock_sha, "MOCK_BRANCH": mock_branch, "MOCK_LEDGER": str(ledger_path), "PYTHONPATH": str(repo_dir)}
    result = subprocess.run(["python3", str(script)], env=env, capture_output=True, text=True)
    return result

def test_scope_local_gates(tmp_path):
    ledger_path = setup_ledger(tmp_path, ["independent task A"], "HUMAN_REQUIRED_CONTACT")
    res = run_continue(ledger_path)
    assert res.returncode == 0
    assert "Selected Next Action: Prove edge: independent task A" in res.stdout
    assert "MINIMAL TASK PACKET" in res.stdout

def test_global_stop(tmp_path):
    ledger_path = setup_ledger(tmp_path, [], "HUMAN_REQUIRED_CONTACT")
    res = run_continue(ledger_path)
    assert res.returncode == 0
    assert "GLOBAL STOP: CLEAN_IDLE" in res.stdout
    assert "No safe, unowned, independent executable tasks exist" in res.stdout

def test_stale_ledger_fail_closed(tmp_path):
    ledger_path = setup_ledger(tmp_path, ["independent task A"], "NONE")
    res = run_continue(ledger_path, mock_sha="1111111111111111111111111111111111111111")
    assert res.returncode == 3
    assert "Ledger is stale. Fail closed" in res.stdout
