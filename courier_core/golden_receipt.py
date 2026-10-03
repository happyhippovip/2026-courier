from dataclasses import dataclass
from typing import Dict, Any
import hashlib

@dataclass
class GoldenEvidenceReceipt:
    """MAC-12: Produce machine-readable proof of Golden acceptance."""
    target_sha: str
    suite_name: str
    duration_sec: float
    passed: bool
    environment: str

    def generate_proof_hash(self) -> str:
        data = f"{self.target_sha}|{self.suite_name}|{self.duration_sec}|{self.passed}|{self.environment}"
        return hashlib.sha256(data.encode('utf-8')).hexdigest()

    def to_payload(self) -> Dict[str, Any]:
        return {
            "type": "GOLDEN_RECEIPT",
            "proof_hash": self.generate_proof_hash(),
            "target_sha": self.target_sha,
            "suite_name": self.suite_name,
            "duration_sec": self.duration_sec,
            "passed": self.passed,
            "environment": self.environment
        }
