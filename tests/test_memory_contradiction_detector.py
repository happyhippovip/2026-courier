import sys
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from memory_contradiction_detector import detect_and_resolve_contradiction, analyze_memory_for_contradictions

def test_no_contradiction_different_workkey():
    record_a = {"workkey": "H1", "state": "CLOSED"}
    record_b = {"workkey": "H2", "state": "OPEN"}
    result = detect_and_resolve_contradiction(record_a, record_b)
    assert result is None

def test_no_contradiction_same_state():
    record_a = {"workkey": "H1", "state": "CLOSED"}
    record_b = {"workkey": "H1", "state": "CLOSED"}
    result = detect_and_resolve_contradiction(record_a, record_b)
    assert result is None

def test_contradiction_requires_reverify_on_tie():
    record_a = {
        "workkey": "H1", 
        "state": "CLOSED", 
        "source": "Agent 1", 
        "timestamp": "2026-10-03T10:00:00Z",
        "has_provenance": True
    }
    record_b = {
        "workkey": "H1", 
        "state": "REGRESSED", 
        "source": "Agent 2", 
        "timestamp": "2026-10-03T11:00:00Z",
        "has_provenance": True
    }
    
    # Both have provenance, one is newer, but because both are strong, it's a TIE on evidence_strength
    result = detect_and_resolve_contradiction(record_a, record_b)
    assert result is not None
    assert "Record A states CLOSED while Record B states REGRESSED" in result.contradiction
    assert result.source_a == "Agent 1"
    assert result.source_b == "Agent 2"
    assert result.requires_reverify == "YES"
    assert result.resolved_state is None

def test_contradiction_resolved_by_evidence():
    record_a = {
        "workkey": "H1", 
        "state": "CLOSED", 
        "source": "Agent 1", 
        "timestamp": "2026-10-03T10:00:00Z",
        "has_provenance": False
    }
    record_b = {
        "workkey": "H1", 
        "state": "REGRESSED", 
        "source": "Agent 2", 
        "timestamp": "2026-10-03T11:00:00Z",
        "has_provenance": True
    }
    
    # Record B is newer AND has stronger evidence
    result = detect_and_resolve_contradiction(record_a, record_b)
    assert result.requires_reverify == "NO"
    assert result.resolved_state == "REGRESSED"

def test_analyze_memory_list():
    records = [
        {"workkey": "H1", "state": "CLOSED", "timestamp": "1", "has_provenance": False},
        {"workkey": "H2", "state": "OPEN", "timestamp": "1", "has_provenance": True},
        {"workkey": "H1", "state": "REGRESSED", "timestamp": "2", "has_provenance": True}
    ]
    
    contradictions = analyze_memory_for_contradictions(records)
    assert len(contradictions) == 1
    assert contradictions[0].requires_reverify == "NO"
    assert contradictions[0].resolved_state == "REGRESSED"
