from dataclasses import dataclass
from typing import List, Dict, Callable

@dataclass
class MemoryClaim:
    id: str
    content: str
    requires_freshness: bool
    status: str
    expected_evidence_command: str = None
    last_verified_value: str = None

class MemoryFreshnessChecker:
    def __init__(self, memory_claims: List[MemoryClaim], evidence_fetcher: Callable[[str], str]):
        """
        evidence_fetcher takes a command string and returns the actual current output.
        """
        self.memory_claims = memory_claims
        self.evidence_fetcher = evidence_fetcher

    def verify_freshness(self) -> List[MemoryClaim]:
        """
        Implements the rule: MEMORY IS A STARTING POINT. CURRENT REPO/EVIDENCE IS TRUTH.
        1. Loads canonical memory (done via constructor)
        2. Identifies claims requiring freshness
        3. Refetches/reverifies claims
        4. Marks changed claims as SUPERSEDED/STALE, matching truth
        """
        for claim in self.memory_claims:
            if claim.requires_freshness and claim.status == "VERIFIED":
                if not claim.expected_evidence_command:
                    continue
                    
                # 3. Refetch
                current_truth = self.evidence_fetcher(claim.expected_evidence_command)
                
                # 4. Reverify & mark superseded
                if current_truth != claim.last_verified_value:
                    claim.status = "SUPERSEDED"
                    claim.content = f"[STALE] Old value: {claim.last_verified_value} | Current Truth: {current_truth}"
                    
        # 5. Return updated memory stream reflecting current truth
        return self.memory_claims
