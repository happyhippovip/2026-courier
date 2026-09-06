#!/usr/bin/env python3
"""Phase A, B, and C targeted tests for Mission 131G.

Covers:
- ProvenanceReceipt cryptographic integrity & tampering detection
- Evidence payload hash binding
- Channel freshness (24h) & Duplicate snapshot freshness (15m)
- Package-specific duplicate preflight binding validations
- Non-overclaiming duplicate semantics (NO_MATCHING_PLATFORM_METADATA_FOUND)
- True interprocess atomic reservation (O_CREAT | O_EXCL) with multiprocessing single-winner proof
- Wrong-owner release protection
"""

from __future__ import annotations

import datetime
import hashlib
import json
import multiprocessing
import os
import shutil
import tempfile
import time
import unittest
from pathlib import Path

from scripts.creator_input_sources import compute_publication_dedupe_fingerprint
from scripts.evidence_provenance import (
    CHANNEL_IDENTITY_MAX_AGE_SECONDS,
    DUPLICATE_SNAPSHOT_MAX_AGE_SECONDS,
    ProvenanceReceipt,
    build_channel_evidence_package,
    build_package_duplicate_preflight,
    build_upload_snapshot_evidence_package,
    compute_payload_hash,
)
from scripts.publication_engine import (
    AuthorizationRecord,
    PublicationEngine,
    PublicationLedger,
    PublicationState,
)

REPO_ROOT = Path(__file__).resolve().parent.parent


def _concurrent_reserve_worker(
    ledger_dir_str: str,
    fingerprint: str,
    token: str,
    result_queue: multiprocessing.Queue,
):
    """Worker process for multiprocessing atomic race test."""
    ledger = PublicationLedger(Path(ledger_dir_str))
    ok, code, data = ledger.reserve(
        fingerprint=fingerprint,
        target_channel_id="UCg0O_a10jsQ74ffS_HgFGqA",
        media_sha256="test_sha",
        reservation_token=token,
    )
    result_queue.put({"ok": ok, "code": code, "token": token, "pid": os.getpid()})


