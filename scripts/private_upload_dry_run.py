#!/usr/bin/env python3
"""FruitKI Private Upload Dry-Run Orchestrator & Safety Simulator.

Simulates the complete 17-step private upload staging sequence in isolated
fixture environments with injected mock providers.

Guarantees:
- ZERO network calls (no videos.insert)
- ZERO mutation of production publication state
- Exactly ONE mock dispatch on normal execution
- AT_MOST_ONE_AUTOMATIC_DISPATCH guarantee across all crash and timeout scenarios
- Ambiguous outcome parking without automatic redispatch
- Exact-ID read-only reconciliation recovery
- Atomic fencing ownership protection blocking old owners
- Strict public release firebreak (PRIVATE_UPLOAD cannot authorize public visibility)
"""

from __future__ import annotations

import datetime
import hashlib
import json
import os
import sys
import tempfile
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.creator_input_sources import compute_publication_dedupe_fingerprint
from scripts.evidence_provenance import (
    ProvenanceReceipt,
    ProvenanceSource,
    TestFixtureYouTubeReadService,
    TrustedYouTubeResponseAdapter,
    build_package_duplicate_preflight,
    compute_payload_hash,
)
from scripts.private_upload_executor import (
    ExecutionResult,
    PrivateUploadExecutor,
    ReconciliationOutcome,
)
from scripts.publication_approval import (
    AppendOnlyApprovalLedger,
    ApprovalAction,
    ApprovalRecord,
    ApprovalRegistry,
    ApprovalState,
    AudienceDecisionRecord,
    AudienceDecisionState,
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
)
from scripts.release_acceptance_gate import (
    AcceptanceResult,
    ReleaseAcceptanceGate,
)

REPO_ROOT = Path(__file__).resolve().parent.parent


class MockYouTubeUploadProvider:
    """In-memory mock YouTube upload provider tracking dispatches and enforcing simulation rules."""

    def __init__(self, target_video_id: str = "VID_MOCK_DRYRUN_101", fail_mode: str | None = None):
        self.target_video_id = target_video_id
        self.fail_mode = fail_mode
        self.dispatch_count = 0
        self.dispatched_payloads: list[dict[str, Any]] = []

    def upload_video(self, package_data: dict[str, Any]) -> dict[str, Any]:
        self.dispatch_count += 1
        self.dispatched_payloads.append(package_data)

        if self.fail_mode == "TIMEOUT":
            raise TimeoutError("Simulated network timeout during mock upload")
        elif self.fail_mode == "RESPONSE_LOST":
            raise ConnectionResetError("Simulated connection reset after mock server accepted request")
        elif self.fail_mode == "SERVER_ERROR":
            return {"status": "ERROR", "error": "500 Internal Server Error"}

        return {
            "status": "SUCCESS",
            "video_id": self.target_video_id,
            "privacy_status": package_data.get("intended_upload_privacy", "private"),
        }


@dataclass
class DryRunScenarioResult:
    scenario_name: str
    status: str  # "SUCCESS" | "BLOCKED" | "ERROR"
    code: str
    dispatch_count: int
    operation_id: str | None = None
    video_id: str | None = None
    approval_state_after: str | None = None
    ledger_state_after: str | None = None
    details: dict[str, Any] = field(default_factory=dict)


