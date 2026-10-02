import pytest
from courier_core.semantic_update_gate import (
    SemanticUpdateGate, SystemState, UpdateManifest, GateDecision
)

def get_base_state():
    return SystemState(
        version="v1.0",
        capabilities={"network", "storage"},
        behaviors={"auth": "strict", "retry": "linear"}
    )

def test_capability_preserved_accepts():
    before = get_base_state()
    # Update maintains capabilities and adds a new one, no behaviors changed
    update = UpdateManifest(
        id="upd-1",
        target_version="v1.1",
        capabilities={"network", "storage", "cloud"}, # Preserved + 1 added
        behaviors={"auth": "strict", "retry": "linear", "cache": "enabled"}, # 1 added
        evidence_refs=["hash:abc"],
        rollback_metadata={"script": "rollback_v1.1.sh"}
    )
    
    decision = SemanticUpdateGate.evaluate(before, update)
    assert decision.accepted is True
    assert decision.reason == "ACCEPT"
    assert decision.rollback_metadata["script"] == "rollback_v1.1.sh"

def test_capability_removed_rejects():
    before = get_base_state()
    # Removes "storage"
    update = UpdateManifest(
        id="upd-2",
        target_version="v1.1",
        capabilities={"network"}, 
        behaviors={"auth": "strict", "retry": "linear"},
        evidence_refs=["hash:abc"],
        rollback_metadata={"snapshot": "snap-123"}
    )
    
    decision = SemanticUpdateGate.evaluate(before, update)
    assert decision.accepted is False
    assert "capability removed" in decision.reason
    assert "storage" in decision.reason

def test_behavior_changed_rejects():
    before = get_base_state()
    # Alters "retry"
    update = UpdateManifest(
        id="upd-3",
        target_version="v1.1",
        capabilities={"network", "storage"}, 
        behaviors={"auth": "strict", "retry": "exponential"}, # Changed
        evidence_refs=["hash:abc"],
        rollback_metadata={"snapshot": "snap-123"}
    )
    
    decision = SemanticUpdateGate.evaluate(before, update)
    assert decision.accepted is False
    assert "behavior changed for 'retry'" in decision.reason

def test_evidence_missing_rejects():
    before = get_base_state()
    update = UpdateManifest(
        id="upd-4",
        target_version="v1.1",
        capabilities={"network", "storage"},
        behaviors={"auth": "strict", "retry": "linear"},
        evidence_refs=[], # MISSING EVIDENCE
        rollback_metadata={"snapshot": "snap-123"}
    )
    
    decision = SemanticUpdateGate.evaluate(before, update)
    assert decision.accepted is False
    assert decision.reason == "REJECT: evidence missing"

def test_rollback_metadata_available_on_reject():
    before = get_base_state()
    update = UpdateManifest(
        id="upd-5",
        target_version="v1.1",
        capabilities={"network"}, # Will reject due to removed capability
        behaviors={"auth": "strict", "retry": "linear"},
        evidence_refs=["hash:abc"],
        rollback_metadata={"snapshot": "snap-999"}
    )
    
    decision = SemanticUpdateGate.evaluate(before, update)
    assert decision.accepted is False
    # Even on reject, rollback instructions must flow through the gate
    assert decision.rollback_metadata["snapshot"] == "snap-999"
