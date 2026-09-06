#!/usr/bin/env python3
"""Bounded deterministic acceptance tests for Mission 146C."""

import tempfile
import unittest
from pathlib import Path

from scripts.resource_intelligence import JobResourceRecord, ResourceIntelligenceManager, ResourceObservation


class ResourceIntelligenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name)
        self.manager = ResourceIntelligenceManager(self.repo)

    def tearDown(self):
        self.temp.cleanup()

    def test_reset_is_not_negative_consumption(self):
        before = ResourceObservation(provider="google", observed_at="2026-08-31T12:00:00+00:00", five_hour_remaining_pct=47, source="HUMAN_OBSERVED")
        after = ResourceObservation(provider="google", observed_at="2026-08-31T13:00:00+00:00", five_hour_remaining_pct=100, five_hour_reset_at="2026-08-31T13:00:00+00:00", source="HUMAN_OBSERVED_RESET")
        self.manager.record_observation(before)
        self.manager.record_observation(after)
        self.assertEqual(self.manager.detect_quota_change(before.__dict__, after.__dict__), "RESET_OBSERVED")
        self.assertEqual(self.manager.runway("google")["latest_change"], "RESET_OBSERVED")

    def test_current_capacity_is_risk_not_purchase_instruction(self):
        self.manager.record_observation(ResourceObservation(provider="codex", five_hour_remaining_pct=9, weekly_remaining_pct=86))
        self.manager.record_observation(ResourceObservation(provider="google", five_hour_remaining_pct=97, weekly_remaining_pct=34))
        self.assertEqual(self.manager.runway("codex")["five_hour_class"], "RED")
        review = self.manager.capacity_review(1, 0, 0, 0, confidence="LOW")
        self.assertFalse(review["five_x_capacity_review"])
        self.assertFalse(review["twenty_x_capacity_review"])

    def test_incident_distinguishes_hung_duplicates_from_service(self):
        self.assertEqual(self.manager.classify_process("python -m unittest a", 540, False), "NO_PROGRESS")
        self.assertEqual(self.manager.classify_process("python -m unittest a", 660, False), "HUNG")
        self.assertEqual(self.manager.classify_process("scripts/run_visual_studio_server.py", 46800, False), "PERSISTENT_EXPECTED")

    def test_duplicate_command_is_suppressed_and_completed_result_reused(self):
        first = self.manager.claim_command("python -m unittest tests/test_x.py", "code-a", "owner-a")
        second = self.manager.claim_command("python -m unittest tests/test_x.py", "code-a", "owner-b")
        self.assertEqual(first["decision"], "CLAIMED")
        self.assertEqual(second["decision"], "BLOCK_DUPLICATE_EXECUTION")
        self.manager.complete_command(first["fingerprint"], "result-a")
        self.assertEqual(self.manager.claim_command("python -m unittest tests/test_x.py", "code-a", "owner-c")["decision"], "REUSE_RESULT")

    def test_productivity_and_20x_safety(self):
        hung = JobResourceRecord(mission_id="146", task_id="hang", provider="google", role="TEST", start="x", waste_class="HUNG")
        useful = JobResourceRecord(mission_id="146", task_id="value", provider="google", role="BUILD", start="x", information_gain=True, useful_work_score=.9)
        self.assertEqual(self.manager.classify_productivity(hung), "HUNG")
        self.assertEqual(self.manager.classify_productivity(useful), "HIGH_VALUE")
        low_value = self.manager.capacity_review(100, 100, 0, 0, repeated_quota_block=True, ready_backlog=10, confidence="HIGH")
        self.assertFalse(low_value["twenty_x_capacity_review"])

    def test_heavy_job_limit_is_one(self):
        first = self.manager.claim_command("godot first", "code-one", "owner-a", heavy=True)
        second = self.manager.claim_command("godot second", "code-two", "owner-b", heavy=True)
        self.assertEqual(first["decision"], "CLAIMED")
        self.assertEqual(second["decision"], "BLOCK_HEAVY_JOB_LIMIT")

    def test_alerts_are_deduplicated_and_memory_remains_proposal_only(self):
        first = self.manager.emit_alert("RESOURCE_RED", {"provider": "codex", "reason": "short-window"})
        second = self.manager.emit_alert("RESOURCE_RED", {"provider": "codex", "reason": "short-window"})
        self.assertEqual(first["alert_id"], second["alert_id"])
        proposal = self.manager.memory_update_proposal()
        self.assertEqual(proposal["status"], "PREPARED_NOT_WRITTEN")
        self.assertTrue(proposal["requires_chief_approval"])


if __name__ == "__main__":
    unittest.main()
