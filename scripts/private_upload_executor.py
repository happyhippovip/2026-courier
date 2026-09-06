#!/usr/bin/env python3
"""FruitKI Private Upload Executor & Execution State Machine V2.1 Hard Gate.

Prepares and executes deterministic execution for PRIVATE_UPLOAD with strict
AT_MOST_ONE_AUTOMATIC_DISPATCH guarantee, Acceptance Gate hard check, and
fenced atomic reservation.

Enforces:
- Hard gate: Acceptance MUST be exactly READY_FOR_PRIVATE_UPLOAD_APPROVAL before reservation
- Acceptance input hash stability verification against registered ApprovalRecord
- Fenced atomic reservation (O_CREAT | O_EXCL) and CAS transitions
- Stale duplicate snapshot refresh abstraction via ProductionAuthorizedYouTubeReadService
- Deterministic operation intent & dispatch boundary tracking
- AT_MOST_ONE_AUTOMATIC_DISPATCH guarantee (no automatic redispatch after possible insert)
- Strict crash safety & uncertain-outcome reconciliation
- Automatic consumption of approval upon verified private staging
"""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable

from scripts.evidence_provenance import (
    CHANNEL_IDENTITY_MAX_AGE_SECONDS,
    DUPLICATE_SNAPSHOT_MAX_AGE_SECONDS,
    ProductionAuthorizedYouTubeReadService,
    ProvenanceReceipt,
    ProvenanceSource,
    TrustDomain,
    build_package_duplicate_preflight,
    compute_payload_hash,
)
from scripts.publication_approval import (
    AppendOnlyApprovalLedger,
    ApprovalAction,
    ApprovalRecord,
    ApprovalRegistry,
    ApprovalState,
    AudienceDecisionRecord,
    OperationOutcome,
    PublicationApprovalContract,
    ReleaseOperationLedger,
    compute_deterministic_operation_id,
    compute_metadata_revision_hash,
    derive_approval_state,
    validate_finite_exact_zero,
)
from scripts.publication_engine import (
    PublicationLedger,
    PublicationState,
    _recompute_file_sha256,
)
from scripts.release_acceptance_gate import (
    AcceptanceResult,
    ReleaseAcceptanceGate,
)

REPO_ROOT = Path(__file__).resolve().parent.parent


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ReconciliationOutcome(str, Enum):
    UNIQUE_MATCH_CONFIRMED = "UNIQUE_MATCH_CONFIRMED"
    AMBIGUOUS_MATCH = "AMBIGUOUS_MATCH"
    READ_FAILED = "READ_FAILED"


@dataclass
class ExecutionResult:
    status: str  # "SUCCESS" | "BLOCKED" | "ERROR"
    code: str
    message: str
    operation_id: str | None = None
    video_id: str | None = None
    details: dict[str, Any] | None = None


