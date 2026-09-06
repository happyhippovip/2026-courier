#!/usr/bin/env python3
"""Comprehensive Unit Tests for Time-Boxed Autonomy & Checkpoint Enforcement (Mission 156G).

Validates all 20 required acceptance points using deterministic FakeClock injection:
1. Target duration of 30-minute lease is 1800s.
2. Fake clock at 299s does not record CP05.
3. Fake clock at 300s records CP05.
4. CP10 not recorded before 600s.
5. CP15 not recorded before 900s.
6. CP20 not recorded before 1200s.
7. CP25 not recorded before 1500s.
8. CP30 not recorded before 1800s.
9. Empty task queue does not exit early.
10. Fallback planner supplies useful task.
11. Duplicate fallback task suppressed.
12. Busywork rejected.
13. Early hard gate records true stop (did_stop_before_deadline=True).
14. Early resource block records true stop (did_stop_before_deadline=True).
15. Normal completion cannot occur before deadline (raises EarlyTerminationError).
16. Final report duration matches clock.
17. did_stop_before_deadline is mechanically correct.
18. Synthetic future checkpoints impossible.
19. Production mode uses RealClock.
20. No artificial idle-fill implementation.
"""

from __future__ import annotations

import datetime
import inspect
import json
import tempfile
import unittest
from pathlib import Path

from scripts.timeboxed_autonomy_engine import (
    CHECKPOINT_THRESHOLDS, ClockProtocol, CreatorFallbackPlanner,
    EarlyTerminationError, FakeClock, RealClock, TimeboxedLeaseEngine,
)


