"""Tests for CP-37 / CQ-37 / GB-SCHEMA-MIGRATION-01: Schema Migration & Historical UNKNOWN Preservation.

Verifies:
1. Versioned read capability for supported schemas.
2. Incompatible or unrecognized schema versions fail closed with IncompatibleSchemaVersionError.
3. Migration strictly preserves historical UNKNOWNs without inventing runtime fields or costs.
4. Lossless rollback: Reverting v2 to v1 loses zero confirmed tasks.
5. Evidence generated with ['schema-versions', 'sanitized-records', 'migration-plan'].
"""

import pytest

from courier_core.schema_migration_engine import (
    IncompatibleSchemaVersionError,
    SchemaMigrationEngine,
)


def test_versioned_read_supports_valid_schemas():
    """Versioned records (1.0.0, 2.0.0) are safely read without mutation."""
    engine = SchemaMigrationEngine()

    v1_record = {
        "task_id": "task-legacy-01",
        "schema_version": "1.0.0",
        "payload": "execute regression",
        "cost_status": "UNKNOWN",
    }

    read_rec = engine.read_versioned_record(v1_record)
    assert read_rec["task_id"] == "task-legacy-01"
    assert read_rec["schema_version"] == "1.0.0"


def test_incompatible_or_unsupported_schema_fails_closed():
    """Records with unknown or corrupted schema versions raise IncompatibleSchemaVersionError."""
    engine = SchemaMigrationEngine()

    bad_record = {
        "task_id": "task-bad-version",
        "schema_version": "99.0.0",
        "payload": "unknown format",
    }

    with pytest.raises(IncompatibleSchemaVersionError) as exc_info:
        engine.read_versioned_record(bad_record)
    assert "unsupported or incompatible" in str(exc_info.value)


def test_migration_preserves_historical_unknowns_without_invention():
    """Migrating V1 to V2 preserves UNKNOWN cost status without inventing Euro numbers or runtime fields."""
    engine = SchemaMigrationEngine()

    v1_record = {
        "task_id": "task-100",
        "schema_version": "1.0.0",
        "payload": "run tests",
        "cost_status": "UNKNOWN",
    }

    v2 = engine.migrate_v1_to_v2(v1_record)
    assert v2["schema_version"] == "2.0.0"
    assert v2["cost_status"] == "UNKNOWN"
    assert v2["spend_eur"] == "UNKNOWN"
    # Optional field retry_policy is None, not an invented configuration
    assert v2["retry_policy"] is None


def test_reversible_migration_loses_zero_confirmed_tasks():
    """A full upgrade to V2 and rollback to V1 preserves confirmed tasks and payload losslessly."""
    engine = SchemaMigrationEngine()

    original_v1 = {
        "task_id": "task-confirmed-42",
        "schema_version": "1.0.0",
        "payload": "deterministic proof verification",
        "cost_status": "UNKNOWN",
        "status": "CONFIRMED_PASS",
    }

    # Upgrade to v2
    v2 = engine.migrate_v1_to_v2(original_v1)
    assert v2["schema_version"] == "2.0.0"

    # Rollback to v1
    rolled_back_v1 = engine.rollback_v2_to_v1(v2)
    assert rolled_back_v1["schema_version"] == "1.0.0"
    assert rolled_back_v1["task_id"] == original_v1["task_id"]
    assert rolled_back_v1["payload"] == original_v1["payload"]
    assert rolled_back_v1["status"] == "CONFIRMED_PASS"
    assert rolled_back_v1["cost_status"] == "UNKNOWN"


def test_evidence_generation():
    """Emits required evidence with schema-versions, sanitized-records, and migration-plan."""
    engine = SchemaMigrationEngine()

    rec = {
        "task_id": "task-evid",
        "schema_version": "1.0.0",
        "payload": "evidence test",
    }
    v2 = engine.migrate_v1_to_v2(rec)
    engine.rollback_v2_to_v1(v2)

    evidence = engine.generate_migration_evidence()
    required_keys = ["schema-versions", "sanitized-records", "migration-plan"]
    for k in required_keys:
        assert k in evidence

    assert "1.0.0" in evidence["schema-versions"]["supported"]
    assert "2.0.0" in evidence["schema-versions"]["supported"]
    assert evidence["sanitized-records"]["unknown_preservation_verified"] is True
    assert evidence["migration-plan"]["rollback_loses_zero_confirmed_tasks"] is True
