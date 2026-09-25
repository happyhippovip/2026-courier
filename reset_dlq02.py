with open("tests/test_DLQ02_freshness_bound.py", "w") as f:
    f.write("""import pytest
import datetime
import sys
from pathlib import Path

# Add scripts directory to path to import agent_handoff_ledger
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
import agent_handoff_ledger as ahl

def get_base():
    def base_record():
        return {
            "PROJECT": "courier",
            "GOAL": "test-goal",
            "BRANCH": "release-candidate-integration",
            "CURRENT_SHA": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            "RUNTIME_IDENTITY": "mac-1",
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
            "LAST_EVIDENCE": [],
            "LAST_UPDATED_BY": "writer",
            "CONTINUATION_CHECKPOINT": "NONE",
            "QUEUE_INDEPENDENT": "YES",
            "CLEAN_IDLE": "NO"
        }
    def base_guard():
        return {
            "flow": [
                "EXECUTION",
                "EVIDENCE",
                "ACCEPTANCE_GUARD",
                "LEDGER_TRANSITION",
                "NEXT_EXECUTABLE_ACTION"
            ],
            "transition_state": "READY",
            "binding": {
                "branch": "release-candidate-integration",
                "current_sha": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                "runtime_identity": "mac-1"
            },
            "worker_state": "ACTIVE",
            "acceptance_predicate": {
                "name": "COURIER_NATIVE",
                "version": "1.0",
                "required_results": ["RUNTIME_ARTIFACT"],
                "results": {
                    "RUNTIME_ARTIFACT": {
                        "status": "UNKNOWN",
                        "observed_value": "PENDING",
                        "evidence_urls": []
                    }
                }
            },
            "evidence": [{
                "source_url": "https://github.com/example/project/actions/runs/12345",
                "source_type": "MACHINE_ARTIFACT",
                "observed_at": "2026-01-01T00:00:00Z",
                "evidence_sha": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                "runtime_binding": "mac-1",
                "validity": "VALID",
                "reason": "initial artifact",
                "producer_id": "github-actions",
                "verifier_id": "sigstore-verifier",
                "result_sha256": "dummy-hash"
            }]
        }
    return base_record, base_guard

def test_dlq02_stale_evidence_rejected(tmp_path):
    path = tmp_path / "ledger.json"
    base_record, base_guard = get_base()
    rec = base_record()
    ahl.initialize(path, rec, base_guard(), 5.0)

    g1 = base_guard()
    g1["acceptance_predicate"]["results"]["RUNTIME_ARTIFACT"] = {
        "status": "PASS", "observed_value": "BOUND",
        "evidence_urls": ["https://github.com/example/project/actions/runs/12345"],
    }
    
    b1 = ahl.update(path, 0, {"TASKS_COMPLETED": 1}, "stale-writer", 5.0, g1)
    assert b1["acceptance_guard"]["transition_state"] == "PROVISIONAL"
    
    b2 = ahl.update(path, 1, {"TASKS_COMPLETED": 2}, "independent-verifier", 5.0)
    assert b2["acceptance_guard"]["transition_state"] == "PROVISIONAL"
    assert b2["record"]["CLEAN_IDLE"] == "NO"

def test_dlq02_fresh_evidence_accepted(tmp_path):
    path = tmp_path / "ledger.json"
    base_record, base_guard = get_base()
    rec = base_record()
    ahl.initialize(path, rec, base_guard(), 5.0)

    g1 = base_guard()
    g1["acceptance_predicate"]["results"]["RUNTIME_ARTIFACT"] = {
        "status": "PASS", "observed_value": "BOUND",
        "evidence_urls": ["https://github.com/example/project/actions/runs/12345"],
    }
    g1["evidence"][0]["observed_at"] = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    
    b1 = ahl.update(path, 0, {"TASKS_COMPLETED": 1}, "stale-writer", 5.0, g1)
    assert b1["acceptance_guard"]["transition_state"] == "PROVISIONAL"
    
    b2 = ahl.update(path, 1, {"TASKS_COMPLETED": 2}, "independent-verifier", 5.0)
    assert b2["acceptance_guard"]["transition_state"] == "CANONICAL_ACCEPTED"
    assert b2["record"]["CLEAN_IDLE"] == "YES"
""")

