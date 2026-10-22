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
