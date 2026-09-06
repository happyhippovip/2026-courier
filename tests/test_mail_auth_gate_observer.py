#!/usr/bin/env python3
"""Test suite for MailAuthGateObserver & Self-Resuming Dispatcher."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.mail_auth_gate_observer import MailAuthGateObserver
from scripts.money_machine_pipeline import OpportunityState


class TestMailAuthGateObserver(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="mail_auth_test_"))

        # Setup tracker directory and file
        tracker_dir = self.test_dir / "events" / "revenue-opportunities" / "offerings" / "b2b_autonomy_audit"
        tracker_dir.mkdir(parents=True, exist_ok=True)
        self.tracker_file = tracker_dir / "outreach_tracker.json"
        self.tracker_file.write_text(json.dumps({
            "prospects": [
                {
                    "prospect_id": "P-01",
                    "target_type": "AI Coding Agent Founder",
                    "channel": "EMAIL_APPLE_MAIL",
                    "personalized_message": "Test offer for €99 AI Agent Reliability Check.",
                    "sent_at": None,
                    "economic_state": "OUTREACH_AUTHORIZED",
                    "response_state": "AWAITING_DISPATCH",
                }
            ]
        }))

        # Setup ledger directory and file
        ledger_dir = self.test_dir / "events" / "revenue-opportunities"
        ledger_dir.mkdir(parents=True, exist_ok=True)
        self.ledger_file = ledger_dir / "canonical_revenue_ledger.json"
        self.ledger_file.write_text(json.dumps({
            "opportunities": {
                "REV-OPP-B2B-AUTONOMY-AUDIT": {
                    "opportunity_id": "REV-OPP-B2B-AUTONOMY-AUDIT",
                    "title": "B2B Autonomous System Determinism & Crash-Safety Audit Blueprint",
                    "state": OpportunityState.OUTREACH_AUTHORIZED.value,
                    "evidence_confidence": 0.8,
                    "result": "OUTREACH_AUTHORIZED",
                }
            }
        }))

        self.observer = MailAuthGateObserver(repo_dir=self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_01_awaiting_auth_state_presentation(self):
        """When mail is not authenticated, returns clear human gate instructions without secrets."""
        res = self.observer.poll_and_auto_resume(dry_run=False)
        # In test sandbox or when Mail has modal open, returns AWAITING_AUTH
        self.assertIn(res["status"], ["AWAITING_AUTH", "AUTH_DETECTED_AND_RESUMED", "AUTH_ACTIVE_P01_ALREADY_SENT"])
        if res["status"] == "AWAITING_AUTH":
            self.assertTrue(res["ready_for_one_time_auth"])
            self.assertIn("Apple Mail", res["human_action"])
            self.assertIn("Do nothing else", res["after_auth"])

    def test_02_simulated_auth_detection_and_p01_auto_dispatch(self):
        """Simulates successful auth detection triggering automated single P-01 dispatch."""
        res = self.observer.poll_and_auto_resume(dry_run=True)
        self.assertEqual(res["status"], "AUTH_DETECTED_AND_RESUMED")
        self.assertTrue(res["transport_ready"])

        dispatch_res = res["dispatch_result"]
        self.assertEqual(dispatch_res["status"], "EXPOSURE_TRANSMITTED")
        self.assertEqual(dispatch_res["prospect_id"], "P-01")
        self.assertEqual(dispatch_res["opportunity_id"], "REV-OPP-B2B-AUTONOMY-AUDIT")
        self.assertIsNotNone(dispatch_res["correlation_id"])
        self.assertIsNotNone(dispatch_res["message_fingerprint"])

        # Check tracker file updated
        tracker_data = json.loads(self.tracker_file.read_text(encoding="utf-8"))
        p1 = tracker_data["prospects"][0]
        self.assertEqual(p1["economic_state"], "EXPOSURE")
        self.assertEqual(p1["response_state"], "WAITING_FOR_RESPONSE")
        self.assertEqual(p1["human_action_count_this_send"], 0)
        self.assertIsNotNone(p1["sent_at"])

        # Check canonical ledger updated
        ledger_data = json.loads(self.ledger_file.read_text(encoding="utf-8"))
        op = ledger_data["opportunities"]["REV-OPP-B2B-AUTONOMY-AUDIT"]
        self.assertEqual(op["state"], OpportunityState.EXPOSURE.value)

    def test_03_duplicate_send_fencing(self):
        """Second execution attempt is strictly blocked with zero duplicate side effects."""
        # First send
        res1 = self.observer.poll_and_auto_resume(dry_run=True)
        self.assertEqual(res1["status"], "AUTH_DETECTED_AND_RESUMED")

        # Second send attempt
        res2 = self.observer.poll_and_auto_resume(dry_run=True)
        self.assertEqual(res2["status"], "AUTH_ACTIVE_P01_ALREADY_SENT")
        self.assertEqual(res2["next_action"], "WAITING_FOR_RESPONSE")

    def test_04_zero_secret_persistence(self):
        """Verifies state files and tracker contain zero passwords, tokens, or cookies."""
        self.observer.poll_and_auto_resume(dry_run=True)
        state_file = self.test_dir / "events" / "runtime-state" / "mail_auth_gate_state.json"
        self.assertTrue(state_file.exists())

        state_text = state_file.read_text(encoding="utf-8")
        self.assertNotIn("password", state_text.lower())
        self.assertNotIn("token", state_text.lower())
        self.assertNotIn("cookie", state_text.lower())
        self.assertNotIn("secret", state_text.lower())


if __name__ == "__main__":
    unittest.main()
