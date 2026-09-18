import pytest
import tempfile
import json
import os
import sys
import subprocess
from pathlib import Path
from tests.test_courier_continue import setup_ledger
from scripts.courier_continue import PLAN

def test_dlq04_adversarial_drain(tmp_path):
    all_edges = PLAN
    
    unproven = ["RELEASE - SAFE_AUTOMATABLE_PREPARATION", "RELEASE - IRREVERSIBLE_HUMAN_ACTION"]
    proven = [e for e in all_edges if e not in unproven]

    record = {
        "PROJECT": "Courier",
        "GOAL": "test-goal",
        "CURRENT_SHA": "0000000000000000000000000000000000000000",
        "BRANCH": "test-branch",
        "RUNTIME_IDENTITY": "0000000000000000000000000000000000000000",
        "RUNTIME_OWNER": "test",
        "STATUS": "TEST",
        "PROVEN_EDGES": proven,
        "UNPROVEN_EDGES": unproven,
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
            "runtime_identity": "0000000000000000000000000000000000000000"
        },
        "evidence": [{"source_url":"https://test.com","source_type":"MACHINE_ARTIFACT","observed_at":"2026-09-18T22:03:59Z","evidence_sha":"0000000000000000000000000000000000000000","runtime_binding":"0000000000000000000000000000000000000000","validity":"VALID","producer_id":"producer_1","verifier_id":"verifier_1","result_sha256":"0000000000000000000000000000000000000000","reason":"test"}],
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
    
    import json
    record_path = tmp_path / "record.json"
    guard_path = tmp_path / "guard.json"
    ledger_path = tmp_path / "agent_handoff_ledger.json"
    
    record_path.write_text(json.dumps(record))
    guard_path.write_text(json.dumps(guard))
    
    repo_dir = Path(__file__).parent.parent.resolve()
    script = repo_dir / "scripts" / "agent_handoff_ledger.py"
    
    subprocess.run([sys.executable, str(script), "init", str(ledger_path), "--record", str(record_path), "--guard", str(guard_path)], check=True)
    repo_dir = Path(__file__).parent.parent.resolve()
    script = repo_dir / "tests" / "mock_courier_continue.py"
    
    env = dict(
        os.environ, 
        MOCK_LEDGER=str(ledger_path), 
        MOCK_BRANCH="test-branch", 
        MOCK_SHA="0000000000000000000000000000000000000000",
        COURIER_WORKER_CAPABILITIES="shell,build_tools,git,api,github_actions,reasoning"
    )
    
    res = subprocess.run(
        [sys.executable, str(script), "--run", "--once"],
        env=env,
        capture_output=True,
        text=True,
        cwd=str(repo_dir)
    )
    
    with open(ledger_path, "r") as f:
        data = json.load(f)
        
    final_unproven = data["record"]["UNPROVEN_EDGES"]
    
    assert res.returncode == 0, f"courier_continue.py crashed! Stdout: {res.stdout}\nStderr: {res.stderr}"
    
    assert "RELEASE - SAFE_AUTOMATABLE_PREPARATION" not in final_unproven, f"First task didn't complete. Stdout: {res.stdout}"
    assert "RELEASE - IRREVERSIBLE_HUMAN_ACTION" in final_unproven, "Second task shouldn't complete"
    
    assert data["record"]["FIRST_CAUSAL_BLOCKER"] == "UNVERIFIED_EXTERNAL_EFFECT_RELEASE - IRREVERSIBLE_HUMAN_ACTION", "Motor exited early before evaluating the dependent task blocker!"

