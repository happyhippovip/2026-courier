from dataclasses import dataclass
from typing import List, Dict, Optional, Any
from enum import Enum

class ReadinessState(str, Enum):
    READY = "READY"
    DEGRADED = "DEGRADED"
    UNKNOWN = "UNKNOWN"

@dataclass
class Evidence:
    evidence_id: str
    evidence_type: str
    sha: str
    os: str
    timestamp: int
    is_superseded: bool = False

@dataclass
class ReadinessNodeDefinition:
    node_id: str
    required_evidence_types: List[str]
    max_age_seconds: int
    required_os: Optional[str]
    dependencies: List[str] # IDs of other nodes

class ReadinessDerivationEngine:
    def __init__(self, current_sha: str, current_time: int):
        self.current_sha = current_sha
        self.current_time = current_time
        
    def derive_status(self, node: ReadinessNodeDefinition, provided_evidence: List[Evidence], dependent_states: Dict[str, ReadinessState]) -> ReadinessState:
        # 1. Check dependencies first
        for dep_id in node.dependencies:
            dep_state = dependent_states.get(dep_id, ReadinessState.UNKNOWN)
            if dep_state == ReadinessState.DEGRADED:
                return ReadinessState.DEGRADED
            if dep_state == ReadinessState.UNKNOWN:
                return ReadinessState.UNKNOWN
                
        # 2. Match evidence to required types
        found_types = set()
        
        for req_type in node.required_evidence_types:
            # Find evidence matching this type
            matching = [e for e in provided_evidence if e.evidence_type == req_type]
            
            if not matching:
                continue
                
            # Evaluate the best matching evidence
            for ev in matching:
                # Check supersession
                if ev.is_superseded:
                    return ReadinessState.DEGRADED
                    
                # Check SHA (must strictly match)
                if ev.sha != self.current_sha:
                    return ReadinessState.DEGRADED # Stale SHA -> Degraded
                    
                # Check OS (if required)
                if node.required_os and ev.os != node.required_os:
                    continue # Not degraded, just doesn't satisfy the requirement
                    
                # Check freshness
                age = self.current_time - ev.timestamp
                if age > node.max_age_seconds:
                    return ReadinessState.DEGRADED # Stale time -> Degraded
                    
                # Valid evidence found
                found_types.add(req_type)
                break
                
        # 3. Verify all required types were found
        if len(found_types) < len(node.required_evidence_types):
            if len(found_types) > 0:
                # Partial evidence found but not all
                return ReadinessState.UNKNOWN 
            return ReadinessState.UNKNOWN
            
        return ReadinessState.READY
