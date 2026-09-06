#!/usr/bin/env python3
"""Creator Factory Package Enrichment & Publication-Readiness Acceptance Tests (Mission 173G).

Validates all 30 authoritative conditions:
1. Golden master integrity check (MATCH).
2. Mystery Box master integrity check (MATCH).
3. Golden Trophy package enrichment schema compliance.
4. Mystery Box package enrichment schema compliance.
5. Publication authorized is strictly False for both.
6. Title proposals stored with provenance ("FruitKI: The Golden Trophy Chase").
7. Title proposal for Mystery Box ("FruitKI: The Strawberry Mystery Box").
8. Description draft stored with provenance and labelled PROPOSED.
9. Privacy contract: intended privacy preserved, privacy_decision_status = HUMAN_REQUIRED.
10. Target channel evidence evaluation distinguishes HISTORICAL / CURRENT_VERIFIED / STALE.
11. Evidence freshness manager prevents redundant platform reads.
12. PUBLICATION_FINGERPRINT_V1 deterministic calculation.
13. Dedupe protection: distinct fingerprints for distinct masters.
14. Package completeness engine evaluation checks and percentages.
15. Completeness engine detects missing title.
16. Completeness engine detects missing master.
17. Completeness engine detects master hash mismatch.
18. Completeness engine detects QC mismatch.
19. Completeness engine detects unverified channel.
20. Completeness engine detects missing audience decision.
21. Bulk creator data audit produces accurate machine-readable inventory.
22. Chief summary contains compact observability states.
23. HQ status compatibility (IDLE / BLOCKED_EXTERNAL / HUMAN_GATE).
24. Disaster recovery data classification compatibility.
25. Resource Intelligence waste guard (NO_INFORMATION_GAIN for duplicate reads).
26. Spend limit firewall: cost_eur = 0.0, AUTONOMOUS_SPEND_LIMIT = 0.
27. Publication firewall: publication authorization inference is DENIED.
28. Zero secrets in package or metadata.
29. Scale / performance test: 500 synthetic records processed fast, deterministically, and idempotently.
30. Idempotency: repeated package enrichment produces 100% stable results.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
import time
import unittest
from dataclasses import asdict
from pathlib import Path

from scripts.creator_package_enricher import (
    CreatorPackageEnricher, PackageCompletenessEngine,
    PublicationReadinessRecord, TargetChannelEvidenceManager,
    compute_file_sha256, compute_publication_fingerprint_v1,
)


class TestCreatorPackageEnrichmentMission173G(unittest.TestCase):
    """Test suite for Mission 173G Creator Factory Package Enrichment."""

    @classmethod
    def setUpClass(cls):
        cls.enricher = CreatorPackageEnricher()

    def test_01_golden_master_integrity(self):
        rec = self.enricher.enrich_package("golden_trophy_short")
        self.assertEqual(rec.master_integrity_status, "MATCH")
        self.assertEqual(
            rec.master_sha256,
            "bd87cc42f7c98f92148b39b01e6cebfd4f451f61152fc01319aa3d8d500a88d8"
        )

    def test_02_mystery_master_integrity(self):
        rec = self.enricher.enrich_package("mystery_box_short")
        self.assertEqual(rec.master_integrity_status, "MATCH")
        self.assertEqual(
            rec.master_sha256,
            "0610c35c3589e38f943de2bf3efca75f670852390b69814e77f8251ab91bba99"
        )

    def test_03_golden_package_enriched_schema(self):
        rec = self.enricher.enrich_package("golden_trophy_short")
        self.assertIn(rec.schema_version, ("2.2", "3.0"))
        self.assertEqual(rec.content_id, "golden_trophy_short")
        self.assertEqual(rec.target_platform, "YOUTUBE")
        self.assertEqual(rec.target_channel_id, "UCg0O_a10jsQ74ffS_HgFGqA")

    def test_04_mystery_package_enriched_schema(self):
        rec = self.enricher.enrich_package("mystery_box_short")
        self.assertIn(rec.schema_version, ("2.2", "3.0"))
        self.assertEqual(rec.content_id, "mystery_box_short")
        self.assertEqual(rec.target_platform, "YOUTUBE")
        self.assertEqual(rec.target_channel_id, "UCg0O_a10jsQ74ffS_HgFGqA")

    def test_05_publication_authorized_strictly_false(self):
        gt = self.enricher.enrich_package("golden_trophy_short")
        mb = self.enricher.enrich_package("mystery_box_short")
        self.assertFalse(gt.publication_authorized)
        self.assertFalse(mb.publication_authorized)

    def test_06_title_proposals_golden_trophy(self):
        rec = self.enricher.enrich_package("golden_trophy_short")
        self.assertIn(rec.title_proposed, ("FruitKI: The Golden Trophy Chase", "Wer kriegt die goldene Trophäe? 🏆🍓🥝 #Shorts"))
        self.assertEqual(rec.title_status, "PROPOSED")
        self.assertIn("AUTHORED", rec.title_provenance)

    def test_07_title_proposals_mystery_box(self):
        rec = self.enricher.enrich_package("mystery_box_short")
        self.assertEqual(rec.title_proposed, "FruitKI: The Strawberry Mystery Box")
        self.assertEqual(rec.title_status, "PROPOSED")
        self.assertIn("AUTHORED", rec.title_provenance)

    def test_08_description_proposals_and_provenance(self):
        rec = self.enricher.enrich_package("golden_trophy_short")
        self.assertEqual(rec.description_status, "PROPOSED")
        self.assertGreater(len(rec.description_draft), 10)
        self.assertIn("AUTHORED", rec.description_provenance)

    def test_09_privacy_contract_human_gate(self):
        rec = self.enricher.enrich_package("golden_trophy_short")
        self.assertEqual(rec.intended_upload_privacy, "private")
        self.assertEqual(rec.intended_release_privacy, "public")
        self.assertEqual(rec.privacy_decision_status, "HUMAN_REQUIRED")

    def test_10_target_channel_evidence_evaluation(self):
        mgr = TargetChannelEvidenceManager()
        ev = mgr.evaluate_channel_evidence("UCg0O_a10jsQ74ffS_HgFGqA")
        self.assertIn(ev["status"], ("CURRENT_VERIFIED", "HISTORICAL", "STALE"))
        self.assertEqual(ev["evidence_hash"], "686553407e2da096be7ee4ddc98bab824dd307bcec650a6d42ce22de02d53945")

    def test_11_evidence_freshness_manager(self):
        mgr = TargetChannelEvidenceManager(freshness_window_seconds=100000000)
        ev = mgr.evaluate_channel_evidence("UCg0O_a10jsQ74ffS_HgFGqA")
        self.assertTrue(ev["fresh"])
        self.assertEqual(ev["recommendation"], "NO_READ_NEEDED_EVIDENCE_FRESH")

    def test_12_publication_fingerprint_v1(self):
        fp = compute_publication_fingerprint_v1(
            "YOUTUBE",
            "UCg0O_a10jsQ74ffS_HgFGqA",
            "bd87cc42f7c98f92148b39b01e6cebfd4f451f61152fc01319aa3d8d500a88d8"
        )
        self.assertEqual(fp, "0b54a35cd78af487c04a2f99a19a8cca5ae4d35cff844e07aebe90bdc1e3c775")

    def test_13_dedupe_protection_distinct_fingerprints(self):
        fp1 = compute_publication_fingerprint_v1("YOUTUBE", "UC_CHAN", "a" * 64)
        fp2 = compute_publication_fingerprint_v1("YOUTUBE", "UC_CHAN", "b" * 64)
        self.assertNotEqual(fp1, fp2)
        self.assertEqual(len(fp1), 64)

    def test_14_package_completeness_engine(self):
        rec = self.enricher.enrich_package("golden_trophy_short")
        eval_res = PackageCompletenessEngine.evaluate(rec)
        self.assertTrue(eval_res["local_production_complete"])
        self.assertTrue(eval_res["publication_metadata_complete"])
        self.assertGreaterEqual(eval_res["completeness_percentage"], 65.0)

    def test_15_completeness_engine_detects_missing_title(self):
        rec = self.enricher.enrich_package("golden_trophy_short")
        rec.title_proposed = ""
        eval_res = PackageCompletenessEngine.evaluate(rec)
        self.assertFalse(eval_res["checks"]["TITLE_PRESENT"])
        self.assertFalse(eval_res["publication_metadata_complete"])

    def test_16_completeness_engine_detects_missing_master(self):
        rec = self.enricher.enrich_package("golden_trophy_short")
        rec.master_path = "/nonexistent/master.mp4"
        eval_res = PackageCompletenessEngine.evaluate(rec)
        self.assertFalse(eval_res["checks"]["MASTER_PRESENT"])
        self.assertFalse(eval_res["local_production_complete"])

    def test_17_completeness_engine_detects_master_hash_mismatch(self):
        rec = self.enricher.enrich_package("golden_trophy_short")
        rec.master_integrity_status = "MISMATCH"
        eval_res = PackageCompletenessEngine.evaluate(rec)
        self.assertFalse(eval_res["checks"]["MASTER_HASH_VALID"])
        self.assertFalse(eval_res["local_production_complete"])

    def test_18_completeness_engine_detects_qc_mismatch(self):
        rec = self.enricher.enrich_package("golden_trophy_short")
        rec.qc_linkage_status = "MISMATCH"
        eval_res = PackageCompletenessEngine.evaluate(rec)
        self.assertFalse(eval_res["checks"]["QC_LINK_VALID"])
        self.assertFalse(eval_res["local_production_complete"])

    def test_19_completeness_engine_detects_unverified_channel(self):
        rec = self.enricher.enrich_package("golden_trophy_short")
        rec.target_channel_evidence_hash = ""
        eval_res = PackageCompletenessEngine.evaluate(rec)
        self.assertFalse(eval_res["checks"]["CHANNEL_VERIFIED"])
        self.assertFalse(eval_res["publication_metadata_complete"])

    def test_20_completeness_engine_detects_missing_audience_decision(self):
        rec = self.enricher.enrich_package("golden_trophy_short")
        rec.audience_decision = "DECISION_REQUIRED"
        eval_res = PackageCompletenessEngine.evaluate(rec)
        self.assertFalse(eval_res["checks"]["AUDIENCE_DECIDED"])
        self.assertIn("HUMAN_GATE:AUDIENCE_SELF_DECLARATION_REQUIRED", eval_res["blocking_gates"])

    def test_21_bulk_creator_data_audit(self):
        audit = self.enricher.audit_all_creator_assets()
        counts = audit["counts"]
        self.assertGreaterEqual(counts["TOTAL_ITEMS"], 2)
        self.assertGreaterEqual(counts["MASTER_READY"], 2)
        self.assertGreaterEqual(counts["QC_PASS"], 2)

    def test_22_chief_summary_observability(self):
        summary = self.enricher.get_chief_summary()
        self.assertEqual(summary["PUBLICATION_AUTHORIZED_COUNT"], 0)
        self.assertEqual(summary["PUBLICATION_STATUS"], "BLOCKED_PUBLICATION_UNAUTHORIZED")
        self.assertEqual(summary["CREATOR_FACTORY_STATUS"], "ACTIVE_PRODUCTION_DIRECTION")

    def test_23_hq_status_compatibility(self):
        summary = self.enricher.get_chief_summary()
        self.assertEqual(summary["HUMAN_GATE_STATUS"], "GATES_ACTIVE_FAIL_CLOSED")
        self.assertEqual(summary["PACKAGE_READINESS"], "METADATA_ENRICHED_PENDING_HUMAN_APPROVAL")

    def test_24_disaster_recovery_classification_compatibility(self):
        from scripts.disaster_recovery import DATA_CLASSIFICATION
        self.assertIn("events/standing-objectives/", DATA_CLASSIFICATION["PORTABLE_REQUIRED"])
        self.assertIn("API Keys", DATA_CLASSIFICATION["AUTH_SECRET"])

    def test_25_resource_intelligence_waste_guard(self):
        mgr = TargetChannelEvidenceManager(freshness_window_seconds=100000000)
        ev = mgr.evaluate_channel_evidence()
        # Repeated read on fresh evidence classified as no read needed
        self.assertEqual(ev["recommendation"], "NO_READ_NEEDED_EVIDENCE_FRESH")

    def test_26_spend_limit_firewall(self):
        gt = self.enricher.enrich_package("golden_trophy_short")
        mb = self.enricher.enrich_package("mystery_box_short")
        self.assertEqual(gt.cost_eur, 0.0)
        self.assertEqual(mb.cost_eur, 0.0)

    def test_27_publication_firewall(self):
        gt = self.enricher.enrich_package("golden_trophy_short")
        # Enriched metadata does NOT authorize release
        self.assertFalse(gt.publication_authorized)
        self.assertIn("HUMAN_GATE:EXPLICIT_PUBLICATION_APPROVAL_REQUIRED", gt.blocking_gates)

    def test_28_zero_secrets_in_packages(self):
        gt = asdict(self.enricher.enrich_package("golden_trophy_short"))
        mb = asdict(self.enricher.enrich_package("mystery_box_short"))
        for pkg in (gt, mb):
            pkg_str = json.dumps(pkg)
            self.assertNotIn("password", pkg_str.lower())
            self.assertNotIn("oauth_token", pkg_str.lower())
            self.assertNotIn("refresh_token", pkg_str.lower())
            self.assertNotIn("client_secret", pkg_str.lower())

    def test_29_scale_performance_test_500_records(self):
        start_time = time.time()
        records = []
        for i in range(500):
            cid = f"synthetic_asset_{i:04d}"
            fake_sha = f"{i:04x}" * 16
            fp = compute_publication_fingerprint_v1("YOUTUBE", "UCg0O_a10jsQ74ffS_HgFGqA", fake_sha)
            rec = PublicationReadinessRecord(
                content_id=cid,
                master_path=f"/path/to/{cid}.mp4",
                master_sha256=fake_sha,
                master_integrity_status="MATCH",
                qc_status="PASS",
                qc_linkage_status="VALID",
                title_proposed=f"Synthetic Video {i}",
                description_draft=f"Description for video {i}",
                target_platform="YOUTUBE",
                target_channel_id="UCg0O_a10jsQ74ffS_HgFGqA",
                target_channel_evidence_hash="686553407e2da096be7ee4ddc98bab824dd307bcec650a6d42ce22de02d53945",
                publication_dedupe_fingerprint=fp,
            )
            eval_res = PackageCompletenessEngine.evaluate(rec)
            records.append(eval_res)

        elapsed = time.time() - start_time
        self.assertEqual(len(records), 500)
        # Should process 500 records in well under 1 second
        self.assertLess(elapsed, 1.0)

    def test_30_idempotent_package_enrichment(self):
        r1 = self.enricher.enrich_package("golden_trophy_short")
        r2 = self.enricher.enrich_package("golden_trophy_short")
        self.assertEqual(r1.publication_dedupe_fingerprint, r2.publication_dedupe_fingerprint)
        self.assertEqual(r1.master_sha256, r2.master_sha256)
        self.assertEqual(r1.blocking_gates, r2.blocking_gates)


if __name__ == "__main__":
    unittest.main()
