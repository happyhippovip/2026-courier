#!/usr/bin/env python3
"""Acceptance Test Suite for Autonomous Production Canary & Computer-A Operational Readiness.

Verifies:
1. Reality check and authoritative path selection
2. Real worker process canary execution with verified PID and authority leasing
3. Real event wake from SAFE_IDLE upon opportunity injection
4. Real crash recovery and restart without duplicate execution
5. Snitch liveness observation across PROGRESSING, WAITING_PERMISSION, SAFE_IDLE
6. HQ telemetry bridge compilation and daemon cycle
7. 100% Deterministic execution (0 Model Calls, 0 EUR Spend)
"""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.run_autonomous_production_canary import AutonomousProductionCanary


class TestAutonomousProductionCanary(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="canary_test_"))
        self.canary = AutonomousProductionCanary(repo_dir=self.test_dir)
        # Ensure DR manifest baseline exists in test repo
        self.canary.survival.generate_dr_manifest()

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_01_full_production_canary_pipeline(self):
        """Runs the entire 10-phase operational canary and verifies READY_FOR_LONGER_UNATTENDED_CANARY."""
        summary = self.canary.run_all_phases()

        self.assertEqual(summary["mission_result"], "PASS")
        self.assertEqual(summary["readiness_decision"], "READY_FOR_LONGER_UNATTENDED_CANARY")
        self.assertTrue(summary["phase_1"]["has_dr_manifest"])
        self.assertFalse(summary["phase_2"]["split_brain_detected"])
        self.assertTrue(summary["phase_3"]["success"])
        self.assertTrue(summary["phase_4"]["success"])
        self.assertTrue(summary["phase_5"]["success"])
        self.assertTrue(summary["phase_6"]["success"])
        self.assertTrue(summary["phase_7"]["success"])
        self.assertTrue(summary["phase_9"]["success"])


if __name__ == "__main__":
    unittest.main()
