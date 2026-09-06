#!/usr/bin/env python3
"""Acceptance Test Suite for Token Burn Auditor."""

import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

TEST_DIR = Path(__file__).resolve().parent
SRC_DIR = TEST_DIR.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from token_burn_auditor.auditor import TokenBurnAuditor, TokenAuditMetrics


class TestTokenBurnAuditor(unittest.TestCase):
    def setUp(self):
        self.auditor = TokenBurnAuditor()

    def test_01_clean_session_audit(self):
        events = [
            {"prompt_tokens": 1000, "completion_tokens": 200, "prompt_snippet": "Task 1", "status": "OK"},
            {"prompt_tokens": 1200, "completion_tokens": 300, "prompt_snippet": "Task 2", "status": "OK"},
        ]
        metrics = self.auditor.audit_session_events(events)
        self.assertEqual(metrics.total_calls, 2)
        self.assertEqual(metrics.total_tokens, 2700)
        self.assertEqual(metrics.wasted_tokens, 0)
        self.assertEqual(metrics.waste_percentage, 0.0)

    def test_02_loop_repetition_and_error_waste_detection(self):
        events = [
            {"prompt_tokens": 5000, "completion_tokens": 100, "prompt_snippet": "Infinite loop task", "status": "OK"},
            {"prompt_tokens": 5000, "completion_tokens": 100, "prompt_snippet": "Infinite loop task", "status": "OK"},
            {"prompt_tokens": 5000, "completion_tokens": 0, "prompt_snippet": "Failed prompt", "status": "ERROR"},
        ]
        metrics = self.auditor.audit_session_events(events)
        self.assertEqual(metrics.total_calls, 3)
        self.assertEqual(metrics.loop_repetitions_detected, 1)
        self.assertGreater(metrics.wasted_tokens, 0)
        self.assertGreater(metrics.waste_percentage, 20.0)
        self.assertTrue(len(metrics.identified_optimizations) >= 1)

    def test_03_markdown_report_generation(self):
        events = [
            {"prompt_tokens": 10000, "completion_tokens": 100, "prompt_snippet": "Task", "status": "OK"},
        ]
        metrics = self.auditor.audit_session_events(events)
        report = self.auditor.generate_markdown_report(metrics)
        self.assertIn("Executive Cost & Efficiency Summary", report)
        self.assertIn("Total Tokens Consumed", report)


if __name__ == "__main__":
    unittest.main()
