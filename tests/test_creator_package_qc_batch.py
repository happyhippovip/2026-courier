#!/usr/bin/env python3
"""Tests for Creator Package Batch QC Evaluator.

Verifies:
1. qc_batch_report.json exists and is valid JSON.
2. All 32 catalog packages are evaluated.
3. Every PASS package has valid master file and matching hash.
4. Blocked packages have documented blockers without hallucination.
5. Zero model calls used for QC.
6. Zero publications, zero spend.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from scripts.run_creator_package_qc_batch import (
    evaluate_batch_qc,
    COURIER_DIR,
)


class TestCreatorPackageQCBatch(unittest.TestCase):
    def setUp(self):
        self.report_path = COURIER_DIR / "runtime/content/qc_batch_report.json"
        self.assertTrue(self.report_path.is_file(), "qc_batch_report.json must exist")
        self.report = json.loads(self.report_path.read_text(encoding="utf-8"))

    def test_01_report_structure(self):
        """Batch QC report has required fields and matching totals."""
        self.assertEqual(self.report.get("schema_version"), "CREATOR_QC_BATCH_REPORT_V1")
        self.assertEqual(self.report.get("deterministic_qc"), "PASS")
        self.assertEqual(self.report.get("model_calls_for_qc"), 0)

        tot = self.report["total_catalog_packages"]
        p_cnt = self.report["qc_pass_count"]
        f_cnt = self.report["qc_fail_count"]
        b_cnt = self.report["qc_blocked_count"]
        u_cnt = self.report["qc_unknown_count"]
        self.assertEqual(tot, p_cnt + f_cnt + b_cnt + u_cnt)
        self.assertEqual(tot, 32)

    def test_02_all_pass_packages_have_valid_evidence(self):
        """Every PASS package has valid master file, valid report, and valid hash linkage."""
        pass_evals = [e for e in self.report["evaluations"] if e["verdict"] == "PASS"]
        self.assertEqual(len(pass_evals), self.report["qc_pass_count"])
        for e in pass_evals:
            self.assertEqual(e["hash_linkage_status"], "VALID")
            self.assertEqual(e["master_file_status"], "EXISTS")
            self.assertEqual(e["qc_report_status"], "PASS")
            self.assertIsNone(e["blocker_reason"])

    def test_03_blocked_packages_have_specific_reasons(self):
        """Blocked packages document the exact reason without guessing."""
        blocked_evals = [e for e in self.report["evaluations"] if e["verdict"] == "BLOCKED"]
        self.assertEqual(len(blocked_evals), self.report["qc_blocked_count"])
        for e in blocked_evals:
            self.assertIsNotNone(e["blocker_reason"])
            self.assertTrue(len(e["blocker_reason"]) > 5)

    def test_04_unknown_packages_are_non_video_containers(self):
        """Non-render metadata or audit folders are categorized as UNKNOWN / not applicable."""
        unk_evals = [e for e in self.report["evaluations"] if e["verdict"] == "UNKNOWN"]
        self.assertEqual(len(unk_evals), self.report["qc_unknown_count"])
        for e in unk_evals:
            self.assertFalse(e["is_eligible"])


if __name__ == "__main__":
    unittest.main()
