from dataclasses import dataclass

@dataclass
class CIEvidence:
    target_sha: str
    ci_provider: str
    passed: bool
    coverage_percent: float

class CIEvidenceValidator:
    """WK-03: Verify integration/v1 CI coverage and exact-SHA evidence."""
    MIN_COVERAGE = 85.0

    @classmethod
    def verify(cls, evidence: CIEvidence, expected_sha: str) -> bool:
        if evidence.target_sha != expected_sha:
            return False
        if not evidence.passed:
            return False
        if evidence.coverage_percent < cls.MIN_COVERAGE:
            return False
        return True
