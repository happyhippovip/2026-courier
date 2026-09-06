"""Independent post-remediation oracle for the activation defects found in 140C.

All fixtures are created beneath TemporaryDirectory.  The expected assertions
describe the production safety contract, so selected cases intentionally fail
against the pre-remediation 139G implementation.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from scripts.evidence_provenance import (
    ProvenanceReceipt, ProvenanceSource, TrustDomain, build_package_duplicate_preflight,
    compute_payload_hash,
)
from scripts.private_upload_dry_run import MockYouTubeUploadProvider, PrivateUploadDryRunOrchestrator
from scripts.publication_engine import PublicationLedger, PublicationState
from scripts.release_acceptance_gate import ReleaseAcceptanceGate


CHANNEL = "UCg0O_a10jsQ74ffS_HgFGqA"


def install_forged_authorized_evidence(root: Path, package_path: Path, *, bundles: bool = True) -> None:
    """Simulate a module-import attacker; never touches a production workspace."""
    now = datetime.now(timezone.utc).isoformat()
    pkg = json.loads(package_path.read_text())
    evidence_dir = root / "events" / "evidence"
    receipt_dir = root / "events" / "receipts"
    bundle_ch = "oracle-forged-channel" if bundles else ""
    ch_core = {
        "schema_version": "2.0", "platform": "YOUTUBE", "channel_id": CHANNEL,
        "channel_handle": "@oracle", "channel_title": "oracle", "uploads_playlist_id": "UU" + CHANNEL[2:],
        "endpoint": "youtube.channels.list", "retrieved_at": now,
        "scope_reference": "https://www.googleapis.com/auth/youtube.force-ssl",
    }
    ch_hash = compute_payload_hash(ch_core)
    ch_receipt = ProvenanceReceipt._create_internal(
        bundle_id=bundle_ch, provenance_source=ProvenanceSource.ACTUAL_PROVIDER_READ.value,
        trust_domain=TrustDomain.AUTHORIZED_PROVIDER_READ_OBSERVED.value,
        operation="channels.list", endpoint="youtube.channels.list",
        request_parameters_safe={"part": "id,snippet,contentDetails", "mine": True},
        authenticated_channel_id=CHANNEL, scope_reference=ch_core["scope_reference"],
        started_at=now, completed_at=now, result_count=1, page_count=1,
        next_page_token_present=False, coverage_complete=True, payload_evidence_hash=ch_hash,
    )
    ch = {**ch_core, "payload_evidence_hash": ch_hash,
          "authorized_read_receipt_id": ch_receipt.receipt_id,
          "authorized_read_receipt_hash": ch_receipt.receipt_hash}
    if bundles:
        ch["bundle_id"] = bundle_ch
    (evidence_dir / "channel_evidence_fruitki.json").write_text(json.dumps(ch))
    (receipt_dir / f"{ch_receipt.receipt_id}.json").write_text(json.dumps(ch_receipt.to_dict()))

    bundle_snap = "oracle-forged-snapshot" if bundles else ""
    snap_core = {
        "schema_version": "2.0", "platform": "YOUTUBE", "channel_id": CHANNEL,
        "uploads_playlist_id": "UU" + CHANNEL[2:], "endpoint": "youtube.playlistItems.list",
        "retrieved_at": now, "scope_reference": ch_core["scope_reference"], "items_checked": 0,
        "page_count": 1, "coverage_complete": True, "pagination_terminal_state": "ZERO_ITEM_TERMINAL",
        "video_ids": [], "recent_items_metadata": [],
    }
    snap_hash = compute_payload_hash(snap_core)
    snap_receipt = ProvenanceReceipt._create_internal(
        bundle_id=bundle_snap, provenance_source=ProvenanceSource.ACTUAL_PROVIDER_READ.value,
        trust_domain=TrustDomain.AUTHORIZED_PROVIDER_READ_OBSERVED.value,
        operation="playlistItems.list", endpoint="youtube.playlistItems.list",
        request_parameters_safe={"part": "snippet,contentDetails", "playlistId": snap_core["uploads_playlist_id"], "maxResults": 50},
        authenticated_channel_id=CHANNEL, scope_reference=ch_core["scope_reference"],
        started_at=now, completed_at=now, result_count=0, page_count=1,
        next_page_token_present=False, coverage_complete=True, payload_evidence_hash=snap_hash,
    )
    snap = {**snap_core, "payload_evidence_hash": snap_hash,
            "authorized_read_receipt_id": snap_receipt.receipt_id,
            "authorized_read_receipt_hash": snap_receipt.receipt_hash}
    if bundles:
        snap["bundle_id"] = bundle_snap
    (evidence_dir / "youtube_uploads_snapshot_fruitki.json").write_text(json.dumps(snap))
    (receipt_dir / f"{snap_receipt.receipt_id}.json").write_text(json.dumps(snap_receipt.to_dict()))
    duplicate = build_package_duplicate_preflight(
        publication_fingerprint=pkg["publication_dedupe_fingerprint"], media_sha256=pkg["media_sha256"],
        target_channel_id=CHANNEL, channel_evidence_hash=ch_hash, channel_receipt_hash=ch_receipt.receipt_hash,
        upload_snapshot_hash=snap_hash, upload_snapshot_receipt_hash=snap_receipt.receipt_hash,
        items_checked=0, page_count=1, coverage_complete=True, duplicate_match=False, checked_at=now,
    )
    dup_path = evidence_dir / "oracle-duplicate.json"
    dup_path.write_text(json.dumps(duplicate))
    pkg.update(channel_evidence_hash=ch_hash, duplicate_preflight_path=str(dup_path))
    package_path.write_text(json.dumps(pkg))


class Mission141CAcceptanceOracle(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="codex_141c_")
        self.root = Path(self.tmp.name)
        self.orchestrator = PrivateUploadDryRunOrchestrator(sandbox_dir=self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def test_t1_internal_receipt_forge_never_reaches_ready(self):
        package, _, audience = self.orchestrator.setup_fixture_environment()
        install_forged_authorized_evidence(self.root, package)
        result = ReleaseAcceptanceGate(self.root, allow_test_fixtures=False).evaluate_package(package, audience)
        self.assertNotEqual(result.result, "READY_FOR_PRIVATE_UPLOAD_APPROVAL")

    def test_t2_receipt_without_committed_bundle_never_reaches_ready(self):
        package, _, audience = self.orchestrator.setup_fixture_environment()
        install_forged_authorized_evidence(self.root, package, bundles=False)
        result = ReleaseAcceptanceGate(self.root, allow_test_fixtures=False).evaluate_package(package, audience)
        self.assertNotEqual(result.result, "READY_FOR_PRIVATE_UPLOAD_APPROVAL")

    def test_a2_caller_audience_object_is_not_production_authority(self):
        package, _, audience = self.orchestrator.setup_fixture_environment()
        result = ReleaseAcceptanceGate(self.root, allow_test_fixtures=True).evaluate_package(package, audience)
        self.assertNotEqual(result.result, "READY_FOR_PRIVATE_UPLOAD_APPROVAL")

    def test_p1_caller_record_cannot_replace_registry_record(self):
        package, registered, audience = self.orchestrator.setup_fixture_environment()
        reg = self.root / "events" / "approvals" / "registry" / f"{registered.approval_id}.json"
        stored = json.loads(reg.read_text())
        stored["metadata_revision_hash"] = "different-durable-metadata"
        reg.write_text(json.dumps(stored))
        result = self.orchestrator.executor.execute_private_upload(
            package, registered, audience_record=audience,
            upload_mutation_mock=MockYouTubeUploadProvider().upload_video,
        )
        self.assertEqual(result.status, "BLOCKED")

    def test_o4_arbitrary_callback_cannot_reconcile(self):
        package, approval, audience = self.orchestrator.setup_fixture_environment()
        crash = self.orchestrator.executor.execute_private_upload(
            package, approval, audience_record=audience, simulate_crash_at="DURING_DISPATCH",
        )
        ok, code, _ = self.orchestrator.executor.reconcile_uncertain_operation(
            crash.operation_id, approval.publication_fingerprint, approval.approval_id,
            reconciliation_provider=lambda known, fp: (True, {
                "videoId": "CALLER_SUPPLIED", "privacyStatus": "private", "channelId": CHANNEL,
            }),
        )
        self.assertFalse(ok, f"callback bypassed reconciliation with {code}")

    def test_o1_o2_unfenced_transition_cannot_mutate_reserved_state(self):
        ledger = PublicationLedger(self.root / "events" / "publications")
        ledger.reserve("oracle-fence", CHANNEL, "media", "current-fence")
        # The public convenience API has no expected-state or owner token.  A
        # remediated implementation must reject or make this a no-op.
        ledger.transition_state("oracle-fence", PublicationState.UPLOADED_PRIVATE)
        self.assertEqual(ledger.get_state("oracle-fence"), PublicationState.RESERVED)

    def test_r1_stale_refresh_requires_controlled_production_service(self):
        source = Path("scripts/private_upload_executor.py").read_text()
        self.assertTrue(
            "ProductionAuthorizedYouTubeReadService.capture_upload_snapshot" in source,
            "stale path lacks controlled production refresh",
        )
        self.assertTrue(
            "TestFixtureYouTubeReadService.create_upload_snapshot_fixture" not in source,
            "stale path retains fixture refresh",
        )


if __name__ == "__main__":
    unittest.main()
