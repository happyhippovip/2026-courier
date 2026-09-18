import pytest
from pathlib import Path
import json
import time
from datetime import datetime, timezone
import shutil
import tempfile
from scripts.agent_handoff_ledger import initialize, update, LedgerError
from tests.test_agent_handoff_ledger import guard as make_guard

def test_two_update_self_cert_rejection():
    # Setup
    tmp_path = Path(tempfile.mkdtemp())
    ledger_path = tmp_path / "ledger.json"
    
    current_sha = "0000000000000000000000000000000000000000"
    runtime = "MAC-MACBOOK-PRO-VON-USER-EDEA96"
    actor = "EVIL-ACTOR"
    
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
        "LAST_EVIDENCE": ["https://example.com/initial"],
        "LAST_UPDATED_BY": "session-a",
        "CONTINUATION_CHECKPOINT": "Session B starts from the acceptance guard.",
    }
    



    guard = make_guard(sha=current_sha, runtime_identity=runtime)
    guard["acceptance_predicate"]["results"]["ISSUE_STATE"]["status"] = "UNKNOWN"
    guard["acceptance_predicate"]["results"]["ISSUE_STATE"]["evidence_urls"] = []
    guard["acceptance_predicate"]["results"]["RUNTIME_ARTIFACT"]["status"] = "UNKNOWN"
    guard["acceptance_predicate"]["results"]["RUNTIME_ARTIFACT"]["evidence_urls"] = []
    guard["evidence"] = [



        {
            "source_url": "https://example.com/initial",
            "source_type": "GITHUB_COMMIT",
            "observed_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "evidence_sha": current_sha,
            "runtime_binding": runtime,
            "validity": "UNKNOWN",
            "reason": "init",
            "producer_id": "sys",
            "verifier_id": "sys"
        }
    ]
    
    initialize(ledger_path, record, guard, 5.0)
    
    # Step 1: Plant self-certified artifact
    guard1 = json.loads(json.dumps(guard))
    plant_url = "https://example.com/planted_artifact"
    guard1["evidence"].append({
        "source_url": plant_url,
        "source_type": "MACHINE_ARTIFACT",
        "observed_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "evidence_sha": current_sha,
        "runtime_binding": runtime,
        "validity": "VALID",
        "reason": "self-planted",
        "producer_id": "fake-sys",
        "verifier_id": "fake-sys2"
    })
    
    update(ledger_path, 0, {"LAST_EVIDENCE": [plant_url]}, actor, 5.0, guard=guard1)
    

    # Step 2: Try to promote using the planted evidence
    guard2 = json.loads(json.dumps(guard1))
    guard2["transition_state"] = "CANONICAL_ACCEPTED"
    guard2["acceptance_predicate"]["results"]["ISSUE_STATE"]["status"] = "PASS"
    guard2["acceptance_predicate"]["results"]["ISSUE_STATE"]["evidence_urls"] = [plant_url]
    guard2["acceptance_predicate"]["results"]["RUNTIME_ARTIFACT"]["status"] = "PASS"
    guard2["acceptance_predicate"]["results"]["RUNTIME_ARTIFACT"]["evidence_urls"] = [plant_url]

    
    with pytest.raises(LedgerError) as exc_info:
        update(ledger_path, 1, {"CLEAN_IDLE": "YES", "STATUS": "CLEAN_IDLE", "NEXT_EXECUTABLE_ACTION": "NONE"}, actor, 5.0, guard=guard2)
        
    assert "CLEAN_IDLE=YES is forbidden without pre-existing physical proof" in str(exc_info.value)

