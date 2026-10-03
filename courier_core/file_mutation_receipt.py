from dataclasses import dataclass
from typing import Optional
import hashlib

@dataclass
class FileMutationReceipt:
    """MAC-22: Record before/after/evidence/rollback information."""
    filepath: str
    before_hash: str
    after_hash: str
    evidence_snippet: str
    rollback_patch: Optional[str]

    def verify_mutation_changed_state(self) -> bool:
        return self.before_hash != self.after_hash

    @staticmethod
    def hash_content(content: str) -> str:
        return hashlib.sha256(content.encode('utf-8')).hexdigest()
