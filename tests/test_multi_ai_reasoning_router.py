#!/usr/bin/env python3
"""Acceptance Test Suite for Multi-AI Reasoning Router.

Verifies:
1. Provider-agnostic surface availability inspection (Gemini, ChatGPT, Local)
2. ChatGPT surface detection state (UNAVAILABLE_OR_NOT_CONNECTED without halting system)
3. Automatic routing fallback to authorized surface
4. Strict evidence state integrity (SOURCE_SUPPORTED, INFERENCE, HYPOTHESIS, UNKNOWN)
5. 0.00 EUR autonomous spend limit
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.gemini_brain_bridge import GeminiJobEnvelope, GeminiTaskClass
from scripts.multi_ai_reasoning_router import (
    EvidenceState,
    MultiAIReasoningRouter,
    ReasoningSurface,
)


class TestMultiAIReasoningRouter(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="multi_ai_router_test_"))
        self.router = MultiAIReasoningRouter(repo_dir=self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_01_surface_availability_inspection(self):
        """Surfaces are inspected truthfully without pretending availability."""
        states = self.router.inspect_surface_states()

        self.assertIn(ReasoningSurface.GEMINI.value, states)
        self.assertIn(ReasoningSurface.CHATGPT.value, states)
        self.assertIn(ReasoningSurface.LOCAL_DETERMINISTIC.value, states)

        self.assertEqual(states[ReasoningSurface.GEMINI.value].status, "ACTIVE_AUTHORIZED")
        self.assertEqual(states[ReasoningSurface.CHATGPT.value].status, "UNAVAILABLE_OR_NOT_CONNECTED")
        self.assertEqual(states[ReasoningSurface.LOCAL_DETERMINISTIC.value].status, "ACTIVE_AUTHORIZED")

    def test_02_routing_fallback_when_surface_unavailable(self):
        """Routing to unavailable ChatGPT surface falls back cleanly to Gemini without error."""
        job = GeminiJobEnvelope(
            job_id="JOB-TEST-FALLBACK-01",
            task_id="TASK-TEST-01",
            opportunity_id="REV-OPP-B2B-AUTONOMY-AUDIT",
            goal="Test alternative hypothesis reasoning",
            task_class=GeminiTaskClass.COMPETITIVE_ANALYSIS.value,
        )

        # Request ChatGPT surface (which is UNAVAILABLE_OR_NOT_CONNECTED)
        res = self.router.submit_reasoning_job(ReasoningSurface.CHATGPT, job)

        self.assertEqual(res.status, "SUCCESS")
        self.assertEqual(res.spend_eur, 0.0)
        self.assertIn(res.provider_state, ["REAL_GEMINI_ACTIVE_AUTHORIZED", "LOCAL_DETERMINISTIC_ACTIVE"])

    def test_03_evidence_state_integrity(self):
        """Unverified model statements are strictly marked HYPOTHESIS, not EXTERNALLY_VERIFIED."""
        job = GeminiJobEnvelope(
            job_id="JOB-TEST-EVIDENCE-01",
            task_id="TASK-TEST-02",
            opportunity_id="REV-OPP-B2B-AUTONOMY-AUDIT",
            goal="Analyze failure rates",
            current_evidence={},  # No source citation provided
        )
        res = self.router.submit_reasoning_job(ReasoningSurface.GEMINI, job)

        self.assertEqual(res.evidence.get("evidence_state"), EvidenceState.HYPOTHESIS.value)


if __name__ == "__main__":
    unittest.main()
