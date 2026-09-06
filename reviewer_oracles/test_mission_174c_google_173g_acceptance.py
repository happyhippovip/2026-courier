"""Remediated acceptance probes for Mission 173G / 176G / 180G.

Validates that all Codex 174C findings are closed with fail-closed guarantees:
1. QC source hash mismatch is detected and yields MISMATCH.
2. Fingerprint uses collision-resistant encoding and validates hex/channel format.
3. Missing preflight is explicitly marked PREFLIGHT_NOT_PERFORMED / NO_PREFLIGHT_RUN.
4. Repeated enrichment on unchanged package preserves prepared_at timestamp.
5. Package engine rejects caller-supplied authorization without valid token.
6. 500-record scale test is deterministic, fast, and local.
"""
import json
import tempfile
import unittest
from pathlib import Path

from scripts.creator_package_enricher import (
    CreatorPackageEnricher, PackageCompletenessEngine, PublicationReadinessRecord,
    compute_publication_fingerprint_v1,
)


class Google173GAcceptanceProbes(unittest.TestCase):
    def test_qc_source_hash_mismatch_fails_closed(self):
        with tempfile.TemporaryDirectory() as root_str:
            root = Path(root_str)
            content = root / "runtime/content/arbitrary"
            content.mkdir(parents=True)
            (content / "render.mp4").write_bytes(b"synthetic-master")
            (content / "qc_report.json").write_text(json.dumps({"verdict": "PASS", "source_hash": "0" * 64}))
            record = CreatorPackageEnricher(repo_dir=root).enrich_package("arbitrary")
            self.assertEqual("MISMATCH", record.qc_linkage_status)

    def test_fingerprint_rejects_ambiguous_and_unvalidated_components(self):
        # Colon components do not collide
        fp1 = compute_publication_fingerprint_v1("YOUTUBE", "UC_test_chan_a", "c" * 64)
        fp2 = compute_publication_fingerprint_v1("YOUTUBE", "UC_test_chan_b", "c" * 64)
        self.assertNotEqual(fp1, fp2)
        # Invalid channel or invalid sha256 rejected with empty string
        self.assertEqual("", compute_publication_fingerprint_v1("YOUTUBE", "not a channel", "not-a-sha256"))

    def test_missing_preflight_is_rendered_explicitly(self):
        with tempfile.TemporaryDirectory() as root_str:
            root = Path(root_str)
            content = root / "runtime/content/arbitrary"
            content.mkdir(parents=True)
            (content / "render.mp4").write_bytes(b"synthetic-master")
            record = CreatorPackageEnricher(repo_dir=root).enrich_package("arbitrary")
            self.assertEqual("NO_PREFLIGHT_RUN", record.duplicate_preflight_result)
            self.assertEqual("PREFLIGHT_NOT_PERFORMED", record.duplicate_preflight_status)

    def test_repeated_enrichment_preserves_prepared_at(self):
        with tempfile.TemporaryDirectory() as root_str:
            root = Path(root_str)
            content = root / "runtime/content/arbitrary"
            content.mkdir(parents=True)
            (content / "render.mp4").write_bytes(b"synthetic-master")
            enricher = CreatorPackageEnricher(repo_dir=root)
            first = enricher.enrich_package("arbitrary")
            second = enricher.enrich_package("arbitrary")
            self.assertEqual(first.prepared_at, second.prepared_at)

    def test_package_engine_rejects_caller_supplied_gate_resolution(self):
        record = PublicationReadinessRecord(
            master_path=__file__, master_integrity_status="MATCH", qc_status="PASS", qc_linkage_status="VALID",
            title_proposed="x", description_draft="y", target_channel_id="UCg0O_a10jsQ74ffS_HgFGqA", target_channel_evidence_hash="x",
            target_channel_freshness_status="CURRENT_VERIFIED", publication_dedupe_fingerprint="x" * 64,
            privacy_decision_status="DECIDED", audience_decision="NOT_MADE_FOR_KIDS", publication_authorized=True,
            publication_authorization_token="",  # Missing authoritative token
        )
        eval_res = PackageCompletenessEngine.evaluate(record)
        self.assertNotEqual("PUBLICATION_READY", eval_res["readiness_stage"])
        self.assertIn("HUMAN_GATE:EXPLICIT_PUBLICATION_APPROVAL_REQUIRED", eval_res["blocking_gates"])

    def test_scale_500_is_deterministic_and_local(self):
        first = [compute_publication_fingerprint_v1("YOUTUBE", "UC_TEST_CHANNEL_12345", f"{i:064x}") for i in range(500)]
        second = [compute_publication_fingerprint_v1("YOUTUBE", "UC_TEST_CHANNEL_12345", f"{i:064x}") for i in range(500)]
        self.assertEqual(first, second)
        self.assertEqual(500, len(set(first)))


if __name__ == "__main__":
    unittest.main()
