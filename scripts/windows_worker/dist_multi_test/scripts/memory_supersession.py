from dataclasses import dataclass, field
from typing import Optional, Dict

@dataclass
class MemoryClaim:
    id: str
    content: str
    status: str = "VERIFIED"
    provenance: Optional[Dict] = None
    superseded_by: Optional[str] = None

class MemorySupersessionError(Exception):
    pass

def supersede_memory_claim(old_claim: MemoryClaim, new_claim: MemoryClaim) -> MemoryClaim:
    """
    Safely supersedes an old memory claim with a new one.
    - Preserves old record.
    - Marks old record SUPERSEDED.
    - Points to replacement.
    - Retains provenance.
    - Prevents old record from driving decisions (by changing its status).
    """
    if old_claim.status in ("SUPERSEDED", "INVALIDATED"):
        raise MemorySupersessionError(f"Cannot supersede a claim that is already {old_claim.status}")
        
    if new_claim.status != "VERIFIED":
        raise MemorySupersessionError("Replacement claim must be VERIFIED before superseding another claim.")
        
    # Mark old claim as superseded
    old_claim.status = "SUPERSEDED"
    old_claim.superseded_by = new_claim.id
    
    # Return the modified old claim (in a real system we'd persist both, here we modify in place)
    return old_claim
    
def get_active_decisions(claims_database: list[MemoryClaim]) -> list[MemoryClaim]:
    """
    Filters out SUPERSEDED and INVALIDATED claims so they do not drive current decisions.
    """
    return [claim for claim in claims_database if claim.status not in ("SUPERSEDED", "INVALIDATED")]
