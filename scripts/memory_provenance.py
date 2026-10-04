from dataclasses import dataclass, field, asdict
from typing import Optional, Dict
import datetime

@dataclass
class MemoryProvenance:
    source: str
    repo: str
    branch: str
    sha: str
    host: str
    os_name: str
    test: str
    artifact: str
    timestamp: str
    workkey: str
    verification_level: str

@dataclass
class MemoryClaim:
    content: str
    is_readiness_critical: bool
    provenance: Optional[MemoryProvenance] = None
    
    def to_dict(self) -> Dict:
        data = {"content": self.content, "is_readiness_critical": self.is_readiness_critical}
        if self.provenance:
            data["provenance"] = asdict(self.provenance)
        return data

class ProvenanceLossError(Exception):
    pass

def update_memory_claim(existing_claim: MemoryClaim, new_content: str, new_provenance: Optional[MemoryProvenance] = None) -> MemoryClaim:
    """
    Updates a memory claim. 
    Enforces that readiness-critical claims cannot lose their provenance.
    """
    if existing_claim.is_readiness_critical:
        # If the existing claim had provenance, the new one must have it too
        if existing_claim.provenance and not new_provenance:
            raise ProvenanceLossError("Cannot remove provenance from a readiness-critical memory claim.")
        
        # Optionally, we can merge or just replace, but the rule is: don't lose it.
        # We require new_provenance if we're updating a readiness critical claim with existing provenance
        
    return MemoryClaim(
        content=new_content,
        is_readiness_critical=existing_claim.is_readiness_critical,
        provenance=new_provenance if new_provenance else existing_claim.provenance
    )
