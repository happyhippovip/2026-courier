import subprocess
import sys
import json
import os
from pathlib import Path

tmp_path = Path("/tmp/courier_test_debug")
tmp_path.mkdir(exist_ok=True)
record = {
    "PROJECT": "Courier",
    "GOAL": "test-goal",
    "CURRENT_SHA": "0000000000000000000000000000000000000000",
    "BRANCH": "test-branch",
    "RUNTIME_IDENTITY": "0000000000000000000000000000000000000000",
    "RUNTIME_OWNER": "test",
    "STATUS": "TEST",
    "PROVEN_EDGES": ["LEDGER/HANDOFF", "PR41 ACCEPTANCE", "RELEASE - SAFE_AUTOMATABLE_PREPARATION", "RELEASE - IRREVERSIBLE_HUMAN_ACTION", "PUBLIC DEPLOYMENT - SAFE_AUTOMATABLE_PREPARATION", "PUBLIC DEPLOYMENT - IRREVERSIBLE_HUMAN_ACTION", "PILOT INTAKE - SAFE_AUTOMATABLE_PREPARATION", "PILOT INTAKE - IRREVERSIBLE_HUMAN_ACTION", "SALES PACKAGE", "FIRST PILOT - SAFE_AUTOMATABLE_PREPARATION", "FIRST PILOT - IRREVERSIBLE_HUMAN_ACTION", "PAYMENT ONLY WHEN ACTUALLY REQUIRED - SAFE_AUTOMATABLE_PREPARATION", "PAYMENT ONLY WHEN ACTUALLY REQUIRED - IRREVERSIBLE_HUMAN_ACTION", "POST-PILOT HARDENING", "EXTERNAL_PUBLICATION - SAFE_AUTOMATABLE_PREPARATION", "EXTERNAL_PUBLICATION - IRREVERSIBLE_HUMAN_ACTION", "ONBOARD_FIRST_PILOT_CUSTOMER - SAFE_AUTOMATABLE_PREPARATION", "ONBOARD_FIRST_PILOT_CUSTOMER - IRREVERSIBLE_HUMAN_ACTION", "PUBLICATION VERIFICATION"],
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
    "evidence": [{"source_url":"https://test.com","source_type":"MACHINE_ARTIFACT","observed_at":"2026-09-17T12:00:00Z","evidence_sha":"0000000000000000000000000000000000000000","runtime_binding":"0000000000000000000000000000000000000000","validity":"VALID","producer_id":"producer_1","verifier_id":"verifier_1","result_sha256":"0000000000000000000000000000000000000000","reason":"test"}],
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

repo_dir = Path("/Users/user/Downloads/2026-courier").resolve()
script = repo_dir / "scripts" / "agent_handoff_ledger.py"

subprocess.run([sys.executable, str(script), "init", str(ledger_path), "--record", str(record_path), "--guard", str(guard_path)], check=True)

res = subprocess.run([sys.executable, str(repo_dir / "scripts" / "courier_continue.py"), "--run", "--once"], env=dict(os.environ, MOCK_LEDGER=str(ledger_path), MOCK_BRANCH="test-branch", MOCK_SHA="0000000000000000000000000000000000000000"), capture_output=True, text=True)

print("Return code:", res.returncode)
print("STDOUT:", res.stdout)
print("STDERR:", res.stderr)

