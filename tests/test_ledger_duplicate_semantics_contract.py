import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
import agent_handoff_ledger as ahl

def base_record():
    return {
        "PROJECT": "happyhippovip/2026-courier",
        "GOAL": "probe",
        "CURRENT_SHA": "cccccccccccccccccccccccccccccccccccccccc",
        "BRANCH": "release-candidate-integration",
        "RUNTIME_IDENTITY": "attacker-runtime",
        "RUNTIME_OWNER": "probe",
        "STATUS": "WAITING_PHYSICAL_PROOF",
        "PROVEN_EDGES": ["issue state"],
        "UNPROVEN_EDGES": [],
        "FIRST_CAUSAL_BLOCKER": "NONE",
        "BLOCKER_OWNER": "probe",
        "NEXT_EXECUTABLE_ACTION": "await proof",
        "ACTIVE_WRITERS": ["probe"],
        "COLLISION_SCOPE": [],
        "GOALS_SUBMITTED": 0,
        "TASKS_COMPLETED": 0,
        "WORKERS_USED": 0,
        "USER_CONTINUE_MESSAGES": 0,
        "MANUAL_PROCESS_RESTARTS": 0,
        "DUPLICATE_EXTERNAL_EFFECTS": 0,
        "TEMP_TASK_PROCESSES_AFTER_DONE": 0,
        "CLEAN_IDLE": "NO",
        "QUEUE_INDEPENDENT": "NO",
        "LAST_EVIDENCE": ["https://github.com/example/project/issues/1"],
        "LAST_UPDATED_BY": "probe",
        "CONTINUATION_CHECKPOINT": "probe",
    }

def base_guard():
    return {
        "flow": ["EXECUTION", "EVIDENCE", "ACCEPTANCE_GUARD", "LEDGER_TRANSITION", "NEXT_EXECUTABLE_ACTION"],
        "transition_state": "PROVISIONAL",
        "binding": {
            "branch": "release-candidate-integration",
            "current_sha": "cccccccccccccccccccccccccccccccccccccccc",
            "runtime_identity": "attacker-runtime",
        },
        "worker_state": "ACTIVE",
        "evidence": [{
            "source_url": "https://github.com/example/project/actions/runs/test",
            "source_type": "MACHINE_ARTIFACT",
            "observed_at": "2026-09-22T16:14:56Z",
            "evidence_sha": "cccccccccccccccccccccccccccccccccccccccc",
            "runtime_binding": "attacker-runtime",
            "validity": "VALID",
            "reason": "test",
            "producer_id": "test",
            "verifier_id": "test2"
        }],
        "acceptance_predicate": {
            "name": "test-predicate",
            "version": "1.0",
            "required_results": ["TEST"],
            "results": {
                "TEST": {
                    "status": "PASS",
                    "observed_value": "test",
                    "evidence_urls": ["https://github.com/example/project/actions/runs/test"],
                }
            }
        },
    }

def test_ledger_duplicate_semantics_contract(tmp_path):
    path = tmp_path / "ledger.json"
    rec = base_record()
    ahl.initialize(path, rec, base_guard(), 5.0)

    # Offline receipt via the production seam: this test pins duplicate /
    # revision semantics, not attestation, so the pre-existing PASS-backed
    # evidence gets a strictly matching local receipt instead of live net.
    previous = ahl._attestation_resolver

    def resolve(url):
        if url != "https://github.com/example/project/actions/runs/test":
            return None
        return {
            "verdict": "PASS",
            "producer_principal": "test",
            "verifier_principal": "test2",
            "goal_id": "probe",
            "binding": {
                "sha": "cccccccccccccccccccccccccccccccccccccccc",
                "runtime": "attacker-runtime",
            },
        }

    ahl._attestation_resolver = resolve
    try:
        # 1. Update TASKS_COMPLETED=1
        b1 = ahl.update(path, 0, {"TASKS_COMPLETED": 1}, "writer1", 5.0, base_guard())
        rev1 = b1["revision"]
        assert rev1 == 1
    
        # Snapshot bytes
        bytes1 = path.read_bytes()

        # 2. Identical retry at same revision
        with pytest.raises(ahl.NoMeaningfulChangeError):
            ahl.update(path, 1, {"TASKS_COMPLETED": 1}, "writer1", 5.0, base_guard())

        # Assert bytes unchanged
        bytes2 = path.read_bytes()
        assert bytes1 == bytes2

        # 3. Advance to TASKS_COMPLETED=5
        b3 = ahl.update(path, 1, {"TASKS_COMPLETED": 5}, "writer2", 5.0, base_guard())
        rev3 = b3["revision"]
        assert rev3 == 2

        # 4. Stale contradictory write of 9 at old revision
        with pytest.raises(ahl.RevisionConflictError):
            ahl.update(path, 1, {"TASKS_COMPLETED": 9}, "writer3", 5.0, base_guard())

        # Assert authoritative TASKS_COMPLETED=5 kept
        b_final = ahl.load_bundle(path)
        assert b_final["record"]["TASKS_COMPLETED"] == 5
    finally:
        ahl._attestation_resolver = previous

