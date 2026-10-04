import sys
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from memory_supersession import MemoryClaim, MemorySupersessionError, supersede_memory_claim, get_active_decisions

def test_successful_supersession():
    old_claim = MemoryClaim(
        id="mem-001",
        content="The port is 8080.",
        status="VERIFIED",
        provenance={"timestamp": "2026-10-01"}
    )
    
    new_claim = MemoryClaim(
        id="mem-002",
        content="The port is 9090.",
        status="VERIFIED",
        provenance={"timestamp": "2026-10-03"}
    )
    
    supersede_memory_claim(old_claim, new_claim)
    
    assert old_claim.status == "SUPERSEDED"
    assert old_claim.superseded_by == "mem-002"
    assert old_claim.provenance["timestamp"] == "2026-10-01" # Provenance retained
    
def test_cannot_supersede_already_terminal_claim():
    old_claim = MemoryClaim(
        id="mem-001",
        content="The port is 8080.",
        status="INVALIDATED"
    )
    
    new_claim = MemoryClaim(
        id="mem-002",
        content="The port is 9090.",
        status="VERIFIED"
    )
    
    with pytest.raises(MemorySupersessionError, match="Cannot supersede a claim that is already INVALIDATED"):
        supersede_memory_claim(old_claim, new_claim)

def test_replacement_must_be_verified():
    old_claim = MemoryClaim(
        id="mem-001",
        content="The port is 8080.",
        status="VERIFIED"
    )
    
    new_claim = MemoryClaim(
        id="mem-002",
        content="The port is 9090.",
        status="TESTED" # Not yet verified
    )
    
    with pytest.raises(MemorySupersessionError, match="Replacement claim must be VERIFIED"):
        supersede_memory_claim(old_claim, new_claim)

def test_get_active_decisions_filters_superseded():
    claims = [
        MemoryClaim(id="mem-001", content="Old port", status="SUPERSEDED"),
        MemoryClaim(id="mem-002", content="New port", status="VERIFIED"),
        MemoryClaim(id="mem-003", content="Bad claim", status="INVALIDATED")
    ]
    
    active = get_active_decisions(claims)
    
    assert len(active) == 1
    assert active[0].id == "mem-002"
