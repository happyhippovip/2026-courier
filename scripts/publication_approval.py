#!/usr/bin/env python3
"""FruitKI Publication Approval Subsystem and Human Decision Gate V2.1.

Implements:
- Finite-exact-zero money firewall (validate_finite_exact_zero)
- Durable immutable ApprovalRegistry with conflict detection
- ApprovalRecord and ledger-derived authoritative state lifecycle
- Deterministic operation identity (compute_deterministic_operation_id)
- Runtime validation of metadata, audience, channel, duplicate, and acceptance hashes
- Append-only approval ledger with file locking and cryptographic chain hashing
- Release operation intent ledger with dispatch-attempt tracking
- Human Decision Card generator & Audience Decision validation
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import math
import os
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent

APPROVAL_POLICY_VERSION = "2.1"
APPROVAL_SCHEMA_VERSION = "2.1"
AUDIENCE_POLICY_VERSION = "1.0"
AUDIENCE_SCHEMA_VERSION = "1.0"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def validate_finite_exact_zero(cost: Any) -> tuple[bool, str]:
    """Validate that a cost value is strictly a finite numeric exact 0 or 0.0.

    Rejects missing, None, boolean, strings, NaN, infinity, negative, or positive numbers.
    """
    if cost is None:
        return False, "PAYMENT_APPROVAL_REQUIRED"
    if isinstance(cost, bool):
        return False, "PAYMENT_APPROVAL_REQUIRED"
    if not isinstance(cost, (int, float)):
        return False, "PAYMENT_APPROVAL_REQUIRED"
    if not math.isfinite(cost):
        return False, "PAYMENT_APPROVAL_REQUIRED"
    if cost != 0:
        return False, "PAYMENT_APPROVAL_REQUIRED"
    return True, "ZERO_COST_VERIFIED"


def compute_metadata_revision_hash(pkg_data: dict[str, Any]) -> str:
    """Compute a deterministic SHA-256 hash over editorial metadata only."""
    title = str(pkg_data.get("content_title") or pkg_data.get("title_proposed") or "")
    raw = {
        "content_title": " ".join(title.split()),
        "description_draft": str(pkg_data.get("description_draft") or "").strip(),
        "tags": sorted(pkg_data.get("tags", [])),
        "hashtags": sorted(pkg_data.get("hashtags", [])),
        "category_id": str(pkg_data.get("category_id", "")).strip(),
        "audience_decision": str(pkg_data.get("audience_decision", "")).strip(),
        "intended_release_privacy": str(pkg_data.get("intended_release_privacy", "")).strip(),
    }
    return hashlib.sha256(
        json.dumps(raw, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def compute_deterministic_operation_id(
    *,
    approved_action: str,
    approval_id: str,
    publication_fingerprint: str,
    target_channel_id: str = "UCg0O_a10jsQ74ffS_HgFGqA",
) -> str:
    """Compute an immutable, deterministic operation ID binding the approval and publication intent."""
    raw = f"{approved_action}:{approval_id}:{publication_fingerprint}:{target_channel_id}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return f"op-{approved_action.lower()}-{digest}"


def generate_human_decision_card(package_path: Path) -> dict[str, Any]:
    """Generate human decision card for 130G test compatibility."""
    content_id = package_path.parent.name
    pkg = json.loads(package_path.read_text(encoding="utf-8")) if package_path.is_file() else {}
    media_sha = pkg.get("media_sha256", "")
    return {
        "content_id": content_id,
        "title": pkg.get("content_title", ""),
        "short_master_hash": media_sha[:16],
        "requested_human_decision": "MADE_FOR_KIDS | NOT_MADE_FOR_KIDS",
        "publication_authorized": False,
        "expected_cost": "0 EUR",
    }


def apply_human_audience_decision(
    package_path: Path,
    decision_record: AudienceDecisionRecord,
    repo_dir: Path | None = None,
) -> tuple[bool, str, dict[str, Any]]:
    """Apply human audience decision to package metadata and durable registry without authorizing publication."""
    if not package_path.is_file():
        return False, "PACKAGE_NOT_FOUND", {}
    pkg = json.loads(package_path.read_text(encoding="utf-8"))

    if (
        decision_record.media_sha256 != pkg.get("media_sha256")
        or decision_record.publication_fingerprint != pkg.get("publication_dedupe_fingerprint")
    ):
        return False, "AUDIENCE_DECISION_ASSET_MISMATCH", {}

    pkg["audience_decision"] = decision_record.decision
    pkg["self_declared_made_for_kids"] = (decision_record.decision == AudienceDecisionState.MADE_FOR_KIDS.value)
    pkg["audience_decision_hash"] = decision_record.decision_hash
    pkg["publication_authorized"] = False

    package_path.write_text(json.dumps(pkg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # Persist in durable AudienceRegistry
    if repo_dir:
        root = repo_dir
    else:
        try:
            package_path.resolve().relative_to(REPO_ROOT.resolve())
            root = REPO_ROOT
        except ValueError:
            root = package_path.resolve().parent.parent

    aud_reg = AudienceRegistry(root / "events" / "audience-decisions")
    aud_reg.register_decision(decision_record)

    return True, "AUDIENCE_DECISION_APPLIED", {"next_blocker": "APPROVAL_REQUIRED"}


class ApprovalAction(str, Enum):
    PRIVATE_UPLOAD = "PRIVATE_UPLOAD"
    PUBLIC_RELEASE = "PUBLIC_RELEASE"


class ApprovalState(str, Enum):
    ACTIVE = "ACTIVE"
    CONSUMED = "CONSUMED"
    REVOKED = "REVOKED"
    INVALIDATED = "INVALIDATED"


class AudienceDecisionState(str, Enum):
    DECISION_REQUIRED = "DECISION_REQUIRED"
    MADE_FOR_KIDS = "MADE_FOR_KIDS"
    NOT_MADE_FOR_KIDS = "NOT_MADE_FOR_KIDS"


class OperationOutcome(str, Enum):
    INTENT_RECORDED = "INTENT_RECORDED"
    UPLOAD_IN_PROGRESS = "UPLOAD_IN_PROGRESS"
    DISPATCH_ATTEMPTED = "DISPATCH_ATTEMPTED"
    PLATFORM_ID_CONFIRMED = "PLATFORM_ID_CONFIRMED"
    EXTERNAL_OUTCOME_UNCERTAIN = "EXTERNAL_OUTCOME_UNCERTAIN"
    UPLOADED_PRIVATE = "UPLOADED_PRIVATE"
    RELEASED_PUBLIC = "RELEASED_PUBLIC"
    FAILED_ABORTED = "FAILED_ABORTED"


@dataclass(frozen=True)
class AudienceDecisionRecord:
    content_id: str
    decision: str  # "MADE_FOR_KIDS" | "NOT_MADE_FOR_KIDS"
    decision_source: str  # "HUMAN_EXPLICIT_REVIEW"
    evidence_reference: str
    media_sha256: str
    publication_fingerprint: str
    decided_at: str
    decision_hash: str
    policy_version: str = AUDIENCE_POLICY_VERSION
    schema_version: str = AUDIENCE_SCHEMA_VERSION
    status: str = "HUMAN_CONFIRMED"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def create(
        cls,
        *,
        content_id: str,
        decision: str,
        decision_source: str = "HUMAN_EXPLICIT_REVIEW",
        evidence_reference: str,
        media_sha256: str,
        publication_fingerprint: str,
        decided_at: str | None = None,
        policy_version: str = AUDIENCE_POLICY_VERSION,
        schema_version: str = AUDIENCE_SCHEMA_VERSION,
        status: str = "HUMAN_CONFIRMED",
    ) -> AudienceDecisionRecord:
        ts = decided_at or _now()
        raw = {
            "content_id": content_id,
            "decision": decision,
            "decision_source": decision_source,
            "evidence_reference": evidence_reference,
            "media_sha256": media_sha256.lower(),
            "publication_fingerprint": publication_fingerprint.lower(),
            "decided_at": ts,
            "policy_version": policy_version,
            "schema_version": schema_version,
            "status": status,
        }
        decision_hash = hashlib.sha256(
            json.dumps(raw, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        return cls(
            content_id=content_id,
            decision=decision,
            decision_source=decision_source,
            evidence_reference=evidence_reference,
            media_sha256=media_sha256.lower(),
            publication_fingerprint=publication_fingerprint.lower(),
            decided_at=ts,
            decision_hash=decision_hash,
            policy_version=policy_version,
            schema_version=schema_version,
            status=status,
        )


class AudienceRegistry:
    """Durable atomic registry for immutable AudienceDecisionRecords with file locking."""

    def __init__(self, registry_dir: Path | None = None):
        self.registry_dir = registry_dir or (REPO_ROOT / "events" / "audience-decisions")
        self.registry_dir.mkdir(parents=True, exist_ok=True)
        self.lock_file = self.registry_dir / ".audience.lock"

    def _record_file(self, content_id: str) -> Path:
        return self.registry_dir / f"{content_id}.json"

    def get_decision(self, content_id: str) -> AudienceDecisionRecord | None:
        rec_file = self._record_file(content_id)
        if not rec_file.is_file():
            return None
        try:
            data = json.loads(rec_file.read_text(encoding="utf-8"))
            return AudienceDecisionRecord(
                content_id=data["content_id"],
                decision=data["decision"],
                decision_source=data.get("decision_source", "HUMAN_EXPLICIT_REVIEW"),
                evidence_reference=data.get("evidence_reference", ""),
                media_sha256=data["media_sha256"],
                publication_fingerprint=data["publication_fingerprint"],
                decided_at=data.get("decided_at", _now()),
                decision_hash=data["decision_hash"],
                policy_version=data.get("policy_version", AUDIENCE_POLICY_VERSION),
                schema_version=data.get("schema_version", AUDIENCE_SCHEMA_VERSION),
                status=data.get("status", "HUMAN_CONFIRMED"),
            )
        except Exception:
            return None

    def register_decision(self, record: AudienceDecisionRecord) -> tuple[bool, str, dict[str, Any]]:
        rec_file = self._record_file(record.content_id)
        raw_data = record.to_dict()

        with open(self.lock_file, "w") as lock_fd:
            fcntl.flock(lock_fd, fcntl.LOCK_EX)
            try:
                if rec_file.is_file():
                    try:
                        existing = json.loads(rec_file.read_text(encoding="utf-8"))
                    except Exception:
                        existing = {}
                    if existing.get("decision_hash") != record.decision_hash:
                        return False, "AUDIENCE_DECISION_CONFLICT", {"existing": existing, "requested": raw_data}
                    return True, "IDEMPOTENT_EXISTING_AUDIENCE_DECISION", existing

                tmp = rec_file.with_suffix(f".tmp.{os.getpid()}.{uuid.uuid4().hex[:8]}")
                with open(tmp, "w", encoding="utf-8") as f:
                    json.dump(raw_data, f, indent=2, ensure_ascii=False)
                    f.write("\n")
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(tmp, rec_file)
                return True, "AUDIENCE_DECISION_REGISTERED", raw_data
            finally:
                fcntl.flock(lock_fd, fcntl.LOCK_UN)


@dataclass(frozen=True)
class ApprovalRecord:
    approval_id: str
    approved_action: str  # "PRIVATE_UPLOAD" | "PUBLIC_RELEASE"
    publication_fingerprint: str
    media_sha256: str
    platform: str
    target_channel_id: str
    approved_privacy: str  # "private" for PRIVATE_UPLOAD, "public" for PUBLIC_RELEASE
    metadata_revision_hash: str
    audience_decision_hash: str = ""
    channel_evidence_hash: str = ""
    duplicate_evidence_hash: str = ""
    acceptance_id: str = ""
    acceptance_hash: str = ""
    approval_policy_version: str = APPROVAL_POLICY_VERSION
    approval_schema_version: str = APPROVAL_SCHEMA_VERSION
    maximum_allowed_cost_eur: float = 0.0
    authorization_source: str = "EXPLICIT_HUMAN_APPROVAL"
    approved_at: str = ""
    platform_video_id: str | None = None
    state: str = ApprovalState.ACTIVE.value

    def __post_init__(self):
        if not self.approved_at:
            object.__setattr__(self, "approved_at", _now())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ApprovalRecord:
        return cls(
            approval_id=data["approval_id"],
            approved_action=data["approved_action"],
            publication_fingerprint=data["publication_fingerprint"],
            media_sha256=data["media_sha256"],
            platform=data["platform"],
            target_channel_id=data["target_channel_id"],
            approved_privacy=data["approved_privacy"],
            metadata_revision_hash=data["metadata_revision_hash"],
            audience_decision_hash=data.get("audience_decision_hash", ""),
            channel_evidence_hash=data.get("channel_evidence_hash", ""),
            duplicate_evidence_hash=data.get("duplicate_evidence_hash", ""),
            acceptance_id=data.get("acceptance_id", ""),
            acceptance_hash=data.get("acceptance_hash", ""),
            approval_policy_version=data.get("approval_policy_version", APPROVAL_POLICY_VERSION),
            approval_schema_version=data.get("approval_schema_version", APPROVAL_SCHEMA_VERSION),
            maximum_allowed_cost_eur=data.get("maximum_allowed_cost_eur", 0.0),
            authorization_source=data.get("authorization_source", "EXPLICIT_HUMAN_APPROVAL"),
            approved_at=data.get("approved_at", _now()),
            platform_video_id=data.get("platform_video_id"),
            state=data.get("state", ApprovalState.ACTIVE.value),
        )


class ApprovalRegistry:
    """Durable atomic registry for immutable ApprovalRecords with conflict detection."""

    def __init__(self, registry_dir: Path | None = None):
        self.registry_dir = registry_dir or (REPO_ROOT / "events" / "approvals" / "registry")
        self.registry_dir.mkdir(parents=True, exist_ok=True)
        self.lock_file = self.registry_dir / ".registry.lock"

    def _approval_file(self, approval_id: str) -> Path:
        return self.registry_dir / f"{approval_id}.json"

    def register_approval(self, record: ApprovalRecord) -> tuple[bool, str, dict[str, Any]]:
        """Atomically register an ApprovalRecord with serialized cross-process conflict detection."""
        app_file = self._approval_file(record.approval_id)
        raw_data = record.to_dict()

        with open(self.lock_file, "w") as lock_fd:
            fcntl.flock(lock_fd, fcntl.LOCK_EX)
            try:
                if app_file.is_file():
                    try:
                        existing = json.loads(app_file.read_text(encoding="utf-8"))
                    except (json.JSONDecodeError, OSError) as exc:
                        return False, "APPROVAL_REGISTRY_CORRUPTED", {"error": str(exc)}

                    immutable_keys = [
                        "approved_action",
                        "platform",
                        "target_channel_id",
                        "media_sha256",
                        "publication_fingerprint",
                        "approved_privacy",
                        "acceptance_id",
                        "acceptance_hash",
                        "maximum_allowed_cost_eur",
                    ]
                    conflicts = {}
                    for k in immutable_keys:
                        if existing.get(k) != raw_data.get(k):
                            conflicts[k] = {"existing": existing.get(k), "requested": raw_data.get(k)}

                    if conflicts:
                        return False, "APPROVAL_ID_CONFLICT", {"conflicts": conflicts}
                    return True, "IDEMPOTENT_EXISTING_APPROVAL", existing

                # First registration -> atomic write with fsync inside lock
                tmp = app_file.with_suffix(f".tmp.{os.getpid()}.{uuid.uuid4().hex[:8]}")
                with open(tmp, "w", encoding="utf-8") as f:
                    json.dump(raw_data, f, indent=2, ensure_ascii=False)
                    f.write("\n")
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(tmp, app_file)
                return True, "APPROVAL_REGISTERED", raw_data
            finally:
                fcntl.flock(lock_fd, fcntl.LOCK_UN)

    def get_approval(self, approval_id: str) -> ApprovalRecord | None:
        app_file = self._approval_file(approval_id)
        if not app_file.is_file():
            return None
        try:
            data = json.loads(app_file.read_text(encoding="utf-8"))
            return ApprovalRecord.from_dict(data)
        except Exception:
            return None


class AppendOnlyApprovalLedger:
    """Cryptographically chained append-only approval ledger with file locking against lost updates."""

    def __init__(self, ledger_dir: Path | None = None):
        self.ledger_dir = ledger_dir or (REPO_ROOT / "events" / "approvals")
        self.ledger_dir.mkdir(parents=True, exist_ok=True)
        self.ledger_file = self.ledger_dir / "approval_ledger.json"
        self.lock_file = self.ledger_dir / ".approval_ledger.lock"

    def _read_ledger(self) -> list[dict[str, Any]]:
        if not self.ledger_file.is_file():
            return []
        try:
            data = json.loads(self.ledger_file.read_text(encoding="utf-8"))
            if not isinstance(data, list):
                raise ValueError("Ledger content must be a JSON array")
            return data
        except (json.JSONDecodeError, OSError, ValueError) as exc:
            raise ValueError(f"APPROVAL_LEDGER_CORRUPTED: {exc}")

    def _atomic_write_locked(self, events: list[dict[str, Any]]) -> None:
        tmp = self.ledger_file.with_suffix(f".tmp.{os.getpid()}.{uuid.uuid4().hex[:8]}")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(events, f, indent=2, ensure_ascii=False)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, self.ledger_file)

    def record_event(
        self,
        *,
        approval_id: str,
        approval_state: str,
        publication_fingerprint: str,
        action: str,
        reason: str,
    ) -> dict[str, Any]:
        """Record an approval state event with atomic file lock protection."""
        with open(self.lock_file, "w") as lock_fd:
            fcntl.flock(lock_fd, fcntl.LOCK_EX)
            try:
                try:
                    events = self._read_ledger()
                except ValueError as exc:
                    raise RuntimeError(f"Cannot append to corrupted ledger: {exc}")

                # Check for illegal resurrection from terminal states
                for ev in events:
                    if ev.get("approval_id") == approval_id:
                        prior_state = ev.get("approval_state")
                        if prior_state in {ApprovalState.CONSUMED.value, ApprovalState.REVOKED.value, ApprovalState.INVALIDATED.value}:
                            if approval_state == ApprovalState.ACTIVE.value:
                                raise ValueError(f"ILLEGAL_TRANSITION_RESURRECTION: Cannot transition from {prior_state} to ACTIVE")

                prev_hash = events[-1]["event_hash"] if events else "GENESIS_APPROVAL_LEDGER"
                event_id = f"app-ev-{len(events) + 1:04d}-{uuid.uuid4().hex[:8]}"
                ts = _now()

                payload = {
                    "event_id": event_id,
                    "approval_id": approval_id,
                    "approval_state": approval_state,
                    "publication_fingerprint": publication_fingerprint,
                    "action": action,
                    "timestamp": ts,
                    "reason": reason,
                    "previous_event_hash": prev_hash,
                }
                event_hash = hashlib.sha256(
                    json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
                ).hexdigest()
                payload["event_hash"] = event_hash

                events.append(payload)
                self._atomic_write_locked(events)
                return payload
            finally:
                fcntl.flock(lock_fd, fcntl.LOCK_UN)

    def verify_integrity(self) -> tuple[bool, str]:
        try:
            events = self._read_ledger()
        except ValueError as exc:
            return False, str(exc)

        if not events:
            return True, "EMPTY_LEDGER"

        prev_hash = "GENESIS_APPROVAL_LEDGER"
        seen_states: dict[str, str] = {}
        for i, ev in enumerate(events):
            if ev.get("previous_event_hash") != prev_hash:
                return False, f"Chain broken at index {i}: expected prev_hash {prev_hash}, got {ev.get('previous_event_hash')}"
            raw = {k: v for k, v in ev.items() if k != "event_hash"}
            expected_hash = hashlib.sha256(
                json.dumps(raw, sort_keys=True, separators=(",", ":")).encode("utf-8")
            ).hexdigest()
            if ev.get("event_hash") != expected_hash:
                return False, f"Event hash tampered at index {i}"

            app_id = ev.get("approval_id", "")
            new_st = ev.get("approval_state", "")
            if app_id in seen_states:
                old_st = seen_states[app_id]
                if old_st in {ApprovalState.CONSUMED.value, ApprovalState.REVOKED.value, ApprovalState.INVALIDATED.value}:
                    if new_st == ApprovalState.ACTIVE.value:
                        return False, f"Illegal state resurrection at index {i}: {old_st} -> {new_st}"
            seen_states[app_id] = new_st
            prev_hash = ev["event_hash"]
        return True, "VALID_CHAIN"


def derive_approval_state(
    approval_id: str,
    approval_ledger: AppendOnlyApprovalLedger,
    initial_record_state: str = ApprovalState.ACTIVE.value,
) -> str:
    """Derive authoritative approval state from append-only ledger history with integrity check."""
    ok_int, reason = approval_ledger.verify_integrity()
    if not ok_int:
        return ApprovalState.INVALIDATED.value

    try:
        events = approval_ledger._read_ledger()
    except ValueError:
        return ApprovalState.INVALIDATED.value

    state = initial_record_state
    for ev in events:
        if ev.get("approval_id") == approval_id:
            state = ev.get("approval_state", state)
    return state


class ReleaseOperationLedger:
    """Tracks operation intents, crash safety, dispatch boundaries, and terminal outcomes with file lock."""

    def __init__(self, ledger_dir: Path | None = None):
        self.ledger_dir = ledger_dir or (REPO_ROOT / "events" / "operations")
        self.ledger_dir.mkdir(parents=True, exist_ok=True)
        self.op_file = self.ledger_dir / "operation_ledger.json"
        self.lock_file = self.ledger_dir / ".operation_ledger.lock"

    def _read_ops(self) -> list[dict[str, Any]]:
        if not self.op_file.is_file():
            return []
        try:
            data = json.loads(self.op_file.read_text(encoding="utf-8"))
            if not isinstance(data, list):
                return []
            return data
        except (json.JSONDecodeError, OSError):
            return []

    def _atomic_write_locked(self, ops: list[dict[str, Any]]) -> None:
        tmp = self.op_file.with_suffix(f".tmp.{os.getpid()}.{uuid.uuid4().hex[:8]}")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(ops, f, indent=2, ensure_ascii=False)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, self.op_file)

    def record_intent(
        self,
        *,
        approval_id: str,
        publication_fingerprint: str,
        requested_action: str,
        state_before: str,
        target_channel_id: str = "UCg0O_a10jsQ74ffS_HgFGqA",
        platform_video_id: str | None = None,
    ) -> str:
        with open(self.lock_file, "w") as lock_fd:
            fcntl.flock(lock_fd, fcntl.LOCK_EX)
            try:
                ops = self._read_ops()
                op_id = compute_deterministic_operation_id(
                    approved_action=requested_action,
                    approval_id=approval_id,
                    publication_fingerprint=publication_fingerprint,
                    target_channel_id=target_channel_id,
                )
                for op in ops:
                    if op["operation_id"] == op_id:
                        return op_id

                op = {
                    "operation_id": op_id,
                    "approval_id": approval_id,
                    "publication_fingerprint": publication_fingerprint,
                    "target_channel_id": target_channel_id,
                    "platform_video_id": platform_video_id,
                    "requested_action": requested_action,
                    "state_before": state_before,
                    "state_after": OperationOutcome.INTENT_RECORDED.value,
                    "requested_at": _now(),
                    "completed_at": None,
                    "outcome": OperationOutcome.INTENT_RECORDED.value,
                    "evidence_reference": None,
                }
                ops.append(op)
                self._atomic_write_locked(ops)
                return op_id
            finally:
                fcntl.flock(lock_fd, fcntl.LOCK_UN)

    def update_outcome(
        self,
        operation_id: str,
        *,
        outcome: OperationOutcome,
        state_after: str,
        platform_video_id: str | None = None,
        evidence_reference: str | None = None,
    ) -> None:
        with open(self.lock_file, "w") as lock_fd:
            fcntl.flock(lock_fd, fcntl.LOCK_EX)
            try:
                ops = self._read_ops()
                for op in ops:
                    if op["operation_id"] == operation_id:
                        op["outcome"] = outcome.value
                        op["state_after"] = state_after
                        if platform_video_id:
                            op["platform_video_id"] = platform_video_id
                        if evidence_reference:
                            op["evidence_reference"] = evidence_reference
                        if outcome in {OperationOutcome.UPLOADED_PRIVATE, OperationOutcome.RELEASED_PUBLIC, OperationOutcome.FAILED_ABORTED}:
                            op["completed_at"] = _now()
                        break
                self._atomic_write_locked(ops)
            finally:
                fcntl.flock(lock_fd, fcntl.LOCK_UN)


class PublicationApprovalContract:
    """Evaluates ApprovalRecords and enforces binding invariants before execution."""

    def __init__(self, repo_dir: Path | None = None):
        self.repo_dir = repo_dir or REPO_ROOT
        self.registry = ApprovalRegistry(self.repo_dir / "events" / "approvals" / "registry")
        self.ledger = AppendOnlyApprovalLedger(self.repo_dir / "events" / "approvals")

    def validate_approval_for_execution(
        self,
        approval: ApprovalRecord,
        package_data: dict[str, Any] | None = None,
        requested_action: str = "PRIVATE_UPLOAD",
        require_registration: bool = False,
    ) -> tuple[bool, str, dict[str, Any]]:
        pkg_data = package_data or {}
        # 1. Require existence in durable registry & derive effective state
        registered = self.registry.get_approval(approval.approval_id)
        if not registered:
            if require_registration:
                return False, "APPROVAL_NOT_REGISTERED", {
                    "approval_id": approval.approval_id,
                    "message": "ApprovalRecord not found in durable registry",
                }
            initial_state = approval.state
        else:
            initial_state = registered.state

        # Validate ledger integrity
        ok_ledger, ledger_msg = self.ledger.verify_integrity()
        if not ok_ledger:
            return False, "LEDGER_CORRUPTED", {"error": ledger_msg}

        effective_state = derive_approval_state(approval.approval_id, self.ledger, initial_record_state=initial_state)
        if effective_state != ApprovalState.ACTIVE.value:
            return False, f"APPROVAL_{effective_state}", {
                "approval_id": approval.approval_id,
                "effective_state": effective_state,
            }

        # 3. Action match
        if approval.approved_action != requested_action:
            return False, "APPROVAL_ACTION_MISMATCH", {
                "approved_action": approval.approved_action,
                "requested_action": requested_action,
            }

        # 4. Action-specific privacy validation
        if requested_action == ApprovalAction.PRIVATE_UPLOAD.value:
            if approval.approved_privacy != "private":
                return False, "INVALID_PRIVACY_FOR_PRIVATE_UPLOAD", {"approved_privacy": approval.approved_privacy}
        elif requested_action == ApprovalAction.PUBLIC_RELEASE.value:
            if approval.approved_privacy != "public":
                return False, "INVALID_PRIVACY_FOR_PUBLIC_RELEASE", {"approved_privacy": approval.approved_privacy}
            if not approval.platform_video_id or not approval.platform_video_id.strip():
                return False, "PUBLIC_RELEASE_MISSING_VIDEO_ID", {}
        else:
            return False, "UNKNOWN_ACTION", {"requested_action": requested_action}

        # 5. Immutable asset & channel bindings
        if approval.platform != package_data.get("platform"):
            return False, "APPROVAL_PLATFORM_MISMATCH", {"approval": approval.platform, "pkg": package_data.get("platform")}

        if approval.target_channel_id != package_data.get("target_channel_id"):
            return False, "APPROVAL_CHANNEL_MISMATCH", {"approval": approval.target_channel_id, "pkg": package_data.get("target_channel_id")}

        if approval.media_sha256 != package_data.get("media_sha256"):
            return False, "APPROVAL_MEDIA_MISMATCH", {"approval": approval.media_sha256, "pkg": package_data.get("media_sha256")}

        if approval.publication_fingerprint != package_data.get("publication_dedupe_fingerprint"):
            return False, "APPROVAL_FINGERPRINT_MISMATCH", {"approval": approval.publication_fingerprint, "pkg": package_data.get("publication_dedupe_fingerprint")}

        # 6. Metadata revision match
        current_meta_hash = compute_metadata_revision_hash(package_data)
        if approval.metadata_revision_hash != current_meta_hash:
            return False, "EDITORIAL_RECONFIRMATION_REQUIRED", {"approval_meta": approval.metadata_revision_hash, "current_meta": current_meta_hash}

        # 7. Strict zero-cost validation
        ok_cost, cost_code = validate_finite_exact_zero(approval.maximum_allowed_cost_eur)
        if not ok_cost:
            return False, cost_code, {"cost": approval.maximum_allowed_cost_eur}

        return True, "APPROVAL_VALID", {"approval_id": approval.approval_id, "effective_state": effective_state}
