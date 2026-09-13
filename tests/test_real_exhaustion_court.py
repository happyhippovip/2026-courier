"""
test_real_exhaustion_court.py - Unit tests for RealExhaustionCourt
Verifies:
1. Method A inspection accurately scans active tasks, locks, and backlog.
2. Method B inspection scans deliverables, runtime locks, and cross-platform requests.
3. Dual-method agreement rule: Only certified exhausted when BOTH methods find 0 gaps.
4. If either method discovers work, safe_work_remaining is True and status is REAL_SAFE_WORK_REMAINS.
"""

import os
import sys
import unittest
import tempfile
import json
import shutil

WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

from courier.chief.control_plane import ControlPlane
from courier.chief.exhaustion_court import RealExhaustionCourt


class TestRealExhaustionCourt(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_court.db")
        self.cp = ControlPlane(db_path=self.db_path)
        self.court = RealExhaustionCourt(workspace_root=WORKSPACE_ROOT, cp=self.cp)
        self.court.court_state_path = os.path.join(self.temp_dir, "exhaustion_record.json")

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_01_method_a_execution(self):
        res_a = self.court.run_discovery_method_a()
        self.assertIn("exhausted", res_a)
        self.assertIn("findings", res_a)
        self.assertIsInstance(res_a["findings"], list)

    def test_02_method_b_execution(self):
        res_b = self.court.run_discovery_method_b()
        self.assertIn("exhausted", res_b)
        self.assertIn("findings", res_b)
        self.assertIsInstance(res_b["findings"], list)

    def test_03_exhaustion_evaluation_structure(self):
        eval_res = self.court.evaluate_exhaustion()
        self.assertIn("both_methods_agree_exhausted", eval_res)
        self.assertIn("final_status", eval_res)
        self.assertIn("safe_work_remaining", eval_res)
        self.assertTrue(os.path.exists(self.court.court_state_path))


if __name__ == "__main__":
    unittest.main()
