from dataclasses import dataclass
from typing import List, Dict, Any, Set

class VerificationRejectedError(Exception):
    pass

@dataclass(frozen=True)
class RawEvidence:
    kind: str  # e.g., 'log', 'screenshot'
    content: str

@dataclass(frozen=True)
class DerivedState:
    extracted_data: Dict[str, Any]
    supporting_evidence_kinds: Set[str]

@dataclass(frozen=True)
class AcceptedState:
    verified_data: Dict[str, Any]

@dataclass(frozen=True)
class Checkpoint:
    id: str
    state: AcceptedState

class ContinuationPipeline:
    """
    Vertical slice of the Verified Continuation flow.
    RAW EVIDENCE -> DERIVED STATE -> ACCEPTED STATE -> CHECKPOINT -> SAFE CONTINUATION
    """

    @staticmethod
    def derive_state(evidences: List[RawEvidence], extractor_logic: callable = None) -> DerivedState:
        """Transforms RAW EVIDENCE into DERIVED STATE."""
        kinds = {e.kind for e in evidences}
        
        # In a real system, extractor_logic would parse the content.
        # For this minimal slice, we simulate extraction.
        data = extractor_logic(evidences) if extractor_logic else {"status": "inferred"}
        return DerivedState(extracted_data=data, supporting_evidence_kinds=kinds)

    @staticmethod
    def verify_state(state: DerivedState) -> AcceptedState:
        """
        Transforms DERIVED STATE into ACCEPTED STATE.
        Domain Rule for this slice: Requires BOTH 'log' and 'screenshot'.
        """
        if state.supporting_evidence_kinds == {"log"}:
            raise VerificationRejectedError("raw log alone cannot become accepted state")
        if state.supporting_evidence_kinds == {"screenshot"}:
            raise VerificationRejectedError("screenshot alone cannot become accepted state")
            
        if "log" not in state.supporting_evidence_kinds or "screenshot" not in state.supporting_evidence_kinds:
            raise VerificationRejectedError("Insufficient evidence to accept state")

        # Evidence is sufficient and accepted
        return AcceptedState(verified_data=state.extracted_data)

    @staticmethod
    def create_checkpoint(state: AcceptedState, checkpoint_id: str) -> Checkpoint:
        """Transforms ACCEPTED STATE into an immutable CHECKPOINT."""
        return Checkpoint(id=checkpoint_id, state=state)

    @staticmethod
    def safe_resume(checkpoint: Checkpoint) -> Dict[str, Any]:
        """Resumes continuation from an accepted CHECKPOINT."""
        # Returns the unwrapped trusted data for the next actor
        return checkpoint.state.verified_data

