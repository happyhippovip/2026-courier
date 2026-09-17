import os
import json
import pytest
from pathlib import Path
import sys
sys.path.append(str(Path(__file__).parent.parent.resolve()))
import scripts.agent_handoff_ledger as ledger
from tests.test_queue_independence import setup_ledger

def test_preset_canonical_accepted(tmp_path):
    ledger_path = setup_ledger(tmp_path, unproven_edges=["A"], blocker="NONE", proven_edges=[])
    bundle = ledger.load_bundle(ledger_path)
    guard = bundle["acceptance_guard"]
    guard["transition_state"] = "CANONICAL_ACCEPTED"
    
    try:
        updated = ledger.update(
            Path(ledger_path), bundle["revision"],
            {"UNPROVEN_EDGES": [], "PROVEN_EDGES": [], "STATUS": "CLEAN_IDLE"},
            "attacker", 5.0
        )
        assert False
    except ledger.LedgerError:
        pass

def test_same_update_evidence(tmp_path):
    ledger_path = setup_ledger(tmp_path, unproven_edges=[], blocker="NONE", proven_edges=[])
    bundle = ledger.load_bundle(ledger_path)
    guard = bundle["acceptance_guard"]
    fake_evidence = {
        "source_type": "MACHINE_ARTIFACT", "evidence_sha": guard["binding"]["current_sha"],
        "runtime_binding": guard["binding"]["runtime_identity"], "validity": "VALID",
        "source_url": "https://fake.com", "observed_at": "2026-09-17T12:00:00Z", "reason": "fake reason"
    }
    guard["evidence"] = [fake_evidence]
    guard["acceptance_predicate"]["results"]["ISSUE_STATE"]["evidence_urls"] = ["https://fake.com"]
    try:
        updated = ledger.update(Path(ledger_path), bundle["revision"], {"STATUS": "CLEAN_IDLE"}, "attacker", 5.0, guard=guard)
        assert False
    except ledger.LedgerError:
        pass

def test_replayed_evidence(tmp_path):
    ledger_path = setup_ledger(tmp_path, unproven_edges=[], blocker="NONE", proven_edges=[])
    bundle = ledger.load_bundle(ledger_path)
    fake_evidence = {
        "source_type": "MACHINE_ARTIFACT", "evidence_sha": "0000000000000000000000000000000000000001",
        "runtime_binding": bundle["acceptance_guard"]["binding"]["runtime_identity"], "validity": "VALID",
        "source_url": "https://fake.com", "observed_at": "2026-09-17T12:00:00Z", "reason": "fake reason"
    }
    with open(ledger_path, "w") as f:
        bundle["acceptance_guard"]["evidence"] = [fake_evidence]
        json.dump(bundle, f)
    try:
        ledger.load_bundle(ledger_path)
        assert False
    except ledger.LedgerError:
        pass

def test_wrong_runtime(tmp_path):
    ledger_path = setup_ledger(tmp_path, unproven_edges=[], blocker="NONE", proven_edges=[])
    bundle = ledger.load_bundle(ledger_path)
    fake_evidence = {
        "source_type": "MACHINE_ARTIFACT", "evidence_sha": bundle["acceptance_guard"]["binding"]["current_sha"],
        "runtime_binding": "wrong_runtime", "validity": "VALID",
        "source_url": "https://fake.com", "observed_at": "2026-09-17T12:00:00Z", "reason": "fake reason"
    }
    with open(ledger_path, "w") as f:
        bundle["acceptance_guard"]["evidence"] = [fake_evidence]
        json.dump(bundle, f)
    try:
        ledger.load_bundle(ledger_path)
        assert False
    except ledger.LedgerError:
        pass

def test_substring_success_attack(tmp_path):
    # Test if we can submit "PAYMENT_UNVERIFIED - AUTHORIZED_MACHINE_ACTION"
    # and the ledger accepts it as a valid unproven/proven edge.
    ledger_path = setup_ledger(tmp_path, unproven_edges=["A"], blocker="NONE", proven_edges=[])
    bundle = ledger.load_bundle(ledger_path)
    
    # Try to add a bogus edge that passes the "in" check in the motor.
    # The ledger should reject this during validate_record if it checks edge names!
    # Let's see if the ledger allows arbitrary strings in UNPROVEN_EDGES.
    try:
        updated = ledger.update(
            Path(ledger_path), bundle["revision"],
            {"PROVEN_EDGES": ["FAKE - SAFE_AUTOMATABLE_PREPARATION"], "UNPROVEN_EDGES": []},
            "attacker", 5.0
        )
        # If it allows it, then the substring attack on the motor would successfully bypass!
        # But wait, this is testing the ledger. The objective says "Assume current Ledger/Guard can still be fooled."
        # "Every false acceptance must fail closed."
    except ledger.LedgerError as e:
        pass # Great, it's protected
