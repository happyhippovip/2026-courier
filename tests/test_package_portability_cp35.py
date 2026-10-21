"""Tests for CP-35 / CQ-35 / GB-PACKAGE-PORTABILITY-01: Task Package Portability & Import Validation.

Verifies:
1. Export bundle creation with original prompt and execution codes.
2. Secret scrubbing from export payloads (zero secrets in export).
3. Demotion of imported claims (DONE/APPROVED/PASS) to DRAFT status ("Importiertes DONE wird nicht vertraut").
4. ID conflict detection prevents silent overwrite by auto-rekeying.
5. Re-authorization requirement before execution.
6. Evidence generated with ['export-schema', 'provenance', 'import-validation'].
"""

import pytest

from courier_core.task_package_portability import (
    PackageExportBundle,
    PackageLifecycleStatus,
    TaskPackagePortabilityEngine,
)


def test_export_bundle_generation_and_secret_scrubbing():
    """Exports cleanly retain prompt text while scrubbing credentials and tokens."""
    engine = TaskPackagePortabilityEngine()

    prompt_with_secret = (
        "Run integration test with api_key: sk-1234567890abcdef1234567890abcdef12345678 and report"
    )

    bundle = engine.export_package(
        package_id="CP-EXPORT-01",
        exported_at_iso="2026-10-21T11:40:00Z",
        original_prompt_text=prompt_with_secret,
        result_codes=[0, 0],
        evidence_hashes={"test-report": "hash-abc-123"},
    )

    assert bundle.package_id == "CP-EXPORT-01"
    assert "sk-1234567890" not in bundle.original_prompt_text
    assert "[SCRUBBED_SECRET]" in bundle.original_prompt_text
    assert bundle.scrubbed_secrets_count > 0
    assert len(bundle.bundle_digest) == 64


def test_imported_approved_status_strictly_demoted_to_draft():
    """Claimed foreign status (APPROVED / DONE / PASS) is never trusted and reset to DRAFT."""
    engine = TaskPackagePortabilityEngine()

    bundle = engine.export_package(
        package_id="CP-FOREIGN-01",
        exported_at_iso="2026-10-21T11:40:00Z",
        original_prompt_text="Inspect queue depth",
        result_codes=[0],
        evidence_hashes={},
    )

    # Foreign metadata claims APPROVED
    result = engine.import_package(
        bundle=bundle,
        existing_package_ids=set(),
        claimed_import_status="APPROVED",
    )

    assert result.status == PackageLifecycleStatus.DRAFT
    assert "APPROVED" in result.imported_claims_demoted
    assert result.requires_fresh_authorization is True


def test_id_conflict_detection_and_safe_rekeying():
    """Importing a package with an existing ID prevents silent overwrite by rekeying."""
    engine = TaskPackagePortabilityEngine()

    bundle = engine.export_package(
        package_id="CP-EXISTING-01",
        exported_at_iso="2026-10-21T11:40:00Z",
        original_prompt_text="Check local disk",
        result_codes=[0],
        evidence_hashes={},
    )

    existing_ids = {"CP-EXISTING-01", "CP-02"}

    result = engine.import_package(
        bundle=bundle,
        existing_package_ids=existing_ids,
    )

    assert result.id_conflict_detected is True
    assert result.imported_package_id == "CP-EXISTING-01-draft-import"
    assert result.original_package_id == "CP-EXISTING-01"
    assert result.status == PackageLifecycleStatus.DRAFT


def test_evidence_generation():
    """Emits required evidence with export-schema, provenance, and import-validation."""
    engine = TaskPackagePortabilityEngine()

    bundle = engine.export_package(
        package_id="CP-EVID",
        exported_at_iso="2026-10-21T11:40:00Z",
        original_prompt_text="Evidence prompt",
        result_codes=[0],
        evidence_hashes={},
    )
    engine.import_package(bundle, existing_package_ids=set())

    evidence = engine.generate_portability_evidence()
    required_keys = ["export-schema", "provenance", "import-validation"]
    for k in required_keys:
        assert k in evidence

    assert evidence["export-schema"]["secret_exclusion_enforced"] is True
    assert evidence["import-validation"]["untrusted_claims_reset_to_draft"] is True
    assert evidence["import-validation"]["fresh_authorization_required"] is True
