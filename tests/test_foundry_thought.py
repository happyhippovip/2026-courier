from scripts.foundry_thought import (
    ThoughtIngestionEnvelope, SourceType, PrivacyClass,
    ThoughtMessage, SourceTypeWithSlack, ThoughtCoverageLedger,
    ThoughtSchemaValidator
)
from datetime import datetime, timezone
import hashlib

def test_ingestion_envelope_validation():
    validator = ThoughtSchemaValidator()
    content_hash = hashlib.sha256(b"hello").hexdigest()
    env = ThoughtIngestionEnvelope(
        ingestion_id="i1",
        source_type=SourceType.CHAT_EXPORT,
        source_message_id="m1",
        source_timestamp=datetime.now(timezone.utc).isoformat(),
        received_at=datetime.now(timezone.utc).isoformat(),
        content_hash=content_hash,
        content={"text": "hello"},
        metadata={"author": "user"},
        correlation_id="c1",
        privacy_class=PrivacyClass.INTERNAL
    )
    validator.validate_ingestion_envelope(env)

def test_thought_message_validation():
    validator = ThoughtSchemaValidator()
    payload_hash = hashlib.sha256(b"hello").hexdigest()
    msg = ThoughtMessage(
        schema_version="thought-message-1.0",
        message_id="msg1",
        timestamp=datetime.now(timezone.utc).isoformat(),
        source=SourceTypeWithSlack.SLACK,
        payload={"text": "hello"},
        payload_hash=payload_hash
    )
    validator.validate_message(msg)

def test_coverage_ledger_validation():
    validator = ThoughtSchemaValidator()
    ledger = ThoughtCoverageLedger(
        schema_version="thought-coverage-ledger-1.0",
        initial_anchor="2026-10-07",
        earliest_available_message=None,
        latest_available_message=None,
        scanner_ranges={},
        completed_checkpoints={},
        gaps=[],
        overlaps=[],
        message_counts={},
        processed_messages={}
    )
    validator.validate_coverage_ledger(ledger)

def test_schema_name_does_not_escape(tmp_path):
    from scripts.foundry_thought import ThoughtSchemaValidator
    schemas = tmp_path / "repo" / "schemas"
    schemas.mkdir(parents=True)
    outside = tmp_path / "outside.json"
    outside.write_text('{"marker":"SECRET-SCHEMA"}\n', encoding="utf-8")
    validator = ThoughtSchemaValidator(str(schemas))
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
    validator = ThoughtSchemaValidator(str(schemas))
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
    validator2 = ThoughtSchemaValidator(str(linked))
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
