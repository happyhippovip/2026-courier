"""Task Package Portability, Export Sanitization & Import Validation Engine (CP-35 / CQ-35).

Verifies and enforces:
1. Export as Data & Evidence Bundle: Serializes package data with original prompt text,
   execution result codes, and verifiable evidence hashes.
2. Complete Secret Exclusion: Strips API keys, tokens, passwords, and sensitive variables from exports.
3. Untrusted Import Status ("Importiertes DONE/APPROVED wird nicht vertraut"):
   Imported packages are never accepted as completed or approved; claimed statuses are demoted to DRAFT.
4. ID Conflict Detection: Prevents silent overwrites of existing packages by auto-rekeying conflicts.
5. Re-Authorization Requirement: Imported drafts must undergo local authorization before execution.
6. Emits structured evidence matching ["export-schema", "provenance", "import-validation"].
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set


class PackageLifecycleStatus(str, Enum):
    DRAFT = "DRAFT"
    PENDING_AUTHORIZATION = "PENDING_AUTHORIZATION"
    AUTHORIZED = "AUTHORIZED"
    EXECUTABLE = "EXECUTABLE"
    COMPLETED = "COMPLETED"


@dataclass(frozen=True)
class PackageExportBundle:
    """An exported data and evidence bundle stripped of secrets."""
    export_schema_version: str
    package_id: str
    source_repository: str
    exported_at_iso: str
    original_prompt_text: str
    historical_result_codes: List[int]
    evidence_hashes: Dict[str, str]
    scrubbed_secrets_count: int
    bundle_digest: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "export_schema_version": self.export_schema_version,
            "package_id": self.package_id,
            "source_repository": self.source_repository,
            "exported_at_iso": self.exported_at_iso,
            "original_prompt_text": self.original_prompt_text,
            "historical_result_codes": list(self.historical_result_codes),
            "evidence_hashes": dict(self.evidence_hashes),
            "scrubbed_secrets_count": self.scrubbed_secrets_count,
            "bundle_digest": self.bundle_digest,
        }


@dataclass(frozen=True)
class ImportValidationResult:
    """Result of importing a bundle with ID conflict checking and status demotion."""
    imported_package_id: str
    original_package_id: str
    id_conflict_detected: bool
    status: PackageLifecycleStatus
    imported_claims_demoted: List[str]
    requires_fresh_authorization: bool
    sanitized_prompt_text: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "imported_package_id": self.imported_package_id,
            "original_package_id": self.original_package_id,
            "id_conflict_detected": self.id_conflict_detected,
            "status": self.status.value,
            "imported_claims_demoted": list(self.imported_claims_demoted),
            "requires_fresh_authorization": self.requires_fresh_authorization,
            "sanitized_prompt_text": self.sanitized_prompt_text,
        }


class TaskPackagePortabilityEngine:
    """Handles secure export bundles and unprivileged draft intake."""

    SECRET_PATTERNS = [
        re.compile(r"(?:api[_-]?key|secret|token|password|auth|bearer)[\s:=]+(['\"])?[a-zA-Z0-9_\-\.]{12,}\1?", re.IGNORECASE),
        re.compile(r"ghp_[a-zA-Z0-9]{36}"),
        re.compile(r"sk-[a-zA-Z0-9]{48}"),
    ]

    def __init__(self, local_source_repo: str = "happyhippovip/2026-courier") -> None:
        self.local_source_repo = local_source_repo
        self.imported_drafts: Dict[str, ImportValidationResult] = {}

    def _scrub_secrets(self, text: str) -> tuple[str, int]:
        scrubbed = text
        count = 0
        for pat in self.SECRET_PATTERNS:
            matches = pat.findall(scrubbed)
            if matches:
                count += len(matches)
                scrubbed = pat.sub("[SCRUBBED_SECRET]", scrubbed)
        return scrubbed, count

    def export_package(
        self,
        package_id: str,
        exported_at_iso: str,
        original_prompt_text: str,
        result_codes: List[int],
        evidence_hashes: Dict[str, str],
    ) -> PackageExportBundle:
        """Serializes a task package into an evidence bundle with all secrets stripped."""
        clean_prompt, prompt_scrubs = self._scrub_secrets(original_prompt_text)

        clean_evidence = {}
        evidence_scrubs = 0
        for k, v in evidence_hashes.items():
            sc_k, c1 = self._scrub_secrets(k)
            sc_v, c2 = self._scrub_secrets(v)
            clean_evidence[sc_k] = sc_v
            evidence_scrubs += (c1 + c2)

        total_scrubs = prompt_scrubs + evidence_scrubs

        raw_data = f"{package_id}:{clean_prompt}:{result_codes}:{sorted(clean_evidence.items())}"
        digest = hashlib.sha256(raw_data.encode("utf-8")).hexdigest()

        return PackageExportBundle(
            export_schema_version="1.0.0",
            package_id=package_id,
            source_repository=self.local_source_repo,
            exported_at_iso=exported_at_iso,
            original_prompt_text=clean_prompt,
            historical_result_codes=list(result_codes),
            evidence_hashes=clean_evidence,
            scrubbed_secrets_count=total_scrubs,
            bundle_digest=digest,
        )

    def import_package(
        self,
        bundle: PackageExportBundle,
        existing_package_ids: Set[str],
        claimed_import_status: Optional[str] = None,
    ) -> ImportValidationResult:
        """Validates bundle intake, demoting claimed statuses to DRAFT and rekeying on conflict."""
        claims_demoted: List[str] = []
        if claimed_import_status in {"DONE", "APPROVED", "PASS", "COMPLETED", "VERIFIED"}:
            claims_demoted.append(claimed_import_status)

        conflict = bundle.package_id in existing_package_ids
        imported_id = f"{bundle.package_id}-draft-import" if conflict else bundle.package_id

        res = ImportValidationResult(
            imported_package_id=imported_id,
            original_package_id=bundle.package_id,
            id_conflict_detected=conflict,
            status=PackageLifecycleStatus.DRAFT,  # Invariant: Always enters as DRAFT
            imported_claims_demoted=claims_demoted,
            requires_fresh_authorization=True,
            sanitized_prompt_text=bundle.original_prompt_text,
        )

        self.imported_drafts[imported_id] = res
        return res

    def generate_portability_evidence(self) -> Dict[str, Any]:
        """Emits required evidence dictionary for CP-35.

        Required fields:
        - 'export-schema'
        - 'provenance'
        - 'import-validation'
        """
        return {
            "export-schema": {
                "schema_version": "1.0.0",
                "secret_exclusion_enforced": True,
                "fields": [
                    "package_id",
                    "original_prompt_text",
                    "historical_result_codes",
                    "evidence_hashes",
                    "bundle_digest",
                ],
            },
            "provenance": {
                "source_repository": self.local_source_repo,
                "trusted_status_preservation": False,
            },
            "import-validation": {
                "imported_draft_count": len(self.imported_drafts),
                "untrusted_claims_reset_to_draft": True,
                "fresh_authorization_required": True,
            },
        }
