#!/usr/bin/env python3
"""Acceptance Test Suite for Chief Decision Protocol & Closed-Loop Autonomous Continuation.

Verifies:
1. Result recording with deterministic fingerprinting (events/results/result_*.json)
2. Structured Chief Decision Records (events/chief-decisions/decision_*.json)
3. Automatic decision evaluation & next-action generation without human prompts
4. Non-blocking human gate parking (park blocked step, continue independent safe work)
5. Multi-step continuous execution chain:
   TASK A -> RESULT A -> Auto Decision -> TASK B -> RESULT B -> Auto Decision -> TASK C -> TASK D (Gated) -> TASK E (Safe continue)
6. 100% Deterministic (0 Model Calls, 0 EUR Spend, 0 Human Copy/Paste, 0 WEITER)
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.chief_decision_protocol import (
    ChiefDecisionProtocol,
    ChiefDecisionRecord,
    DecisionReasonCode,
)
from scripts.money_machine_pipeline import OpportunityState


class TestChiefDecisionProtocol(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="decision_protocol_test_"))
        self.protocol = ChiefDecisionProtocol(repo_dir=self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_01_record_execution_result_and_fingerprint(self):
        """Result envelope is saved to disk with deterministic SHA-256 fingerprint."""
        res_file, fp = self.protocol.record_execution_result(
            task_id="TASK-TEST-01",
            opportunity_id="OPP-01",
            status="SUCCESS",
            findings="Deterministic verification passed",
            artifacts={"output": "docs/test.md"},
            evidence={"step": 1},
        )
        self.assertTrue(res_file.exists())
        self.assertEqual(len(fp), 16)

        data = json.loads(res_file.read_text(encoding="utf-8"))
        self.assertEqual(data["task_id"], "TASK-TEST-01")
        self.assertEqual(data["result_fingerprint"], fp)

    def test_02_evaluate_result_and_generate_auto_decision(self):
        """Evaluates completed result and emits structured ChiefDecisionRecord."""
        rec = self.protocol.evaluate_result_and_decide(
            task_id="TASK-TEST-02",
            opportunity_id="REV-OPP-B2B-AUTONOMY-AUDIT",
            result_status="SUCCESS",
            findings="Offer dossier created",
            artifacts={"offer": "offer.md"},
        )
        self.assertIsInstance(rec, ChiefDecisionRecord)
        self.assertFalse(rec.human_gate_required)
        self.assertEqual(rec.cost_class, "ZERO_COST")
        self.assertIn("AUTO_CONTINUE", rec.reason_code)

        dec_file = self.test_dir / "events" / "chief-decisions" / f"decision_{rec.decision_id}.json"
        self.assertTrue(dec_file.exists())

    def test_03_human_gate_parks_step_without_blocking_system(self):
        """When publication or payment is needed, Human Fast-Gate is generated and step is parked."""
        rec = self.protocol.evaluate_result_and_decide(
            task_id="TASK-TEST-03-GATE",
            opportunity_id="REV-OPP-YOUTUBE-CREATOR-AUTOMATION",
            result_status="BLOCKED_GATE",
            findings="Requires public social media post authorization",
            artifacts={},
            evidence={"requires_publication": True},
        )
        self.assertTrue(rec.human_gate_required)
        self.assertEqual(rec.human_gate_type, "PUBLICATION")
        self.assertEqual(rec.reason_code, DecisionReasonCode.PARK_HUMAN_FAST_GATE.value)
        self.assertEqual(rec.recommended_next_action, "AUTO_CONTINUE_NEXT_INDEPENDENT_SAFE_TASK")

    def test_04_closed_loop_continuous_autonomous_chain(self):
        """Demonstrates continuous multi-step autonomous chain without human copy/paste or WEITER."""
        chain = self.protocol.run_continuous_autonomous_chain(max_steps=4)
        self.assertGreaterEqual(len(chain), 3)

        for step_data in chain:
            self.assertTrue(step_data["auto_continued"])
            self.assertIn("decision", step_data)
            self.assertIn("task_id", step_data)

        # Verify decisions were persisted to disk
        dec_files = list((self.test_dir / "events" / "chief-decisions").glob("decision_*.json"))
        self.assertEqual(len(dec_files), len(chain))

    def test_05_dependency_wait_semantics_scope_local(self):
        """Dependency wait blocks only matching scope and resolves upon result arrival."""
        wait = self.protocol.register_dependency_wait(
            worker_id="GOOGLE_BUILDER",
            task_id="TASK-DEP-01",
            correlation_id="CORR-DEP-01",
            expected_result_type="GEMINI_REASONING_RESULT",
            blocking_scope=["events/revenue-opportunities/offerings/b2b_autonomy_audit"],
        )
        self.assertEqual(wait.state, "WAITING_FOR_RESULT")

        # Check scope blocking: b2b_autonomy_audit is blocked, fruitki is NOT blocked
        self.assertTrue(self.protocol.is_scope_blocked_by_wait(["events/revenue-opportunities/offerings/b2b_autonomy_audit"]))
        self.assertFalse(self.protocol.is_scope_blocked_by_wait(["events/revenue-opportunities/offerings/fruitki_asset_licensing"]))

        # Resolve dependency wait
        resolved = self.protocol.resolve_dependency_wait(
            task_id="TASK-DEP-01",
            correlation_id="CORR-DEP-01",
            result_fingerprint="abc123def456",
        )
        self.assertIsNotNone(resolved)
        self.assertEqual(resolved.state, "RESULT_RECEIVED")
        self.assertFalse(self.protocol.is_scope_blocked_by_wait(["events/revenue-opportunities/offerings/b2b_autonomy_audit"]))


if __name__ == "__main__":
    unittest.main()
