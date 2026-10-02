from enum import Enum
from dataclasses import dataclass, field
from typing import List, Dict, Any

class ReadinessState(Enum):
    SPECIFIED = 1
    IMPLEMENTED = 2
    TESTED = 3
    EVIDENCE_VERIFIED = 4
    SHIPPING_READY = 5

    def __lt__(self, other):
        if self.__class__ is other.__class__:
            return self.value < other.value
        return NotImplemented

@dataclass
class EvidenceArtifact:
    kind: str  # 'doc', 'commit', 'test_log', 'regression_result'
    metadata: Dict[str, Any] = field(default_factory=dict)

def evaluate_readiness(artifacts: List[EvidenceArtifact], required_platform: str = "generic") -> ReadinessState:
    """
    Evaluates the strict progression of readiness from raw evidence.
    Progress is exclusively derived from accepted evidence, not human estimations.
    """
    has_doc = any(a.kind == "doc" for a in artifacts)
    has_commit = any(a.kind == "commit" for a in artifacts)
    test_logs = [a for a in artifacts if a.kind == "test_log"]
    regressions = [a for a in artifacts if a.kind == "regression_result"]

    # Base state: we have specs or docs
    state = ReadinessState.SPECIFIED

    # Rule: documentation cannot jump directly to evidence verified or implemented
    if not has_commit:
        return state
        
    state = ReadinessState.IMPLEMENTED

    # Rule: a commit alone is not test evidence
    if not test_logs:
        return state

    state = ReadinessState.TESTED

    # Rule: platform-specific evidence requirements (e.g. linux evidence cannot satisfy windows_native)
    verified = False
    for log in test_logs:
        platform = log.metadata.get("platform", "generic")
        if required_platform == "generic" or platform == required_platform:
            verified = True
            break
            
    if not verified:
        return state
        
    state = ReadinessState.EVIDENCE_VERIFIED

    # Rule: failed regression may block shipping-ready
    # We require a regression run to reach SHIPPING_READY, and it must pass.
    if not regressions:
        return state
        
    has_failures = any(not r.metadata.get("passed", False) for r in regressions)
    if has_failures:
        # Blocks shipping-ready
        return state

    return ReadinessState.SHIPPING_READY
