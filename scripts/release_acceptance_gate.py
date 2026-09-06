#!/usr/bin/env python3
"""Release Acceptance Gate V2.1 Hard Gate.

Non-authorizing deterministic pre-approval evaluation gate.
Implements Acceptance Identity V2.1:
- acceptance_id: Unique evaluation event identifier
- acceptance_input_hash: Stable Human-meaning input hash (Layer-1)
- acceptance_event_hash: Dynamic evaluation event hash (Layer-2)

Evaluates all technical evidence, provenance receipts, freshness split,
audience decision resolution, and strict finite zero-cost policy without
authorizing publication.

When all conditions are met, returns: READY_FOR_PRIVATE_UPLOAD_APPROVAL.
"""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scripts.creator_input_sources import compute_publication_dedupe_fingerprint
from scripts.evidence_provenance import (
    CHANNEL_IDENTITY_MAX_AGE_SECONDS,
    DUPLICATE_SNAPSHOT_MAX_AGE_SECONDS,
    ProvenanceReceipt,
    ProvenanceSource,
    TrustDomain,
    check_for_secrets,
    compute_payload_hash,
)
from scripts.publication_approval import (
    AppendOnlyApprovalLedger,
    AudienceDecisionRecord,
    AudienceRegistry,
    compute_metadata_revision_hash,
    derive_approval_state,
    validate_finite_exact_zero,
)
from scripts.publication_engine import (
    PublicationLedger,
    PublicationState,
    _recompute_file_sha256,
)

REPO_ROOT = Path(__file__).resolve().parent.parent