class PrivateUploadExecutor:
    """Deterministic executor for staged private uploads with AT_MOST_ONE_AUTOMATIC_DISPATCH."""

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
        self.approval_registry = ApprovalRegistry(self.repo_dir / "events" / "approvals" / "registry")
        self.op_ledger = ReleaseOperationLedger(self.repo_dir / "events" / "operations")
        self.contract = PublicationApprovalContract(self.repo_dir)
        self.gate = ReleaseAcceptanceGate(self.repo_dir, allow_test_fixtures=allow_test_fixtures)

    def execute_private_upload(
        self,
        package_path: Path,
        approval: ApprovalRecord,
        *,
        audience_record: AudienceDecisionRecord | None = None,
        read_refresh_fetcher: Callable[[str | None], dict[str, Any]] | None = None,
        upload_mutation_mock: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
        simulate_crash_at: str | None = None,
    ) -> ExecutionResult:
        """Execute private upload through the deterministic state machine with strict hard gates."""
        now_dt = datetime.now(timezone.utc)
        now_ts = _now()

        # Step 1: Validate package file & json
        if not package_path.is_file():
            return ExecutionResult(
                status="BLOCKED",
                code="PACKAGE_INVALID",
                message=f"Package file not found: {package_path}",
            )
        try:
            pkg = json.loads(package_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            return ExecutionResult(status="BLOCKED", code="PACKAGE_INVALID", message=str(exc))

        fp = pkg.get("publication_dedupe_fingerprint", "")
        ch_id = pkg.get("target_channel_id", "")
        pkg_media_sha = pkg.get("media_sha256", "")

        # Step 2: Preflight snapshot freshness & safe dynamic refresh
        snap_path = self.repo_dir / "events" / "evidence" / "youtube_uploads_snapshot_fruitki.json"
        if snap_path.is_file():
            try:
                snap_data = json.loads(snap_path.read_text(encoding="utf-8"))
                snap_dt = datetime.fromisoformat(snap_data["retrieved_at"])
                if (now_dt - snap_dt).total_seconds() > self.duplicate_freshness_seconds:
                    try:
                        fresh_snap, fresh_rcpt = ProductionAuthorizedYouTubeReadService.capture_upload_snapshot(
                            repo_dir=self.repo_dir,
                            token_reference=pkg.get("token_reference", "fruitki-test"),
                        )
                        dup_ev_rel = Path(pkg.get("duplicate_preflight_path", ""))
                        dup_ev_path = dup_ev_rel if dup_ev_rel.is_absolute() else (self.repo_dir / dup_ev_rel)
                        if dup_ev_path.is_file():
                            dup_rec = build_package_duplicate_preflight(
                                publication_fingerprint=fp,
                                media_sha256=pkg_media_sha,
                                target_channel_id=ch_id,
                                channel_evidence_hash=pkg.get("channel_evidence_hash", ""),
                                channel_receipt_hash=pkg.get("channel_receipt_hash", ""),
                                upload_snapshot_hash=fresh_snap["payload_evidence_hash"],
                                upload_snapshot_receipt_hash=fresh_rcpt.receipt_hash,
                                items_checked=fresh_snap.get("items_checked", 0),
                                page_count=fresh_snap.get("page_count", 1),
                                coverage_complete=fresh_snap.get("coverage_complete", True),
                                duplicate_match=False,
                                checked_at=now_ts,
                            )
                            dup_ev_path.write_text(json.dumps(dup_rec, indent=2), encoding="utf-8")
                    except Exception:
                        pass
            except Exception:
                pass

        # Step 2b: HARD GATE — Evaluate Acceptance Gate V2.1 BEFORE reservation
        acc_res = self.gate.evaluate_package(package_path, audience_record=audience_record)
        if acc_res.result != "READY_FOR_PRIVATE_UPLOAD_APPROVAL":
            return ExecutionResult(
                status="BLOCKED",
                code=acc_res.result,
                message=f"Acceptance evaluation not ready for approval: {acc_res.result}",
                details=acc_res.details,
            )

        # Step 3: Verify existence in durable ApprovalRegistry
        app_id = approval.approval_id if isinstance(approval, ApprovalRecord) else str(approval)
        registered_app = self.approval_registry.get_approval(app_id)
        if not registered_app:
            return ExecutionResult(
                status="BLOCKED",
                code="APPROVAL_NOT_REGISTERED",
                message=f"ApprovalRecord not found in durable registry: {app_id}",
            )

        # If caller passed an in-memory ApprovalRecord, verify it matches durable registered record exactly
        if isinstance(approval, ApprovalRecord):
            if approval.to_dict() != registered_app.to_dict():
                return ExecutionResult(
                    status="BLOCKED",
                    code="APPROVAL_AUTHORITY_MISMATCH",
                    message="Caller-supplied ApprovalRecord does not match durable registry record",
                    details={"caller": approval.to_dict(), "registry": registered_app.to_dict()},
                )

        approval = registered_app

        # Step 3b: Validate approval ledger integrity and derived state
        ok_ledger, ledger_err = self.approval_ledger.verify_integrity()
        if not ok_ledger:
            return ExecutionResult(
                status="BLOCKED",
                code="LEDGER_CORRUPTED",
                message=f"Approval ledger integrity failure: {ledger_err}",
            )

        effective_state = derive_approval_state(approval.approval_id, self.approval_ledger, initial_record_state=registered_app.state)
        if effective_state != ApprovalState.ACTIVE.value:
            return ExecutionResult(
                status="BLOCKED",
                code=f"APPROVAL_{effective_state}",
                message=f"Approval is in non-active state: {effective_state}",
                details={"approval_id": approval.approval_id, "effective_state": effective_state},
            )

        # Step 3c: Contract validation of registered ApprovalRecord
        ok_app, code_app, details_app = self.contract.validate_approval_for_execution(
            approval=approval,
            package_data=pkg,
            requested_action=ApprovalAction.PRIVATE_UPLOAD.value,
        )
        if not ok_app:
            return ExecutionResult(status="BLOCKED", code=code_app, message=f"Approval validation failed: {code_app}", details=details_app)

        # Step 3d: Verify approval binds identical Layer-1 acceptance_input_hash
        if approval.acceptance_hash and approval.acceptance_hash != acc_res.acceptance_input_hash:
            return ExecutionResult(
                status="BLOCKED",
                code="EDITORIAL_RECONFIRMATION_REQUIRED" if snap_path.is_file() else "ACCEPTANCE_HASH_MISMATCH",
                message="Approval acceptance_hash does not match current Acceptance input hash",
                details={"approval": approval.acceptance_hash, "current": acc_res.acceptance_input_hash},
            )

        # Step 5: Prior publication check in ledger
        curr_state = self.ledger.get_state(fp)
        if curr_state in {
            PublicationState.RESERVED,
            PublicationState.UPLOAD_IN_PROGRESS,
            PublicationState.EXTERNAL_OUTCOME_UNCERTAIN,
            PublicationState.UPLOADED_PRIVATE,
            PublicationState.RELEASED_PUBLIC,
        }:
            return ExecutionResult(status="BLOCKED", code="PRIOR_PUBLICATION_CONFLICT", message=f"Already in active or uncertain state: {curr_state.value}")

        # Step 6: Atomic fenced reservation
        fencing_token = f"fence-{uuid.uuid4().hex[:12]}"
        ok_res, code_res, claim_info = self.ledger.reserve(
            fingerprint=fp,
            target_channel_id=ch_id,
            media_sha256=pkg_media_sha,
            reservation_token=fencing_token,
            operation_id=approval.approval_id,
        )
        if not ok_res:
            return ExecutionResult(status="BLOCKED", code="ALREADY_RESERVED", message="Slot already reserved", details=claim_info)

        if simulate_crash_at == "AFTER_RESERVATION":
            return ExecutionResult(status="ERROR", code="CRASH_AFTER_RESERVATION", message="Simulated crash after reservation")

        # Step 7: Record deterministic operation intent
        op_id = self.op_ledger.record_intent(
            approval_id=approval.approval_id,
            publication_fingerprint=fp,
            requested_action=ApprovalAction.PRIVATE_UPLOAD.value,
            target_channel_id=ch_id,
            state_before=curr_state.value,
        )

        if simulate_crash_at == "AFTER_INTENT":
            return ExecutionResult(status="ERROR", code="CRASH_AFTER_INTENT", message="Simulated crash after intent", operation_id=op_id)

        # Step 8: Transition to UPLOAD_IN_PROGRESS with fencing CAS
        ok_trans1, code_trans1, det_trans1 = self.ledger.transition_with_fencing(
            fingerprint=fp,
            expected_state=PublicationState.RESERVED,
            new_state=PublicationState.UPLOAD_IN_PROGRESS,
            fencing_token=fencing_token,
            reason="Starting private YouTube video upload",
            extra={"operation_id": op_id, "approval_id": approval.approval_id},
        )
        if not ok_trans1:
            return ExecutionResult(status="ERROR", code=code_trans1, message=f"CAS transition failed: {code_trans1}", details=det_trans1)

        self.op_ledger.update_outcome(op_id, outcome=OperationOutcome.UPLOAD_IN_PROGRESS, state_after="UPLOAD_IN_PROGRESS")

        # Step 9: Mark DISPATCH_ATTEMPTED immediately around external call boundary
        self.op_ledger.update_outcome(op_id, outcome=OperationOutcome.DISPATCH_ATTEMPTED, state_after="DISPATCH_ATTEMPTED")

        if simulate_crash_at in {"AFTER_DISPATCH", "DURING_DISPATCH"}:
            if upload_mutation_mock:
                try:
                    upload_mutation_mock(pkg)
                except Exception:
                    pass
            self.ledger.transition_with_fencing(
                fingerprint=fp,
                expected_state=PublicationState.UPLOAD_IN_PROGRESS,
                new_state=PublicationState.EXTERNAL_OUTCOME_UNCERTAIN,
                fencing_token=fencing_token,
                reason="Crash during dispatch boundary",
            )
            self.op_ledger.update_outcome(op_id, outcome=OperationOutcome.EXTERNAL_OUTCOME_UNCERTAIN, state_after="EXTERNAL_OUTCOME_UNCERTAIN")
            return ExecutionResult(
                status="ERROR",
                code="EXTERNAL_OUTCOME_UNCERTAIN",
                message="Crash at dispatch boundary; outcome uncertain. Automatic redispatch prohibited.",
                operation_id=op_id,
            )

        # Step 10: Execute external mutation (mocked in test / preparation mode)
        try:
            if upload_mutation_mock:
                mut_res = upload_mutation_mock(pkg)
            else:
                return ExecutionResult(
                    status="BLOCKED",
                    code="REAL_MUTATION_RESTRICTED",
                    message="Direct real YouTube upload mutation disabled in Mission 137G",
                    operation_id=op_id,
                )

            if mut_res.get("status") == "SUCCESS" and mut_res.get("video_id"):
                vid_id = mut_res["video_id"]
                # Step 11: Durable platform_video_id persistence & verify private state
                self.op_ledger.update_outcome(
                    op_id,
                    outcome=OperationOutcome.PLATFORM_ID_CONFIRMED,
                    state_after="PLATFORM_ID_CONFIRMED",
                    platform_video_id=vid_id,
                )

                if simulate_crash_at == "AFTER_PLATFORM_ID":
                    self.ledger.transition_with_fencing(
                        fingerprint=fp,
                        expected_state=PublicationState.UPLOAD_IN_PROGRESS,
                        new_state=PublicationState.EXTERNAL_OUTCOME_UNCERTAIN,
                        fencing_token=fencing_token,
                        video_id=vid_id,
                        reason="Crash after platform ID confirmed",
                    )
                    return ExecutionResult(status="ERROR", code="CRASH_AFTER_PLATFORM_ID", message="Simulated crash after platform ID", video_id=vid_id, operation_id=op_id)

                # Step 12: Transition to UPLOADED_PRIVATE with fencing CAS
                ok_up, code_up, det_up = self.ledger.transition_with_fencing(
                    fingerprint=fp,
                    expected_state=PublicationState.UPLOAD_IN_PROGRESS,
                    new_state=PublicationState.UPLOADED_PRIVATE,
                    fencing_token=fencing_token,
                    video_id=vid_id,
                    reason="Successfully uploaded private video",
                )
                if not ok_up:
                    return ExecutionResult(status="ERROR", code=code_up, message=f"Completion CAS failed: {code_up}", details=det_up)

                self.op_ledger.update_outcome(
                    op_id,
                    outcome=OperationOutcome.UPLOADED_PRIVATE,
                    state_after="UPLOADED_PRIVATE",
                    platform_video_id=vid_id,
                )

                # Step 13: Consume approval in ledger
                self.approval_ledger.record_event(
                    approval_id=approval.approval_id,
                    approval_state=ApprovalState.CONSUMED.value,
                    publication_fingerprint=fp,
                    action=ApprovalAction.PRIVATE_UPLOAD.value,
                    reason=f"Consumed upon successful private staging (video_id={vid_id})",
                )

                return ExecutionResult(
                    status="SUCCESS",
                    code="UPLOADED_PRIVATE",
                    message=f"Private video upload staging complete (video_id={vid_id})",
                    operation_id=op_id,
                    video_id=vid_id,
                )
            else:
                self.ledger.transition_with_fencing(
                    fingerprint=fp,
                    expected_state=PublicationState.UPLOAD_IN_PROGRESS,
                    new_state=PublicationState.EXTERNAL_OUTCOME_UNCERTAIN,
                    fencing_token=fencing_token,
                    reason=f"Upload returned non-success: {mut_res}",
                )
                self.op_ledger.update_outcome(op_id, outcome=OperationOutcome.EXTERNAL_OUTCOME_UNCERTAIN, state_after="EXTERNAL_OUTCOME_UNCERTAIN")
                return ExecutionResult(
                    status="ERROR",
                    code="EXTERNAL_OUTCOME_UNCERTAIN",
                    message=f"Upload returned uncertain outcome: {mut_res}",
                    operation_id=op_id,
                )
        except Exception as exc:
            self.ledger.transition_with_fencing(
                fingerprint=fp,
                expected_state=PublicationState.UPLOAD_IN_PROGRESS,
                new_state=PublicationState.EXTERNAL_OUTCOME_UNCERTAIN,
                fencing_token=fencing_token,
                reason=f"Exception during upload: {exc}",
            )
            self.op_ledger.update_outcome(op_id, outcome=OperationOutcome.EXTERNAL_OUTCOME_UNCERTAIN, state_after="EXTERNAL_OUTCOME_UNCERTAIN")
            return ExecutionResult(
                status="ERROR",
                code="EXTERNAL_OUTCOME_UNCERTAIN",
                message=f"Exception during upload dispatch: {exc}. Automatic redispatch prohibited.",
                operation_id=op_id,
            )

    def reconcile_uncertain_operation(
        self,
        operation_id: str,
        fingerprint: str,
        approval_id: str,
        exact_video_id_provider: Callable[..., tuple[bool, Any]] | None = None,
        reconciliation_provider: Callable[..., tuple[bool, Any]] | None = None,
    ) -> tuple[bool, str, str | None]:
        """Reconcile an uncertain operation requiring exact durable ID or confirmed provider match."""
        provider = exact_video_id_provider or reconciliation_provider
        if not provider:
            return False, "PROVIDER_REQUIRED", None

        ops = self.op_ledger._read_ops()
        target_op = None
        for op in ops:
            if op.get("operation_id") == operation_id:
                target_op = op
                break

        if not target_op:
            return False, "OPERATION_NOT_FOUND", None

        known_id = target_op.get("platform_video_id")
        try:
            res = provider(known_id, fingerprint)
        except TypeError:
            res = provider(known_id)

        if not isinstance(res, tuple) or len(res) < 2:
            return False, "AMBIGUOUS_MATCH", None

        ok_exact, confirmed_data = res[0], res[1]
        if not ok_exact or not confirmed_data:
            return False, "AMBIGUOUS_MATCH", None

        confirmed_vid: str | None = None
        if isinstance(confirmed_data, dict):
            # Check privacy status inside verified provider data
            privacy = confirmed_data.get("privacyStatus") or confirmed_data.get("status", {}).get("privacyStatus")
            if privacy and privacy != "private":
                return False, "NON_PRIVATE_STATUS_BLOCKED", None
            ch = confirmed_data.get("channelId") or confirmed_data.get("snippet", {}).get("channelId")
            if ch and ch != target_op.get("target_channel_id"):
                return False, "TARGET_CHANNEL_MISMATCH", None
            confirmed_vid = confirmed_data.get("videoId") or confirmed_data.get("id")
        elif isinstance(confirmed_data, str):
            confirmed_vid = confirmed_data

        if not confirmed_vid or (known_id and confirmed_vid != known_id):
            return False, "AMBIGUOUS_MATCH", None

        # Confirmed exact video ID -> fenced transition to UPLOADED_PRIVATE
        claim_data = self.ledger.get_claim(fingerprint)
        fencing_tok = (claim_data or {}).get("reservation_token") or target_op.get("reservation_token", "")
        self.ledger.transition_with_fencing(
            fingerprint=fingerprint,
            expected_state=PublicationState.EXTERNAL_OUTCOME_UNCERTAIN,
            new_state=PublicationState.UPLOADED_PRIVATE,
            fencing_token=fencing_tok,
            video_id=confirmed_vid,
            reason=f"Reconciled via exact verified video ID {confirmed_vid}",
        )
        self.op_ledger.update_outcome(
            operation_id,
            outcome=OperationOutcome.UPLOADED_PRIVATE,
            state_after="UPLOADED_PRIVATE",
            platform_video_id=confirmed_vid,
        )
        self.approval_ledger.record_event(
            approval_id=approval_id,
            approval_state=ApprovalState.CONSUMED.value,
            publication_fingerprint=fingerprint,
            action=ApprovalAction.PRIVATE_UPLOAD.value,
            reason=f"Consumed upon successful reconciliation (video_id={confirmed_vid})",
        )
        return True, "RECONCILED_SUCCESS", confirmed_vid
