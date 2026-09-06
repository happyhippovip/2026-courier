#!/usr/bin/env python3
"""Acceptance Tests for Canonical Autonomy Orchestrator (Mission 2026-Projektzentrale)."""

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.autonomy_orchestrator import (
    AutonomyOrchestrator,
    RoutingAction,
    SafeJob,
    WorkerRole,
    WorkerState,
)


class TestAutonomyOrchestrator(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="orch_test_"))
        self.orch = AutonomyOrchestrator(repo_dir=self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_01_no_manual_weiter_google_to_cli2(self):
        """When Google builder completes, automatically routes to CLI2 without manual WEITER."""
        action, _ = self.orch.route(
            event_name="GOOGLE_COMPLETED",
            event_payload={"fingerprint": "abc123hash"},
        )
        self.assertEqual(action, RoutingAction.CLI2_FINAL_ATTACK)

        # Execute safe next step automatically enqueues CLI2 test
        act, detail = self.orch.execute_next_step()
        self.assertEqual(act, RoutingAction.CLI2_FINAL_ATTACK)
        self.assertTrue(any(j.job_type == "CLI2_ADVERSARIAL_TEST" for j in self.orch.queue))

    def test_02_cli2_pass_routes_to_codex(self):
        """When CLI2 passes same fingerprint, automatically routes to Codex acceptance review."""
        self.orch.active_fingerprint = "abc123hash"
        action, _ = self.orch.route(
            event_name="CLI2_FINAL_ATTACK_PASS",
            event_payload={"fingerprint": "abc123hash"},
        )
        self.assertEqual(action, RoutingAction.CODEX_FINAL_ACCEPTANCE)

        act, detail = self.orch.execute_next_step()
        self.assertEqual(act, RoutingAction.CODEX_FINAL_ACCEPTANCE)
        self.assertTrue(any(j.job_type == "CODEX_ACCEPTANCE_REVIEW" for j in self.orch.queue))

    def test_03_cli2_defect_and_codex_remediate_route_to_google(self):
        """CLI2 defects or Codex remediation requests route back to Google builder."""
        action, _ = self.orch.route(event_name="CLI2_HIGH_DEFECT")
        self.assertEqual(action, RoutingAction.GOOGLE_REMEDIATE)

        action2, _ = self.orch.route(event_name="CODEX_REMEDIATE")
        self.assertEqual(action2, RoutingAction.GOOGLE_REMEDIATE)

    def test_04_codex_release_unlocks_next_mission(self):
        """Codex release verdict unlocks next safe autonomy phase automatically."""
        action, _ = self.orch.route(event_name="CODEX_RELEASE")
        self.assertEqual(action, RoutingAction.ENABLE_NEXT_SAFE_AUTONOMY_PHASE)

        act, detail = self.orch.execute_next_step()
        self.assertEqual(detail, "NEXT_PHASE_UNLOCKED")

    def test_05_quota_and_surface_block_wait_safely(self):
        """Provider quota exhaustion or surface block transitions to WAITING_RESOURCE."""
        act1, _ = self.orch.route(event_name="PROVIDER_QUOTA_REACHED")
        self.assertEqual(act1, RoutingAction.WAITING_RESOURCE)

        act2, _ = self.orch.route(event_name="CODEX_EXECUTION_SURFACE_BLOCK")
        self.assertEqual(act2, RoutingAction.WAITING_RESOURCE)

    def test_06_pid_none_not_alive_and_dead_pid_orphaned(self):
        """pid=None is never assumed alive; dead PID transitions to ORPHANED."""
        st = self.orch.observe_worker_liveness(WorkerRole.CLI1.value, pid=None)
        self.assertEqual(st, WorkerState.SAFE_IDLE)

        st2 = self.orch.observe_worker_liveness(WorkerRole.CLI2.value, pid=99999999)
        self.assertEqual(st2, WorkerState.ORPHANED)

    def test_07_dependency_enforcement_and_no_duplicate_execution(self):
        """Jobs with unmet dependencies are not executed; completed jobs are not re-executed."""
        self.orch.enqueue_job(job_id="job-dep-1", job_type="BUILD_STEP", priority=10)
        self.orch.enqueue_job(
            job_id="job-dep-2",
            job_type="VERIFY_STEP",
            priority=5,
            dependencies=["job-dep-1"],
        )

        # First step should execute job-dep-1 (even though job-dep-2 has higher priority, its dep is unmet)
        act, j_id = self.orch.execute_next_step(runner_fn=lambda j: True)
        self.assertEqual(j_id, "job-dep-1")
        self.assertIn("job-dep-1", self.orch.completed_job_ids)

        # Second step can now execute job-dep-2
        act2, j_id2 = self.orch.execute_next_step(runner_fn=lambda j: True)
        self.assertEqual(j_id2, "job-dep-2")
        self.assertIn("job-dep-2", self.orch.completed_job_ids)

    def test_08_paid_action_and_human_gate_block_fail_closed(self):
        """Paid jobs block at WAITING_PERMISSION; human gates block at WAITING_HUMAN."""
        self.orch.enqueue_job(job_id="job-paid", job_type="PURCHASE", requires_payment=True)
        act, _ = self.orch.route()
        self.assertEqual(act, RoutingAction.WAITING_PERMISSION)

        self.orch.queue.clear()
        self.orch.enqueue_job(job_id="job-human", job_type="OAUTH", requires_human=True)
        act2, _ = self.orch.route()
        self.assertEqual(act2, RoutingAction.WAITING_HUMAN)

    def test_09_checkpoint_persistence_and_restart(self):
        """State, queue, and completed jobs survive orchestrator restart."""
        self.orch.enqueue_job(job_id="job-persisted", job_type="TASK_A")
        self.orch.completed_job_ids.add("job-old-done")
        self.orch.save_checkpoint()

        new_orch = AutonomyOrchestrator(repo_dir=self.test_dir)
        self.assertIn("job-old-done", new_orch.completed_job_ids)
        self.assertTrue(any(j.job_id == "job-persisted" for j in new_orch.queue))


if __name__ == "__main__":
    unittest.main()
