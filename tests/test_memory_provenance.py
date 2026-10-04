import os
import sys
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from memory_provenance import MemoryProvenance, MemoryClaim, ProvenanceLossError, update_memory_claim

def get_sample_provenance():
    return MemoryProvenance(
        source="Agent Worker 2",
        repo="2026-courier",
        branch="main",
        sha="1a2b3c4d",
        host="win-test-agent",
        os_name="Windows 11",
        test="test_multi_launch.ps1",
        artifact="test_multi_launch.ps1",
        timestamp="2026-10-03T09:30:00Z",
        workkey="H2",
        verification_level="VERIFIED"
    )

def test_ordinary_note_no_provenance_required():
    note = MemoryClaim(content="We should investigate slow startups later.", is_readiness_critical=False)
    updated_note = update_memory_claim(note, "We should investigate slow startups in Q4.", new_provenance=None)
    assert updated_note.provenance is None
    assert updated_note.content == "We should investigate slow startups in Q4."

def test_readiness_critical_provenance_retention():
    claim = MemoryClaim(
        content="Windows multiple launcher verified.",
        is_readiness_critical=True,
        provenance=get_sample_provenance()
    )
    
    # Trying to update content while stripping provenance should fail
    with pytest.raises(ProvenanceLossError, match="Cannot remove provenance"):
        update_memory_claim(claim, "Windows multiple launcher verified and stable.", new_provenance=None)
        
    # Providing a new provenance should succeed
    new_prov = get_sample_provenance()
    new_prov.timestamp = "2026-10-04T09:30:00Z"
    
    updated_claim = update_memory_claim(claim, "Updated content", new_provenance=new_prov)
    assert updated_claim.provenance.timestamp == "2026-10-04T09:30:00Z"
