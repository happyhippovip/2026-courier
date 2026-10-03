from dataclasses import dataclass
from typing import Dict, Any, List

@dataclass
class AutomationReceipt:
    """MAC-13: Record planned/executed/verified automation state."""
    transaction_id: str
    target_system: str
    planned_steps: List[str]
    executed_steps: List[str]
    verification_success: bool
    evidence_refs: List[str]

    def is_complete_and_verified(self) -> bool:
        return (
            self.planned_steps == self.executed_steps and
            self.verification_success and
            len(self.evidence_refs) > 0
        )
