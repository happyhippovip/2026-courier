import pytest
import sys
import json
import shutil
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))
from scripts.agent_handoff_ledger import update, LedgerError
from scripts import agent_handoff_ledger as ledger_module


def test_generic_writer_cannot_promote_task_name_to_proven_edge(tmp_path):
    """Execution/task naming alone must never grow the proof frontier."""
    ledger = tmp_path / "ledger.json"
    from tests.test_agent_handoff_ledger import initialize

    initialize(ledger)
    bundle = json.loads(ledger.read_text())
    promoted = [*bundle["record"]["PROVEN_EDGES"], "TASK_REPORTED_SUCCESS"]

    with pytest.raises(LedgerError) as exc:
        update(
            ledger,
            bundle["revision"],
            {"PROVEN_EDGES": promoted},
            "task-executor",
            5.0,
        )

    assert "cannot promote PROVEN_EDGES" in str(exc.value)
    unchanged = json.loads(ledger.read_text())
    assert unchanged["record"]["PROVEN_EDGES"] == bundle["record"]["PROVEN_EDGES"]


def test_distinct_caller_supplied_names_do_not_admit_machine_evidence(tmp_path):
    """Different producer/verifier labels are not an independent attestation."""
    ledger = tmp_path / "ledger.json"
    from tests.test_agent_handoff_ledger import initialize, guard as mock_guard

    initialize(ledger)
    bundle = json.loads(ledger.read_text())
    guard = mock_guard(
        sha=bundle["record"]["CURRENT_SHA"],
        runtime_identity=bundle["record"]["RUNTIME_IDENTITY"],
    )
    guard["evidence"].append({
        "source_url": "https://example.com/caller-manufactured-artifact",
        "source_type": "MACHINE_ARTIFACT",
        "observed_at": "2026-09-17T12:00:00Z",
        "evidence_sha": guard["binding"]["current_sha"],
        "runtime_binding": guard["binding"]["runtime_identity"],
        "validity": "VALID",
        "reason": "syntactically valid but unauthenticated",
        "producer_id": "claimed-physical-producer",
        "verifier_id": "claimed-independent-verifier",
    })

    with pytest.raises(LedgerError) as exc:
        update(
            ledger,
            bundle["revision"],
            {"STATUS": "DONE"},
            "third-name-ledger-writer",
            5.0,
            guard,
        )

    assert "cannot admit VALID MACHINE_ARTIFACT" in str(exc.value)
    assert json.loads(ledger.read_text())["revision"] == bundle["revision"]


def test_removed_machine_evidence_cannot_be_replayed_later(tmp_path):
    """A later update cannot launder a prior caller-created artifact."""
    ledger = tmp_path / "ledger.json"
    from tests.test_agent_handoff_ledger import initialize, guard as mock_guard

    initialize(ledger)
    bundle = json.loads(ledger.read_text())
    artifact = {
        "source_url": "https://example.com/replayed-artifact",
        "source_type": "MACHINE_ARTIFACT",
        "observed_at": "2026-09-17T12:00:00Z",
        "evidence_sha": bundle["record"]["CURRENT_SHA"],
        "runtime_binding": bundle["record"]["RUNTIME_IDENTITY"],
        "validity": "VALID",
        "reason": "replayed",
        "producer_id": "producer-a",
        "verifier_id": "verifier-b",
    }

    first_guard = mock_guard(
        sha=bundle["record"]["CURRENT_SHA"],
        runtime_identity=bundle["record"]["RUNTIME_IDENTITY"],
    )
    first_guard["evidence"].append(artifact)
    with pytest.raises(LedgerError):
        update(
            ledger,
            bundle["revision"],
            {"STATUS": "READY"},
            "writer-c",
            5.0,
            first_guard,
        )

    # The rejected update is atomic, so the same artifact remains new and is
    # rejected again instead of aging into trusted evidence.
    current = json.loads(ledger.read_text())
    second_guard = mock_guard(
        sha=current["record"]["CURRENT_SHA"],
        runtime_identity=current["record"]["RUNTIME_IDENTITY"],
    )
    second_guard["evidence"].append(artifact)
    with pytest.raises(LedgerError):
        update(
            ledger,
            current["revision"],
            {"STATUS": "BLOCKED"},
            "writer-d",
            5.0,
            second_guard,
        )
    assert json.loads(ledger.read_text())["revision"] == bundle["revision"]