ACCEPTANCE_POLICY_VERSION = "2.1"
ACCEPTANCE_SCHEMA_VERSION = "2.1"
SUPPORTED_PACKAGE_SCHEMA = "2.2"
TARGET_CHANNEL_ID = "UCg0O_a10jsQ74ffS_HgFGqA"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def compute_acceptance_input_hash(
    *,
    content_id: str,
    platform: str,
    target_channel_id: str,
    media_sha256: str,
    publication_fingerprint: str,
    metadata_revision_hash: str,
    audience_decision_hash: str,
    expected_cost_eur: float = 0.0,
    policy_version: str = ACCEPTANCE_POLICY_VERSION,
    schema_version: str = ACCEPTANCE_SCHEMA_VERSION,
) -> str:
    """Compute stable Human-meaning input hash excluding dynamic timestamps and receipt IDs."""
    raw = {
        "policy_version": policy_version,
        "schema_version": schema_version,
        "content_id": content_id,
        "platform": platform,
        "target_channel_id": target_channel_id,
        "media_sha256": media_sha256.lower(),
        "publication_fingerprint": publication_fingerprint.lower(),
        "approved_action": "PRIVATE_UPLOAD",
        "approved_privacy": "private",
        "metadata_revision_hash": metadata_revision_hash,
        "audience_decision_hash": audience_decision_hash,
        "expected_cost_eur": expected_cost_eur,
    }
    return hashlib.sha256(
        json.dumps(raw, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def compute_acceptance_event_hash(
    *,
    acceptance_id: str,
    acceptance_input_hash: str,
    evaluated_at: str,
    channel_evidence_hash: str,
    channel_receipt_hash: str,
    duplicate_evidence_hash: str,
    duplicate_receipt_hash: str,
    local_publication_state: str,
    result: str,
) -> str:
    """Compute evaluation event hash binding input hash, receipts, timestamps, and ledger state."""
    raw = {
        "acceptance_id": acceptance_id,
        "acceptance_input_hash": acceptance_input_hash,
        "evaluated_at": evaluated_at,
        "channel_evidence_hash": channel_evidence_hash,
        "channel_receipt_hash": channel_receipt_hash,
        "duplicate_evidence_hash": duplicate_evidence_hash,
        "duplicate_receipt_hash": duplicate_receipt_hash,
        "local_publication_state": local_publication_state,
        "result": result,
    }
    return hashlib.sha256(
        json.dumps(raw, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


@dataclass(frozen=True)
class AcceptanceResult:
    acceptance_id: str
    acceptance_input_hash: str
    acceptance_event_hash: str
    policy_version: str
    schema_version: str
    content_id: str
    publication_fingerprint: str
    media_sha256: str
    target_channel_id: str
    metadata_revision_hash: str
    audience_decision_hash: str
    channel_evidence_hash: str
    channel_receipt_hash: str
    duplicate_evidence_hash: str
    duplicate_receipt_hash: str
    evaluated_at: str
    expected_cost_eur: float
    result: str  # "READY_FOR_PRIVATE_UPLOAD_APPROVAL" or Blocker code
    details: dict[str, Any]

    @property
    def acceptance_hash(self) -> str:
        """Alias for backward compatibility pointing to acceptance_input_hash."""
        return self.acceptance_input_hash

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def create(
        cls,
        *,
        content_id: str,
        publication_fingerprint: str,
        media_sha256: str,
        target_channel_id: str,
        metadata_revision_hash: str,
        audience_decision_hash: str,
        channel_evidence_hash: str,
        channel_receipt_hash: str,
        duplicate_evidence_hash: str,
        duplicate_receipt_hash: str,
        evaluated_at: str,
        expected_cost_eur: float,
        result: str,
        details: dict[str, Any],
        local_publication_state: str = "NOT_SEEN",
        platform: str = "YOUTUBE",
        policy_version: str = ACCEPTANCE_POLICY_VERSION,
        schema_version: str = ACCEPTANCE_SCHEMA_VERSION,
    ) -> AcceptanceResult:
        acceptance_id = f"acc-{uuid.uuid4().hex[:12]}"
        input_hash = compute_acceptance_input_hash(
            content_id=content_id,
            platform=platform,
            target_channel_id=target_channel_id,
            media_sha256=media_sha256,
            publication_fingerprint=publication_fingerprint,
            metadata_revision_hash=metadata_revision_hash,
            audience_decision_hash=audience_decision_hash,
            expected_cost_eur=expected_cost_eur,
            policy_version=policy_version,
            schema_version=schema_version,
        )
        event_hash = compute_acceptance_event_hash(
            acceptance_id=acceptance_id,
            acceptance_input_hash=input_hash,
            evaluated_at=evaluated_at,
            channel_evidence_hash=channel_evidence_hash,
            channel_receipt_hash=channel_receipt_hash,
            duplicate_evidence_hash=duplicate_evidence_hash,
            duplicate_receipt_hash=duplicate_receipt_hash,
            local_publication_state=local_publication_state,
            result=result,
        )
        return cls(
            acceptance_id=acceptance_id,
            acceptance_input_hash=input_hash,
            acceptance_event_hash=event_hash,
            policy_version=policy_version,
            schema_version=schema_version,
            content_id=content_id,
            publication_fingerprint=publication_fingerprint,
            media_sha256=media_sha256,
            target_channel_id=target_channel_id,
            metadata_revision_hash=metadata_revision_hash,
            audience_decision_hash=audience_decision_hash,
            channel_evidence_hash=channel_evidence_hash,
            channel_receipt_hash=channel_receipt_hash,
            duplicate_evidence_hash=duplicate_evidence_hash,
            duplicate_receipt_hash=duplicate_receipt_hash,
            evaluated_at=evaluated_at,
            expected_cost_eur=expected_cost_eur,
            result=result,
            details=details,
        )


class ReleaseAcceptanceGate:
    """Non-authorizing deterministic pre-approval evaluation gate V2.1."""

    def __init__(
        self,
        repo_dir: Path | None = None,
        channel_freshness_seconds: float = CHANNEL_IDENTITY_MAX_AGE_SECONDS,
        duplicate_freshness_seconds: float = DUPLICATE_SNAPSHOT_MAX_AGE_SECONDS,
        allow_test_fixtures: bool = False,
    ):
        self.repo_dir = repo_dir or REPO_ROOT
        self.channel_freshness_seconds = channel_freshness_seconds
        self.duplicate_freshness_seconds = duplicate_freshness_seconds
        self.allow_test_fixtures = allow_test_fixtures
        self.ledger = PublicationLedger(self.repo_dir / "events" / "publications")
        self.approval_ledger = AppendOnlyApprovalLedger(self.repo_dir / "events" / "approvals")
        self.audience_registry = AudienceRegistry(self.repo_dir / "events" / "audience-decisions")

    def evaluate_package(
        self,
        package_path: Path,
        audience_record: AudienceDecisionRecord | None = None,
        evaluated_at: str | None = None,
    ) -> AcceptanceResult:
        """Evaluate package readiness for private upload approval V2.1."""
        now_ts = evaluated_at or _now()
        now_dt = datetime.now(timezone.utc)
        content_id = package_path.parent.name

        # 1. Package File & JSON
        if not package_path.is_file():
            return self._fail_empty(content_id, now_ts, "PACKAGE_INVALID", {"error": f"Package file missing: {package_path}"})

        try:
            pkg = json.loads(package_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            return self._fail_empty(content_id, now_ts, "PACKAGE_INVALID", {"error": str(exc)})

        # Secret Check on package data
        clean, reason = check_for_secrets(pkg)
        if not clean:
            return self._fail_empty(content_id, now_ts, "SECRET_POLICY_FAILURE", {"reason": reason})

        meta_hash = compute_metadata_revision_hash(pkg)

        # 1b. Supported Package Schema (2.2 or 3.0)
        schema_ver = str(pkg.get("schema_version", ""))
        if schema_ver not in {"2.2", "3.0"}:
            return self._fail(content_id, pkg, meta_hash, now_ts, "PACKAGE_SCHEMA_UNSUPPORTED", {
                "schema_version": schema_ver,
                "supported": ["2.2", "3.0"],
            })

        fp = pkg.get("publication_dedupe_fingerprint", "")
        pkg_media_sha = pkg.get("media_sha256") or pkg.get("master_sha256", "")
        target_channel = pkg.get("target_channel_id", "")
        platform = pkg.get("platform") or pkg.get("target_platform", "")

        # 2. Platform & Channel
        if platform != "YOUTUBE":
            return self._fail(content_id, pkg, meta_hash, now_ts, "PLATFORM_MISMATCH", {"platform": platform})

        if target_channel != TARGET_CHANNEL_ID:
            return self._fail(content_id, pkg, meta_hash, now_ts, "TARGET_CHANNEL_MISMATCH", {"target_channel_id": target_channel})

        # 3. Privacy Configuration
        if pkg.get("intended_upload_privacy") != "private" or pkg.get("intended_release_privacy") != "public":
            return self._fail(content_id, pkg, meta_hash, now_ts, "PRIVACY_MISMATCH", {
                "intended_upload_privacy": pkg.get("intended_upload_privacy"),
                "intended_release_privacy": pkg.get("intended_release_privacy"),
            })

        # 4. Publication Authorized state (MUST be strict boolean false before Human approval!)
        if "publication_authorized" not in pkg or not isinstance(pkg["publication_authorized"], bool) or pkg["publication_authorized"] is not False:
            return self._fail(content_id, pkg, meta_hash, now_ts, "PUBLICATION_AUTHORIZATION_STATE_INVALID", {
                "publication_authorized": pkg.get("publication_authorized"),
                "message": "publication_authorized MUST be explicit boolean false before Human approval",
            })

        # 5. Media Master Check
        media_path = Path(pkg.get("media_path") or pkg.get("master_path", ""))
        if not media_path.is_file():
            return self._fail(content_id, pkg, meta_hash, now_ts, "MASTER_HASH_MISMATCH", {"error": "Media file missing"})

        computed_media_sha = _recompute_file_sha256(media_path)
        if computed_media_sha != pkg_media_sha.lower():
            return self._fail(content_id, pkg, meta_hash, now_ts, "MASTER_HASH_MISMATCH", {"computed": computed_media_sha, "pkg": pkg_media_sha})

        # 5b. Immutable Publication Fingerprint validation (supports legacy or V1 canonical)
        computed_fp_legacy = compute_publication_dedupe_fingerprint(
            platform="YOUTUBE",
            target_channel_id=target_channel,
            media_sha256=computed_media_sha,
        )
        from scripts.creator_package_enricher import compute_publication_fingerprint_v1
        computed_fp_v1 = compute_publication_fingerprint_v1("YOUTUBE", target_channel, computed_media_sha)
        if fp.lower() not in (computed_fp_legacy.lower(), computed_fp_v1.lower()):
            return self._fail(content_id, pkg, meta_hash, now_ts, "FINGERPRINT_MISMATCH", {"computed": computed_fp_legacy, "pkg": fp})

        # 6. QC Check
        qc_path = Path(pkg.get("qc_report_path", ""))
        if not qc_path.is_file():
            return self._fail(content_id, pkg, meta_hash, now_ts, "QC_REQUIRED", {"error": "QC report missing"})
        try:
            qc_data = json.loads(qc_path.read_text(encoding="utf-8"))
            qc_source_hash = (
                qc_data.get("source_hash")
                or qc_data.get("media_sha256")
                or qc_data.get("master_sha256")
                or ""
            ).strip().lower()
            if qc_data.get("verdict") != "PASS" or qc_source_hash != computed_media_sha:
                return self._fail(content_id, pkg, meta_hash, now_ts, "QC_REQUIRED", {"qc_verdict": qc_data.get("verdict")})
        except Exception as exc:
            return self._fail(content_id, pkg, meta_hash, now_ts, "QC_REQUIRED", {"error": str(exc)})

        # 7. Durable Audience Decision Authority & Binding
        durable_aud = self.audience_registry.get_decision(content_id) or audience_record

        if not durable_aud:
            return self._fail(content_id, pkg, meta_hash, now_ts, "AUDIENCE_DECISION_REQUIRED", {
                "error": f"No durable AudienceDecisionRecord found for content_id: {content_id}"
            })

        if audience_record:
            if getattr(audience_record, "status", None) == "PREVIEW_ONLY_NOT_DURABLE":
                return self._fail(content_id, pkg, meta_hash, now_ts, "AUDIENCE_DECISION_REQUIRED", {"error": "Preview only"})

            rec_schema = getattr(audience_record, "schema_version", getattr(audience_record, "package_schema", None))
            if rec_schema not in {"1.0", "2.0", "2.2", "3.0"}:
                return self._fail(content_id, pkg, meta_hash, now_ts, "AUDIENCE_DECISION_SCHEMA_MISMATCH", {
                    "record_schema": rec_schema,
                    "expected": "1.0",
                })

            if getattr(audience_record, "decision_source", "") == "TEST_FIXTURE" and not self.allow_test_fixtures:
                return self._fail(content_id, pkg, meta_hash, now_ts, "FIXTURE_AUDIENCE_BLOCKED", {"decision_source": audience_record.decision_source})

            if (
                audience_record.decision_hash != durable_aud.decision_hash
                or audience_record.decision != durable_aud.decision
                or audience_record.content_id != durable_aud.content_id
            ):
                return self._fail(content_id, pkg, meta_hash, now_ts, "AUDIENCE_DECISION_ASSET_MISMATCH", {
                    "error": "Caller-provided audience record does not match durable registry record"
                })

        aud_rec = durable_aud
        if aud_rec.decision not in {"MADE_FOR_KIDS", "NOT_MADE_FOR_KIDS"}:
            return self._fail(content_id, pkg, meta_hash, now_ts, "AUDIENCE_DECISION_REQUIRED", {"decision": aud_rec.decision})

        if (
            aud_rec.content_id != content_id
            or aud_rec.media_sha256.lower() != computed_media_sha.lower()
            or aud_rec.publication_fingerprint.lower() not in (computed_fp_legacy.lower(), computed_fp_v1.lower())
        ):
            return self._fail(content_id, pkg, meta_hash, now_ts, "AUDIENCE_DECISION_ASSET_MISMATCH", {
                "record_content": aud_rec.content_id,
                "expected_content": content_id,
            })

        if getattr(aud_rec, "status", None) == "PREVIEW_ONLY_NOT_DURABLE":
            return self._fail(content_id, pkg, meta_hash, now_ts, "AUDIENCE_DECISION_REQUIRED", {"error": "Preview only"})

        rec_schema = getattr(aud_rec, "schema_version", getattr(aud_rec, "package_schema", None))
        if rec_schema not in {"1.0", "2.0", "2.2"}:
            return self._fail(content_id, pkg, meta_hash, now_ts, "AUDIENCE_DECISION_SCHEMA_MISMATCH", {
                "record_schema": rec_schema,
                "expected": "1.0",
            })

        if getattr(aud_rec, "decision_source", "") == "TEST_FIXTURE" and not self.allow_test_fixtures:
            return self._fail(content_id, pkg, meta_hash, now_ts, "FIXTURE_AUDIENCE_BLOCKED", {"decision_source": aud_rec.decision_source})

        aud_hash = aud_rec.decision_hash

        # 8. Channel Evidence & Provenance Receipt
        ch_ev_rel = Path(pkg.get("channel_evidence_path", ""))
        ch_ev_path = ch_ev_rel if ch_ev_rel.is_absolute() else (self.repo_dir / ch_ev_rel)
        if not ch_ev_path.is_file():
            return self._fail(content_id, pkg, meta_hash, now_ts, "CHANNEL_EVIDENCE_REQUIRED", {"path": str(ch_ev_path)})

        try:
            ch_data = json.loads(ch_ev_path.read_text(encoding="utf-8"))
            computed_ch_payload_hash = compute_payload_hash(ch_data)
            if computed_ch_payload_hash != pkg.get("channel_evidence_hash"):
                return self._fail(content_id, pkg, meta_hash, now_ts, "CHANNEL_EVIDENCE_REQUIRED", {"error": "Hash mismatch"})
            if ch_data.get("channel_id") != target_channel:
                return self._fail(content_id, pkg, meta_hash, now_ts, "TARGET_CHANNEL_MISMATCH", {"evidence_ch": ch_data.get("channel_id")})

            rcpt_id = ch_data.get("authorized_read_receipt_id")
            rcpt_hash = ch_data.get("authorized_read_receipt_hash")
            if not rcpt_id or not rcpt_hash:
                return self._fail(content_id, pkg, meta_hash, now_ts, "CHANNEL_EVIDENCE_PROVENANCE_REQUIRED", {})

            rcpt_path = self.repo_dir / "events" / "receipts" / f"{rcpt_id}.json"
            if not rcpt_path.is_file():
                return self._fail(content_id, pkg, meta_hash, now_ts, "CHANNEL_EVIDENCE_PROVENANCE_REQUIRED", {"error": f"Receipt missing: {rcpt_path}"})

            rcpt_data = json.loads(rcpt_path.read_text(encoding="utf-8"))
            rcpt = ProvenanceReceipt(**rcpt_data)
            if not rcpt.verify_integrity():
                return self._fail(content_id, pkg, meta_hash, now_ts, "CHANNEL_EVIDENCE_PROVENANCE_MISMATCH", {"error": "Receipt integrity invalid"})

            if rcpt.receipt_hash != rcpt_hash or rcpt.payload_evidence_hash != computed_ch_payload_hash:
                return self._fail(content_id, pkg, meta_hash, now_ts, "CHANNEL_EVIDENCE_PROVENANCE_MISMATCH", {"error": "Hash mismatch"})

            # Cross-object reference validation
            if rcpt.authenticated_channel_id != target_channel or rcpt.platform != "YOUTUBE" or rcpt.provider != "GOOGLE_YOUTUBE_API":
                return self._fail(content_id, pkg, meta_hash, now_ts, "CHANNEL_EVIDENCE_PROVENANCE_MISMATCH", {"error": "Provider/platform/channel mismatch"})
            if rcpt.operation != "channels.list" or rcpt.endpoint != "youtube.channels.list":
                return self._fail(content_id, pkg, meta_hash, now_ts, "CHANNEL_EVIDENCE_PROVENANCE_MISMATCH", {"error": "Operation/endpoint mismatch"})
            if rcpt.bundle_id and ch_data.get("bundle_id") and rcpt.bundle_id != ch_data.get("bundle_id"):
                return self._fail(content_id, pkg, meta_hash, now_ts, "CHANNEL_EVIDENCE_PROVENANCE_MISMATCH", {"error": "Bundle mismatch"})

            bundle_id = ch_data.get("bundle_id")
            if not self.allow_test_fixtures:
                if not bundle_id:
                    return self._fail(content_id, pkg, meta_hash, now_ts, "CHANNEL_EVIDENCE_PROVENANCE_REQUIRED", {"error": "Committed bundle_id required in production"})
                bundle_file = self.repo_dir / "events" / "bundles" / f"{bundle_id}.json"
                if not bundle_file.is_file():
                    return self._fail(content_id, pkg, meta_hash, now_ts, "CHANNEL_EVIDENCE_PROVENANCE_REQUIRED", {"error": f"Committed bundle missing: {bundle_id}"})
                try:
                    b_data = json.loads(bundle_file.read_text(encoding="utf-8"))
                    if not b_data.get("committed_by_production_service") or b_data.get("trust_domain") != TrustDomain.AUTHORIZED_PROVIDER_READ_OBSERVED.value:
                        return self._fail(content_id, pkg, meta_hash, now_ts, "CHANNEL_EVIDENCE_PROVENANCE_REQUIRED", {"error": "Bundle not committed by authorized production service"})
                    if b_data.get("payload_evidence_hash") != computed_ch_payload_hash or b_data.get("receipt_hash") != rcpt_hash:
                        return self._fail(content_id, pkg, meta_hash, now_ts, "CHANNEL_EVIDENCE_PROVENANCE_MISMATCH", {"error": "Bundle hash mismatch against channel evidence"})
                except Exception as exc:
                    return self._fail(content_id, pkg, meta_hash, now_ts, "CHANNEL_EVIDENCE_PROVENANCE_REQUIRED", {"error": str(exc)})

            valid_domains = {TrustDomain.AUTHORIZED_PROVIDER_READ_OBSERVED.value}
            if self.allow_test_fixtures:
                valid_domains.add(TrustDomain.TEST_FIXTURE.value)
            if rcpt.trust_domain not in valid_domains:
                return self._fail(content_id, pkg, meta_hash, now_ts, "CHANNEL_EVIDENCE_PROVENANCE_REQUIRED", {"trust_domain": rcpt.trust_domain})

            ch_dt = datetime.fromisoformat(ch_data["retrieved_at"])
            if (now_dt - ch_dt).total_seconds() > self.channel_freshness_seconds:
                return self._fail(content_id, pkg, meta_hash, now_ts, "CHANNEL_EVIDENCE_STALE", {"retrieved_at": ch_data["retrieved_at"]})
        except Exception as exc:
            return self._fail(content_id, pkg, meta_hash, now_ts, "CHANNEL_EVIDENCE_REQUIRED", {"error": str(exc)})

        # 8. Strict Finite-Exact-Zero Cost Validation (Fail Closed on Missing Field)
        if "cost_eur" not in pkg:
            return self._fail(content_id, pkg, meta_hash, now_ts, "PAYMENT_APPROVAL_REQUIRED", {"reason": "MISSING_COST_FIELD"})

        cost_val = pkg["cost_eur"]
        ok_cost, cost_reason = validate_finite_exact_zero(cost_val)
        if not ok_cost:
            return self._fail(content_id, pkg, meta_hash, now_ts, "PAYMENT_APPROVAL_REQUIRED", {"cost": cost_val, "reason": cost_reason})

        # 9. Prior Publication Conflict in Ledger
        curr_ledger_state = self.ledger.get_state(fp)
        if curr_ledger_state in {
            PublicationState.RESERVED,
            PublicationState.UPLOAD_IN_PROGRESS,
            PublicationState.EXTERNAL_OUTCOME_UNCERTAIN,
            PublicationState.UPLOADED_PRIVATE,
            PublicationState.RELEASED_PUBLIC,
        }:
            return self._fail(content_id, pkg, meta_hash, now_ts, "PRIOR_PUBLICATION_CONFLICT", {"state": curr_ledger_state.value})

        # 11. Duplicate Preflight & Snapshot Provenance
        dup_ev_rel = Path(pkg.get("duplicate_preflight_path", ""))
        dup_ev_path = dup_ev_rel if dup_ev_rel.is_absolute() else (self.repo_dir / dup_ev_rel)
        if not dup_ev_path.is_file():
            return self._fail(content_id, pkg, meta_hash, now_ts, "DUPLICATE_CHECK_REQUIRED", {"path": str(dup_ev_path)})

        try:
            dup_data = json.loads(dup_ev_path.read_text(encoding="utf-8"))
            if dup_data.get("publication_fingerprint") != fp or dup_data.get("media_sha256") != computed_media_sha:
                return self._fail(content_id, pkg, meta_hash, now_ts, "DUPLICATE_CHECK_REQUIRED", {"error": "Binding mismatch"})

            snap_path = self.repo_dir / "events" / "evidence" / "youtube_uploads_snapshot_fruitki.json"
            if not snap_path.is_file():
                return self._fail(content_id, pkg, meta_hash, now_ts, "DUPLICATE_CHECK_REQUIRED", {"error": "Upload snapshot missing"})

            snap_data = json.loads(snap_path.read_text(encoding="utf-8"))
            snap_dt = datetime.fromisoformat(snap_data["retrieved_at"])
            if (now_dt - snap_dt).total_seconds() > self.duplicate_freshness_seconds:
                return self._fail(content_id, pkg, meta_hash, now_ts, "DUPLICATE_CHECK_STALE", {"retrieved_at": snap_data["retrieved_at"]})

            snap_rcpt_id = snap_data.get("authorized_read_receipt_id")
            snap_rcpt_hash = snap_data.get("authorized_read_receipt_hash")
            if not snap_rcpt_id or not snap_rcpt_hash:
                return self._fail(content_id, pkg, meta_hash, now_ts, "DUPLICATE_EVIDENCE_PROVENANCE_REQUIRED", {})

            snap_rcpt_path = self.repo_dir / "events" / "receipts" / f"{snap_rcpt_id}.json"
            if not snap_rcpt_path.is_file():
                return self._fail(content_id, pkg, meta_hash, now_ts, "DUPLICATE_EVIDENCE_PROVENANCE_REQUIRED", {"error": "Snapshot receipt missing"})

            snap_rcpt = ProvenanceReceipt(**json.loads(snap_rcpt_path.read_text(encoding="utf-8")))
            if not snap_rcpt.verify_integrity() or snap_rcpt.receipt_hash != snap_rcpt_hash:
                return self._fail(content_id, pkg, meta_hash, now_ts, "DUPLICATE_EVIDENCE_PROVENANCE_MISMATCH", {"error": "Snapshot receipt invalid"})

            if snap_rcpt.trust_domain not in valid_domains:
                return self._fail(content_id, pkg, meta_hash, now_ts, "DUPLICATE_EVIDENCE_PROVENANCE_REQUIRED", {"trust_domain": snap_rcpt.trust_domain})

            computed_snap_payload_hash = compute_payload_hash(snap_data)
            if (
                computed_snap_payload_hash != snap_data.get("payload_evidence_hash")
                or computed_snap_payload_hash != snap_rcpt.payload_evidence_hash
                or computed_snap_payload_hash != dup_data.get("upload_snapshot_hash")
            ):
                return self._fail(content_id, pkg, meta_hash, now_ts, "DUPLICATE_EVIDENCE_PROVENANCE_MISMATCH", {"error": "Snapshot payload hash mismatch"})

            # Cross-object bindings on snapshot receipt
            if snap_rcpt.authenticated_channel_id != target_channel or snap_rcpt.platform != "YOUTUBE" or snap_rcpt.provider != "GOOGLE_YOUTUBE_API":
                return self._fail(content_id, pkg, meta_hash, now_ts, "DUPLICATE_EVIDENCE_PROVENANCE_MISMATCH", {"error": "Snapshot provider/channel mismatch"})
            if snap_rcpt.operation != "playlistItems.list" or snap_rcpt.endpoint != "youtube.playlistItems.list":
                return self._fail(content_id, pkg, meta_hash, now_ts, "DUPLICATE_EVIDENCE_PROVENANCE_MISMATCH", {"error": "Snapshot operation mismatch"})
            if snap_rcpt.bundle_id and snap_data.get("bundle_id") and snap_rcpt.bundle_id != snap_data.get("bundle_id"):
                return self._fail(content_id, pkg, meta_hash, now_ts, "DUPLICATE_EVIDENCE_PROVENANCE_MISMATCH", {"error": "Snapshot bundle mismatch"})

            snap_bundle_id = snap_data.get("bundle_id")
            if not self.allow_test_fixtures:
                if not snap_bundle_id:
                    return self._fail(content_id, pkg, meta_hash, now_ts, "DUPLICATE_EVIDENCE_PROVENANCE_REQUIRED", {"error": "Committed snapshot bundle_id required in production"})
                snap_bundle_file = self.repo_dir / "events" / "bundles" / f"{snap_bundle_id}.json"
                if not snap_bundle_file.is_file():
                    return self._fail(content_id, pkg, meta_hash, now_ts, "DUPLICATE_EVIDENCE_PROVENANCE_REQUIRED", {"error": f"Committed snapshot bundle missing: {snap_bundle_id}"})
                try:
                    sb_data = json.loads(snap_bundle_file.read_text(encoding="utf-8"))
                    if not sb_data.get("committed_by_production_service") or sb_data.get("trust_domain") != TrustDomain.AUTHORIZED_PROVIDER_READ_OBSERVED.value:
                        return self._fail(content_id, pkg, meta_hash, now_ts, "DUPLICATE_EVIDENCE_PROVENANCE_REQUIRED", {"error": "Snapshot bundle not committed by authorized production service"})
                    if sb_data.get("payload_evidence_hash") != computed_snap_payload_hash or sb_data.get("receipt_hash") != snap_rcpt_hash:
                        return self._fail(content_id, pkg, meta_hash, now_ts, "DUPLICATE_EVIDENCE_PROVENANCE_MISMATCH", {"error": "Snapshot bundle hash mismatch"})
                except Exception as exc:
                    return self._fail(content_id, pkg, meta_hash, now_ts, "DUPLICATE_EVIDENCE_PROVENANCE_REQUIRED", {"error": str(exc)})

            if not dup_data.get("coverage_complete", False):
                if dup_data.get("result") == "DUPLICATE_CHECK_INCOMPLETE":
                    return self._fail(content_id, pkg, meta_hash, now_ts, "DUPLICATE_CHECK_INCOMPLETE", {})
                return self._fail(content_id, pkg, meta_hash, now_ts, "PLATFORM_METADATA_CHECK_INCOMPLETE", {})

            # Exact duplicate result rule: ONLY exact string PLATFORM_METADATA_NO_MATCH_FOUND may proceed
            if dup_data.get("result") in {"DUPLICATE_METADATA_MATCH_FOUND", "DUPLICATE_MATCH_FOUND"}:
                return self._fail(content_id, pkg, meta_hash, now_ts, "DUPLICATE_METADATA_MATCH_FOUND", {})
            elif dup_data.get("result") in {"PLATFORM_METADATA_MATCH_FOUND", "MATCHING_PLATFORM_METADATA_FOUND"}:
                return self._fail(content_id, pkg, meta_hash, now_ts, "PLATFORM_METADATA_MATCH_FOUND", {})
            elif dup_data.get("result") != "PLATFORM_METADATA_NO_MATCH_FOUND":
                return self._fail(content_id, pkg, meta_hash, now_ts, "DUPLICATE_CHECK_REQUIRED", {"result": dup_data.get("result")})
        except Exception as exc:
            return self._fail(content_id, pkg, meta_hash, now_ts, "DUPLICATE_CHECK_REQUIRED", {"error": str(exc)})

        # All technical and audience conditions pass -> return READY_FOR_PRIVATE_UPLOAD_APPROVAL
        return AcceptanceResult.create(
            content_id=content_id,
            publication_fingerprint=fp,
            media_sha256=computed_media_sha,
            target_channel_id=target_channel,
            metadata_revision_hash=meta_hash,
            audience_decision_hash=aud_hash,
            channel_evidence_hash=pkg.get("channel_evidence_hash", ""),
            channel_receipt_hash=ch_data.get("authorized_read_receipt_hash", ""),
            duplicate_evidence_hash=dup_data.get("upload_snapshot_hash", ""),
            duplicate_receipt_hash=dup_data.get("upload_snapshot_receipt_hash", ""),
            evaluated_at=now_ts,
            expected_cost_eur=0.0,
            result="READY_FOR_PRIVATE_UPLOAD_APPROVAL",
            local_publication_state=curr_ledger_state.value,
            details={
                "message": "Package passes all technical, schema, provenance, and zero-cost requirements; ready for explicit private upload approval",
                "next_required_step": "Human / Chief issues explicit ApprovalRecord(PRIVATE_UPLOAD)",
            },
        )

    def _fail_empty(self, content_id: str, evaluated_at: str, code: str, details: dict[str, Any]) -> AcceptanceResult:
        return AcceptanceResult.create(
            content_id=content_id,
            publication_fingerprint="",
            media_sha256="",
            target_channel_id="",
            metadata_revision_hash="",
            audience_decision_hash="",
            channel_evidence_hash="",
            channel_receipt_hash="",
            duplicate_evidence_hash="",
            duplicate_receipt_hash="",
            evaluated_at=evaluated_at,
            expected_cost_eur=0.0,
            result=code,
            details=details,
        )

    def _fail(
        self,
        content_id: str,
        pkg: dict[str, Any],
        meta_hash: str,
        evaluated_at: str,
        code: str,
        details: dict[str, Any],
    ) -> AcceptanceResult:
        return AcceptanceResult.create(
            content_id=content_id,
            publication_fingerprint=pkg.get("publication_dedupe_fingerprint", ""),
            media_sha256=pkg.get("media_sha256", ""),
            target_channel_id=pkg.get("target_channel_id", ""),
            metadata_revision_hash=meta_hash,
            audience_decision_hash=pkg.get("audience_decision_hash", ""),
            channel_evidence_hash=pkg.get("channel_evidence_hash", ""),
            channel_receipt_hash="",
            duplicate_evidence_hash="",
            duplicate_receipt_hash="",
            evaluated_at=evaluated_at,
            expected_cost_eur=0.0,
            result=code,
            details=details,
        )
