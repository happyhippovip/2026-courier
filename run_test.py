import sys, json, os, subprocess
from pathlib import Path

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
    "evidence": [
        {
            "source_type": "MACHINE_ARTIFACT",
            "source_url": "https://test.com",
            "validity": "VALID",
            "observed_at": "2026-09-18T22:06:15Z",
            "reason": "test",
            "evidence_sha": "0000000000000000000000000000000000000000",
            "result_sha256": "0000000000000000000000000000000000000000",
            "runtime_binding": "0000000000000000000000000000000000000000",
            "verifier_id": "verifier_1",
            "producer_id": "producer_1"
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

Path("/tmp/l2.json").unlink(missing_ok=True)
Path("/tmp/r2.json").write_text(json.dumps(record))
Path("/tmp/g2.json").write_text(json.dumps(guard))

subprocess.run(["python3", "scripts/agent_handoff_ledger.py", "init", "/tmp/l2.json", "--record", "/tmp/r2.json", "--guard", "/tmp/g2.json"], check=True)

# Important: The test adds COURIER_API_KEY ? Or something else?
# Let's see what environment the test had.
env = dict(os.environ, MOCK_LEDGER="/tmp/l2.json", MOCK_BRANCH="test-branch", MOCK_SHA="0000000000000000000000000000000000000000")
res = subprocess.run(["python3", "tests/mock_courier_continue.py", "--run", "--once"], env=env, capture_output=True, text=True)

print("RETURN CODE:", res.returncode)
print("STDOUT:", res.stdout)
print("STDERR:", res.stderr)
