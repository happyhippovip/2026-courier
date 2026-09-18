import sys
import pytest
import subprocess
import os
import json
import time
from pathlib import Path

def test_queue_independent_daemon(tmp_path):
    repo_dir = Path(__file__).parent.parent.resolve()
    # Write a mock ledger
    ledger_path = tmp_path / "agent_handoff_ledger.json"
    record_path = tmp_path / "record.json"
    guard_path = tmp_path / "guard.json"
    
    record = {
        "PROJECT": "Courier",
        "GOAL": "QUEUE-INDEPENDENT-TEST",
        "STATUS": "TEST",
        "BRANCH": "test-branch",
        "CURRENT_SHA": "0000000000000000000000000000000000000000",
        "LAST_UPDATED_BY": "test",
        "PROVEN_EDGES": [
            "LEDGER/HANDOFF", "PR41 ACCEPTANCE", "RELEASE", 
            "PUBLIC DEPLOYMENT", "PUBLICATION VERIFICATION"
        ],
        "UNPROVEN_EDGES": [],
        "FIRST_CAUSAL_BLOCKER": "NONE",
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
        "RUNTIME_OWNER": "test",
        "RUNTIME_IDENTITY": "0000000000000000000000000000000000000000",
        "CONTINUATION_CHECKPOINT": "none",
        "LAST_EVIDENCE": []
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
        "worker_state": "IDLE/YIELDED",
        "transition_state": "PROVISIONAL",
        "binding": {
            "branch": "test-branch",
            "current_sha": "0000000000000000000000000000000000000000",
            "runtime_identity": "0000000000000000000000000000000000000000"
        },
        "evidence": [{"source_url":"https://test.com","source_type":"MACHINE_ARTIFACT","observed_at":"2026-09-17T12:00:00Z","evidence_sha":"0000000000000000000000000000000000000000","runtime_binding":"test","validity":"UNKNOWN","reason":"test"}],
        "flow": [
            "EXECUTION",
            "EVIDENCE",
            "ACCEPTANCE_GUARD",
            "LEDGER_TRANSITION",
            "NEXT_EXECUTABLE_ACTION"
        ]
    }
    
    with open(record_path, "w") as f:
        json.dump(record, f)
    with open(guard_path, "w") as f:
        json.dump(guard, f)
        
    script = repo_dir / "scripts" / "agent_handoff_ledger.py"
    subprocess.run([sys.executable, str(script), "init", str(ledger_path), "--record", str(record_path), "--guard", str(guard_path)], check=True)
    
    env = os.environ.copy()
    env.update({"MOCK_SHA": "0000000000000000000000000000000000000000", "MOCK_BRANCH": "test-branch", "MOCK_LEDGER": str(ledger_path), "PYTHONPATH": str(repo_dir)})
    
    runner = repo_dir / "tests" / "mock_courier_continue.py"
    
    # Launch as a detached daemon/background process
    with open(tmp_path / "daemon.out", "w") as outf:
        p = subprocess.Popen([sys.executable, str(runner), "--run"], env=env, stdout=outf, stderr=outf, start_new_session=True)
    
    # Let it run detached
    try:
        p.wait(timeout=10)
    except subprocess.TimeoutExpired:
        p.terminate()
        p.kill()
        assert False, "Daemon run hung and timed out"

    
    with open(tmp_path / "daemon.out", "r") as outf:
        output = outf.read()
    
    # Prove that the OS-owned persistent motor continued completely without any interactive loop
    assert "Prove edge: PILOT INTAKE" in output
    assert "Prove edge: SALES PACKAGE" in output
    assert "Prove edge: POST-PILOT HARDENING" in output