def test_manually_rehashed_canonical_bundle_is_not_a_trust_root(tmp_path):
    """Valid JSON and internally consistent hashes cannot certify reality."""
    ledger = tmp_path / "ledger.json"
    from tests.test_agent_handoff_ledger import initialize, guard as mock_guard

    initialize(ledger)
    bundle = json.loads(ledger.read_text())
    canonical = mock_guard(
        sha=bundle["record"]["CURRENT_SHA"],
        runtime_identity=bundle["record"]["RUNTIME_IDENTITY"],
        transition_state="CANONICAL_ACCEPTED",
    )
    bundle["acceptance_guard"] = canonical
    latest = bundle["history"][-1]
    latest["acceptance_guard"] = canonical
    latest["state_sha256"] = ledger_module.digest({
        "record": latest["record"],
        "acceptance_guard": canonical,
    })
    latest["entry_sha256"] = ledger_module._entry_hash(latest)

    with pytest.raises(LedgerError) as exc:
        ledger_module.validate_bundle(bundle)

    assert "no authenticated independent evidence-admission authority" in str(
        exc.value
    )

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
    
    assert "caller-created or self-certifying MACHINE_ARTIFACT evidence rejected" in str(exc.value)

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

def test_stale_evidence_sha(tmp_path):
    ledger = tmp_path / "ledger.json"
    from tests.test_agent_handoff_ledger import initialize, guard as mock_guard
    initialize(ledger)
    with open(ledger, "r") as f:
        bundle = json.load(f)
    
    # Bundle has CURRENT_SHA, let's say the evidence has a DIFFERENT sha
    bundle["acceptance_guard"] = mock_guard(sha=bundle["record"]["CURRENT_SHA"], runtime_identity=bundle["record"]["RUNTIME_IDENTITY"])
    guard = bundle["acceptance_guard"]
    
    guard["evidence"].append({
        "source_url": "https://test.com/evidence_stale",
        "source_type": "MACHINE_ARTIFACT",
        "observed_at": "2026-09-17T12:00:00Z",
        "evidence_sha": "some_stale_sha_123",
        "runtime_binding": guard["binding"]["runtime_identity"],
        "validity": "VALID",
        "reason": "test",
        "producer_id": "P-01",
        "verifier_id": "V-01"
    })
    
    # We can test that has_physical_proof in courier_continue or update in agent_handoff_ledger ignores this evidence.
    # Actually, in agent_handoff_ledger.py, the check for has_physical_proof requires evidence_sha == current_sha
    # Let's call update and see if it fails to transition to CANONICAL_ACCEPTED if the only evidence is stale
    with pytest.raises(LedgerError) as exc:
        update(ledger, bundle["revision"], {"CLEAN_IDLE": "YES"}, "V-01", 5.0, guard)
    assert "CLEAN_IDLE=YES is forbidden" in str(exc.value)

def test_wrong_runtime_sha(tmp_path):
    ledger = tmp_path / "ledger.json"
    from tests.test_agent_handoff_ledger import initialize, guard as mock_guard
    initialize(ledger)
    with open(ledger, "r") as f:
        bundle = json.load(f)
    
    bundle["acceptance_guard"] = mock_guard(sha=bundle["record"]["CURRENT_SHA"], runtime_identity=bundle["record"]["RUNTIME_IDENTITY"])
    guard = bundle["acceptance_guard"]
    
    guard["evidence"].append({
        "source_url": "https://test.com/evidence_runtime",
        "source_type": "MACHINE_ARTIFACT",
        "observed_at": "2026-09-17T12:00:00Z",
        "evidence_sha": guard["binding"]["current_sha"],
        "runtime_binding": "some_wrong_runtime_id",
        "validity": "VALID",
        "reason": "test",
        "producer_id": "P-01",
        "verifier_id": "V-01"
    })
    
    with pytest.raises(LedgerError) as exc:
        update(ledger, bundle["revision"], {"CLEAN_IDLE": "YES"}, "V-01", 5.0, guard)
    assert "CLEAN_IDLE=YES is forbidden" in str(exc.value)

def test_empty_unproven_without_evidence_forbidden(tmp_path):
    ledger = tmp_path / "ledger.json"
    from tests.test_agent_handoff_ledger import initialize, guard as mock_guard
    initialize(ledger)
    with open(ledger, "r") as f:
        bundle = json.load(f)
    
    bundle["record"]["UNPROVEN_EDGES"] = []
    bundle["acceptance_guard"] = mock_guard(sha=bundle["record"]["CURRENT_SHA"], runtime_identity=bundle["record"]["RUNTIME_IDENTITY"])
    guard = bundle["acceptance_guard"]
    
    with pytest.raises(LedgerError) as exc:
        update(ledger, bundle["revision"], {"CLEAN_IDLE": "YES"}, "V-01", 5.0, guard)
    assert "CLEAN_IDLE=YES is forbidden" in str(exc.value)
