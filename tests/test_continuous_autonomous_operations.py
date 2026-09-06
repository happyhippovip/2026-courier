#!/usr/bin/env python3
"""Acceptance Tests for Continuous Autonomous Operations & Resource-Aware Routing."""

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.autonomy_orchestrator import WorkerRole, WorkerState
from scripts.continuous_operations_engine import ContinuousOperationsEngine
from scripts.resource_aware_model_router import (
    ModelGroup,
    ResourceAwareModelRouter,
)


class TestContinuousAutonomousOperations(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="cont_ops_test_"))
        self.engine = ContinuousOperationsEngine(repo_dir=self.test_dir)
        self.router = ResourceAwareModelRouter(repo_dir=self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_01_google_candidate_triggers_cli2_attack_automatically(self):
        """GOOGLE candidate ready automatically dispatches CLI2 attack without manual WEITER."""
        res = self.engine.step_continuous_cycle(
            event_name="GOOGLE_COMPLETED",
            event_payload={"fingerprint": "abc1234567890"},
        )
        self.assertFalse(res.manual_weiter_required)
        self.assertEqual(res.active_worker, WorkerRole.CLI2.value)
        self.assertIn("CLI2_ATTACK_DISPATCHED", res.action_taken)

    def test_02_cli2_high_defect_triggers_google_remediate_automatically(self):
        """CLI2 HIGH defect automatically triggers GOOGLE remediation without manual WEITER."""
        res = self.engine.step_continuous_cycle(
            event_name="CLI2_HIGH_DEFECT",
            event_payload={"defect": "Authority leak in scope locking"},
        )
        self.assertFalse(res.manual_weiter_required)
        self.assertEqual(res.active_worker, WorkerRole.GOOGLE.value)
        self.assertEqual(res.action_taken, "GOOGLE_REMEDIATE_TRIGGERED")

    def test_03_cli2_pass_triggers_codex_acceptance_automatically(self):
        """CLI2 pass automatically dispatches CODEX acceptance without manual WEITER."""
        res = self.engine.step_continuous_cycle(
            event_name="CLI2_FINAL_ATTACK_PASS",
            event_payload={"fingerprint": "abc1234567890"},
        )
        self.assertFalse(res.manual_weiter_required)
        self.assertEqual(res.active_worker, WorkerRole.CODEX.value)
        self.assertEqual(res.action_taken, "CODEX_ACCEPTANCE_DISPATCHED")

    def test_04_resource_aware_model_routing_fallback_to_claude_when_gemini_zero(self):
        """When Gemini quota is 0%, router seamlessly assigns Claude 3.5 Sonnet."""
        self.router.record_quota_observation("ANTIGRAVITY_BEATA", ModelGroup.GEMINI_MODELS, 0.0)
        self.router.record_quota_observation("ANTIGRAVITY_BEATA", ModelGroup.CLAUDE_MODELS, 100.0)

        dec = self.router.select_best_model_for_task(
            task_id="test-task-1",
            task_type="ADVERSARIAL_TEST",
            preferred_worker_id="CLI2",
            compatible_groups=[ModelGroup.GEMINI_MODELS, ModelGroup.CLAUDE_MODELS],
        )
        self.assertEqual(dec.routing_verdict, "ROUTED_SUCCESS")
        self.assertEqual(dec.assigned_model_group, ModelGroup.CLAUDE_MODELS.value)
        self.assertEqual(dec.assigned_model_name, "claude-3-5-sonnet")
        self.assertEqual(dec.spend_eur, 0.0)

    def test_05_all_quotas_exhausted_transitions_to_waiting_resource(self):
        """When all compatible models are exhausted, router sets WAITING_RESOURCE (0 EUR spend)."""
        self.router.record_quota_observation("ANTIGRAVITY_BEATA", ModelGroup.GEMINI_MODELS, 0.0)
        self.router.record_quota_observation("ANTIGRAVITY_BEATA", ModelGroup.CLAUDE_MODELS, 0.0)

        dec = self.router.select_best_model_for_task(
            task_id="test-task-2",
            task_type="ADVERSARIAL_TEST",
            preferred_worker_id="CLI2",
            compatible_groups=[ModelGroup.GEMINI_MODELS, ModelGroup.CLAUDE_MODELS],
        )
        self.assertEqual(dec.routing_verdict, "WAITING_RESOURCE")
        self.assertEqual(dec.spend_eur, 0.0)

    def test_06_chain_of_safe_jobs_executed_continuously_without_weiter(self):
        """A series of safe jobs execute sequentially without requiring manual WEITER."""
        j1 = self.engine.orchestrator.enqueue_job("job-1", "SAFE_TEST_A", priority=10)
        j2 = self.engine.orchestrator.enqueue_job("job-2", "SAFE_TEST_B", priority=20, dependencies=["job-1"])

        # Execute step 1 (job-1)
        r1 = self.engine.step_continuous_cycle(execute_fn=lambda j: True)
        self.assertEqual(r1.job_id, "job-1")
        self.assertEqual(r1.action_taken, "JOB_COMPLETED_job-1")
        self.assertFalse(r1.manual_weiter_required)

        # Execute step 2 (job-2 becomes eligible now that job-1 is completed)
        r2 = self.engine.step_continuous_cycle(execute_fn=lambda j: True)
        self.assertEqual(r2.job_id, "job-2")
        self.assertEqual(r2.action_taken, "JOB_COMPLETED_job-2")
        self.assertFalse(r2.manual_weiter_required)

    def test_07_payment_job_blocks_at_waiting_permission(self):
        """Job requiring payment strictly blocks at WAITING_PERMISSION."""
        self.engine.orchestrator.enqueue_job("job-pay-1", "BUY_SUBSCRIPTION", priority=5, requires_payment=True)
        res = self.engine.step_continuous_cycle()
        self.assertEqual(res.action_taken, "WAITING_PERMISSION")
        self.assertTrue(res.manual_weiter_required)


if __name__ == "__main__":
    unittest.main()
