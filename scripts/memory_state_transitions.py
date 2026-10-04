import enum

class MemoryState(str, enum.Enum):
    UNKNOWN = "UNKNOWN"
    REPORTED = "REPORTED"
    OBSERVED = "OBSERVED"
    TESTED = "TESTED"
    VERIFIED = "VERIFIED"
    SUPERSEDED = "SUPERSEDED"
    INVALIDATED = "INVALIDATED"

class MemoryTransitionError(Exception):
    pass

VALID_TRANSITIONS = {
    MemoryState.UNKNOWN: {MemoryState.REPORTED, MemoryState.OBSERVED, MemoryState.INVALIDATED},
    MemoryState.REPORTED: {MemoryState.OBSERVED, MemoryState.TESTED, MemoryState.INVALIDATED},
    MemoryState.OBSERVED: {MemoryState.TESTED, MemoryState.INVALIDATED},
    MemoryState.TESTED: {MemoryState.VERIFIED, MemoryState.INVALIDATED},
    MemoryState.VERIFIED: {MemoryState.SUPERSEDED, MemoryState.INVALIDATED},
    MemoryState.SUPERSEDED: set(),  # Terminal state
    MemoryState.INVALIDATED: set()  # Terminal state
}

def transition_memory_state(current_state: MemoryState, new_state: MemoryState, evidence: dict = None) -> MemoryState:
    """
    Safely transitions a memory item from one state to another, enforcing rules.
    """
    if new_state not in VALID_TRANSITIONS.get(current_state, set()):
        raise MemoryTransitionError(f"Invalid transition from {current_state} to {new_state}")
    
    # Specific rule: To reach VERIFIED, strict provenance evidence is required.
    if new_state == MemoryState.VERIFIED:
        if not evidence:
            raise MemoryTransitionError("Cannot transition to VERIFIED without evidence.")
        
        required_keys = [
            "what_is_known", 
            "why_is_it_believed", 
            "applicable_state", 
            "producer_identity", 
            "verification_timestamp", 
            "invalidation_conditions"
        ]
        
        for key in required_keys:
            if key not in evidence or not evidence[key]:
                raise MemoryTransitionError(f"Cannot transition to VERIFIED. Missing required evidence key: {key}")
                
    return new_state
