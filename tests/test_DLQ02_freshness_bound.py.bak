import pytest
import datetime
import sys
from pathlib import Path

# Add scripts directory to path to import agent_handoff_ledger
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
import agent_handoff_ledger as ahl

sys.path.insert(0, "/tmp")
from dlq01_refresh import record as base_record, base_guard

def test_dlq02_stale_evidence_rejected(tmp_path):
    path = tmp_path / "ledger.json"
    rec = base_record()
    ahl.initialize(path, rec, base_guard(), 5.0)

    g1 = base_guard()
    g1["acceptance_predicate"]["results"]["RUNTIME_ARTIFACT"] = {
        "status": "PASS", "observed_value": "BOUND",
        "evidence_urls": ["https://github.com/example/project/actions/runs/stale-1"],
    }
    g1["evidence"].append({
        "source_url": "https://github.com/example/project/actions/runs/stale-1",
        "source_type": "MACHINE_ARTIFACT",
        "observed_at": "2020-01-01T00:00:00Z",  # Stale
        "evidence_sha": g1["binding"]["current_sha"],
        "runtime_binding": g1["binding"]["runtime_identity"],
        "validity": "VALID",
        "reason": "ancient artifact",
        "producer_id": "stale-producer",
        "verifier_id": "stale-verifier",
    })
    
    b1 = ahl.update(path, 0, {"TASKS_COMPLETED": 1}, "stale-writer", 5.0, g1)
    assert b1["acceptance_guard"]["transition_state"] == "PROVISIONAL"
    
    b2 = ahl.update(path, 1, {"TASKS_COMPLETED": 2}, "independent-verifier", 5.0)
    assert b2["acceptance_guard"]["transition_state"] == "PROVISIONAL"
    assert b2["record"]["CLEAN_IDLE"] == "NO"

def test_dlq02_fresh_evidence_accepted(tmp_path):
    path = tmp_path / "ledger.json"
    rec = base_record()
    ahl.initialize(path, rec, base_guard(), 5.0)

    g1 = base_guard()
    g1["acceptance_predicate"]["results"]["RUNTIME_ARTIFACT"] = {
        "status": "PASS", "observed_value": "BOUND",
        "evidence_urls": ["https://github.com/example/project/actions/runs/stale-1"],
    }
    g1["evidence"].append({
        "source_url": "https://github.com/example/project/actions/runs/stale-1",
        "source_type": "MACHINE_ARTIFACT",
        "observed_at": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),  # Fresh
        "evidence_sha": g1["binding"]["current_sha"],
        "runtime_binding": g1["binding"]["runtime_identity"],
        "validity": "VALID",
        "reason": "fresh artifact",
        "producer_id": "stale-producer",
        "verifier_id": "stale-verifier",
    })
    
    b1 = ahl.update(path, 0, {"TASKS_COMPLETED": 1}, "stale-writer", 5.0, g1)
    assert b1["acceptance_guard"]["transition_state"] == "PROVISIONAL"
    
    b2 = ahl.update(path, 1, {"TASKS_COMPLETED": 2}, "independent-verifier", 5.0)
    assert b2["acceptance_guard"]["transition_state"] == "CANONICAL_ACCEPTED"
    assert b2["record"]["CLEAN_IDLE"] == "YES"
