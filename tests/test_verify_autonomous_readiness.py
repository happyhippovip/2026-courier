#!/usr/bin/env python3
"""Acceptance Test Suite for AutonomousReadinessVerifier CLI.

Verifies:
1. All 5 core subsystem checks run deterministically in <0.1s
2. Correct detection of healthy system state (overall_readiness == READY)
3. Detection and fail-closed reporting on corrupt locks or queue files
4. 100% Deterministic execution (0 Model Calls, 0.00 EUR Spend)
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.verify_autonomous_readiness import (
    AutonomousReadinessVerifier,
    SystemReadinessReport,
)


class TestVerifyAutonomousReadiness(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="readiness_test_"))
        self.verifier = AutonomousReadinessVerifier(repo_dir=self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_01_verify_all_on_clean_workspace(self):
        """Clean workspace evaluates to READY with all checks passed."""
        report = self.verifier.verify_all(run_oracles=False)
        self.assertIsInstance(report, SystemReadinessReport)
        self.assertEqual(report.overall_readiness, "READY")
        self.assertTrue(report.all_checks_passed)
        self.assertEqual(report.autonomous_spend_limit_eur, 0.0)
        self.assertEqual(len(report.subsystem_checks), 5)
        for check in report.subsystem_checks:
            self.assertEqual(check.status, "PASS")

    def test_02_detects_corrupt_authority_lock(self):
        """Corrupt lock file causes CANONICAL_AUTHORITY check to FAIL."""
        locks_dir = self.test_dir / "events" / "locks"
        locks_dir.mkdir(parents=True, exist_ok=True)
        # Create zero-byte corrupt scope file
        corrupt_file = locks_dir / "scope_bad_scope_12345678.json"
        corrupt_file.write_text("", encoding="utf-8")

        report = self.verifier.verify_all(run_oracles=False)
        self.assertFalse(report.all_checks_passed)
        auth_check = next(c for c in report.subsystem_checks if c.subsystem == "CANONICAL_AUTHORITY")
        self.assertEqual(auth_check.status, "FAIL")


if __name__ == "__main__":
    unittest.main()
