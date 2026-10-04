import sys
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from readiness_memory import ReadinessNode, EvidenceRef, MemoryStatus

def test_readiness_is_ready_when_evidence_verified():
    memory_store = {
        "mem-1": EvidenceRef(claim_id="mem-1", status=MemoryStatus.VERIFIED)
    }
    node = ReadinessNode("Unit Tests", ["mem-1"])
    assert node.evaluate_readiness(memory_store) == "READY"

def test_readiness_is_unknown_when_evidence_missing():
    memory_store = {}
    node = ReadinessNode("Unit Tests", ["mem-1"])
    assert node.evaluate_readiness(memory_store) == "UNKNOWN"

def test_readiness_downgrades_on_invalidated_evidence():
    memory_store = {
        "mem-1": EvidenceRef(claim_id="mem-1", status=MemoryStatus.INVALIDATED)
    }
    node = ReadinessNode("Unit Tests", ["mem-1"])
    assert node.evaluate_readiness(memory_store) == "DEGRADED"

def test_readiness_downgrades_on_superseded_evidence():
    memory_store = {
        "mem-1": EvidenceRef(claim_id="mem-1", status=MemoryStatus.SUPERSEDED)
    }
    node = ReadinessNode("Unit Tests", ["mem-1"])
    assert node.evaluate_readiness(memory_store) == "DEGRADED"

def test_readiness_tree_propagation():
    memory_store = {
        "mem-unit": EvidenceRef(claim_id="mem-unit", status=MemoryStatus.VERIFIED),
        "mem-e2e": EvidenceRef(claim_id="mem-e2e", status=MemoryStatus.VERIFIED)
    }
    
    root = ReadinessNode("All Tests", [])
    unit_node = ReadinessNode("Unit Tests", ["mem-unit"])
    e2e_node = ReadinessNode("E2E Tests", ["mem-e2e"])
    
    root.add_child(unit_node)
    root.add_child(e2e_node)
    
    # Both verified -> Root is READY
    assert root.evaluate_readiness(memory_store) == "READY"
    
    # One becomes invalidated -> Root becomes DEGRADED
    memory_store["mem-e2e"].status = MemoryStatus.INVALIDATED
    assert root.evaluate_readiness(memory_store) == "DEGRADED"
    
    # One becomes unknown -> Root becomes UNKNOWN
    memory_store["mem-e2e"].status = MemoryStatus.UNKNOWN
    assert root.evaluate_readiness(memory_store) == "UNKNOWN"
