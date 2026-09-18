import pytest
from pathlib import Path
import json
import time
from datetime import datetime, timedelta, timezone
import shutil
import tempfile
from scripts.agent_handoff_ledger import initialize, update, LedgerError
from tests.test_agent_handoff_ledger import guard as make_guard

def test_freshness_rejection():
    tmp_path = Path(tempfile.mkdtemp())
    ledger_path = tmp_path / "ledger.json"
    
    current_sha = "0000000000000000000000000000000000000000"
    runtime = "MAC-MACBOOK-PRO-VON-USER-EDEA96"
    

    record = {
        "PROJECT": "courier",
        "GOAL": "test",
        "BRANCH": "release-candidate-integration",
        "CURRENT_SHA": current_sha,
        "RUNTIME_IDENTITY": runtime,
        "RUNTIME_OWNER": "test-owner",
        "STATUS": "READY",
        "PROVEN_EDGES": [],
        "UNPROVEN_EDGES": [],
        "FIRST_CAUSAL_BLOCKER": "NONE",
        "BLOCKER_OWNER": "NONE",
        "NEXT_EXECUTABLE_ACTION": "DO_WORK",
        "ACTIVE_WRITERS": ["session-a"],
        "COLLISION_SCOPE": [],
        "GOALS_SUBMITTED": 1,
        "TASKS_COMPLETED": 2,
        "WORKERS_USED": 1,
        "USER_CONTINUE_MESSAGES": 0,
        "MANUAL_PROCESS_RESTARTS": 0,
        "DUPLICATE_EXTERNAL_EFFECTS": 0,
        "TEMP_TASK_PROCESSES_AFTER_DONE": 0,
        "CLEAN_IDLE": "NO",
        "QUEUE_INDEPENDENT": "UNKNOWN",
        "LAST_EVIDENCE": ["https://example.com/stale"],
        "LAST_UPDATED_BY": "session-a",
        "CONTINUATION_CHECKPOINT": "Session B starts from the acceptance guard.",
    }
    
    guard = make_guard(sha=current_sha, runtime_identity=runtime)
    guard["acceptance_predicate"]["results"]["ISSUE_STATE"]["status"] = "UNKNOWN"
    guard["acceptance_predicate"]["results"]["ISSUE_STATE"]["evidence_urls"] = []
    guard["acceptance_predicate"]["results"]["RUNTIME_ARTIFACT"]["status"] = "UNKNOWN"
    guard["acceptance_predicate"]["results"]["RUNTIME_ARTIFACT"]["evidence_urls"] = []

    
    # Put a stale timestamp (5 days ago)
    stale_dt = datetime.utcnow() - timedelta(days=5)
    
    guard["evidence"] = [
        {
            "source_url": "https://example.com/stale",
            "source_type": "MACHINE_ARTIFACT",
            "observed_at": stale_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "evidence_sha": current_sha,
            "runtime_binding": runtime,
    
        "validity": "UNKNOWN",

            "reason": "stale-proof",
            "producer_id": "sys",
            "verifier_id": "sys"
        }
    ]
    
    # We should be able to initialize the ledger because update() enforces it on has_physical_proof.
    # Oh wait! validate_guard also checks it? Let's see if initialize throws.
    # Actually validate_guard only checks if the timestamp is in the future.
    # But wait, my implementation only checks freshness inside `has_physical_proof`.
    # So `initialize` will succeed.
    initialize(ledger_path, record, guard, 5.0)
    
    # Attempting to go CLEAN_IDLE using this stale proof should fail!
    guard1 = json.loads(json.dumps(guard))
    guard1["transition_state"] = "CANONICAL_ACCEPTED"
    guard1["acceptance_predicate"]["results"]["ISSUE_STATE"]["status"] = "PASS"
    guard1["acceptance_predicate"]["results"]["ISSUE_STATE"]["evidence_urls"] = ["https://example.com/stale"]
    guard1["acceptance_predicate"]["results"]["RUNTIME_ARTIFACT"]["status"] = "PASS"
    guard1["acceptance_predicate"]["results"]["RUNTIME_ARTIFACT"]["evidence_urls"] = ["https://example.com/stale"]
    
    with pytest.raises(LedgerError) as exc_info:
        update(ledger_path, 0, {"CLEAN_IDLE": "YES", "STATUS": "CLEAN_IDLE", "NEXT_EXECUTABLE_ACTION": "NONE"}, "actor", 5.0, guard=guard1)
        
    assert "CLEAN_IDLE=YES is forbidden without pre-existing physical proof" in str(exc_info.value)

