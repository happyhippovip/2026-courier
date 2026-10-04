from dataclasses import dataclass
from typing import List, Dict, Optional
import enum

class MemoryStatus(str, enum.Enum):
    VERIFIED = "VERIFIED"
    TESTED = "TESTED"
    UNKNOWN = "UNKNOWN"
    SUPERSEDED = "SUPERSEDED"
    INVALIDATED = "INVALIDATED"

@dataclass
class EvidenceRef:
    claim_id: str
    status: MemoryStatus

class ReadinessNode:
    def __init__(self, name: str, evidence_deps: List[str]):
        """
        name: Name of the readiness node (e.g. 'Installer E2E')
        evidence_deps: List of memory claim IDs that must be VERIFIED for this node to be ready.
        """
        self.name = name
        self.evidence_deps = evidence_deps
        self.children = [] # type: List[ReadinessNode]

    def add_child(self, child: "ReadinessNode"):
        self.children.append(child)

    def evaluate_readiness(self, memory_store: Dict[str, EvidenceRef]) -> str:
        """
        Dynamically evaluates readiness based strictly on underlying memory evidence.
        Returns: "READY", "DEGRADED", or "UNKNOWN"
        """
        # If no dependencies and no children, we can't assert readiness
        if not self.evidence_deps and not self.children:
            return "UNKNOWN"
            
        # Check direct evidence dependencies
        for claim_id in self.evidence_deps:
            ref = memory_store.get(claim_id)
            if not ref:
                return "UNKNOWN"
                
            if ref.status in [MemoryStatus.SUPERSEDED, MemoryStatus.INVALIDATED]:
                return "DEGRADED"
                
            if ref.status != MemoryStatus.VERIFIED:
                return "UNKNOWN"
                
        # Check children recursively
        for child in self.children:
            child_status = child.evaluate_readiness(memory_store)
            if child_status == "DEGRADED":
                return "DEGRADED"
            if child_status == "UNKNOWN":
                return "UNKNOWN"
                
        return "READY"
