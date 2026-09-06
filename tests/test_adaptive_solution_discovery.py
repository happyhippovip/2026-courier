#!/usr/bin/env python3
"""Deterministic Test Suite for Adaptive Solution Discovery & Self-Tuning Cadence.

Verifies all requirements of the Chief Permanent Directive:
1. Adaptive Cadence Shrinking on Information Gain (3 -> 2 -> 1 day)
2. Adaptive Cadence Expanding on Stability / No-Change (3 -> 5 -> 7 days)
3. Immediate Event-Triggered Scan Overrides (Out-of-cycle search on provider failure)
4. Challenger vs. Incumbent Evaluation with Minimum Improvement Threshold
5. Safe Reversible Auto-Switching & Rollback
6. No-Change Result Reuse (0 Model Calls, 0 EUR Spend)
7. Weekly Strategic Floor Enforcement (7 Days)
"""

from __future__ import annotations

import datetime as dt
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.adaptive_solution_discovery import (
    AdaptiveSolutionDiscoveryEngine,
    AutoSwitchLevel,
    InformationGainClass,
    SearchDepth,
)


class TestAdaptiveSolutionDiscovery(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="adaptive_discovery_test_"))
        self.engine = AdaptiveSolutionDiscoveryEngine(repo_dir=self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_01_initial_cadence_defaults_to_3_days(self):
        """Initial search cadence is 3 days by default."""
        self.assertEqual(self.engine.current_cadence_days, 3)
        self.assertIn("REPOSITORY_ENGINEERING", self.engine.routes)
        self.assertIn("OPERATIONS_MONITORING", self.engine.routes)

    def test_02_cadence_shrinking_on_high_or_medium_info_gain(self):
        """Cadence shortens toward 1 day upon high/medium information gain."""
        # Medium info gain drops 3 -> 2
        new_cadence_medium = self.engine.adjust_cadence(
            info_gain=InformationGainClass.MEDIUM_INFORMATION_GAIN,
            consecutive_no_change=0,
        )
        self.assertEqual(new_cadence_medium, 2)

        # High info gain drops 2 -> 1
        self.engine.current_cadence_days = 2
        new_cadence_high = self.engine.adjust_cadence(
            info_gain=InformationGainClass.HIGH_INFORMATION_GAIN,
            consecutive_no_change=0,
        )
        self.assertEqual(new_cadence_high, 1)

    def test_03_cadence_expanding_on_consecutive_no_change_scans(self):
        """Cadence extends toward 5-7 days upon consecutive no-change scans."""
        self.engine.current_cadence_days = 3

        # Consecutive no change >= 2 expands 3 -> 5
        c1 = self.engine.adjust_cadence(
            info_gain=InformationGainClass.NO_INFORMATION_GAIN,
            consecutive_no_change=2,
        )
        self.assertEqual(c1, 5)

        # Subsequent no change expands 5 -> 7
        self.engine.current_cadence_days = 5
        c2 = self.engine.adjust_cadence(
            info_gain=InformationGainClass.NO_INFORMATION_GAIN,
            consecutive_no_change=3,
        )
        self.assertEqual(c2, 7)

    def test_04_immediate_event_triggered_scan_override(self):
        """Emergency or provider failure immediately triggers out-of-cycle search."""
        self.engine.current_cadence_days = 7
        audit = self.engine.run_adaptive_solution_discovery(
            event_override="PROVIDER_QUOTA_EXHAUSTED",
        )

        self.assertEqual(audit.search_depth, SearchDepth.NORMAL_SCAN)
        self.assertIn("EVENT_OVERRIDE_PROVIDER_QUOTA_EXHAUSTED", audit.trigger_reason)
        self.assertEqual(audit.information_gain_class, InformationGainClass.HIGH_INFORMATION_GAIN)
        self.assertLessEqual(audit.new_cadence_days, 2)

    def test_05_challenger_evaluation_and_minimum_improvement_threshold(self):
        """Challenger must exceed minimum threshold (+15%) for primary switch."""
        # Marginal improvement (< 15%) remains Level C / Level B
        level_marginal, _ = self.engine.evaluate_challenger(
            task_class="REPOSITORY_ENGINEERING",
            challenger_surface="Challenger Alpha",
            metrics={"composite_score": 0.94, "incumbent_composite_score": 0.90, "sample_count": 2},
        )
        self.assertEqual(level_marginal, AutoSwitchLevel.LEVEL_C_LIMITED_ROUTING)

        # Clear superiority (> 15% with >= 3 samples) triggers Level D Primary Switch
        level_superior, _ = self.engine.evaluate_challenger(
            task_class="REPOSITORY_ENGINEERING",
            challenger_surface="Challenger Beta",
            metrics={"composite_score": 0.98, "incumbent_composite_score": 0.80, "sample_count": 5},
        )
        self.assertEqual(level_superior, AutoSwitchLevel.LEVEL_D_PRIMARY_SWITCH)

        # Inferior score remains Level A
        level_inferior, _ = self.engine.evaluate_challenger(
            task_class="REPOSITORY_ENGINEERING",
            challenger_surface="Challenger Gamma",
            metrics={"composite_score": 0.70, "incumbent_composite_score": 0.90, "sample_count": 5},
        )
        self.assertEqual(level_inferior, AutoSwitchLevel.LEVEL_A_NO_CHANGE)

    def test_06_safe_reversible_auto_switch_and_rollback(self):
        """Auto-switch preserves rollback route and can be cleanly rolled back."""
        # 1. Execute reversible switch
        switch_res = self.engine.execute_reversible_switch(
            task_class="OPERATIONS_MONITORING",
            new_route="Autonomous Stream Observer v2",
            reason="Verified 20% lower latency on telemetry digestion",
        )
        self.assertEqual(switch_res["old_route"], "CLI1 / Snitch Observer")
        self.assertEqual(switch_res["new_route"], "Autonomous Stream Observer v2")
        self.assertEqual(switch_res["rollback_route"], "CLI1 / Snitch Observer")

        # 2. Verify state persistence
        reloaded_engine = AdaptiveSolutionDiscoveryEngine(repo_dir=self.test_dir)
        r_state = reloaded_engine.routes["OPERATIONS_MONITORING"]
        self.assertEqual(r_state.incumbent_surface, "Autonomous Stream Observer v2")
        self.assertEqual(r_state.rollback_route, "CLI1 / Snitch Observer")

        # 3. Execute rollback
        rollback_res = reloaded_engine.execute_rollback(
            task_class="OPERATIONS_MONITORING",
            reason="Observed edge case memory spike in stream observer",
        )
        self.assertEqual(rollback_res["restored_to"], "CLI1 / Snitch Observer")
        self.assertIsNone(reloaded_engine.routes["OPERATIONS_MONITORING"].rollback_route)

    def test_07_no_change_result_reuse_avoids_model_calls(self):
        """When no change occurred, search reuses stable state with 0 model calls and 0 EUR spend."""
        # Set next search in the future
        future_ts = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=3)).isoformat()
        self.engine.next_search_at = future_ts

        audit = self.engine.run_adaptive_solution_discovery()

        self.assertEqual(audit.search_fingerprint, "REUSED_PREVIOUS_STABLE_STATE")
        self.assertEqual(audit.model_calls, 0)
        self.assertEqual(audit.model_calls_avoided, 1)
        self.assertEqual(audit.spend_eur, 0.0)

    def test_08_weekly_strategic_floor_triggers_scan_after_7_days(self):
        """Weekly strategic floor triggers evaluation after 7 days even if fully stable."""
        eight_days_ago = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=8)).isoformat()
        self.engine.last_search_at = eight_days_ago
        # Set next search in future to ensure floor takes priority
        self.engine.next_search_at = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=2)).isoformat()

        should_scan, reason, depth = self.engine.evaluate_daily_change_check()

        self.assertTrue(should_scan)
        self.assertEqual(reason, "WEEKLY_STRATEGIC_FLOOR_ELAPSED")
        self.assertEqual(depth, SearchDepth.NORMAL_SCAN)


if __name__ == "__main__":
    unittest.main()
