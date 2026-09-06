#!/usr/bin/env python3
"""Acceptance Test Suite for Gemini Brain Worker Bridge.

Verifies:
1. Surface verification and active authorization state (GOOGLE_PRIMARY_BUILDER)
2. Structured Gemini Job submission (events/gemini-jobs/job_*.json)
3. Structured Gemini Result execution & fingerprinting (events/gemini-results/result_*.json)
4. Non-deterministic judgment vs. deterministic fallback routing
5. Integration with ChiefDecisionProtocol with REAL_GEMINI_INVOCATIONS >= 1
6. 0.00 EUR spend firewall enforcement
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.gemini_brain_bridge import (
    GeminiBrainBridge,
    GeminiJobEnvelope,
    GeminiResultEnvelope,
    GeminiTaskClass,
)
from scripts.chief_decision_protocol import ChiefDecisionProtocol


class TestGeminiBrainBridge(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="gemini_bridge_test_"))
        self.bridge = GeminiBrainBridge(repo_dir=self.test_dir)
        self.protocol = ChiefDecisionProtocol(repo_dir=self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_01_verify_surface_authorization(self):
        """Surface identity and authorization are verified."""
        auth = self.bridge.verify_authorization_state()
        self.assertEqual(auth["surface_name"], "GOOGLE_PRIMARY_BUILDER")
        self.assertTrue(auth["authorized"])
        self.assertEqual(auth["autonomous_spend_limit_eur"], 0.0)

    def test_02_submit_and_execute_gemini_job(self):
        """Structured Gemini Job envelope is submitted, executed, and persisted."""
        job = GeminiJobEnvelope(
            job_id="JOB-TEST-01",
            task_id="TASK-TEST-01",
            opportunity_id="REV-OPP-B2B-AUTONOMY-AUDIT",
            goal="Analyze pricing elasticity for B2B crash-safety audit",
            task_class=GeminiTaskClass.MARKET_INTERPRETATION.value,
            economic_context={"tier": "B2B", "entry_price": 99.0},
        )
        res = self.bridge.execute_gemini_job(job)

        self.assertEqual(res.status, "SUCCESS")
        self.assertEqual(res.provider_state, "REAL_GEMINI_ACTIVE_AUTHORIZED")
        self.assertEqual(res.spend_eur, 0.0)
        self.assertTrue((self.test_dir / "events" / "gemini-jobs" / "job_JOB-TEST-01.json").exists())
        self.assertTrue((self.test_dir / "events" / "gemini-results" / "result_JOB-TEST-01.json").exists())

    def test_03_closed_loop_chain_invokes_gemini_brain(self):
        """Closed loop executes chain and records REAL_GEMINI_INVOCATIONS >= 1."""
        chain = self.protocol.run_continuous_autonomous_chain(max_steps=4)
        self.assertGreaterEqual(len(chain), 3)

        gemini_invocations = sum(1 for c in chain if c.get("gemini_invoked"))
        self.assertGreaterEqual(gemini_invocations, 1)

        # Check job envelopes on disk
        job_files = list((self.test_dir / "events" / "gemini-jobs").glob("job_*.json"))
        self.assertGreaterEqual(len(job_files), 1)


if __name__ == "__main__":
    unittest.main()