class PrivateUploadDryRunOrchestrator:
    """Deterministic orchestrator executing simulated private uploads in isolated sandbox environments."""

    def __init__(self, sandbox_dir: Path | None = None):
        self.owns_dir = sandbox_dir is None
        self.sandbox_dir = sandbox_dir or Path(tempfile.mkdtemp(prefix="fruitki_dryrun_"))
        self.executor = PrivateUploadExecutor(repo_dir=self.sandbox_dir, allow_test_fixtures=True)
        self.gate = ReleaseAcceptanceGate(repo_dir=self.sandbox_dir, allow_test_fixtures=True)
        self.approval_registry = ApprovalRegistry(self.sandbox_dir / "events" / "approvals" / "registry")
        self.approval_ledger = AppendOnlyApprovalLedger(self.sandbox_dir / "events" / "approvals")
        self.op_ledger = ReleaseOperationLedger(self.sandbox_dir / "events" / "operations")
        self.contract = PublicationApprovalContract(self.sandbox_dir)

    def cleanup(self) -> None:
        if self.owns_dir and self.sandbox_dir.is_dir():
            shutil.rmtree(self.sandbox_dir, ignore_errors=True)

    def setup_fixture_environment(
        self,
        content_id: str | None = None,
        audience_decision: str = "NOT_MADE_FOR_KIDS",
        intended_privacy: str = "private",
    ) -> tuple[Path, ApprovalRecord, AudienceDecisionRecord]:
        """Setup complete isolated fixture package, evidence, receipts, audience record, and approval."""
        cid = content_id or f"dryrun_pkg_{uuid.uuid4().hex[:8]}"
        pkg_dir = self.sandbox_dir / "content" / cid
        pkg_dir.mkdir(parents=True, exist_ok=True)
        ev_dir = self.sandbox_dir / "events" / "evidence"
        rcpt_dir = self.sandbox_dir / "events" / "receipts"
        ev_dir.mkdir(parents=True, exist_ok=True)
        rcpt_dir.mkdir(parents=True, exist_ok=True)

        now_ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
        media_bytes = f"fruitki_dryrun_simulated_video_stream_{cid}_{uuid.uuid4().hex[:8]}".encode("utf-8")
        media_sha = hashlib.sha256(media_bytes).hexdigest()
        media_path = pkg_dir / "render.mp4"
        media_path.write_bytes(media_bytes)

        qc_path = pkg_dir / "qc_report.json"
        qc_path.write_text(json.dumps({"verdict": "PASS", "source_hash": media_sha}), encoding="utf-8")

        ch_id = "UCg0O_a10jsQ74ffS_HgFGqA"
        ch_ev, ch_rcpt = TestFixtureYouTubeReadService.create_channel_fixture(
            channel_id=ch_id, started_at=now_ts, retrieved_at=now_ts
        )
        (ev_dir / "channel_evidence_fruitki.json").write_text(json.dumps(ch_ev, indent=2), encoding="utf-8")
        (rcpt_dir / f"{ch_rcpt.receipt_id}.json").write_text(json.dumps(ch_rcpt.to_dict(), indent=2), encoding="utf-8")

        snap_ev, snap_rcpt = TestFixtureYouTubeReadService.create_upload_snapshot_fixture(
            channel_id=ch_id, started_at=now_ts, retrieved_at=now_ts
        )
        (ev_dir / "youtube_uploads_snapshot_fruitki.json").write_text(json.dumps(snap_ev, indent=2), encoding="utf-8")
        (rcpt_dir / f"{snap_rcpt.receipt_id}.json").write_text(json.dumps(snap_rcpt.to_dict(), indent=2), encoding="utf-8")

        fp = compute_publication_dedupe_fingerprint(platform="YOUTUBE", target_channel_id=ch_id, media_sha256=media_sha)
        dup_rec = build_package_duplicate_preflight(
            publication_fingerprint=fp,
            media_sha256=media_sha,
            target_channel_id=ch_id,
            channel_evidence_hash=ch_ev["payload_evidence_hash"],
            channel_receipt_hash=ch_rcpt.receipt_hash,
            upload_snapshot_hash=snap_ev["payload_evidence_hash"],
            upload_snapshot_receipt_hash=snap_rcpt.receipt_hash,
            items_checked=2,
            page_count=1,
            coverage_complete=True,
            duplicate_match=False,
            checked_at=now_ts,
        )
        dup_ev_path = ev_dir / f"duplicate_preflight_{fp[:16]}.json"
        dup_ev_path.write_text(json.dumps(dup_rec, indent=2), encoding="utf-8")

        aud_record = AudienceDecisionRecord.create(
            content_id=cid,
            decision=audience_decision,
            decision_source="HUMAN_EXPLICIT_REVIEW",
            evidence_reference="scene_dryrun.gd",
            media_sha256=media_sha,
            publication_fingerprint=fp,
            decided_at=now_ts,
        )
        aud_dir = self.sandbox_dir / "events" / "audience-decisions"
        aud_dir.mkdir(parents=True, exist_ok=True)
        (aud_dir / f"{cid}.json").write_text(json.dumps(aud_record.to_dict(), indent=2), encoding="utf-8")

        pkg_path = pkg_dir / "publish_package.json"
        pkg_data = {
            "schema_version": "2.2",
            "platform": "YOUTUBE",
            "target_channel_id": ch_id,
            "target_channel_handle": "@kifruchtefilme",
            "token_reference": "fruitki-test",
            "channel_evidence_path": str(ev_dir / "channel_evidence_fruitki.json"),
            "channel_evidence_hash": ch_ev["payload_evidence_hash"],
            "channel_verified_at": now_ts,
            "duplicate_preflight_path": str(dup_ev_path),
            "duplicate_preflight_result": dup_rec["result"],
            "content_title": "Dry-Run Simulation Title #Shorts",
            "description_draft": "Dry-run simulation description",
            "tags": ["FruitKI", "Shorts"],
            "hashtags": ["#Shorts", "#FruitKI"],
            "category_id": "22",
            "audience_decision": audience_decision,
            "self_declared_made_for_kids": (audience_decision == "MADE_FOR_KIDS"),
            "intended_upload_privacy": intended_privacy,
            "intended_release_privacy": "public",
            "media_path": str(media_path),
            "media_sha256": media_sha,
            "cost_eur": 0.0,
            "qc_report_path": str(qc_path),
            "qc_status": "PASS",
            "publication_dedupe_fingerprint": fp,
            "publication_authorized": False,
            "publication_state": "COMPLETE_READY_FOR_REVIEW",
            "prepared_at": now_ts,
            "audience_decision_hash": aud_record.decision_hash,
        }
        pkg_path.write_text(json.dumps(pkg_data, indent=2), encoding="utf-8")

        acc_res = self.gate.evaluate_package(pkg_path, aud_record)

        approval = ApprovalRecord(
            approval_id=f"app-dryrun-{uuid.uuid4().hex[:8]}",
            approved_action="PRIVATE_UPLOAD",
            publication_fingerprint=fp,
            media_sha256=media_sha,
            platform="YOUTUBE",
            target_channel_id=ch_id,
            approved_privacy=intended_privacy,
            metadata_revision_hash=compute_metadata_revision_hash(pkg_data),
            audience_decision_hash=aud_record.decision_hash,
            channel_evidence_hash=ch_ev["payload_evidence_hash"],
            duplicate_evidence_hash=dup_rec["upload_snapshot_hash"],
            acceptance_id=acc_res.acceptance_id,
            acceptance_hash=acc_res.acceptance_input_hash,
            maximum_allowed_cost_eur=0.0,
            authorization_source="HUMAN_EXPLICIT_APPROVAL",
            approved_at=now_ts,
        )
        self.approval_registry.register_approval(approval)
        return pkg_path, approval, aud_record

    def run_normal_success_dryrun(self) -> DryRunScenarioResult:
        """Execute standard successful private upload dry run."""
        pkg_path, approval, aud_rec = self.setup_fixture_environment()
        self.executor.gate.audience_registry.register_decision(aud_rec)
        provider = MockYouTubeUploadProvider(target_video_id="VID_DRYRUN_SUCCESS_200")

        exec_res = self.executor.execute_private_upload(
            package_path=pkg_path,
            approval=approval,
            audience_record=aud_rec,
            upload_mutation_mock=provider.upload_video,
        )

        eff_state = derive_approval_state(approval.approval_id, self.approval_ledger)
        ledger_state = self.executor.ledger.get_state(approval.publication_fingerprint)

        return DryRunScenarioResult(
            scenario_name="NORMAL_SUCCESS",
            status=exec_res.status,
            code=exec_res.code,
            dispatch_count=provider.dispatch_count,
            operation_id=exec_res.operation_id,
            video_id=exec_res.video_id,
            approval_state_after=eff_state,
            ledger_state_after=ledger_state.value,
            details={"message": exec_res.message},
        )

    def run_crash_simulation_dryrun(self, crash_point: str) -> DryRunScenarioResult:
        """Execute crash simulation at a specific boundary in the execution state machine."""
        pkg_path, approval, aud_rec = self.setup_fixture_environment()
        self.executor.gate.audience_registry.register_decision(aud_rec)
        fail_mode = "TIMEOUT" if crash_point == "TIMEOUT_AFTER_POSSIBLE_DISPATCH" else (
            "RESPONSE_LOST" if crash_point == "RESPONSE_LOST_AFTER_ACCEPT" else None
        )
        provider = MockYouTubeUploadProvider(target_video_id="VID_DRYRUN_CRASH", fail_mode=fail_mode)

        sim_arg = None if fail_mode is not None else crash_point
        exec_res = self.executor.execute_private_upload(
            package_path=pkg_path,
            approval=approval,
            audience_record=aud_rec,
            upload_mutation_mock=provider.upload_video,
            simulate_crash_at=sim_arg,
        )

        eff_state = derive_approval_state(approval.approval_id, self.approval_ledger)
        ledger_state = self.executor.ledger.get_state(approval.publication_fingerprint)

        return DryRunScenarioResult(
            scenario_name=f"CRASH_{crash_point}",
            status=exec_res.status,
            code=exec_res.code,
            dispatch_count=provider.dispatch_count,
            operation_id=exec_res.operation_id,
            video_id=exec_res.video_id,
            approval_state_after=eff_state,
            ledger_state_after=ledger_state.value,
            details={"message": exec_res.message},
        )

    def run_reconciliation_simulation(self, exact_id_available: bool) -> tuple[bool, str, str | None]:
        """Simulate post-crash reconciliation with either exact durable ID or ambiguous scan."""
        pkg_path, approval, aud_rec = self.setup_fixture_environment()
        self.executor.gate.audience_registry.register_decision(aud_rec)
        provider = MockYouTubeUploadProvider(target_video_id="VID_RECON_TARGET")

        res = self.executor.execute_private_upload(
            package_path=pkg_path,
            approval=approval,
            audience_record=aud_rec,
            upload_mutation_mock=provider.upload_video,
            simulate_crash_at="AFTER_PLATFORM_ID",
        )

        if exact_id_available:
            ok, code, vid = self.executor.reconcile_uncertain_operation(
                operation_id=res.operation_id,
                fingerprint=approval.publication_fingerprint,
                approval_id=approval.approval_id,
                exact_video_id_provider=lambda known_id: (True, known_id),
            )
        else:
            ok, code, vid = self.executor.reconcile_uncertain_operation(
                operation_id=res.operation_id,
                fingerprint=approval.publication_fingerprint,
                approval_id=approval.approval_id,
                exact_video_id_provider=lambda known_id: (False, None),
            )
        return ok, code, vid

    def run_fencing_old_owner_simulation(self) -> dict[str, bool]:
        """Simulate old owner attempting mutations after reservation token replacement."""
        pkg_path, approval, _ = self.setup_fixture_environment()
        fp = approval.publication_fingerprint
        ch_id = approval.target_channel_id
        media_sha = approval.media_sha256

        # 1. Owner 1 reserves
        token_1 = "fence-owner-1"
        ok1, _, _ = self.executor.ledger.reserve(
            fingerprint=fp, target_channel_id=ch_id, media_sha256=media_sha, reservation_token=token_1, operation_id="op-1"
        )

        # 2. Reservation renewed by Owner 2
        token_2 = "fence-owner-2"
        # Release and re-reserve to simulate new fencing epoch
        self.executor.ledger.release_claim(fp, token_1)
        ok2, _, _ = self.executor.ledger.reserve(
            fingerprint=fp, target_channel_id=ch_id, media_sha256=media_sha, reservation_token=token_2, operation_id="op-2"
        )

        # 3. Old owner attempts release with stale token_1
        ok_old_release, code_old_rel = self.executor.ledger.release_claim(fp, token_1)

        return {
            "owner_1_initial_reservation": ok1,
            "owner_2_new_reservation": ok2,
            "owner_1_stale_release_blocked": not ok_old_release,
            "rejection_code": code_old_rel,
        }

    def run_public_release_firebreak_test(self) -> dict[str, Any]:
        """Verify that PRIVATE_UPLOAD approval strictly blocks any public release or visibility change."""
        pkg_path, approval, _ = self.setup_fixture_environment()
        pkg = json.loads(pkg_path.read_text(encoding="utf-8"))

        # 1. Attempt validate_approval_for_execution with PUBLIC_RELEASE action
        ok_pub_action, code_pub_action, _ = self.contract.validate_approval_for_execution(
            approval=approval,
            package_data=pkg,
            requested_action=ApprovalAction.PUBLIC_RELEASE.value,
        )

        # 2. Attempt validate_approval_for_execution with public approval privacy
        approval_public = ApprovalRecord(
            approval_id=f"app-pubprivacy-{uuid.uuid4().hex[:8]}",
            approved_action="PRIVATE_UPLOAD",
            publication_fingerprint=approval.publication_fingerprint,
            media_sha256=approval.media_sha256,
            platform=approval.platform,
            target_channel_id=approval.target_channel_id,
            approved_privacy="public",
            metadata_revision_hash=approval.metadata_revision_hash,
            audience_decision_hash=approval.audience_decision_hash,
            channel_evidence_hash=approval.channel_evidence_hash,
            duplicate_evidence_hash=approval.duplicate_evidence_hash,
            acceptance_id=approval.acceptance_id,
            acceptance_hash=approval.acceptance_hash,
            maximum_allowed_cost_eur=0.0,
        )
        self.approval_registry.register_approval(approval_public)
        ok_pub_privacy, code_pub_privacy, _ = self.contract.validate_approval_for_execution(
            approval=approval_public,
            package_data=pkg,
            requested_action=ApprovalAction.PRIVATE_UPLOAD.value,
        )

        return {
            "public_release_action_blocked": not ok_pub_action,
            "public_release_action_code": code_pub_action,
            "public_privacy_blocked": not ok_pub_privacy,
            "public_privacy_code": code_pub_privacy,
        }
