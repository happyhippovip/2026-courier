import sys
import os
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from evidence_integrity import EvidenceIntegrityVerifier, EvidenceIntegrityException

def test_evidence_integrity_workflow(tmp_path):
    # 1. Create a dummy evidence file
    evidence_file = tmp_path / "evidence.log"
    evidence_file.write_text("TEST RESULTS: PASS")
    
    # 2. Create the integrity record
    record = EvidenceIntegrityVerifier.create_record(
        evidence_id="ev-123",
        file_path=str(evidence_file),
        creation_time=1000,
        producer="pytest_worker",
        source_sha="abc123sha"
    )
    
    assert record.expected_size == len("TEST RESULTS: PASS")
    assert record.expected_hash is not None
    
    # 3. Verify it passes
    assert EvidenceIntegrityVerifier.verify(record) is True
    
    # 4. Tamper with the evidence (change content, keep size same)
    evidence_file.write_text("TEST RESULTS: FAIL")
    with pytest.raises(EvidenceIntegrityException, match="Hash mismatch"):
        EvidenceIntegrityVerifier.verify(record)
        
    # 5. Tamper with the evidence (change size)
    evidence_file.write_text("TEST RESULTS: PASS - BUT MORE TEXT")
    with pytest.raises(EvidenceIntegrityException, match="Size mismatch"):
        EvidenceIntegrityVerifier.verify(record)
        
    # 6. Delete the file
    evidence_file.unlink()
    with pytest.raises(EvidenceIntegrityException, match="missing"):
        EvidenceIntegrityVerifier.verify(record)
