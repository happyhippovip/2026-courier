import sys
import os
import json
import subprocess
from pathlib import Path

def setup_ledger(tmp_path, unproven_edges, blocker, proven_edges):
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
        "PROVEN_EDGES": proven_edges,
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
        "evidence": [{"source_url":"https://test.com","source_type":"MACHINE_ARTIFACT","observed_at":"2026-09-17T12:00:00Z","evidence_sha":"0000000000000000000000000000000000000000","runtime_binding":"0000000000000000000000000000000000000000","validity":"VALID","reason":"test"}],
        "flow": ["EXECUTION", "EVIDENCE", "ACCEPTANCE_GUARD", "LEDGER_TRANSITION", "NEXT_EXECUTABLE_ACTION"]
    }
    
    with open(record_path, "w") as f:
        json.dump(record, f)
    with open(guard_path, "w") as f:
        json.dump(guard, f)
        
    repo_dir = Path(__file__).parent.parent.resolve()
    script = repo_dir / "scripts" / "agent_handoff_ledger.py"
    subprocess.run([sys.executable, str(script), "init", str(ledger_path), "--record", str(record_path), "--guard", str(guard_path)], check=True)
    return ledger_path

def test_queue_independence_a_waits_b_executes_c_executes(tmp_path):
    marker = tmp_path / "mock_a_called.txt"
    if marker.exists():
        marker.unlink()
        
    # We want C to become READY after B. So C is dependent, B is independent.
    # We can use B = PUBLIC DEPLOYMENT (independent) and C = PUBLICATION VERIFICATION (independent but we put it after B)
    # Wait, all independent edges are executed in parallel if there is no collision!
    # "C = becomes READY after B". To do this, C must be dependent on B in the same chain!
    # For example, PUBLIC DEPLOYMENT - SAFE_AUTOMATABLE_PREPARATION (B)
    # PUBLIC DEPLOYMENT - AUTHORIZED_MACHINE_ACTION (C)
    # These are sequential in the same chain!
    
    # A = EXTERNAL_PUBLICATION - SAFE_AUTOMATABLE_PREPARATION
    ledger_path = setup_ledger(
        tmp_path,
            unproven_edges=['EXTERNAL_PUBLICATION - SAFE_AUTOMATABLE_PREPARATION', 'PUBLIC DEPLOYMENT - SAFE_AUTOMATABLE_PREPARATION',],
            blocker="NONE",
            proven_edges=['LEDGER/HANDOFF', 'PR41 ACCEPTANCE', 'RELEASE - SAFE_AUTOMATABLE_PREPARATION', 'RELEASE - IRREVERSIBLE_HUMAN_ACTION', 'PUBLIC DEPLOYMENT - IRREVERSIBLE_HUMAN_ACTION', 'PUBLICATION VERIFICATION', 'PILOT INTAKE - SAFE_AUTOMATABLE_PREPARATION', 'PILOT INTAKE - IRREVERSIBLE_HUMAN_ACTION', 'SALES PACKAGE', 'FIRST PILOT - SAFE_AUTOMATABLE_PREPARATION', 'FIRST PILOT - IRREVERSIBLE_HUMAN_ACTION', 'PAYMENT ONLY WHEN ACTUALLY REQUIRED - SAFE_AUTOMATABLE_PREPARATION', 'PAYMENT ONLY WHEN ACTUALLY REQUIRED - IRREVERSIBLE_HUMAN_ACTION', 'POST-PILOT HARDENING', 'EXTERNAL_PUBLICATION - IRREVERSIBLE_HUMAN_ACTION', 'ONBOARD_FIRST_PILOT_CUSTOMER - SAFE_AUTOMATABLE_PREPARATION', 'ONBOARD_FIRST_PILOT_CUSTOMER - IRREVERSIBLE_HUMAN_ACTION'],
    )
    
    env = os.environ.copy()
    env["MOCK_LEDGER"] = str(ledger_path)
    env["MOCK_BRANCH"] = "test-branch"
    env["MOCK_SHA"] = "0000000000000000000000000000000000000000"
    env["MOCK_WAITING_TASK"] = "EXTERNAL_PUBLICATION - SAFE_AUTOMATABLE_PREPARATION"
    
    # Run the motor in the temp dir so it creates marker there
    repo_dir = Path(__file__).parent.parent.resolve()
    script = repo_dir / "scripts" / "courier_continue.py"
    
    # We run with --run --once? 
    # If we run with --once, it does exactly one loop.
    # But we want to prove that "queue continues... A is re-evaluated later".
    # If we do --run with MOCK_SHA, it does 3 iterations (because mock_iters >= 3 break).
    # In 3 iterations:
    # Loop 1: A, B evaluated. A fails with WAITING_PROVIDER. B succeeds. 
    # Loop 2: A evaluated again? C evaluated (since B is done). A fails. C succeeds.
    # Loop 3: A evaluated again. A succeeds (marker >= 2).
    # Then it finishes!
    # Let's run it.
    
    res = subprocess.run([sys.executable, str(script), "--run"], env=env, cwd=str(tmp_path), capture_output=True, text=True, timeout=30)
    
    # Verify A, B, C succeeded
    with open(ledger_path) as f:
        data = json.load(f)
    
    unproven = data["record"]["UNPROVEN_EDGES"]
    print(res.stdout)
    print(res.stderr)
    assert "PUBLIC DEPLOYMENT - SAFE_AUTOMATABLE_PREPARATION" not in unproven
    print(res.stdout)
    print(res.stderr)
    assertnot in unproven
    assert "EXTERNAL_PUBLICATION - SAFE_AUTOMATABLE_PREPARATION" not in unproven

