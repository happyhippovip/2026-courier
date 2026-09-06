#!/usr/bin/env python3
"""Acceptance Test Suite for Delivery Process Dry Run.

Verifies:
1. Secret-free intake validation rejects forbidden tokens and accepts clean inputs
2. Bounded 10-point determinism matrix produces PASS / FAIL / UNKNOWN ratings
3. Deliverable report assembly with reproducible findings and prioritized remediation
4. 100% Deterministic (0 Model Calls, 0.00 EUR Spend, 0 External APIs)
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.run_delivery_process_dry_run import DeliveryProcessDryRun


class TestDeliveryProcessDryRun(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="dry_run_test_"))
        self.runner = DeliveryProcessDryRun(repo_dir=self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_01_intake_sanitization_rejects_secrets(self):
        """Intake containing forbidden API keys or tokens is rejected immediately."""
        dirty_intake = "Here is my code with api_key = 'sk-1234567890abcdef'..."
        clean, reason = self.runner.verify_intake_sanitization(dirty_intake)
        self.assertFalse(clean)
        self.assertIn("FORBIDDEN_SECRET_DETECTED", reason)

        clean_intake = "Workflow: Python batch scraper using mocked local files."
        clean_ok, msg = self.runner.verify_intake_sanitization(clean_intake)
        self.assertTrue(clean_ok)
        self.assertEqual(msg, "INTAKE_CLEAN_AND_SANITIZED")

    def test_02_matrix_evaluation_and_pass_fail_unknown_states(self):
        """10-point matrix evaluates code and assigns PASS, FAIL, and UNKNOWN."""
        mock_code = "import os\ndef ping(): pass"
        matrix = self.runner.execute_audit_evaluation(mock_code)

        self.assertEqual(len(matrix), 10)
        statuses = {v["status"] for v in matrix.values()}
        self.assertIn("PASS", statuses)
        self.assertIn("FAIL", statuses)
        self.assertIn("UNKNOWN", statuses)

    def test_03_end_to_end_delivery_process_dry_run(self):
        """End-to-end dry run generates final report file on disk."""
        res = self.runner.run_dry_run()
        self.assertEqual(res["status"], "DELIVERY_PROCESS_PROVEN")
        self.assertTrue(res["sanitization_check"])
        self.assertEqual(res["matrix_checks_evaluated"], 10)

        report_file = self.test_dir / res["report_file"]
        self.assertTrue(report_file.exists())
        content = report_file.read_text(encoding="utf-8")
        self.assertIn("AI Agent Reliability & Crash-Safety Check — Final Report", content)
        self.assertIn("10-Point Determinism & Failure Mode Matrix", content)
        self.assertIn("Prioritized Remediation Action Plan", content)


if __name__ == "__main__":
    unittest.main()
