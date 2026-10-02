import pytest
from courier_core.readiness import (
    evaluate_readiness, ReadinessState, EvidenceArtifact
)

def test_documentation_cannot_jump_to_verified():
    # Only doc and test log, no commit
    artifacts = [
        EvidenceArtifact(kind="doc", metadata={"content": "Specs"}),
        EvidenceArtifact(kind="test_log", metadata={"platform": "windows_native"})
    ]
    
    # Must not jump to EVIDENCE_VERIFIED
    state = evaluate_readiness(artifacts, required_platform="windows_native")
    assert state == ReadinessState.SPECIFIED

def test_commit_alone_is_not_test_evidence():
    artifacts = [
        EvidenceArtifact(kind="commit", metadata={"sha": "abc1234"})
    ]
    
    state = evaluate_readiness(artifacts)
    assert state == ReadinessState.IMPLEMENTED

def test_linux_evidence_cannot_satisfy_windows_requirement():
    artifacts = [
        EvidenceArtifact(kind="commit", metadata={"sha": "abc"}),
        EvidenceArtifact(kind="test_log", metadata={"platform": "linux"})
    ]
    
    # Reaches TESTED but fails to reach EVIDENCE_VERIFIED
    state = evaluate_readiness(artifacts, required_platform="windows_native")
    assert state == ReadinessState.TESTED

def test_matching_evidence_achieves_verified():
    artifacts = [
        EvidenceArtifact(kind="commit", metadata={"sha": "abc"}),
        EvidenceArtifact(kind="test_log", metadata={"platform": "windows_native"})
    ]
    
    state = evaluate_readiness(artifacts, required_platform="windows_native")
    assert state == ReadinessState.EVIDENCE_VERIFIED

def test_failed_regression_blocks_shipping_ready():
    artifacts = [
        EvidenceArtifact(kind="commit", metadata={"sha": "abc"}),
        EvidenceArtifact(kind="test_log", metadata={"platform": "generic"}),
        EvidenceArtifact(kind="regression_result", metadata={"passed": False})
    ]
    
    state = evaluate_readiness(artifacts, required_platform="generic")
    # Gets stuck at EVIDENCE_VERIFIED
    assert state == ReadinessState.EVIDENCE_VERIFIED

def test_passing_regression_achieves_shipping_ready():
    artifacts = [
        EvidenceArtifact(kind="commit", metadata={"sha": "abc"}),
        EvidenceArtifact(kind="test_log", metadata={"platform": "generic"}),
        EvidenceArtifact(kind="regression_result", metadata={"passed": True})
    ]
    
    state = evaluate_readiness(artifacts, required_platform="generic")
    assert state == ReadinessState.SHIPPING_READY

