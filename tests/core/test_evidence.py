import pytest
from courier_core.evidence import (
    EvidenceMetadata, EvidenceRequirement,
    verify_evidence_capabilities, EvidenceRejectedError
)

def test_requirement_says_windows_native_with_linux_evidence_rejects():
    # Requirement: windows_native
    req = EvidenceRequirement(required_capabilities={"windows_native"})
    
    # Evidence: Linux
    evidence = EvidenceMetadata(capabilities={"linux"})
    
    with pytest.raises(EvidenceRejectedError, match="missing required host capabilities: \\['windows_native'\\]"):
        verify_evidence_capabilities(evidence, req)

def test_requirement_says_generic_with_valid_linux_evidence_accepts():
    # Requirement: generic
    req = EvidenceRequirement(generic=True)
    
    # Evidence: Linux
    evidence = EvidenceMetadata(capabilities={"linux"}, refs=["/var/log/syslog"])
    
    # Should not raise
    verify_evidence_capabilities(evidence, req)

def test_exact_match_capabilities_accepts():
    req = EvidenceRequirement(required_capabilities={"mac_native", "local_file_access"})
    evidence = EvidenceMetadata(capabilities={"mac_native", "local_file_access", "browser"})
    
    # Should not raise (evidence has a superset of required capabilities)
    verify_evidence_capabilities(evidence, req)

def test_missing_multiple_capabilities_rejects():
    req = EvidenceRequirement(required_capabilities={"cloud", "browser"})
    evidence = EvidenceMetadata(capabilities={"local_file_access"})
    
    with pytest.raises(EvidenceRejectedError, match="missing required host capabilities: \\['browser', 'cloud'\\]"):
        verify_evidence_capabilities(evidence, req)

def test_empty_requirements_accepts_any():
    req = EvidenceRequirement(required_capabilities=set())
    evidence = EvidenceMetadata(capabilities={"linux"})
    
    # Should not raise
    verify_evidence_capabilities(evidence, req)
