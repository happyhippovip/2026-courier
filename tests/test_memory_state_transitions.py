import os
import sys
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from memory_state_transitions import MemoryState, MemoryTransitionError, transition_memory_state

def test_valid_basic_transitions():
    assert transition_memory_state(MemoryState.UNKNOWN, MemoryState.REPORTED) == MemoryState.REPORTED
    assert transition_memory_state(MemoryState.REPORTED, MemoryState.OBSERVED) == MemoryState.OBSERVED
    assert transition_memory_state(MemoryState.OBSERVED, MemoryState.TESTED) == MemoryState.TESTED

def test_invalid_transition():
    with pytest.raises(MemoryTransitionError, match="Invalid transition"):
        # Cannot go straight from REPORTED to VERIFIED
        transition_memory_state(MemoryState.REPORTED, MemoryState.VERIFIED)
        
    with pytest.raises(MemoryTransitionError, match="Invalid transition"):
        # Terminal state SUPERSEDED cannot transition to anything
        transition_memory_state(MemoryState.SUPERSEDED, MemoryState.REPORTED)

def test_verified_transition_requires_evidence():
    with pytest.raises(MemoryTransitionError, match="Cannot transition to VERIFIED without evidence"):
        transition_memory_state(MemoryState.TESTED, MemoryState.VERIFIED, evidence=None)

def test_verified_transition_requires_complete_provenance():
    incomplete_evidence = {
        "what_is_known": "Test passed",
        "why_is_it_believed": "Saw in log"
        # Missing other keys
    }
    with pytest.raises(MemoryTransitionError, match="Missing required evidence key: applicable_state"):
        transition_memory_state(MemoryState.TESTED, MemoryState.VERIFIED, evidence=incomplete_evidence)

def test_verified_transition_success():
    complete_evidence = {
        "what_is_known": "Agent can resolve identity",
        "why_is_it_believed": "test_resolve_project_identity.py passed",
        "applicable_state": "a1b2c3d4",
        "producer_identity": "Antigravity Worker 1",
        "verification_timestamp": "2026-10-03T12:00:00Z",
        "invalidation_conditions": ["Codebase changes"]
    }
    
    assert transition_memory_state(MemoryState.TESTED, MemoryState.VERIFIED, evidence=complete_evidence) == MemoryState.VERIFIED

def test_invalidated_state():
    assert transition_memory_state(MemoryState.VERIFIED, MemoryState.INVALIDATED) == MemoryState.INVALIDATED