class TestTimeboxedAutonomyEngineMission156G(unittest.TestCase):
    """Test suite validating time-boxed autonomy mechanics and checkpoint integrity."""

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.lease_path = Path(self.tmp_dir.name) / "test_lease.json"
        self.fake_clock = FakeClock(
            start_utc=datetime.datetime(2026, 8, 31, 15, 38, 0, tzinfo=datetime.timezone.utc),
            start_monotonic=1000.0,
        )

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_01_lease_target_duration_is_1800(self):
        engine = TimeboxedLeaseEngine(
            mission_id="156G",
            target_duration_seconds=1800,
            lease_file=self.lease_path,
            clock=self.fake_clock,
        )
        self.assertEqual(engine.target_duration_seconds, 1800)
        self.assertEqual(engine.remaining_seconds(), 1800.0)
        self.assertFalse(engine.is_deadline_reached())

    def test_02_fake_clock_at_299s_does_not_create_cp05(self):
        engine = TimeboxedLeaseEngine(target_duration_seconds=1800, lease_file=self.lease_path, clock=self.fake_clock)
        self.fake_clock.advance(299.0)
        engine.maybe_record_checkpoints()
        self.assertEqual(engine.checkpoints["CHECKPOINT_05"]["status"], "NOT_REACHED")

    def test_03_fake_clock_at_300s_creates_cp05(self):
        engine = TimeboxedLeaseEngine(target_duration_seconds=1800, lease_file=self.lease_path, clock=self.fake_clock)
        self.fake_clock.advance(300.0)
        newly = engine.maybe_record_checkpoints(task_context="TASK_AUDIT")
        self.assertIn("CHECKPOINT_05", newly)
        self.assertEqual(engine.checkpoints["CHECKPOINT_05"]["status"], "RECORDED")
        self.assertEqual(engine.checkpoints["CHECKPOINT_05"]["elapsed_seconds"], 300.0)
        self.assertEqual(engine.checkpoints["CHECKPOINT_05"]["threshold_seconds"], 300)

    def test_04_cp10_not_before_600s(self):
        engine = TimeboxedLeaseEngine(target_duration_seconds=1800, lease_file=self.lease_path, clock=self.fake_clock)
        self.fake_clock.advance(599.0)
        engine.maybe_record_checkpoints()
        self.assertEqual(engine.checkpoints["CHECKPOINT_10"]["status"], "NOT_REACHED")
        self.fake_clock.advance(1.0)
        engine.maybe_record_checkpoints()
        self.assertEqual(engine.checkpoints["CHECKPOINT_10"]["status"], "RECORDED")

    def test_05_cp15_not_before_900s(self):
        engine = TimeboxedLeaseEngine(target_duration_seconds=1800, lease_file=self.lease_path, clock=self.fake_clock)
        self.fake_clock.advance(899.0)
        engine.maybe_record_checkpoints()
        self.assertEqual(engine.checkpoints["CHECKPOINT_15"]["status"], "NOT_REACHED")
        self.fake_clock.advance(1.0)
        engine.maybe_record_checkpoints()
        self.assertEqual(engine.checkpoints["CHECKPOINT_15"]["status"], "RECORDED")

    def test_06_cp20_not_before_1200s(self):
        engine = TimeboxedLeaseEngine(target_duration_seconds=1800, lease_file=self.lease_path, clock=self.fake_clock)
        self.fake_clock.advance(1199.0)
        engine.maybe_record_checkpoints()
        self.assertEqual(engine.checkpoints["CHECKPOINT_20"]["status"], "NOT_REACHED")
        self.fake_clock.advance(1.0)
        engine.maybe_record_checkpoints()
        self.assertEqual(engine.checkpoints["CHECKPOINT_20"]["status"], "RECORDED")

    def test_07_cp25_not_before_1500s(self):
        engine = TimeboxedLeaseEngine(target_duration_seconds=1800, lease_file=self.lease_path, clock=self.fake_clock)
        self.fake_clock.advance(1499.0)
        engine.maybe_record_checkpoints()
        self.assertEqual(engine.checkpoints["CHECKPOINT_25"]["status"], "NOT_REACHED")
        self.fake_clock.advance(1.0)
        engine.maybe_record_checkpoints()
        self.assertEqual(engine.checkpoints["CHECKPOINT_25"]["status"], "RECORDED")

    def test_08_cp30_not_before_1800s(self):
        engine = TimeboxedLeaseEngine(target_duration_seconds=1800, lease_file=self.lease_path, clock=self.fake_clock)
        self.fake_clock.advance(1799.0)
        engine.maybe_record_checkpoints()
        self.assertEqual(engine.checkpoints["CHECKPOINT_30"]["status"], "NOT_REACHED")
        self.fake_clock.advance(1.0)
        engine.maybe_record_checkpoints()
        self.assertEqual(engine.checkpoints["CHECKPOINT_30"]["status"], "RECORDED")

    def test_09_empty_task_queue_does_not_complete_early(self):
        engine = TimeboxedLeaseEngine(target_duration_seconds=1800, lease_file=self.lease_path, clock=self.fake_clock)
        self.fake_clock.advance(297.0)
        # Attempting to declare COMPLETE at 297s MUST raise EarlyTerminationError
        with self.assertRaises(EarlyTerminationError):
            engine.finalize(declared_status="COMPLETE")

    def test_10_fallback_planner_supplies_useful_task(self):
        planner = CreatorFallbackPlanner()
        completed = {"mystery_portal_apple_v2_short"}
        task = planner.get_next_useful_task(completed_slugs=completed, remaining_seconds=1500.0)
        self.assertIsNotNone(task)
        self.assertNotEqual(task.slug, "mystery_portal_apple_v2_short")
        self.assertIn("1080x1920", task.description or str(task.metadata))

    def test_11_duplicate_fallback_task_suppressed(self):
        planner = CreatorFallbackPlanner()
        completed = {"mystery_portal_apple_v2_short"}
        task1 = planner.get_next_useful_task(completed_slugs=completed, remaining_seconds=1500.0)
        self.assertIsNotNone(task1)
        completed.add(task1.slug)
        task2 = planner.get_next_useful_task(completed_slugs=completed, remaining_seconds=1400.0)
        self.assertIsNotNone(task2)
        self.assertNotEqual(task1.slug, task2.slug)

    def test_12_busywork_rejected_when_time_insufficient(self):
        planner = CreatorFallbackPlanner()
        completed = {s["slug"] for s in planner.BACKLOG_SEEDS} | set(planner.UPGRADE_CANDIDATES) | {"asset_expression_pack", "master_contact_sheet_refresh"}
        task = planner.get_next_useful_task(completed_slugs=completed, remaining_seconds=5.0)
        self.assertIsNone(task, "Planner must return None rather than creating duplicate busywork")

    def test_13_early_hard_gate_records_true_stop(self):
        engine = TimeboxedLeaseEngine(target_duration_seconds=1800, lease_file=self.lease_path, clock=self.fake_clock)
        self.fake_clock.advance(450.0)
        summary = engine.finalize(declared_status="HUMAN_GATE", stop_reason="AUDIENCE_DECISION_REQUIRED")
        self.assertEqual(summary["status"], "HUMAN_GATE")
        self.assertTrue(summary["did_stop_before_deadline"])
        self.assertEqual(summary["actual_duration_seconds"], 450.0)

    def test_14_early_resource_block_records_true_stop(self):
        engine = TimeboxedLeaseEngine(target_duration_seconds=1800, lease_file=self.lease_path, clock=self.fake_clock)
        self.fake_clock.advance(720.0)
        summary = engine.finalize(declared_status="RESOURCE_WAIT", stop_reason="RATE_LIMIT_RESET_PENDING")
        self.assertEqual(summary["status"], "RESOURCE_WAIT")
        self.assertTrue(summary["did_stop_before_deadline"])
        self.assertEqual(summary["actual_duration_seconds"], 720.0)

    def test_15_normal_completion_cannot_occur_before_deadline(self):
        engine = TimeboxedLeaseEngine(target_duration_seconds=1800, tolerance_seconds=60.0, lease_file=self.lease_path, clock=self.fake_clock)
        self.fake_clock.advance(1730.0)  # 1730 < (1800 - 60)
        with self.assertRaises(EarlyTerminationError):
            engine.finalize(declared_status="COMPLETE")

        self.fake_clock.advance(20.0)  # 1750 >= 1740 (within 60s tolerance)
        summary = engine.finalize(declared_status="COMPLETE")
        self.assertEqual(summary["status"], "COMPLETE")
        self.assertFalse(summary["did_stop_before_deadline"])

    def test_16_final_report_duration_matches_clock(self):
        engine = TimeboxedLeaseEngine(target_duration_seconds=1800, lease_file=self.lease_path, clock=self.fake_clock)
        self.fake_clock.advance(1805.5)
        summary = engine.finalize(declared_status="COMPLETE")
        self.assertEqual(summary["actual_duration_seconds"], 1805.5)
        self.assertFalse(summary["did_stop_before_deadline"])

    def test_17_did_stop_before_deadline_is_mechanically_correct(self):
        engine_early = TimeboxedLeaseEngine(target_duration_seconds=1800, lease_file=self.lease_path, clock=self.fake_clock)
        self.fake_clock.advance(1200.0)
        summary_early = engine_early.finalize(declared_status="BLOCKED_SAFE", stop_reason="TEST")
        self.assertTrue(summary_early["did_stop_before_deadline"])

        fake_clock2 = FakeClock(start_monotonic=2000.0)
        engine_full = TimeboxedLeaseEngine(target_duration_seconds=1800, lease_file=self.lease_path, clock=fake_clock2)
        fake_clock2.advance(1800.0)
        summary_full = engine_full.finalize(declared_status="COMPLETE")
        self.assertFalse(summary_full["did_stop_before_deadline"])

    def test_18_synthetic_future_checkpoints_impossible(self):
        engine = TimeboxedLeaseEngine(target_duration_seconds=1800, lease_file=self.lease_path, clock=self.fake_clock)
        self.fake_clock.advance(297.0)
        engine.maybe_record_checkpoints()
        for cp in ["CHECKPOINT_05", "CHECKPOINT_10", "CHECKPOINT_15", "CHECKPOINT_20", "CHECKPOINT_25", "CHECKPOINT_30"]:
            self.assertEqual(engine.checkpoints[cp]["status"], "NOT_REACHED", f"{cp} must NOT be recorded at 297s")

    def test_19_production_mode_uses_real_clock(self):
        engine = TimeboxedLeaseEngine(target_duration_seconds=1800, lease_file=self.lease_path)
        self.assertIsInstance(engine.clock, RealClock, "Default engine clock must be RealClock")

    def test_20_no_artificial_idle_fill_in_source(self):
        engine_source = inspect.getsource(TimeboxedLeaseEngine)
        self.assertNotIn("sleep(1500)", engine_source)
        self.assertNotIn("sleep(1800)", engine_source)


if __name__ == "__main__":
    unittest.main()