class TestEvidenceProvenanceMission131G(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="pub_131g_test_"))
        self.engine = PublicationEngine(repo_dir=self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    # ----------------------------------------------------
    # PHASE A: PROVENANCE & FRESHNESS TESTS
    # ----------------------------------------------------

    def test_provenance_receipt_integrity_and_tampering(self):
        rcpt = ProvenanceReceipt.create(
            operation="channels.list",
            endpoint="youtube.channels.list",
            request_parameters_safe={"mine": True},
            authenticated_channel_id="UCg0O_a10jsQ74ffS_HgFGqA",
            scope_reference="https://www.googleapis.com/auth/youtube.force-ssl",
            started_at="2026-08-31T11:00:00Z",
            completed_at="2026-08-31T11:00:01Z",
            result_count=1,
            page_count=1,
            next_page_token_present=False,
            coverage_complete=True,
            payload_evidence_hash="mock_hash_123",
        )
        self.assertTrue(rcpt.verify_integrity())

        # Tampered receipt fails
        tampered = ProvenanceReceipt(
            receipt_id=rcpt.receipt_id,
            provider=rcpt.provider,
            platform=rcpt.platform,
            provenance_source=rcpt.provenance_source,
            operation=rcpt.operation,
            endpoint=rcpt.endpoint,
            request_parameters_safe=rcpt.request_parameters_safe,
            authenticated_channel_id="TAMPERED_CHANNEL_ID",
            scope_reference=rcpt.scope_reference,
            started_at=rcpt.started_at,
            completed_at=rcpt.completed_at,
            result_count=rcpt.result_count,
            page_count=rcpt.page_count,
            next_page_token_present=rcpt.next_page_token_present,
            coverage_complete=rcpt.coverage_complete,
            payload_evidence_hash=rcpt.payload_evidence_hash,
            receipt_hash=rcpt.receipt_hash,
        )
        self.assertFalse(tampered.verify_integrity())

    def _create_mock_environment(
        self,
        *,
        channel_age_seconds: float = 0.0,
        snapshot_age_seconds: float = 0.0,
        tamper_channel_payload: bool = False,
        missing_provenance: bool = False,
        coverage_complete: bool = True,
        duplicate_match: bool = False,
        fp_override: str | None = None,
        media_override: str | None = None,
        channel_override: str | None = None,
        audience_decision: str = "NOT_MADE_FOR_KIDS",
    ) -> tuple[Path, AuthorizationRecord]:
        pkg_dir = self.test_dir / "mock_pkg"
        pkg_dir.mkdir(parents=True, exist_ok=True)
        ev_dir = self.test_dir / "events" / "evidence"
        rcpt_dir = self.test_dir / "events" / "receipts"
        ev_dir.mkdir(parents=True, exist_ok=True)
        rcpt_dir.mkdir(parents=True, exist_ok=True)

        now_dt = datetime.datetime.now(datetime.timezone.utc)
        ch_ts = (now_dt - datetime.timedelta(seconds=channel_age_seconds)).isoformat()
        snap_ts = (now_dt - datetime.timedelta(seconds=snapshot_age_seconds)).isoformat()

        # 1. Channel Evidence & Receipt
        ch_id = channel_override or "UCg0O_a10jsQ74ffS_HgFGqA"
        ch_ev, ch_rcpt = build_channel_evidence_package(
            channel_id=ch_id,
            channel_handle="@kifruchtefilme",
            channel_title="FruitKI",
            retrieved_at=ch_ts,
            started_at=ch_ts,
        )
        if tamper_channel_payload:
            ch_ev["channel_title"] = "Tampered Title"
        if missing_provenance:
            ch_ev.pop("authorized_read_receipt_id", None)
            ch_ev.pop("authorized_read_receipt_hash", None)
        else:
            (rcpt_dir / f"{ch_rcpt.receipt_id}.json").write_text(json.dumps(ch_rcpt.to_dict(), indent=2), encoding="utf-8")

        ch_ev_path = ev_dir / "channel_evidence_fruitki.json"
        ch_ev_path.write_text(json.dumps(ch_ev, indent=2), encoding="utf-8")

        # 2. Upload Snapshot Evidence & Receipt
        snap_ev, snap_rcpt = build_upload_snapshot_evidence_package(
            channel_id=ch_id,
            uploads_playlist_id=f"UU{ch_id[2:]}",
            video_ids=["V1", "V2", "V3"],
            coverage_complete=coverage_complete,
            retrieved_at=snap_ts,
            started_at=snap_ts,
        )
        (rcpt_dir / f"{snap_rcpt.receipt_id}.json").write_text(json.dumps(snap_rcpt.to_dict(), indent=2), encoding="utf-8")
        (ev_dir / "youtube_uploads_snapshot_fruitki.json").write_text(json.dumps(snap_ev, indent=2), encoding="utf-8")

        # 3. Media & QC
        media_bytes = b"sample_video_payload_mission_131g"
        media_path = pkg_dir / "render.mp4"
        media_path.write_bytes(media_bytes)
        media_sha = media_override or hashlib.sha256(media_bytes).hexdigest()

        qc_path = pkg_dir / "qc_report.json"
        qc_path.write_text(json.dumps({"verdict": "PASS", "source_hash": media_sha}), encoding="utf-8")

        # 4. Duplicate Preflight
        canonical_fp = compute_publication_dedupe_fingerprint(
            platform="YOUTUBE", target_channel_id=ch_id, media_sha256=media_sha
        )
        fp = fp_override or canonical_fp

        dup_rec = build_package_duplicate_preflight(
            publication_fingerprint=fp,
            media_sha256=media_sha,
            target_channel_id=ch_id,
            channel_evidence_hash=ch_ev.get("payload_evidence_hash", "mock_hash"),
            channel_receipt_hash=ch_rcpt.receipt_hash if not missing_provenance else "missing",
            upload_snapshot_hash=snap_ev["payload_evidence_hash"],
            upload_snapshot_receipt_hash=snap_rcpt.receipt_hash,
            items_checked=3,
            page_count=1,
            coverage_complete=coverage_complete,
            duplicate_match=duplicate_match,
            checked_at=snap_ts,
        )
        dup_ev_path = ev_dir / f"duplicate_preflight_{fp[:16]}.json"
        dup_ev_path.write_text(json.dumps(dup_rec, indent=2), encoding="utf-8")

        # 5. Package
        pkg_path = pkg_dir / "publish_package.json"
        pkg_path.write_text(json.dumps({
            "schema_version": "2.2",
            "platform": "YOUTUBE",
            "target_channel_id": ch_id,
            "target_channel_handle": "@kifruchtefilme",
            "token_reference": "fruitki-test",
            "channel_evidence_path": str(ch_ev_path),
            "channel_evidence_hash": ch_ev.get("payload_evidence_hash", ""),
            "channel_verified_at": ch_ts,
            "duplicate_preflight_path": str(dup_ev_path),
            "duplicate_preflight_result": dup_rec["result"],
            "content_title": "Test Title #Shorts",
            "description_draft": "Test description draft",
            "tags": ["FruitKI", "Shorts"],
            "hashtags": ["#Shorts", "#FruitKI"],
            "category_id": "22",
            "audience_decision": audience_decision,
            "self_declared_made_for_kids": (audience_decision == "MADE_FOR_KIDS"),
            "intended_upload_privacy": "private",
            "intended_release_privacy": "public",
            "media_path": str(media_path),
            "media_sha256": media_sha,
            "qc_report_path": str(qc_path),
            "qc_status": "PASS",
            "publication_dedupe_fingerprint": fp,
            "publication_authorized": True,
            "publication_state": "COMPLETE_READY_FOR_REVIEW",
            "prepared_at": ch_ts,
        }), encoding="utf-8")

        auth_record = AuthorizationRecord(
            approval_id="app-131-test",
            package_fingerprint=fp,
            approved_action="PRIVATE_UPLOAD",
            approved_channel=ch_id,
            approved_privacy="private",
            approved_at=ch_ts,
            authorization_source="EXPLICIT_HUMAN_APPROVAL",
        )
        return pkg_path, auth_record

    def test_stale_channel_evidence_rejected_24h(self):
        pkg_path, auth = self._create_mock_environment(channel_age_seconds=86500.0)
        res = self.engine.validate_package(pkg_path, auth)
        self.assertFalse(res.valid)
        self.assertEqual(res.code, "CHANNEL_EVIDENCE_STALE")

    def test_stale_duplicate_snapshot_rejected_15m(self):
        pkg_path, auth = self._create_mock_environment(snapshot_age_seconds=1000.0)
        res = self.engine.validate_package(pkg_path, auth)
        self.assertFalse(res.valid)
        self.assertEqual(res.code, "DUPLICATE_CHECK_STALE")

    def test_missing_provenance_rejected(self):
        pkg_path, auth = self._create_mock_environment(missing_provenance=True)
        res = self.engine.validate_package(pkg_path, auth)
        self.assertFalse(res.valid)
        self.assertEqual(res.code, "EVIDENCE_PROVENANCE_REQUIRED")

    def test_channel_payload_tampering_rejected(self):
        pkg_path, auth = self._create_mock_environment(tamper_channel_payload=True)
        res = self.engine.validate_package(pkg_path, auth)
        self.assertFalse(res.valid)
        self.assertEqual(res.code, "CHANNEL_EVIDENCE_HASH_MISMATCH")

    # ----------------------------------------------------
    # PHASE B: DUPLICATE PREFLIGHT BINDINGS & SEMANTICS
    # ----------------------------------------------------

    def test_duplicate_preflight_fingerprint_mismatch_rejected(self):
        pkg_path, auth = self._create_mock_environment(fp_override="wrong_fingerprint_hash")
        res = self.engine.validate_package(pkg_path, auth)
        self.assertFalse(res.valid)
        self.assertEqual(res.code, "DEDUPE_FINGERPRINT_MISMATCH")

    def test_duplicate_preflight_incomplete_coverage_rejected(self):
        pkg_path, auth = self._create_mock_environment(coverage_complete=False)
        res = self.engine.validate_package(pkg_path, auth)
        self.assertFalse(res.valid)
        self.assertEqual(res.code, "DUPLICATE_CHECK_INCOMPLETE")

    def test_duplicate_preflight_duplicate_match_rejected(self):
        pkg_path, auth = self._create_mock_environment(duplicate_match=True)
        res = self.engine.validate_package(pkg_path, auth)
        self.assertFalse(res.valid)
        self.assertEqual(res.code, "DUPLICATE_MATCH_FOUND")

    # ----------------------------------------------------
    # PHASE C: TRUE INTERPROCESS ATOMIC RESERVATION
    # ----------------------------------------------------

    def test_multiprocess_atomic_reservation_single_winner(self):
        """Regression test: multiple concurrent processes attempt to reserve the same slot."""
        fp = "multiprocess_test_fingerprint_131g"
        claims_ledger_dir = self.test_dir / "events" / "publications"
        claims_ledger_dir.mkdir(parents=True, exist_ok=True)

        queue = multiprocessing.Queue()
        processes = []
        process_count = 6

        for i in range(process_count):
            p = multiprocessing.Process(
                target=_concurrent_reserve_worker,
                args=(str(claims_ledger_dir), fp, f"token-{i}", queue),
            )
            processes.append(p)

        for p in processes:
            p.start()
        for p in processes:
            p.join(timeout=5)

        results = []
        while not queue.empty():
            results.append(queue.get())

        self.assertEqual(len(results), process_count)
        winners = [r for r in results if r["ok"] is True]
        losers = [r for r in results if r["ok"] is False]

        self.assertEqual(len(winners), 1, "Exactly ONE process must win the atomic reservation")
        self.assertEqual(len(losers), process_count - 1)
        for loser in losers:
            self.assertEqual(loser["code"], "ALREADY_RESERVED")

    def test_wrong_owner_release_blocked(self):
        ledger = PublicationLedger(self.test_dir / "events" / "publications")
        fp = "release_owner_test_fp"

        ok, code, _ = ledger.reserve(
            fingerprint=fp,
            target_channel_id="UCg0O_a10jsQ74ffS_HgFGqA",
            media_sha256="sha_test",
            reservation_token="correct_token_123",
        )
        self.assertTrue(ok)

        # Release with wrong token fails
        rel_ok, rel_code = ledger.release_claim(fp, "wrong_token_456")
        self.assertFalse(rel_ok)
        self.assertEqual(rel_code, "WRONG_OWNER_RELEASE_BLOCKED")

        # Release with correct token succeeds
        rel_ok2, rel_code2 = ledger.release_claim(fp, "correct_token_123")
        self.assertTrue(rel_ok2)
        self.assertEqual(rel_code2, "RELEASED")

    # ----------------------------------------------------
    # REAL PACKAGE CANARY
    # ----------------------------------------------------

    def test_real_packages_stop_at_audience_decision_required(self):
        """Verify real Golden Trophy and Mystery Box packages pass provenance and stop at audience gate."""
        real_engine = PublicationEngine(repo_dir=REPO_ROOT)

        gt_pkg = REPO_ROOT / "runtime" / "content" / "golden_trophy_short" / "publish_package.json"
        gt_res = real_engine.validate_package(gt_pkg)
        self.assertFalse(gt_res.valid)
        self.assertEqual(gt_res.code, "AUDIENCE_DECISION_REQUIRED")

        mb_pkg = REPO_ROOT / "runtime" / "content" / "mystery_box_short" / "publish_package.json"
        mb_res = real_engine.validate_package(mb_pkg)
        self.assertFalse(mb_res.valid)
        self.assertEqual(mb_res.code, "AUDIENCE_DECISION_REQUIRED")


if __name__ == "__main__":
    unittest.main()
