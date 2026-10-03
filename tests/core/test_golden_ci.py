from courier_core.golden_integrity import GoldenIntegrityRunner, GoldenTestResult
from courier_core.integration_ci import CIEvidenceValidator, CIEvidence

def test_golden_integrity_runner():
    results = [
        GoldenTestResult("test_A", True, True),
        GoldenTestResult("test_B", False, True), # Deterministic fail
        GoldenTestResult("test_C", False, False) # Flaky
    ]
    
    evaluation = GoldenIntegrityRunner.evaluate_results(results)
    assert evaluation["integrity_status"] == "FAIL"
    assert "test_B" in evaluation["deterministic_failures"]
    assert "test_C" in evaluation["flaky_failures"]
    assert "test_A" not in evaluation["deterministic_failures"]

def test_ci_evidence_validator():
    evidence = CIEvidence("sha123", "github_actions", True, 90.0)
    
    # Valid
    assert CIEvidenceValidator.verify(evidence, "sha123") is True
    
    # Invalid SHA
    assert CIEvidenceValidator.verify(evidence, "sha456") is False
    
    # Low coverage
    low_cov_evidence = CIEvidence("sha123", "github_actions", True, 80.0)
    assert CIEvidenceValidator.verify(low_cov_evidence, "sha123") is False
