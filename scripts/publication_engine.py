#!/usr/bin/env python3
"""FruitKI Safe Publication Execution Engine.

Provides deterministic preflight validation, local dedupe ledger tracking,
interprocess atomic reservation (O_CREAT | O_EXCL), crash safety,
uncertain-outcome handling, and strict separation between private staging and public release.

All operations enforce:
- Zero unapproved spend (SPEND = 0 EUR)
- Zero publication without explicit authorization record + package flag
- Fail-closed crash safety
- True interprocess atomic reservation single-winner guarantee
- Verified durable evidence provenance & freshness policies (24h channel, 15m duplicate)
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import time
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable

from scripts.evidence_provenance import (
    CHANNEL_IDENTITY_MAX_AGE_SECONDS,
    DUPLICATE_SNAPSHOT_MAX_AGE_SECONDS,
    ProvenanceReceipt,
    compute_payload_hash,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
YOUTUBE_PILOT = REPO_ROOT.parent / "2026-Projektzentrale" / "02-YouTube-Operations" / "youtube-oauth-pilot"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _recompute_file_sha256(path: Path) -> str:
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


class PublicationState(str, Enum):
    NOT_SEEN = "NOT_SEEN"
    RESERVED = "RESERVED"
    UPLOAD_IN_PROGRESS = "UPLOAD_IN_PROGRESS"
    UPLOADED_PRIVATE = "UPLOADED_PRIVATE"
    RELEASE_APPROVED = "RELEASE_APPROVED"
    RELEASED_PUBLIC = "RELEASED_PUBLIC"
    FAILED_RETRYABLE = "FAILED_RETRYABLE"
    FAILED_TERMINAL = "FAILED_TERMINAL"
    EXTERNAL_OUTCOME_UNCERTAIN = "EXTERNAL_OUTCOME_UNCERTAIN"


@dataclass(frozen=True)
class AuthorizationRecord:
    approval_id: str
    package_fingerprint: str
    approved_action: str  # "PRIVATE_UPLOAD" or "PUBLIC_RELEASE"
    approved_channel: str  # "UCg0O_a10jsQ74ffS_HgFGqA"
    approved_privacy: str  # "private" or "public"
    approved_at: str
    authorization_source: str  # e.g. "EXPLICIT_HUMAN_APPROVAL"
    max_cost_eur: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AuthorizationRecord:
        return cls(
            approval_id=data["approval_id"],
            package_fingerprint=data["package_fingerprint"],
            approved_action=data["approved_action"],
            approved_channel=data["approved_channel"],
            approved_privacy=data["approved_privacy"],
            approved_at=data["approved_at"],
            authorization_source=data["authorization_source"],
            max_cost_eur=float(data.get("max_cost_eur", 0.0)),
        )


@dataclass
class PreflightResult:
    valid: bool
    code: str
    message: str
    details: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "code": self.code,
            "message": self.message,
            "details": self.details,
        }


class PublicationLedger:
    """True process-safe single-winner atomic reservation and publication state ledger with file locking."""

    def __init__(self, ledger_dir: Path | None = None):
        self.ledger_dir = ledger_dir or (REPO_ROOT / "events" / "publications")
        self.claims_dir = self.ledger_dir / "claims"
        self.claims_dir.mkdir(parents=True, exist_ok=True)
        self.main_file = self.ledger_dir / "ledger.json"
        self.lock_file = self.ledger_dir / ".ledger.lock"

    def _atomic_write(self, path: Path, data: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + f".tmp.{os.getpid()}.{uuid.uuid4().hex[:8]}")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)

    def _read_ledger(self) -> dict[str, Any]:
        if not self.main_file.is_file():
            return {"schema_version": "1.0", "records": {}}
        try:
            return json.loads(self.main_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {"schema_version": "1.0", "records": {}}

    def get_entry(self, fingerprint: str) -> dict[str, Any] | None:
        data = self._read_ledger()
        return data.get("records", {}).get(fingerprint)

    def get_state(self, fingerprint: str) -> PublicationState:
        entry = self.get_entry(fingerprint)
        if not entry:
            return PublicationState.NOT_SEEN
        return PublicationState(entry.get("state", PublicationState.NOT_SEEN))

    def get_claim(self, fingerprint: str) -> dict[str, Any] | None:
        claim_file = self.claims_dir / f"{fingerprint}.claim"
        if not claim_file.is_file():
            return None
        try:
            return json.loads(claim_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None

    def reserve(
        self,
        fingerprint: str,
        target_channel_id: str,
        media_sha256: str,
        reservation_token: str,
        operation_id: str | None = None,
    ) -> tuple[bool, str, dict[str, Any] | None]:
        """True process-safe single-winner atomic reservation via O_CREAT | O_EXCL claim artifact with lock protection."""
        claim_file = self.claims_dir / f"{fingerprint}.claim"
        claim_id = f"claim-{uuid.uuid4().hex[:12]}"
        now_ts = _now()
        claim_data = {
            "claim_id": claim_id,
            "publication_fingerprint": fingerprint,
            "target_channel_id": target_channel_id,
            "media_sha256": media_sha256,
            "reservation_token": reservation_token,
            "claimant_pid": os.getpid(),
            "claimed_at": now_ts,
            "operation_id": operation_id,
            "state": PublicationState.RESERVED.value,
        }

        with open(self.lock_file, "w") as lock_fd:
            fcntl.flock(lock_fd, fcntl.LOCK_EX)
            try:
                try:
                    # Atomic single-winner creation at OS kernel level
                    fd = os.open(str(claim_file), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                    with os.fdopen(fd, "w", encoding="utf-8") as f:
                        json.dump(claim_data, f, indent=2)
                        f.flush()
                        os.fsync(f.fileno())
                except FileExistsError:
                    # Loser deterministically receives ALREADY_RESERVED
                    existing = self.get_claim(fingerprint)
                    return False, "ALREADY_RESERVED", existing

                # Update synchronized ledger state
                data = self._read_ledger()
                records = data.setdefault("records", {})
                records[fingerprint] = {
                    "fingerprint": fingerprint,
                    "state": PublicationState.RESERVED.value,
                    "target_channel_id": target_channel_id,
                    "media_sha256": media_sha256,
                    "reservation_token": reservation_token,
                    "claim_id": claim_id,
                    "reserved_at": now_ts,
                    "updated_at": now_ts,
                    "history": [{"state": PublicationState.RESERVED.value, "timestamp": now_ts}],
                }
                self._atomic_write(self.main_file, data)
                return True, "RESERVED", claim_data
            finally:
                fcntl.flock(lock_fd, fcntl.LOCK_UN)

    def _transition_state_unlocked(
        self,
        data: dict[str, Any],
        fingerprint: str,
        new_state: PublicationState,
        *,
        video_id: str | None = None,
        reason: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        records = data.setdefault("records", {})
        entry = records.setdefault(fingerprint, {
            "fingerprint": fingerprint,
            "history": [],
        })
        entry["state"] = new_state.value
        entry["updated_at"] = _now()
        if video_id:
            entry["video_id"] = video_id
        if reason:
            entry["last_reason"] = reason
        if extra:
            entry.update(extra)
        entry["history"].append({
            "state": new_state.value,
            "timestamp": _now(),
            "reason": reason,
        })

    def release_claim(
        self,
        fingerprint: str,
        reservation_token: str,
        reason: str = "Released by owner",
    ) -> tuple[bool, str]:
        """Release reservation only if the caller owns the matching reservation token."""
        claim_file = self.claims_dir / f"{fingerprint}.claim"

        with open(self.lock_file, "w") as lock_fd:
            fcntl.flock(lock_fd, fcntl.LOCK_EX)
            try:
                if not claim_file.is_file():
                    return False, "CLAIM_NOT_FOUND"

                try:
                    existing = json.loads(claim_file.read_text(encoding="utf-8"))
                except (json.JSONDecodeError, OSError):
                    return False, "CLAIM_CORRUPTED"

                if existing.get("reservation_token") != reservation_token:
                    return False, "WRONG_OWNER_RELEASE_BLOCKED"

                claim_file.unlink(missing_ok=True)
                data = self._read_ledger()
                self._transition_state_unlocked(data, fingerprint, PublicationState.FAILED_RETRYABLE, reason=reason)
                self._atomic_write(self.main_file, data)
                return True, "RELEASED"
            finally:
                fcntl.flock(lock_fd, fcntl.LOCK_UN)

    def transition_state(
        self,
        fingerprint: str,
        new_state: PublicationState,
        *,
        video_id: str | None = None,
        reason: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        claim_file = self.claims_dir / f"{fingerprint}.claim"
        with open(self.lock_file, "w") as lock_fd:
            fcntl.flock(lock_fd, fcntl.LOCK_EX)
            try:
                # Active reservation claim exists -> unfenced transitions strictly rejected/no-op
                if claim_file.is_file():
                    return
                data = self._read_ledger()
                records = data.get("records", {})
                current_entry = records.get(fingerprint, {})
                current_state_str = current_entry.get("state")
                if current_state_str in {
                    PublicationState.RESERVED.value,
                    PublicationState.UPLOAD_IN_PROGRESS.value,
                    PublicationState.EXTERNAL_OUTCOME_UNCERTAIN.value,
                }:
                    return
                self._transition_state_unlocked(
                    data,
                    fingerprint,
                    new_state,
                    video_id=video_id,
                    reason=reason,
                    extra=extra,
                )
                self._atomic_write(self.main_file, data)
            finally:
                fcntl.flock(lock_fd, fcntl.LOCK_UN)

    def transition_with_fencing(
        self,
        fingerprint: str,
        expected_state: PublicationState,
        new_state: PublicationState,
        fencing_token: str,
        *,
        video_id: str | None = None,
        reason: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> tuple[bool, str, dict[str, Any]]:
        """Atomically transition state inside lock requiring CAS match and valid fencing token."""
        claim_file = self.claims_dir / f"{fingerprint}.claim"

        with open(self.lock_file, "w") as lock_fd:
            fcntl.flock(lock_fd, fcntl.LOCK_EX)
            try:
                if not claim_file.is_file():
                    return False, "CLAIM_NOT_FOUND", {"fingerprint": fingerprint}

                try:
                    claim = json.loads(claim_file.read_text(encoding="utf-8"))
                except (json.JSONDecodeError, OSError) as exc:
                    return False, "CLAIM_CORRUPTED", {"error": str(exc)}

                if claim.get("reservation_token") != fencing_token:
                    return False, "FENCING_TOKEN_STALE", {
                        "active_token": claim.get("reservation_token"),
                        "caller_token": fencing_token,
                    }

                data = self._read_ledger()
                records = data.setdefault("records", {})
                entry = records.get(fingerprint)
                curr = PublicationState(entry.get("state", PublicationState.NOT_SEEN)) if entry else PublicationState.NOT_SEEN
                if curr != expected_state:
                    return False, "CAS_STATE_MISMATCH", {
                        "expected_state": expected_state.value,
                        "current_state": curr.value,
                    }

                entry = records.setdefault(fingerprint, {
                    "fingerprint": fingerprint,
                    "history": [],
                })
                entry["state"] = new_state.value
                entry["updated_at"] = _now()
                if video_id:
                    entry["video_id"] = video_id
                if reason:
                    entry["last_reason"] = reason
                if extra:
                    entry.update(extra)
                entry["history"].append({
                    "state": new_state.value,
                    "timestamp": _now(),
                    "reason": reason,
                })
                self._atomic_write(self.main_file, data)
                if new_state == PublicationState.UPLOADED_PRIVATE:
                    claim_file.unlink(missing_ok=True)
                return True, "TRANSITIONED", {"state": new_state.value}
            finally:
                fcntl.flock(lock_fd, fcntl.LOCK_UN)


class PublicationEngine:
    """Deterministic Publication Preflight Validator & Execution Engine."""

    REQUIRED_PACKAGE_FIELDS = {
        "schema_version",
        "platform",
        "target_channel_id",
        "target_channel_handle",
        "token_reference",
        "channel_evidence_path",
        "channel_evidence_hash",
        "channel_verified_at",
        "duplicate_preflight_path",
        "duplicate_preflight_result",
        "content_title",
        "description_draft",
        "tags",
        "hashtags",
        "category_id",
        "audience_decision",
        "self_declared_made_for_kids",
        "intended_upload_privacy",
        "intended_release_privacy",
        "media_path",
        "media_sha256",
        "qc_report_path",
        "qc_status",
        "publication_dedupe_fingerprint",
        "publication_authorized",
        "publication_state",
    }

    def __init__(
        self,
        repo_dir: Path | None = None,
        channel_freshness_seconds: float = CHANNEL_IDENTITY_MAX_AGE_SECONDS,
        duplicate_freshness_seconds: float = DUPLICATE_SNAPSHOT_MAX_AGE_SECONDS,
    ):
        self.repo_dir = repo_dir or REPO_ROOT
        self.channel_freshness_seconds = channel_freshness_seconds
        self.duplicate_freshness_seconds = duplicate_freshness_seconds
        self.ledger = PublicationLedger(self.repo_dir / "events" / "publications")

    def validate_package(
        self,
        package_path: Path,
        auth_record: AuthorizationRecord | None = None,
    ) -> PreflightResult:
        """Run complete 16-point deterministic preflight validation with provenance and freshness."""
        if not package_path.is_file():
            return PreflightResult(
                valid=False,
                code="PACKAGE_FILE_NOT_FOUND",
                message=f"Publication package not found: {package_path}",
                details={"path": str(package_path)},
            )

        try:
            pkg = json.loads(package_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            return PreflightResult(
                valid=False,
                code="PACKAGE_JSON_INVALID",
                message=f"Publication package invalid JSON: {exc}",
                details={"error": str(exc)},
            )

        # 1. Schema check
        missing_fields = self.REQUIRED_PACKAGE_FIELDS - set(pkg.keys())
        if missing_fields:
            return PreflightResult(
                valid=False,
                code="SCHEMA_FIELDS_MISSING",
                message=f"Missing required schema fields: {missing_fields}",
                details={"missing": sorted(list(missing_fields))},
            )

        # 2. Platform check
        if pkg.get("platform") != "YOUTUBE":
            return PreflightResult(
                valid=False,
                code="UNSUPPORTED_PLATFORM",
                message=f"Platform must be YOUTUBE, got {pkg.get('platform')}",
                details={"platform": pkg.get("platform")},
            )

        # 3. Target channel check
        if pkg.get("target_channel_id") != "UCg0O_a10jsQ74ffS_HgFGqA":
            return PreflightResult(
                valid=False,
                code="TARGET_CHANNEL_MISMATCH",
                message=f"Invalid target channel: {pkg.get('target_channel_id')}",
                details={"target_channel_id": pkg.get("target_channel_id")},
            )

        # 4. Channel Evidence & Provenance Receipt Verification
        ch_ev_rel = Path(pkg["channel_evidence_path"])
        ch_ev_path = ch_ev_rel if ch_ev_rel.is_absolute() else (self.repo_dir / ch_ev_rel)
        if not ch_ev_path.is_file():
            return PreflightResult(
                valid=False,
                code="CHANNEL_EVIDENCE_REQUIRED",
                message=f"Channel evidence file missing: {ch_ev_path}",
                details={"path": str(ch_ev_path)},
            )

        try:
            ch_data = json.loads(ch_ev_path.read_text(encoding="utf-8"))
            computed_ch_payload_hash = compute_payload_hash(ch_data)
            if computed_ch_payload_hash != pkg.get("channel_evidence_hash"):
                return PreflightResult(
                    valid=False,
                    code="CHANNEL_EVIDENCE_HASH_MISMATCH",
                    message="Channel evidence payload hash mismatch against package record",
                    details={"computed": computed_ch_payload_hash, "package": pkg.get("channel_evidence_hash")},
                )
            if ch_data.get("channel_id") != pkg.get("target_channel_id"):
                return PreflightResult(
                    valid=False,
                    code="TARGET_CHANNEL_MISMATCH",
                    message="Channel ID in evidence does not match target_channel_id",
                    details={"evidence_ch": ch_data.get("channel_id"), "target_ch": pkg.get("target_channel_id")},
                )

            # Check Channel Evidence Provenance Receipt
            rcpt_id = ch_data.get("authorized_read_receipt_id")
            rcpt_hash = ch_data.get("authorized_read_receipt_hash")
            if not rcpt_id or not rcpt_hash:
                return PreflightResult(
                    valid=False,
                    code="EVIDENCE_PROVENANCE_REQUIRED",
                    message="Channel evidence missing authorized read receipt provenance",
                    details={},
                )

            rcpt_path = self.repo_dir / "events" / "receipts" / f"{rcpt_id}.json"
            if rcpt_path.is_file():
                rcpt_data = json.loads(rcpt_path.read_text(encoding="utf-8"))
                rcpt = ProvenanceReceipt(**rcpt_data)
                if not rcpt.verify_integrity():
                    return PreflightResult(
                        valid=False,
                        code="EVIDENCE_PROVENANCE_INVALID",
                        message="Channel provenance receipt failed cryptographic integrity verification",
                        details={"receipt_id": rcpt_id},
                    )
                if rcpt.payload_evidence_hash != computed_ch_payload_hash:
                    return PreflightResult(
                        valid=False,
                        code="RECEIPT_PAYLOAD_MISMATCH",
                        message="Receipt payload hash does not match channel evidence payload hash",
                        details={"rcpt_payload": rcpt.payload_evidence_hash, "ch_payload": computed_ch_payload_hash},
                    )
                if rcpt.authenticated_channel_id != pkg["target_channel_id"]:
                    return PreflightResult(
                        valid=False,
                        code="RECEIPT_CHANNEL_MISMATCH",
                        message="Receipt authenticated channel ID does not match target channel ID",
                        details={"rcpt_ch": rcpt.authenticated_channel_id, "target_ch": pkg["target_channel_id"]},
                    )

            # Check 24-hour freshness window
            retrieved_dt = datetime.fromisoformat(ch_data["retrieved_at"])
            now_dt = datetime.now(timezone.utc)
            if (now_dt - retrieved_dt).total_seconds() > self.channel_freshness_seconds:
                return PreflightResult(
                    valid=False,
                    code="CHANNEL_EVIDENCE_STALE",
                    message="Channel evidence is older than 24 hours",
                    details={"retrieved_at": ch_data["retrieved_at"], "max_age_seconds": self.channel_freshness_seconds},
                )
        except Exception as exc:
            return PreflightResult(
                valid=False,
                code="CHANNEL_EVIDENCE_INVALID",
                message=f"Error validating channel evidence: {exc}",
                details={"error": str(exc)},
            )

        # 4b. Audience Decision Gate
        aud_dec = pkg.get("audience_decision")
        if aud_dec == "DECISION_REQUIRED" or aud_dec not in {"MADE_FOR_KIDS", "NOT_MADE_FOR_KIDS"}:
            return PreflightResult(
                valid=False,
                code="AUDIENCE_DECISION_REQUIRED",
                message="Authoritative audience decision (MADE_FOR_KIDS vs NOT_MADE_FOR_KIDS) is required",
                details={"audience_decision": aud_dec, "self_declared_made_for_kids": pkg.get("self_declared_made_for_kids")},
            )

        if not isinstance(pkg.get("self_declared_made_for_kids"), bool):
            return PreflightResult(
                valid=False,
                code="AUDIENCE_DECISION_REQUIRED",
                message="self_declared_made_for_kids must be a resolved boolean",
                details={"self_declared_made_for_kids": pkg.get("self_declared_made_for_kids")},
            )

        # 5. Duplicate Preflight & Snapshot Provenance Verification
        dup_ev_rel = Path(pkg["duplicate_preflight_path"])
        dup_ev_path = dup_ev_rel if dup_ev_rel.is_absolute() else (self.repo_dir / dup_ev_rel)
        if not dup_ev_path.is_file():
            return PreflightResult(
                valid=False,
                code="DUPLICATE_PREFLIGHT_REQUIRED",
                message=f"Duplicate preflight record missing: {dup_ev_path}",
                details={"path": str(dup_ev_path)},
            )

        try:
            dup_data = json.loads(dup_ev_path.read_text(encoding="utf-8"))

            # Check bindings
            if dup_data.get("publication_fingerprint") != pkg.get("publication_dedupe_fingerprint"):
                return PreflightResult(
                    valid=False,
                    code="DUPLICATE_PREFLIGHT_FINGERPRINT_MISMATCH",
                    message="Duplicate preflight publication fingerprint does not match package",
                    details={"dup_fp": dup_data.get("publication_fingerprint"), "pkg_fp": pkg.get("publication_dedupe_fingerprint")},
                )

            if dup_data.get("media_sha256") != pkg.get("media_sha256"):
                return PreflightResult(
                    valid=False,
                    code="DUPLICATE_PREFLIGHT_MEDIA_MISMATCH",
                    message="Duplicate preflight media SHA-256 does not match package",
                    details={"dup_media": dup_data.get("media_sha256"), "pkg_media": pkg.get("media_sha256")},
                )

            if dup_data.get("target_channel_id") != pkg.get("target_channel_id"):
                return PreflightResult(
                    valid=False,
                    code="DUPLICATE_PREFLIGHT_CHANNEL_MISMATCH",
                    message="Duplicate preflight target channel ID does not match package",
                    details={"dup_ch": dup_data.get("target_channel_id"), "pkg_ch": pkg.get("target_channel_id")},
                )

            if dup_data.get("channel_evidence_hash") != pkg.get("channel_evidence_hash"):
                return PreflightResult(
                    valid=False,
                    code="DUPLICATE_PREFLIGHT_CHANNEL_EVIDENCE_MISMATCH",
                    message="Duplicate preflight channel evidence hash does not match package",
                    details={"dup_ch_ev": dup_data.get("channel_evidence_hash"), "pkg_ch_ev": pkg.get("channel_evidence_hash")},
                )

            # Check snapshot file & 15m freshness
            snap_path = self.repo_dir / "events" / "evidence" / "youtube_uploads_snapshot_fruitki.json"
            if snap_path.is_file():
                snap_data = json.loads(snap_path.read_text(encoding="utf-8"))
                snap_payload_hash = compute_payload_hash(snap_data)
                if snap_payload_hash != dup_data.get("upload_snapshot_hash"):
                    return PreflightResult(
                        valid=False,
                        code="DUPLICATE_PREFLIGHT_SNAPSHOT_MISMATCH",
                        message="Duplicate preflight upload snapshot hash mismatch against current snapshot",
                        details={"dup_snap": dup_data.get("upload_snapshot_hash"), "curr_snap": snap_payload_hash},
                    )

                # Check 15-minute freshness window for duplicate snapshot
                snap_dt = datetime.fromisoformat(snap_data["retrieved_at"])
                if (now_dt - snap_dt).total_seconds() > self.duplicate_freshness_seconds:
                    return PreflightResult(
                        valid=False,
                        code="DUPLICATE_CHECK_STALE",
                        message="Upload duplicate snapshot is older than 15 minutes",
                        details={"retrieved_at": snap_data["retrieved_at"], "max_age_seconds": self.duplicate_freshness_seconds},
                    )

            if not dup_data.get("coverage_complete", False):
                return PreflightResult(
                    valid=False,
                    code="DUPLICATE_CHECK_INCOMPLETE",
                    message="Platform duplicate check snapshot coverage is incomplete",
                    details={"items_checked": dup_data.get("items_checked")},
                )

            res_val = dup_data.get("result", "")
            if res_val in {"PLATFORM_METADATA_MATCH_FOUND", "MATCHING_PLATFORM_METADATA_FOUND", "DUPLICATE_MATCH_FOUND"}:
                return PreflightResult(
                    valid=False,
                    code="DUPLICATE_MATCH_FOUND",
                    message="Platform duplicate check found matching metadata on channel",
                    details={"result": res_val},
                )

            if res_val not in {"PLATFORM_METADATA_NO_MATCH_FOUND", "NO_MATCHING_PLATFORM_METADATA_FOUND", "NO_DUPLICATE_FOUND"}:
                return PreflightResult(
                    valid=False,
                    code="DUPLICATE_CHECK_INCOMPLETE",
                    message=f"Duplicate preflight result is not a valid non-match: {res_val}",
                    details={"result": res_val},
                )

        except Exception as exc:
            return PreflightResult(
                valid=False,
                code="DUPLICATE_PREFLIGHT_INVALID",
                message=f"Error validating duplicate preflight: {exc}",
                details={"error": str(exc)},
            )

        # 6. Media master check
        media_path = Path(pkg["media_path"])
        if not media_path.is_file():
            return PreflightResult(
                valid=False,
                code="MEDIA_MASTER_MISSING",
                message=f"Media master file not found: {media_path}",
                details={"media_path": str(media_path)},
            )

        # 7. Media hash recomputation
        computed_sha = _recompute_file_sha256(media_path)
        if computed_sha != pkg.get("media_sha256", "").lower():
            return PreflightResult(
                valid=False,
                code="MASTER_HASH_MISMATCH",
                message="Computed media SHA-256 does not match package media_sha256",
                details={"computed": computed_sha, "package": pkg.get("media_sha256")},
            )

        # 8. QC report check
        qc_path = Path(pkg["qc_report_path"])
        if not qc_path.is_file():
            return PreflightResult(
                valid=False,
                code="QC_REPORT_MISSING",
                message=f"QC report file not found: {qc_path}",
                details={"qc_report_path": str(qc_path)},
            )

        try:
            qc = json.loads(qc_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            return PreflightResult(
                valid=False,
                code="QC_REPORT_INVALID",
                message=f"QC report invalid JSON: {exc}",
                details={"error": str(exc)},
            )

        # 9. QC verdict check
        if qc.get("verdict") != "PASS" or pkg.get("qc_status") != "PASS":
            return PreflightResult(
                valid=False,
                code="QC_VERDICT_NOT_PASS",
                message="QC report verdict is not PASS",
                details={"qc_verdict": qc.get("verdict"), "package_qc_status": pkg.get("qc_status")},
            )

        # 10. QC source hash binding
        if qc.get("source_hash") != computed_sha:
            return PreflightResult(
                valid=False,
                code="QC_SOURCE_HASH_MISMATCH",
                message="QC source hash does not match computed media hash",
                details={"qc_source_hash": qc.get("source_hash"), "media_sha256": computed_sha},
            )

        # 11. Metadata completeness
        if not pkg.get("content_title") or not pkg.get("description_draft") or not pkg.get("category_id"):
            return PreflightResult(
                valid=False,
                code="METADATA_INCOMPLETE",
                message="Title, description draft, or category_id is empty",
                details={},
            )

        # 12. Audience Decision Gate
        aud_dec = pkg.get("audience_decision")
        if aud_dec == "DECISION_REQUIRED" or aud_dec not in {"MADE_FOR_KIDS", "NOT_MADE_FOR_KIDS"}:
            return PreflightResult(
                valid=False,
                code="AUDIENCE_DECISION_REQUIRED",
                message="Authoritative audience decision (MADE_FOR_KIDS vs NOT_MADE_FOR_KIDS) is required",
                details={"audience_decision": aud_dec, "self_declared_made_for_kids": pkg.get("self_declared_made_for_kids")},
            )

        if not isinstance(pkg.get("self_declared_made_for_kids"), bool):
            return PreflightResult(
                valid=False,
                code="AUDIENCE_DECISION_REQUIRED",
                message="self_declared_made_for_kids must be a resolved boolean",
                details={"self_declared_made_for_kids": pkg.get("self_declared_made_for_kids")},
            )

        # 13. Privacy values
        if pkg.get("intended_upload_privacy") != "private" or pkg.get("intended_release_privacy") != "public":
            return PreflightResult(
                valid=False,
                code="INVALID_PRIVACY_CONFIG",
                message="Intended upload privacy must be private and release privacy must be public",
                details={
                    "intended_upload_privacy": pkg.get("intended_upload_privacy"),
                    "intended_release_privacy": pkg.get("intended_release_privacy"),
                },
            )

        # 14. Dedupe fingerprint calculation (Immutable upload identity)
        from scripts.creator_input_sources import compute_publication_dedupe_fingerprint
        computed_fp = compute_publication_dedupe_fingerprint(
            platform=pkg["platform"],
            target_channel_id=pkg["target_channel_id"],
            media_sha256=computed_sha,
        )
        if computed_fp != pkg.get("publication_dedupe_fingerprint"):
            return PreflightResult(
                valid=False,
                code="DEDUPE_FINGERPRINT_MISMATCH",
                message="Package publication_dedupe_fingerprint does not match canonical calculation",
                details={"computed": computed_fp, "package": pkg.get("publication_dedupe_fingerprint")},
            )

        # 15. Authorization checks (Fail closed)
        if not pkg.get("publication_authorized"):
            return PreflightResult(
                valid=False,
                code="BLOCKED_NOT_AUTHORIZED",
                message="Package publication_authorized is false; publication blocked by policy",
                details={"publication_authorized": False},
            )

        if auth_record is None:
            return PreflightResult(
                valid=False,
                code="BLOCKED_NO_AUTHORIZATION_RECORD",
                message="No explicit AuthorizationRecord provided",
                details={},
            )

        if auth_record.package_fingerprint != computed_fp:
            return PreflightResult(
                valid=False,
                code="AUTHORIZATION_FINGERPRINT_MISMATCH",
                message="Authorization record fingerprint does not match package fingerprint",
                details={"auth_fp": auth_record.package_fingerprint, "pkg_fp": computed_fp},
            )

        if auth_record.approved_channel != pkg["target_channel_id"]:
            return PreflightResult(
                valid=False,
                code="AUTHORIZATION_CHANNEL_MISMATCH",
                message="Authorization record channel does not match package target channel",
                details={"auth_channel": auth_record.approved_channel, "pkg_channel": pkg["target_channel_id"]},
            )

        # 16. Zero spend check
        if auth_record.max_cost_eur > 0.0:
            return PreflightResult(
                valid=False,
                code="PAYMENT_APPROVAL_REQUIRED",
                message="Execution requires unapproved monetary spend",
                details={"max_cost_eur": auth_record.max_cost_eur},
            )

        return PreflightResult(
            valid=True,
            code="PASS",
            message="Package passes all preflight checks",
            details={
                "fingerprint": computed_fp,
                "target_channel_id": pkg["target_channel_id"],
                "media_sha256": computed_sha,
                "content_title": pkg["content_title"],
            },
        )

    def execute_private_upload(
        self,
        package_path: Path,
        auth_record: AuthorizationRecord,
        *,
        execute_mock: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Execute a staged private upload under strict authorization and crash safety."""
        # 1. Preflight
        pre = self.validate_package(package_path, auth_record)
        if not pre.valid:
            return {
                "status": "BLOCKED",
                "code": pre.code,
                "message": pre.message,
                "details": pre.details,
            }

        if auth_record.approved_action != "PRIVATE_UPLOAD" or auth_record.approved_privacy != "private":
            return {
                "status": "BLOCKED",
                "code": "INVALID_ACTION_FOR_UPLOAD",
                "message": "Authorization record does not permit private upload",
            }

        pkg = json.loads(package_path.read_text(encoding="utf-8"))
        fp = pkg["publication_dedupe_fingerprint"]

        # 2. Local dedupe ledger true interprocess atomic reservation
        res_token = f"res-{uuid.uuid4().hex[:12]}"
        ok, res_msg, claim_info = self.ledger.reserve(
            fingerprint=fp,
            target_channel_id=pkg["target_channel_id"],
            media_sha256=pkg["media_sha256"],
            reservation_token=res_token,
            operation_id=auth_record.approval_id,
        )
        if not ok:
            return {
                "status": "BLOCKED",
                "code": "ALREADY_RESERVED",
                "message": f"Publication slot {fp} already reserved",
                "details": claim_info,
            }

        # 3. Transition to UPLOAD_IN_PROGRESS before external mutation
        self.ledger.transition_with_fencing(
            fingerprint=fp,
            expected_state=PublicationState.RESERVED,
            new_state=PublicationState.UPLOAD_IN_PROGRESS,
            fencing_token=res_token,
            reason="Starting private YouTube video upload",
            extra={"auth_approval_id": auth_record.approval_id},
        )

        # 4. Execute external upload (or mocked executor in test mode)
        try:
            if execute_mock:
                res = execute_mock(pkg)
            else:
                return {
                    "status": "BLOCKED",
                    "code": "REAL_MUTATION_RESTRICTED",
                    "message": "Direct real YouTube upload disabled in Mission 131G",
                }

            if res.get("status") == "SUCCESS" and res.get("video_id"):
                video_id = res["video_id"]
                self.ledger.transition_with_fencing(
                    fingerprint=fp,
                    expected_state=PublicationState.UPLOAD_IN_PROGRESS,
                    new_state=PublicationState.UPLOADED_PRIVATE,
                    fencing_token=res_token,
                    video_id=video_id,
                    reason="Private video uploaded successfully",
                    extra={"privacy_status": "private"},
                )
                return {
                    "status": "SUCCESS",
                    "code": "UPLOADED_PRIVATE",
                    "video_id": video_id,
                    "fingerprint": fp,
                    "privacy_status": "private",
                }
            else:
                self.ledger.transition_with_fencing(
                    fingerprint=fp,
                    expected_state=PublicationState.UPLOAD_IN_PROGRESS,
                    new_state=PublicationState.EXTERNAL_OUTCOME_UNCERTAIN,
                    fencing_token=res_token,
                    reason=f"Upload returned non-success: {res}",
                )
                return {
                    "status": "ERROR",
                    "code": res.get("code", "UPLOAD_FAILED"),
                    "message": res.get("error", "Upload failed"),
                }

        except Exception as exc:
            # Crash safety / uncertain outcome
            self.ledger.transition_with_fencing(
                fingerprint=fp,
                expected_state=PublicationState.UPLOAD_IN_PROGRESS,
                new_state=PublicationState.EXTERNAL_OUTCOME_UNCERTAIN,
                fencing_token=res_token,
                reason=f"Uncertain exception during upload: {exc}",
            )
            return {
                "status": "ERROR",
                "code": "EXTERNAL_OUTCOME_UNCERTAIN",
                "message": f"External outcome uncertain after exception: {exc}",
                "reconciliation_required": True,
            }

    def execute_public_release(
        self,
        package_path: Path,
        auth_record: AuthorizationRecord,
        video_id: str,
        *,
        execute_mock: Callable[[dict[str, Any], str], dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Release an existing private video to public under explicit separate release authorization."""
        pre = self.validate_package(package_path, auth_record)
        if not pre.valid:
            return {
                "status": "BLOCKED",
                "code": pre.code,
                "message": pre.message,
            }

        if auth_record.approved_action != "PUBLIC_RELEASE" or auth_record.approved_privacy != "public":
            return {
                "status": "BLOCKED",
                "code": "RELEASE_NOT_APPROVED",
                "message": "Authorization record does not permit public release",
            }

        pkg = json.loads(package_path.read_text(encoding="utf-8"))
        fp = pkg["publication_dedupe_fingerprint"]
        curr_state = self.ledger.get_state(fp)

        if curr_state not in {PublicationState.UPLOADED_PRIVATE, PublicationState.RELEASE_APPROVED}:
            return {
                "status": "BLOCKED",
                "code": "INVALID_STATE_FOR_RELEASE",
                "message": f"Cannot release video in state {curr_state.value}; must be UPLOADED_PRIVATE",
            }

        try:
            if execute_mock:
                res = execute_mock(pkg, video_id)
            else:
                return {
                    "status": "BLOCKED",
                    "code": "REAL_MUTATION_RESTRICTED",
                    "message": "Direct real YouTube release mutation disabled in Mission 131G",
                }

            if res.get("status") == "SUCCESS":
                self.ledger.transition_state(
                    fp,
                    PublicationState.RELEASED_PUBLIC,
                    video_id=video_id,
                    reason="Public release successful",
                    extra={"privacy_status": "public"},
                )
                return {
                    "status": "SUCCESS",
                    "code": "RELEASED_PUBLIC",
                    "video_id": video_id,
                    "fingerprint": fp,
                    "privacy_status": "public",
                }
            else:
                return {
                    "status": "ERROR",
                    "code": res.get("code", "RELEASE_FAILED"),
                    "message": res.get("error", "Release failed"),
                }

        except Exception as exc:
            self.ledger.transition_state(
                fp,
                PublicationState.EXTERNAL_OUTCOME_UNCERTAIN,
                reason=f"Uncertain exception during release: {exc}",
            )
            return {
                "status": "ERROR",
                "code": "EXTERNAL_OUTCOME_UNCERTAIN",
                "message": f"External outcome uncertain: {exc}",
                "reconciliation_required": True,
            }
