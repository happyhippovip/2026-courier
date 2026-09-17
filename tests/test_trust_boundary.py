import pytest
import sys
import json
import shutil
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))
from scripts.agent_handoff_ledger import update, LedgerError

def test_reject_caller_created_evidence(tmp_path):
    ledger = tmp_path / "ledger.json"
    from tests.test_agent_handoff_ledger import initialize, guard as mock_guard
    initialize(ledger)
    with open(ledger, "r") as f:
        bundle = json.load(f)
    # Fix current_sha to match the mock_guard binding
    bundle["acceptance_guard"] = mock_guard(sha=bundle["record"]["CURRENT_SHA"], runtime_identity=bundle["record"]["RUNTIME_IDENTITY"])
    
    guard = bundle["acceptance_guard"]
    guard["evidence"].append({
        "source_url": "https://test.com/evidence2",
        "source_type": "MACHINE_ARTIFACT",
        "observed_at": "2026-09-17T12:00:00Z",
        "evidence_sha": guard["binding"]["current_sha"],
        "runtime_binding": guard["binding"]["runtime_identity"],
        "validity": "VALID",
        "reason": "test",
        "producer_id": "P-01",
        "verifier_id": "Google-Antigravity"
    })
    
    with pytest.raises(LedgerError) as exc:
        update(ledger, bundle["revision"], {"STATUS": "DONE"}, "Google-Antigravity", 5.0, guard)
    
    assert "caller-created or self-certifying" in str(exc.value) or "evidence produced by the acceptance decision path itself" in str(exc.value)

def test_missing_producer_verifier(tmp_path):
    ledger = tmp_path / "ledger.json"
    from tests.test_agent_handoff_ledger import initialize, guard as mock_guard
    initialize(ledger)
    with open(ledger, "r") as f:
        bundle = json.load(f)
    # Fix current_sha to match the mock_guard binding
    bundle["acceptance_guard"] = mock_guard(sha=bundle["record"]["CURRENT_SHA"], runtime_identity=bundle["record"]["RUNTIME_IDENTITY"])
    
    guard = bundle["acceptance_guard"]
    guard["evidence"].append({
        "source_url": "https://test.com/evidence3",
        "source_type": "MACHINE_ARTIFACT",
        "observed_at": "2026-09-17T12:00:00Z",
        "evidence_sha": guard["binding"]["current_sha"],
        "runtime_binding": guard["binding"]["runtime_identity"],
        "validity": "VALID",
        "reason": "test"
    })
    
    with pytest.raises(LedgerError) as exc:
        update(ledger, bundle["revision"], {"STATUS": "DONE"}, "VERIFIER-01", 5.0, guard)
    
    assert "unverifiable producer or verifier" in str(exc.value)

def test_evidence_produced_by_decision_path(tmp_path):
    ledger = tmp_path / "ledger.json"
    from tests.test_agent_handoff_ledger import initialize, guard as mock_guard
    initialize(ledger)
    with open(ledger, "r") as f:
        bundle = json.load(f)
    # Fix current_sha to match the mock_guard binding
    bundle["acceptance_guard"] = mock_guard(sha=bundle["record"]["CURRENT_SHA"], runtime_identity=bundle["record"]["RUNTIME_IDENTITY"])
    
    guard = bundle["acceptance_guard"]
    guard["evidence"].append({
        "source_url": "https://test.com/evidence4",
        "source_type": "MACHINE_ARTIFACT",
        "observed_at": "2026-09-17T12:00:00Z",
        "evidence_sha": guard["binding"]["current_sha"],
        "runtime_binding": guard["binding"]["runtime_identity"],
        "validity": "VALID",
        "reason": "test",
        "producer_id": "VERIFIER-01",
        "verifier_id": "VERIFIER-01"
    })
    
    with pytest.raises(LedgerError) as exc:
        update(ledger, bundle["revision"], {"STATUS": "DONE"}, "VERIFIER-01", 5.0, guard)
    
    assert "evidence produced by the acceptance decision path itself" in str(exc.value)

def test_false_clean_idle(tmp_path):
    ledger = tmp_path / "ledger.json"
    from tests.test_agent_handoff_ledger import initialize, guard as mock_guard
    initialize(ledger)
    with open(ledger, "r") as f:
        bundle = json.load(f)
    # Fix current_sha to match the mock_guard binding
    bundle["acceptance_guard"] = mock_guard(sha=bundle["record"]["CURRENT_SHA"], runtime_identity=bundle["record"]["RUNTIME_IDENTITY"])
    
    guard = bundle["acceptance_guard"]
    
    with pytest.raises(LedgerError) as exc:
        update(ledger, bundle["revision"], {"CLEAN_IDLE": "YES", "NEXT_EXECUTABLE_ACTION": "EXTERNAL_PUBLICATION"}, "VERIFIER-01", 5.0, guard)
    
    assert "CLEAN_IDLE=YES is forbidden" in str(exc.value)
