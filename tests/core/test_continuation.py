import pytest
from courier_core.continuation import (
    ContinuationPipeline, RawEvidence, 
    VerificationRejectedError
)

def test_raw_log_alone_cannot_become_accepted_state():
    evidences = [RawEvidence(kind="log", content="SUCCESS: Task done")]
    derived = ContinuationPipeline.derive_state(evidences)
    
    with pytest.raises(VerificationRejectedError, match="raw log alone cannot become accepted state"):
        ContinuationPipeline.verify_state(derived)

def test_screenshot_alone_cannot_become_accepted_state():
    evidences = [RawEvidence(kind="screenshot", content="<binary data>")]
    derived = ContinuationPipeline.derive_state(evidences)
    
    with pytest.raises(VerificationRejectedError, match="screenshot alone cannot become accepted state"):
        ContinuationPipeline.verify_state(derived)

def test_accepted_evidence_can_create_checkpoint():
    # Multi-modal evidence
    evidences = [
        RawEvidence(kind="log", content="Clicking submit"),
        RawEvidence(kind="screenshot", content="<img src='success.png'/>")
    ]
    
    def mock_extractor(evs):
        return {"step": 5, "completed": True}

    derived = ContinuationPipeline.derive_state(evidences, extractor_logic=mock_extractor)
    accepted = ContinuationPipeline.verify_state(derived)
    
    checkpoint = ContinuationPipeline.create_checkpoint(accepted, "cp-123")
    
    assert checkpoint.id == "cp-123"
    assert checkpoint.state == accepted

def test_continuation_resumes_from_accepted_checkpoint():
    evidences = [
        RawEvidence(kind="log", content="Clicking submit"),
        RawEvidence(kind="screenshot", content="<img src='success.png'/>")
    ]
    
    derived = ContinuationPipeline.derive_state(evidences, extractor_logic=lambda e: {"step": 5})
    accepted = ContinuationPipeline.verify_state(derived)
    checkpoint = ContinuationPipeline.create_checkpoint(accepted, "cp-123")
    
    resume_data = ContinuationPipeline.safe_resume(checkpoint)
    
    assert resume_data["step"] == 5

def test_rejected_evidence_does_not_advance_state():
    evidences = [RawEvidence(kind="log", content="Something happened")]
    derived = ContinuationPipeline.derive_state(evidences)
    
    # Verify raises, so we never get an AcceptedState, meaning we can't create a Checkpoint
    with pytest.raises(VerificationRejectedError):
        ContinuationPipeline.verify_state(derived)
        
    # State machine remains halted (exception boundary)
