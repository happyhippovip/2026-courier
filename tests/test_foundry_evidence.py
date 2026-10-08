from scripts.foundry_evidence import (
    DossierGoalMissionLink, VerifiedFounderReviewGate, PilotEvidenceRecord,
    FounderApprovalState, EvidenceType, FoundrySchemaValidator
)
from datetime import datetime, timezone

def test_dossier_link_validation():
    validator = FoundrySchemaValidator()
    link = DossierGoalMissionLink(
        dossier_id="d1",
        goal_id="g1",
        mission_id="m1",
        link_rationale="Derived from market research",
        timestamp_utc=datetime.now(timezone.utc).isoformat()
    )
    validator.validate_link(link)

def test_founder_review_validation():
    validator = FoundrySchemaValidator()
    gate = VerifiedFounderReviewGate(
        gate_id="gate1",
        review_target="m1",
        founder_approval=FounderApprovalState.APPROVED,
        feedback_notes="Looks good",
        timestamp_utc=datetime.now(timezone.utc).isoformat()
    )
    validator.validate_review_gate(gate)

def test_pilot_evidence_validation():
    validator = FoundrySchemaValidator()
    evidence = PilotEvidenceRecord(
        pilot_id="p1",
        evidence_type=EvidenceType.ECONOMIC,
        metric="WTP",
        result="5.0",
        timestamp_utc=datetime.now(timezone.utc).isoformat()
    )
    validator.validate_evidence(evidence)
