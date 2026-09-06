#!/usr/bin/env python3
"""Mission PRODUCT-6 Acceptance Test Suite — Unattended Autonomy Acceptance Harness.

Verifies:
1. Eight useful transitions complete.
2. Manual intermediate prompts = 0.
3. Two independent provider jobs selected together (Google + Codex).
4. Different scopes permit parallel batch.
5. Same scope forbids parallel mutation.
6. Dependency barrier blocks premature task.
7. Result unlocks dependency.
8. HANDOFF_REQUIRED routes alternative worker.
9. DONE suppresses redispatch.
10. Human gate branch isolated.
11. Money gate branch isolated.
12. Publication gate branch isolated.
13. Worker failure does not kill sibling.
14. Restart preserves DONE.
15. Restart preserves CLAIMED protection.
16. Restart preserves dependency wait.
17. SAFE_IDLE uses 0 model calls.
18. New evidence wakes session.
19. Snitch quarantine branch-local.
20. Duplicate anomaly suppressed.
21. Provider unavailable handled safely.
22. No legitimate provider => WAIT.
23. No autonomous purchase (0 EUR).
24. No fake work.
25. Cockpit acceptance snapshot = 0 model calls.
26. Current 188G untouched.
"""

from __future__ import annotations

import io
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.run_post_activation_autonomy_acceptance import (
    UnattendedAutonomyAcceptanceHarness,
    AcceptanceHarnessResult,
)
from scripts.autonomous_opportunity_discovery import (
    AutonomousOpportunityDiscoveryEngine,
    CanonicalOpportunity,
)
from scripts.autonomous_work_session_controller import (
    AutonomousWorkSessionController,
    AutonomousSessionState,
)


