import json
import sys
from pathlib import Path
repo_dir = Path(".").resolve()
sys.path.insert(0, str(repo_dir / "scripts"))
from agent_handoff_ledger import update, load_bundle, initialize

record = {
    "PROJECT": "Test",
    "GOAL": "Test Goal",
    "CURRENT_SHA": "cccccccccccccccccccccccccccccccccccccccc",
    "BRANCH": "main",
    "RUNTIME_IDENTITY": "attacker-runtime",
    "RUNTIME_OWNER": "system",
    "STATUS": "RUNNING",
    "PROVEN_EDGES": ["LEDGER/HANDOFF", "PR41 ACCEPTANCE", "RELEASE - SAFE_AUTOMATABLE_PREPARATION", "RELEASE - IRREVERSIBLE_HUMAN_ACTION"],
    "UNPROVEN_EDGES": ["PUBLIC DEPLOYMENT - SAFE_AUTOMATABLE_PREPARATION", "PUBLIC DEPLOYMENT - IRREVERSIBLE_HUMAN_ACTION", "PUBLICATION VERIFICATION", "PILOT INTAKE - SAFE_AUTOMATABLE_PREPARATION", "PILOT INTAKE - IRREVERSIBLE_HUMAN_ACTION", "SALES PACKAGE", "FIRST PILOT - SAFE_AUTOMATABLE_PREPARATION", "FIRST PILOT - IRREVERSIBLE_HUMAN_ACTION", "PAYMENT ONLY WHEN ACTUALLY REQUIRED - SAFE_AUTOMATABLE_PREPARATION", "PAYMENT ONLY WHEN ACTUALLY REQUIRED - IRREVERSIBLE_HUMAN_ACTION", "POST-PILOT HARDENING", "EXTERNAL_PUBLICATION - SAFE_AUTOMATABLE_PREPARATION", "EXTERNAL_PUBLICATION - IRREVERSIBLE_HUMAN_ACTION", "ONBOARD_FIRST_PILOT_CUSTOMER - SAFE_AUTOMATABLE_PREPARATION", "ONBOARD_FIRST_PILOT_CUSTOMER - IRREVERSIBLE_HUMAN_ACTION"],
    "FIRST_CAUSAL_BLOCKER": "NONE",
    "BLOCKER_OWNER": "NONE",
    "NEXT_EXECUTABLE_ACTION": "NONE",
    "ACTIVE_WRITERS": ["probe"],
    "COLLISION_SCOPE": [],
    "GOALS_SUBMITTED": 1,
    "TASKS_COMPLETED": 0,
    "WORKERS_USED": 1,
    "USER_CONTINUE_MESSAGES": 0,
    "MANUAL_PROCESS_RESTARTS": 0,
    "DUPLICATE_EXTERNAL_EFFECTS": 0,
    "TEMP_TASK_PROCESSES_AFTER_DONE": 0,
    "CLEAN_IDLE": "NO",
    "QUEUE_INDEPENDENT": "NO",
    "LAST_EVIDENCE": ["https://github.com/example/project/issues/1"],
    "LAST_UPDATED_BY": "system",
    "CONTINUATION_CHECKPOINT": "NONE"
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
        "branch": "main",
        "current_sha": "cccccccccccccccccccccccccccccccccccccccc",
        "runtime_identity": "attacker-runtime"
    },
    "evidence": [{"source_url":"https://test.com","source_type":"MACHINE_ARTIFACT","observed_at":"2026-09-17T12:00:00Z","evidence_sha":"cccccccccccccccccccccccccccccccccccccccc","runtime_binding":"attacker-runtime","validity":"VALID","reason":"test"}],
    "flow": ["EXECUTION", "EVIDENCE", "ACCEPTANCE_GUARD", "LEDGER_TRANSITION", "NEXT_EXECUTABLE_ACTION"],
    "transition_state": "PROVISIONAL",
    "worker_state": "IDLE/YIELDED"
}

path = repo_dir / "test_tmp.json"
path.unlink(missing_ok=True)
initialize(path, record, guard, 5.0)

bundle = load_bundle(path)
guard = bundle["acceptance_guard"]

def update_ledger(ledger_path, edge_name, bundle):
    revision = bundle["revision"]
    record = bundle["record"]
    proven = list(record.get("PROVEN_EDGES", []))
    unproven = list(record.get("UNPROVEN_EDGES", []))
    
    updates = {}
    if edge_name and edge_name not in proven and edge_name != "CLEAN_IDLE_ACHIEVED":
        proven.append(edge_name)
    if edge_name in unproven:
        unproven.remove(edge_name)
    updates["PROVEN_EDGES"] = proven
    updates["UNPROVEN_EDGES"] = unproven
    
    guard = bundle["acceptance_guard"]
    
    print(f"DEBUG UPDATES: {updates}")
    new_bundle = update(
        ledger_path,
        revision,
        updates,
        "Google-Antigravity",
        5.0,
        guard
    )
    return new_bundle

try:
    print("STEP 1: PUBLICATION VERIFICATION")
    bundle = update_ledger(path, "PUBLICATION VERIFICATION", bundle)
    print("PROVEN:", bundle["record"]["PROVEN_EDGES"])
    
    print("STEP 2: RELEASE - SAFE_AUTOMATABLE_PREPARATION")
    bundle = update_ledger(path, "RELEASE - SAFE_AUTOMATABLE_PREPARATION", bundle)
    print("PROVEN:", bundle["record"]["PROVEN_EDGES"])
except Exception as e:
    print("ERROR:", type(e).__name__, e)
