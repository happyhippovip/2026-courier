#!/usr/bin/env python3
"""Phase A & B targeted tests for Mission 130G Approval Contract & Human Decision Gate."""

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.creator_input_sources import compute_publication_dedupe_fingerprint
from scripts.publication_approval import (
    AppendOnlyApprovalLedger,
    ApprovalAction,
    ApprovalRecord,
    ApprovalState,
    AudienceDecisionRecord,
    AudienceDecisionState,
    OperationOutcome,
    PublicationApprovalContract,
    ReleaseOperationLedger,
    apply_human_audience_decision,
    compute_metadata_revision_hash,
    generate_human_decision_card,
)

REPO_ROOT = Path(__file__).resolve().parent.parent


class TestPublicationApprovalMission130G(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="pub_130g_test_"))
        self.contract = PublicationApprovalContract(repo_dir=self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def _create_mock_package_data(
        self,
        *,
        channel_id: str = "UCg0O_a10jsQ74ffS_HgFGqA",
        media_sha: str = "bd87cc42f7c98f92148b39b01e6cebfd4f451f61152fc01319aa3d8d500a88d8",
        title: str = "Test Title #Shorts",
        desc: str = "Test description draft",
        audience_decision: str = "NOT_MADE_FOR_KIDS",
    ) -> dict:
        fp = compute_publication_dedupe_fingerprint(
            platform="YOUTUBE",
            target_channel_id=channel_id,
            media_sha256=media_sha,
        )
        pkg = {
            "schema_version": "2.1",
            "platform": "YOUTUBE",
            "target_channel_id": channel_id,
            "target_channel_handle": "@kifruchtefilme",
            "token_reference": "fruitki-test",
            "channel_evidence_path": "events/evidence/channel_evidence_fruitki.json",
            "channel_evidence_hash": "43c69e1e6e25d1b58456e482c91d33158581be5343aea7f5f327908f8058d539",
            "channel_verified_at": "2026-08-31T09:04:14+00:00",
            "duplicate_preflight_path": "events/evidence/duplicate_preflight_c42c6830a2b5f3d4.json",
            "duplicate_preflight_result": "NO_DUPLICATE_FOUND",
            "content_title": title,
            "description_draft": desc,
            "tags": ["FruitKI", "Shorts"],
            "hashtags": ["#Shorts", "#FruitKI"],
            "category_id": "22",
            "audience_decision": audience_decision,
            "self_declared_made_for_kids": (audience_decision == "MADE_FOR_KIDS"),
            "intended_upload_privacy": "private",
            "intended_release_privacy": "public",
            "media_path": "/path/to/render.mp4",
            "media_sha256": media_sha,
            "qc_report_path": "/path/to/qc.json",
            "qc_status": "PASS",
            "publication_dedupe_fingerprint": fp,
            "publication_authorized": False,
            "publication_state": "COMPLETE_READY_FOR_REVIEW",
            "prepared_at": "2026-08-31T09:15:00+00:00",
        }
        return pkg

    def _create_approval(
        self,
        pkg: dict,
        *,
        state: str = ApprovalState.ACTIVE.value,
        action: str = ApprovalAction.PRIVATE_UPLOAD.value,
        privacy: str = "private",
        video_id: str | None = None,
        max_cost: float = 0.0,
    ) -> ApprovalRecord:
        meta_hash = compute_metadata_revision_hash(pkg)
        return ApprovalRecord(
            approval_id="app-130-test",
            state=state,
            approved_action=action,
            publication_fingerprint=pkg["publication_dedupe_fingerprint"],
            media_sha256=pkg["media_sha256"],
            platform=pkg["platform"],
            target_channel_id=pkg["target_channel_id"],
            platform_video_id=video_id,
            approved_privacy=privacy,
            metadata_revision_hash=meta_hash,
            audience_decision_hash="mock_aud_hash",
            channel_evidence_hash=pkg["channel_evidence_hash"],
            duplicate_evidence_hash="mock_dup_hash",
            maximum_allowed_cost_eur=max_cost,
            authorization_source="EXPLICIT_HUMAN_APPROVAL",
            approved_at="2026-08-31T11:00:00Z",
        )

    # ----------------------------------------------------
    # PHASE A TESTS
    # ----------------------------------------------------

    def test_valid_private_approval(self):
        pkg = self._create_mock_package_data()
        app = self._create_approval(pkg, action="PRIVATE_UPLOAD", privacy="private")
        valid, code, _ = self.contract.validate_approval_for_execution(app, pkg, "PRIVATE_UPLOAD")
        self.assertTrue(valid)
        self.assertEqual(code, "APPROVAL_VALID")

    def test_action_mismatch_rejected(self):
        pkg = self._create_mock_package_data()
        app = self._create_approval(pkg, action="PRIVATE_UPLOAD", privacy="private")
        valid, code, _ = self.contract.validate_approval_for_execution(app, pkg, "PUBLIC_RELEASE")
        self.assertFalse(valid)
        self.assertEqual(code, "APPROVAL_ACTION_MISMATCH")

    def test_wrong_privacy_for_upload_rejected(self):
        pkg = self._create_mock_package_data()
        app = self._create_approval(pkg, action="PRIVATE_UPLOAD", privacy="public")
        valid, code, _ = self.contract.validate_approval_for_execution(app, pkg, "PRIVATE_UPLOAD")
        self.assertFalse(valid)
        self.assertEqual(code, "INVALID_PRIVACY_FOR_PRIVATE_UPLOAD")

    def test_public_release_missing_video_id_rejected(self):
        pkg = self._create_mock_package_data()
        app = self._create_approval(pkg, action="PUBLIC_RELEASE", privacy="public", video_id=None)
        valid, code, _ = self.contract.validate_approval_for_execution(app, pkg, "PUBLIC_RELEASE")
        self.assertFalse(valid)
        self.assertEqual(code, "PUBLIC_RELEASE_MISSING_VIDEO_ID")

    def test_changed_metadata_editorial_reconfirmation_required(self):
        pkg = self._create_mock_package_data()
        app = self._create_approval(pkg, action="PRIVATE_UPLOAD", privacy="private")
        # Edit title only
        pkg["content_title"] = "New Editorial Title #Shorts"
        valid, code, _ = self.contract.validate_approval_for_execution(app, pkg, "PRIVATE_UPLOAD")
        self.assertFalse(valid)
        self.assertEqual(code, "EDITORIAL_RECONFIRMATION_REQUIRED")

    def test_changed_master_rejected(self):
        pkg = self._create_mock_package_data()
        app = self._create_approval(pkg, action="PRIVATE_UPLOAD", privacy="private")
        pkg["media_sha256"] = "different_sha_256_hash"
        valid, code, _ = self.contract.validate_approval_for_execution(app, pkg, "PRIVATE_UPLOAD")
        self.assertFalse(valid)
        self.assertEqual(code, "APPROVAL_MEDIA_MISMATCH")

    def test_terminal_approval_states_rejected(self):
        pkg = self._create_mock_package_data()
        for state in (ApprovalState.CONSUMED, ApprovalState.REVOKED, ApprovalState.INVALIDATED):
            app = self._create_approval(pkg, state=state.value)
            valid, code, _ = self.contract.validate_approval_for_execution(app, pkg, "PRIVATE_UPLOAD")
            self.assertFalse(valid)
            self.assertEqual(code, f"APPROVAL_{state.value}")

    def test_money_gate_firewall(self):
        pkg = self._create_mock_package_data()
        app_costly = self._create_approval(pkg, max_cost=5.0)
        valid, code, _ = self.contract.validate_approval_for_execution(app_costly, pkg, "PRIVATE_UPLOAD")
        self.assertFalse(valid)
        self.assertEqual(code, "PAYMENT_APPROVAL_REQUIRED")

    def test_metadata_revision_hash_stability_and_invariance(self):
        pkg1 = self._create_mock_package_data(title="Title A", desc="Desc A")
        h1 = compute_metadata_revision_hash(pkg1)

        # Whitespace normalization in title
        pkg1_ws = self._create_mock_package_data(title="Title   A  ", desc="Desc A")
        self.assertEqual(h1, compute_metadata_revision_hash(pkg1_ws))

        # Media change does NOT alter metadata revision hash
        pkg1_diff_media = self._create_mock_package_data(title="Title A", desc="Desc A", media_sha="000000")
        self.assertEqual(h1, compute_metadata_revision_hash(pkg1_diff_media))

        # Description change DOES alter metadata revision hash
        pkg1_diff_desc = self._create_mock_package_data(title="Title A", desc="Desc B")
        self.assertNotEqual(h1, compute_metadata_revision_hash(pkg1_diff_desc))

    def test_append_only_approval_ledger_integrity(self):
        ledger = AppendOnlyApprovalLedger(self.test_dir / "events" / "approvals")
        ledger.record_event(
            approval_id="app-1",
            approval_state=ApprovalState.ACTIVE.value,
            publication_fingerprint="fp-1",
            action="PRIVATE_UPLOAD",
            reason="Human approval granted",
        )
        ledger.record_event(
            approval_id="app-1",
            approval_state=ApprovalState.CONSUMED.value,
            publication_fingerprint="fp-1",
            action="PRIVATE_UPLOAD",
            reason="Upload confirmed on platform",
        )
        valid, msg = ledger.verify_integrity()
        self.assertTrue(valid)
        self.assertEqual(msg, "VALID_CHAIN")

        # Verify tampering detection
        data = json.loads(ledger.ledger_file.read_text(encoding="utf-8"))
        data[0]["reason"] = "Tampered reason"
        ledger.ledger_file.write_text(json.dumps(data), encoding="utf-8")
        valid_tampered, msg_tampered = ledger.verify_integrity()
        self.assertFalse(valid_tampered)

    def test_release_operation_intent_and_crash_safety(self):
        op_ledger = ReleaseOperationLedger(self.test_dir / "events" / "operations")
        op_id = op_ledger.record_intent(
            approval_id="app-100",
            publication_fingerprint="fp-100",
            requested_action="PRIVATE_UPLOAD",
            state_before="RESERVED",
        )
        self.assertTrue(op_id.startswith("op-"))

        # Check intent persisted before external mutation
        ops = op_ledger._read_ops()
        self.assertEqual(len(ops), 1)
        self.assertEqual(ops[0]["outcome"], OperationOutcome.INTENT_RECORDED.value)

        # Ambiguous failure updates to EXTERNAL_OUTCOME_UNCERTAIN
        op_ledger.update_outcome(
            op_id,
            outcome=OperationOutcome.EXTERNAL_OUTCOME_UNCERTAIN,
            state_after="EXTERNAL_OUTCOME_UNCERTAIN",
            evidence_reference="socket_timeout_err",
        )
        ops_after = op_ledger._read_ops()
        self.assertEqual(ops_after[0]["outcome"], OperationOutcome.EXTERNAL_OUTCOME_UNCERTAIN.value)

    # ----------------------------------------------------
    # PHASE B TESTS
    # ----------------------------------------------------

    def test_human_decision_card_generation(self):
        pkg_dir = self.test_dir / "golden_trophy_short"
        pkg_dir.mkdir(parents=True, exist_ok=True)
        pkg_path = pkg_dir / "publish_package.json"
        pkg_data = self._create_mock_package_data(title="Wer kriegt die goldene Trophäe? 🏆🍓🥝 #Shorts")
        pkg_path.write_text(json.dumps(pkg_data, indent=2), encoding="utf-8")

        card = generate_human_decision_card(pkg_path)
        self.assertEqual(card["content_id"], "golden_trophy_short")
        self.assertEqual(card["title"], "Wer kriegt die goldene Trophäe? 🏆🍓🥝 #Shorts")
        self.assertEqual(card["short_master_hash"], "bd87cc42f7c98f92")
        self.assertEqual(card["requested_human_decision"], "MADE_FOR_KIDS | NOT_MADE_FOR_KIDS")
        self.assertFalse(card["publication_authorized"])
        self.assertEqual(card["expected_cost"], "0 EUR")

    def test_apply_human_audience_decision_success(self):
        pkg_dir = self.test_dir / "mystery_box_short"
        pkg_dir.mkdir(parents=True, exist_ok=True)
        pkg_path = pkg_dir / "publish_package.json"
        pkg_data = self._create_mock_package_data()
        pkg_path.write_text(json.dumps(pkg_data, indent=2), encoding="utf-8")

        dec_record = AudienceDecisionRecord.create(
            content_id="mystery_box_short",
            decision=AudienceDecisionState.NOT_MADE_FOR_KIDS.value,
            decision_source="HUMAN_EXPLICIT_REVIEW",
            evidence_reference="strawberry_mystery_box.gd",
            media_sha256=pkg_data["media_sha256"],
            publication_fingerprint=pkg_data["publication_dedupe_fingerprint"],
        )

        ok, code, details = apply_human_audience_decision(pkg_path, dec_record, repo_dir=self.test_dir)
        self.assertTrue(ok)
        self.assertEqual(code, "AUDIENCE_DECISION_APPLIED")
        self.assertEqual(details["next_blocker"], "APPROVAL_REQUIRED")

        # Package is updated with decision, but NOT authorized
        updated_pkg = json.loads(pkg_path.read_text(encoding="utf-8"))
        self.assertEqual(updated_pkg["audience_decision"], "NOT_MADE_FOR_KIDS")
        self.assertFalse(updated_pkg["self_declared_made_for_kids"])
        self.assertFalse(updated_pkg["publication_authorized"])

    def test_apply_human_audience_decision_asset_mismatch_rejected(self):
        pkg_dir = self.test_dir / "golden_trophy_short"
        pkg_dir.mkdir(parents=True, exist_ok=True)
        pkg_path = pkg_dir / "publish_package.json"
        pkg_data = self._create_mock_package_data()
        pkg_path.write_text(json.dumps(pkg_data, indent=2), encoding="utf-8")

        dec_record = AudienceDecisionRecord.create(
            content_id="golden_trophy_short",
            decision=AudienceDecisionState.MADE_FOR_KIDS.value,
            decision_source="HUMAN_EXPLICIT_REVIEW",
            evidence_reference="strawberry_golden_trophy.gd",
            media_sha256="wrong_media_sha",
            publication_fingerprint=pkg_data["publication_dedupe_fingerprint"],
        )

        ok, code, _ = apply_human_audience_decision(pkg_path, dec_record, repo_dir=self.test_dir)
        self.assertFalse(ok)
        self.assertEqual(code, "AUDIENCE_DECISION_ASSET_MISMATCH")


if __name__ == "__main__":
    unittest.main()
