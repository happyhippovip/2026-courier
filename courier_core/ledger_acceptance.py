from dataclasses import dataclass
from typing import List, Dict, Any

@dataclass
class EvidenceSubmission:
    evidence_id: str
    confidence: float
    schema_version: str
    has_signature: bool
    data: Dict[str, Any]

class LedgerAcceptanceEngine:
    """
    Deterministic rule engine for Ledger Acceptance.
    MAC-01: Make evidence acceptance deterministic and testable.
    """
    REQUIRED_SCHEMA = "v1"
    MIN_CONFIDENCE = 0.95

    @classmethod
    def evaluate(cls, submission: EvidenceSubmission) -> bool:
        if not submission.has_signature:
            return False
        if submission.schema_version != cls.REQUIRED_SCHEMA:
            return False
        if submission.confidence < cls.MIN_CONFIDENCE:
            return False
        if not submission.data:
            return False
        return True
