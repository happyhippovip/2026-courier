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

def test_schema_name_does_not_escape(tmp_path):
    schemas = tmp_path / "repo" / "schemas"
    schemas.mkdir(parents=True)
    outside = tmp_path / "outside.json"
    outside.write_text('{"marker":"SECRET-SCHEMA"}\n', encoding="utf-8")
    validator = FoundrySchemaValidator(str(schemas))
    try:
        data = validator._load_schema("../../outside.json")
        err = None
        marker = data.get("marker")
    except ValueError as exc:
        err = str(exc)
        marker = None
    assert (err, marker) == ("refusing an unsafe schema name", None)
    assert "SECRET-SCHEMA" in outside.read_text(encoding="utf-8")

def test_schema_file_does_not_follow_a_symlink(tmp_path):
    schemas = tmp_path / "schemas"
    schemas.mkdir()
    outside = tmp_path / "outside.json"
    outside.write_text('{"marker":"SECRET-SCHEMA"}\n', encoding="utf-8")
    (schemas / "gate.schema.json").symlink_to(outside)
    validator = FoundrySchemaValidator(str(schemas))
    try:
        data = validator._load_schema("gate.schema.json")
        err = None
        marker = data.get("marker")
    except ValueError as exc:
        err = str(exc)
        marker = None
    parent_outside = tmp_path / "parent-outside"
    parent_outside.mkdir()
    (parent_outside / "keep.txt").write_text("keep", encoding="utf-8")
    (parent_outside / "gate.schema.json").write_text('{"marker":"SECRET-PARENT"}\n', encoding="utf-8")
    linked = tmp_path / "linked-schemas"
    linked.symlink_to(parent_outside)
    validator2 = FoundrySchemaValidator(str(linked))
    try:
        data2 = validator2._load_schema("gate.schema.json")
        err2 = None
        marker2 = data2.get("marker")
    except ValueError as exc:
        err2 = str(exc)
        marker2 = None
    assert (err, marker, err2, marker2) == (
        "refusing to follow a symlink",
        None,
        "refusing to follow a symlink",
        None,
    )
    assert "SECRET-SCHEMA" in outside.read_text(encoding="utf-8")
    assert "SECRET-PARENT" in (parent_outside / "gate.schema.json").read_text(encoding="utf-8")
