from dataclasses import dataclass, field
from typing import Set, List

class EvidenceRejectedError(Exception):
    pass

@dataclass
class EvidenceRequirement:
    """
    Specifies the host capabilities required from the evidence.
    If 'generic' is True, any valid evidence is accepted regardless of its specific capabilities.
    """
    required_capabilities: Set[str] = field(default_factory=set)
    generic: bool = False

@dataclass
class EvidenceMetadata:
    """
    Metadata attached to an evidence submission.
    Capabilities assert the host/environment properties where the evidence was gathered.
    Examples: 'windows_native', 'mac_native', 'linux', 'browser', 'cloud', 'local_file_access'
    """
    capabilities: Set[str] = field(default_factory=set)
    
    # Provider-neutral references (e.g. URI, hashes)
    refs: List[str] = field(default_factory=list)

    def meets_requirement(self, requirement: EvidenceRequirement) -> bool:
        if requirement.generic:
            return True
        return requirement.required_capabilities.issubset(self.capabilities)

def verify_evidence_capabilities(evidence: EvidenceMetadata, requirement: EvidenceRequirement) -> None:
    """
    Validates that the provided evidence meets the specified requirement.
    Raises EvidenceRejectedError if required capabilities are missing.
    """
    if not evidence.meets_requirement(requirement):
        missing = requirement.required_capabilities - evidence.capabilities
        raise EvidenceRejectedError(
            f"Evidence rejected: missing required host capabilities: {sorted(missing)}"
        )
