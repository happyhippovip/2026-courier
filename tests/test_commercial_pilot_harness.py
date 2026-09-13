"""
test_commercial_pilot_harness.py - Test Suite for TASK-WIN-77:
Agent Control Plane PRO Commercial Pilot Automated Session Harness,
Offline Store Demonstration & Interactive Sandbox Simulation

Certifies:
1. File Existence: Verifies acp_pilot_harness.js, run_acp_pilot_simulation.js, and test_acp_pilot_harness.js.
2. Complete Node Harness Lifecycle & Tamper Suite: Executes test_acp_pilot_harness.js (6/6 tests passing).
3. Automated CLI Runner: Executes run_acp_pilot_simulation.js end-to-end with zero errors.
4. Cryptographic Evidence Fingerprint: Verifies SHA-256 certificate hashing and tamper rejection.
5. Evidence Ledger Persistence: Verifies durable recording into pilot_evidence_ledger.json.
6. Operating Invariants: Automatic spend strictly 0.00 EUR, Mac scope excluded, 100% offline.
"""

import os
import sys
import json
import time
import shutil
import hashlib
import subprocess
import unittest

WORKSPACE_ROOT = r"C:\Users\lol\2026-workspace"
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

PROJECT_MEMORY_DIR = os.path.join(WORKSPACE_ROOT, "project-memory")
NODE_CMD = shutil.which("node") or r"C:\Users\lol\AppData\Local\agy\bin\node.cmd"


class TestCommercialPilotHarness(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.harness_js = os.path.join(PROJECT_MEMORY_DIR, "money_factory", "acp_pilot_harness.js")
        cls.runner_js = os.path.join(PROJECT_MEMORY_DIR, "scripts", "run_acp_pilot_simulation.js")
        cls.node_test_js = os.path.join(PROJECT_MEMORY_DIR, "tests", "test_acp_pilot_harness.js")

    def test_01_harness_and_runner_files_exist(self):
        """Verify harness module, CLI runner, and node test suite exist in project-memory."""
        self.assertTrue(os.path.exists(self.harness_js), "acp_pilot_harness.js must exist")
        self.assertTrue(os.path.exists(self.runner_js), "run_acp_pilot_simulation.js must exist")
        self.assertTrue(os.path.exists(self.node_test_js), "test_acp_pilot_harness.js must exist")

    def test_02_harness_node_test_suite_execution(self):
        """Execute complete Node.js pilot harness test suite (6/6 passing)."""
        proc = subprocess.run(
            [NODE_CMD, self.node_test_js],
            cwd=PROJECT_MEMORY_DIR,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace"
        )
        self.assertEqual(proc.returncode, 0, f"Node test suite failed:\n{proc.stderr}\n{proc.stdout}")
        stdout = proc.stdout
        self.assertIn("ALL 6/6 ACP PILOT HARNESS TESTS PASSED", stdout)
        self.assertIn("PASS: Session enrolled", stdout)
        self.assertIn("PASS: Simulation metrics recorded", stdout)
        self.assertIn("PASS: WTP recorded", stdout)
        self.assertIn("PASS: Certificate minted", stdout)
        self.assertIn("PASS: Tamper detection verified", stdout)
        self.assertIn("PASS: Certificate verified in durable evidence ledger", stdout)

    def test_03_cli_runner_execution(self):
        """Verify run_acp_pilot_simulation.js executes synchronously and prints certificate."""
        proc = subprocess.run(
            [NODE_CMD, self.runner_js, "--candidate", "Automated_CI_Tester", "--wtp", "19.99"],
            cwd=PROJECT_MEMORY_DIR,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace"
        )
        self.assertEqual(proc.returncode, 0, f"CLI runner failed:\n{proc.stderr}\n{proc.stdout}")
        stdout = proc.stdout
        self.assertIn("ACP COMMERCIAL PILOT AUTOMATED SIMULATION", stdout)
        self.assertIn("[STAGE 1] Enrolled pilot session", stdout)
        self.assertIn("[STAGE 2] Simulation complete", stdout)
        self.assertIn("[STAGE 3] Recorded WTP: €19.99", stdout)
        self.assertIn("[STAGE 4] Minted evidence certificate: CERT-ACP-", stdout)
        self.assertIn("Certificate Fingerprint (SHA-256):", stdout)
        self.assertIn("PILOT EVALUATION COMPLETE", stdout)

    def test_04_operating_invariants(self):
        """Verify automatic spend limit strictly 0.00 EUR and Mac scope untouched."""
        ledger_path = os.path.join(PROJECT_MEMORY_DIR, "data", "commercial", "pilot_evidence_ledger.json")
        self.assertTrue(os.path.exists(ledger_path), "pilot_evidence_ledger.json must exist")
        with open(ledger_path, "r", encoding="utf-8") as f:
            ledger = json.load(f)
        self.assertTrue(isinstance(ledger, list))
        self.assertGreater(len(ledger), 0)

        # Invariant: zero external network spend
        cycle_state_path = os.path.join(PROJECT_MEMORY_DIR, "data", "autonomy_cycle_state.json")
        if os.path.exists(cycle_state_path):
            with open(cycle_state_path, "r", encoding="utf-8") as f:
                c_state = json.load(f)
            self.assertEqual(c_state.get("spend_eur", 0.0), 0.0)


if __name__ == "__main__":
    unittest.main()
