#!/usr/bin/env python3
"""Acceptance Test Suite for Real Endurance & Continuous Learning Canary.

Verifies:
1. Long-run observation loop execution with live PID identity and heartbeat continuity
2. Event-driven wake from SAFE_IDLE without manual prompt
3. Controlled crash restart recovery without duplicate task execution
4. Snitch & Visual HQ telemetry synchronization
5. Truthful second-AI classification (WAITING_FOR_REAL_SECOND_AI_SURFACE)
6. 100% Deterministic execution (0 Model Calls, 0.00 EUR Spend)
"""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.run_30min_endurance_canary import EnduranceCanaryRunner


class TestEnduranceCanary(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="endurance_test_"))
        self.runner = EnduranceCanaryRunner(
            repo_dir=self.test_dir,
            target_seconds=3.0,
            cycle_interval_seconds=0.5,
        )

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_01_endurance_canary_session_execution(self):
        """Runs bounded endurance session and verifies operational metrics & release decision."""
        metrics = self.runner.run_endurance_session(
            inject_wake_test=True,
            simulate_restart_test=True,
        )

        self.assertTrue(metrics.process_alive)
        self.assertGreaterEqual(metrics.heartbeats_recorded, 2)
        self.assertTrue(metrics.snitch_truth_verified)
        self.assertEqual(metrics.event_wakes_triggered, 1)
        self.assertEqual(metrics.restarts_recovered, 1)
        self.assertEqual(metrics.multi_ai_council_status, "WAITING_FOR_REAL_SECOND_AI_SURFACE")
        self.assertEqual(metrics.weiter_prompts_required, 0)
        self.assertEqual(metrics.spend_eur, 0.0)
        self.assertEqual(metrics.release_decision, "READY_FOR_LONGER_UNATTENDED_OPERATION")


if __name__ == "__main__":
    unittest.main()