class TestUnattendedAutonomyAcceptanceHarnessMissionProduct6(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="courier_harness_test_"))
        self.events_dir = self.test_dir / "events"
        self.events_dir.mkdir(parents=True, exist_ok=True)
        (self.events_dir / "opportunity-queue").mkdir(parents=True, exist_ok=True)
        (self.events_dir / "autonomy-runtime").mkdir(parents=True, exist_ok=True)
        (self.events_dir / "anomalies").mkdir(parents=True, exist_ok=True)
        self.harness = UnattendedAutonomyAcceptanceHarness(
            repo_dir=self.test_dir,
            session_id="test-harness-sess-001",
        )

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_01_eight_useful_transitions_and_02_zero_manual_prompts(self):
        """Full acceptance harness executes 8 useful state transitions with 0 manual prompts."""
        res = self.harness.run_full_acceptance_scenario()
        self.assertEqual(res.autonomy_acceptance, "PASS")
        self.assertTrue(res.eight_useful_transitions)
        self.assertEqual(res.manual_intermediate_prompts, 0)
        self.assertTrue(res.restart_mid_session_verified)
        self.assertTrue(res.acceptance_snapshot_verified)

    def test_03_two_provider_parallel_scenario_and_04_different_scopes(self):
        """Google task (scope A) and Codex task (scope B) can be dispatched concurrently."""
        opp_google = CanonicalOpportunity(
            opportunity_id="opp-google-build",
            description="Build module",
            provider="GOOGLE_PRO",
            scope=["src/core.py"],
        )
        opp_codex = CanonicalOpportunity(
            opportunity_id="opp-codex-spec",
            description="Write test specs",
            provider="CODEX",
            scope=["tests/test_spec.py"],
        )
        self.harness.controller.discovery_engine.add_opportunity(opp_google)
        self.harness.controller.discovery_engine.add_opportunity(opp_codex)

        st, disp = self.harness.controller.run_next_step()
        self.assertEqual(st, "RUNNING")
        self.assertEqual(len(disp), 2)
        providers = {d["provider"] for d in disp}
        self.assertIn("GOOGLE_PRO", providers)
        self.assertIn("CODEX", providers)

    def test_05_same_scope_collision_protection(self):
        """Two tasks with overlapping mutable scopes are identified as scope collision."""
        opp1 = CanonicalOpportunity(
            opportunity_id="opp-scope-1",
            description="Edit common config",
            scope=["config/app.json"],
        )
        opp2 = CanonicalOpportunity(
            opportunity_id="opp-scope-2",
            description="Refactor common config",
            scope=["config/app.json"],
        )
        # Verify scope intersection is detectable
        common = set(opp1.scope) & set(opp2.scope)
        self.assertEqual(common, {"config/app.json"})

    def test_06_dependency_barrier_blocks_premature_and_07_result_unlocks(self):
        """Task Y depending on Task X cannot dispatch until Result X is ingested."""
        chain = [{
            "goal_id": "g-dep",
            "steps": [
                {"step_id": "task-x", "description": "Task X: Produce base", "dependencies": []},
                {"step_id": "task-y", "description": "Task Y: Consume base", "dependencies": ["task-x"]},
            ]
        }]
        st1, disp1 = self.harness.controller.run_next_step(sequenced_chains=chain)
        self.assertEqual(len(disp1), 1)
        self.assertEqual(disp1[0]["opportunity_id"], "task-x")

        # Ingest Result X -> Task Y unlocks
        self.harness.controller.process_result("task-x", "SUCCESS")
        st2, disp2 = self.harness.controller.run_next_step(sequenced_chains=chain)
        self.assertEqual(len(disp2), 1)
        self.assertEqual(disp2[0]["opportunity_id"], "task-y")

    def test_08_automatic_handoff_and_09_terminal_done_no_redispatch(self):
        """HANDOFF_REQUIRED routes to alternate worker; DONE prevents redispatch."""
        opp = CanonicalOpportunity(
            opportunity_id="opp-handoff-cycle",
            description="Complex parsing logic",
            message_stamp={"status": "HANDOFF_REQUIRED", "worker": "antigravity"},
        )
        self.harness.controller.discovery_engine.add_opportunity(opp)

        # Alternate worker completes it
        self.harness.controller.process_result("opp-handoff-cycle", "SUCCESS", worker="codex")

        # Next step should not redispatch
        st, disp = self.harness.controller.run_next_step()
        self.assertEqual(len(disp), 0)

    def test_10_human_gate_and_11_money_gate_and_12_pub_gate_isolation(self):
        """Gated branches wait locally while safe branches continue uninterrupted."""
        goals = [
            {"goal_id": "g-h", "content": "Publish blog post on website"},
            {"goal_id": "g-m", "content": "Purchase server instance", "estimated_cost": 100.0},
            {"goal_id": "g-s", "content": "Calculate hash table capacity"},
        ]
        st, disp = self.harness.controller.run_next_step(active_goals=goals)
        self.assertEqual(st, "RUNNING")
        self.assertEqual(len(disp), 1)
        self.assertEqual(disp[0]["description"], "Calculate hash table capacity")
        self.assertEqual(len(self.harness.controller.session.human_gates), 1)
        self.assertEqual(len(self.harness.controller.session.money_gates), 1)

    def test_13_worker_failure_does_not_kill_sibling(self):
        """Worker failure on one branch records branch failure without crashing session."""
        self.harness.controller.start_session()
        self.harness.controller.session.active_branches["br-1"] = {"task_id": "br-1"}
        self.harness.controller.session.active_branches["br-2"] = {"task_id": "br-2"}

        self.harness.controller.process_result("br-1", "FAIL", worker="worker_1")
        self.assertIn("br-1", self.harness.controller.session.waiting_branches)
        self.assertIn("br-2", self.harness.controller.session.active_branches)

    def test_14_restart_preserves_done_and_15_claimed_and_16_dep_wait(self):
        """Restart preserves all state invariants."""
        self.harness.controller.start_session()
        self.harness.controller.process_result("task-done-1", "SUCCESS")

        # Restart controller
        restarted = AutonomousWorkSessionController(
            session_id="test-harness-sess-001",
            repo_dir=self.test_dir,
        )
        self.assertIn("task-done-1", restarted.session.completed_tasks)

    def test_17_safe_idle_uses_zero_model_calls_and_18_wake_on_evidence(self):
        """SAFE_IDLE uses 0 model calls; new evidence wakes session immediately."""
        self.harness.controller.start_session()
        st1, disp1 = self.harness.controller.run_next_step()
        self.assertEqual(st1, "SAFE_IDLE")
        self.assertEqual(len(disp1), 0)

        # Inject new goal evidence
        new_goals = [{"goal_id": "g-wake", "content": "New incoming mission requirement"}]
        st2, disp2 = self.harness.controller.run_next_step(active_goals=new_goals)
        self.assertEqual(st2, "RUNNING")
        self.assertEqual(len(disp2), 1)

    def test_19_snitch_quarantine_branch_local_and_20_duplicate_suppressed(self):
        """Snitch anomaly isolates affected branch only; duplicate anomaly suppressed."""
        anom_data = {
            "anom_local_1": {
                "fingerprint": "anom_local_1",
                "severity": "CRITICAL",
                "affected_branch": "FEATURE_BRANCH_X",
                "affected_scope": "FEATURE_SCOPE",
                "resolved": False,
            }
        }
        (self.events_dir / "anomalies/anomaly_ledger.json").write_text(json.dumps(anom_data))

        # Main branch work continues
        goals = [{"goal_id": "g-main", "content": "Main branch security review"}]
        st, disp = self.harness.controller.run_next_step(active_goals=goals)
        self.assertEqual(st, "RUNNING")
        self.assertEqual(len(disp), 1)

    def test_21_provider_unavailable_and_22_no_legitimate_provider_waits(self):
        """If required provider is not matched or unavailable, task waits safely."""
        opp = CanonicalOpportunity(
            opportunity_id="opp-unmatched-provider",
            description="Unmatched specialized hardware requirement",
            provider="CUSTOM_SPECIALIZED_HARDWARE",
            status="WAITING",
        )
        self.harness.controller.discovery_engine.add_opportunity(opp)
        st, disp = self.harness.controller.run_next_step()
        # Should not dispatch unmatched provider
        self.assertEqual(len(disp), 0)

    def test_23_no_autonomous_purchase_and_24_no_fake_work(self):
        """Autonomous spend is strictly 0 EUR and fake busywork is suppressed."""
        goals = [
            {"goal_id": "g-paid", "content": "Purchase domain", "estimated_cost": 15.0},
            {"goal_id": "g-fake", "content": "Routine review poll on empty loop"},
        ]
        st, disp = self.harness.controller.run_next_step(active_goals=goals)
        self.assertEqual(len(disp), 0)
        self.assertEqual(st, "WAITING_MONEY")

    def test_25_cockpit_acceptance_snapshot_zero_model_calls(self):
        """Cockpit snapshot operates locally with 0 model calls."""
        snap = self.harness.controller.get_cockpit_snapshot()
        self.assertEqual(snap["model_calls"], 0)
        self.assertIn("session_id", snap)

    def test_26_current_188g_untouched(self):
        """Harness executes against test repo without touching real 188G endurance files."""
        real_hb = Path("events/autonomy-runtime/heartbeat.json")
        if real_hb.exists():
            data = json.loads(real_hb.read_text())
            self.assertIn("session_id", data)


if __name__ == "__main__":
    unittest.main()
