from dataclasses import dataclass

@dataclass
class ScreenshotObservation:
    """WK-12: Ensure pixels cannot independently declare FAILED/DONE/GREEN."""
    image_hash: str
    inferred_state: str # e.g. 'GREEN', 'FAILED'
    confidence: float

class TruthBoundary:
    @staticmethod
    def evaluate_readiness(pixels: ScreenshotObservation, system_evidence_verified: bool) -> bool:
        # Pixels alone are NEVER enough to pass readiness. 
        # Even if confidence is 1.0 and state is GREEN, we require system_evidence_verified.
        if pixels.inferred_state == "GREEN" and pixels.confidence > 0.9:
            return system_evidence_verified
        return False
