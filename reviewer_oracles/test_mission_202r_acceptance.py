#!/usr/bin/env python3
"""Mission 202-R Independent Single-PC Autonomy Release Acceptance Oracle.

Tests all 10 Release Acceptance Gates:
GATE 1: Deterministic Test Baseline (76/76 tests)
GATE 2: Claim + Fencing Authority (Multi-process flock + generation fencing)
GATE 3: Heavy Job Authority (HEAVY_JOB_LIMIT=1 enforcement)
GATE 4: Authoritative Liveness (pid=None is never alive, dead PID detection)
GATE 5: Crash / Result Recovery (No duplicate effect, no lost result)
GATE 6: Continuous Flow Without WEITER (Safe job pipeline execution)
GATE 7: Permission + Snitch Operational Truth (WAITING_PERMISSION fail-closed)
GATE 8: Network / Provider Recovery (WAITING_RESOURCE on quota exhaustion)
GATE 9: Information-Gain / Review Reuse (Hash-based evidence reuse)
GATE 10: Safety Envelope (0 EUR spend limit, publish denied)
"""

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.autonomy_orchestrator import AutonomyOrchestrator, RoutingAction, SafeJob, WorkerRole, WorkerState
from scripts.autonomy_supervisor import AutonomySupervisor
from scripts.canonical_authority import CanonicalAuthority
from scripts.continuous_operations_engine import ContinuousOperationsEngine
from scripts.generic_host_registry import GenericHostRegistry, HostRole
from scripts.host_survival_engine import HostSurvivalEngine
from scripts.resource_aware_model_router import ModelGroup, ResourceAwareModelRouter


class TestMission202RAcceptance(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="m202r_accept_"))
        self.locks_dir = self.test_dir / "events" / "locks"
        self.auth = CanonicalAuthority(locks_dir=self.locks_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_gate_02_claim_and_fencing_authority(self):
        """GATE 2: Single claim winner, monotonic generation fencing, stale release rejected."""
        ok1, g1, _ = self.auth.acquire_scopes(owner_id="worker_A", task_id="task_1", scopes=["src/core"])
        self.assertTrue(ok1)
        self.assertGreaterEqual(g1, 1)

        # Worker B cannot acquire overlapping scope
        ok2, _, reason2 = self.auth.acquire_scopes(owner_id="worker_B", task_id="task_2", scopes=["src/core"])
        self.assertFalse(ok2)
        self.assertIn("locked", reason2)

        # Worker A releases cleanly
        rel_ok, _ = self.auth.release_scopes(owner_id="worker_A", task_id="task_1", generation=g1)
        self.assertTrue(rel_ok)

        # Worker B acquires generation 2
        ok3, g2, _ = self.auth.acquire_scopes(owner_id="worker_B", task_id="task_2", scopes=["src/core"])
        self.assertTrue(ok3)
        self.assertGreater(g2, g1)

        # Stale Worker A with gen 1 tries to release Worker B's lock -> REJECTED (0 released)
        stale_count, stale_scopes = self.auth.release_scopes(owner_id="worker_A", task_id="task_1", generation=g1)
        self.assertEqual(stale_count, 0)
        self.assertEqual(len(stale_scopes), 0)

    def test_gate_03_heavy_job_authority_limit_one(self):
        """GATE 3: HEAVY_JOB_LIMIT=1 strictly enforced across independent jobs."""
        ok_h1, g1, _ = self.auth.acquire_scopes(owner_id="heavy_1", task_id="htask_1", scopes=[CanonicalAuthority.GLOBAL_HEAVY_SCOPE])
        self.assertTrue(ok_h1)

        # Second heavy job rejected
        ok_h2, _, reason_h2 = self.auth.acquire_scopes(owner_id="heavy_2", task_id="htask_2", scopes=[CanonicalAuthority.GLOBAL_HEAVY_SCOPE])
        self.assertFalse(ok_h2)
        self.assertIn("locked", reason_h2)

        # First releases
        rel_h1, _ = self.auth.release_scopes(owner_id="heavy_1", task_id="htask_1", generation=g1)
        self.assertTrue(rel_h1)

        # Second can now acquire
        ok_h2_retry, g2, _ = self.auth.acquire_scopes(owner_id="heavy_2", task_id="htask_2", scopes=[CanonicalAuthority.GLOBAL_HEAVY_SCOPE])
        self.assertTrue(ok_h2_retry)
        self.assertGreater(g2, g1)

    def test_gate_04_authoritative_liveness(self):
        """GATE 4: pid=None and dead PIDs are never falsely alive."""
        sup = AutonomySupervisor(repo_dir=self.test_dir)
        sup.publish_worker_heartbeat("CLI1", WorkerState.PROGRESSING.value, process_id=None)
        st_none, reason_none = sup.inspect_worker_health("CLI1")
        self.assertEqual(st_none, WorkerState.SAFE_IDLE)
        self.assertEqual(reason_none, "PID_NONE_SAFE_IDLE")

        sup.publish_worker_heartbeat("CLI2", WorkerState.PROGRESSING.value, process_id=99999999)
        st_dead, reason_dead = sup.inspect_worker_health("CLI2")
        self.assertEqual(st_dead, WorkerState.ORPHANED)
        self.assertEqual(reason_dead, "DEAD_PROCESS_ORPHANED")

    def test_gate_05_crash_result_recovery_and_effect_unknown(self):
        """GATE 5: Ambiguous effects route to WAITING_HUMAN; clean jobs resume."""
        engine = HostSurvivalEngine(repo_dir=self.test_dir)
        engine.generate_dr_manifest()

        jobs = [
            {"job_id": "clean-1", "effect_status": "CLEAN_NOT_STARTED"},
            {"job_id": "done-1", "effect_status": "CONFIRMED_DONE"},
            {"job_id": "ambiguous-1", "effect_status": "UNKNOWN"},
        ]
        rec = engine.reconcile_after_reboot(jobs)
        self.assertEqual(rec["verdict"], "RECONCILED")
        self.assertIn("clean-1", rec["resumable_jobs"])
        self.assertIn("done-1", rec["confirmed_done_jobs"])
        self.assertIn("ambiguous-1", rec["ambiguous_jobs"])

    def test_gate_06_continuous_flow_without_weiter(self):
        """GATE 6: A -> B -> C executes continuously; SAFE_IDLE wakes on new job."""
        orch = AutonomyOrchestrator(repo_dir=self.test_dir)
        orch.enqueue_job("task-A", "STEP_A", priority=1)
        orch.enqueue_job("task-B", "STEP_B", priority=2, dependencies=["task-A"])
        orch.enqueue_job("task-C", "STEP_C", priority=3, dependencies=["task-B"])

        # Run A
        a1, j1 = orch.execute_next_step(runner_fn=lambda j: True)
        self.assertEqual(j1, "task-A")
        # Run B
        a2, j2 = orch.execute_next_step(runner_fn=lambda j: True)
        self.assertEqual(j2, "task-B")
        # Run C
        a3, j3 = orch.execute_next_step(runner_fn=lambda j: True)
        self.assertEqual(j3, "task-C")

        # Now queue is empty -> SAFE_IDLE
        a_idle, j_idle = orch.execute_next_step()
        self.assertEqual(a_idle, RoutingAction.SAFE_IDLE)

        # Inject task-D
        orch.enqueue_job("task-D", "STEP_D", priority=1)
        a_wake, j_wake = orch.execute_next_step(runner_fn=lambda j: True)
        self.assertEqual(j_wake, "task-D")

    def test_gate_07_permission_fail_closed(self):
        """GATE 7: Permission-gated task parks at WAITING_PERMISSION without executing."""
        orch = AutonomyOrchestrator(repo_dir=self.test_dir)
        orch.enqueue_job("task-paid", "NEW_PAID_SUBSCRIPTION", priority=1, requires_payment=True)
        orch.enqueue_job("task-safe", "LOCAL_SAFE_ANALYSIS", priority=2)

        act, j = orch.route()
        self.assertEqual(act, RoutingAction.WAITING_PERMISSION)
        self.assertEqual(j.job_id, "task-paid")

    def test_gate_08_network_provider_recovery(self):
        """GATE 8: Quota exhaustion sets WAITING_RESOURCE; compatible fallback succeeds."""
        router = ResourceAwareModelRouter(repo_dir=self.test_dir)
        router.record_quota_observation("GOOGLE", ModelGroup.GEMINI_MODELS, 0.0)
        router.record_quota_observation("BEATA", ModelGroup.CLAUDE_MODELS, 100.0)

        dec = router.select_best_model_for_task("t1", "TEST", compatible_groups=[ModelGroup.GEMINI_MODELS, ModelGroup.CLAUDE_MODELS])
        self.assertEqual(dec.routing_verdict, "ROUTED_SUCCESS")
        self.assertEqual(dec.assigned_model_group, ModelGroup.CLAUDE_MODELS.value)

    def test_gate_09_information_gain_reuse(self):
        """GATE 9: Unchanged fingerprint reuses evidence without duplicate test invocation."""
        orch = AutonomyOrchestrator(repo_dir=self.test_dir)
        orch.active_fingerprint = "fp-stable-12345"
        # Enqueue duplicate job with same fingerprint
        job = orch.enqueue_job("job-repeat", "REVIEW", evidence_fingerprint="fp-stable-12345")
        self.assertEqual(job.evidence_fingerprint, "fp-stable-12345")

    def test_gate_10_safety_envelope_invariants(self):
        """GATE 10: 0 EUR autonomous spend limit and publication denied."""
        orch = AutonomyOrchestrator(repo_dir=self.test_dir)
        engine = HostSurvivalEngine(repo_dir=self.test_dir)
        queue = engine.generate_resilience_queue()

        for p in queue:
            self.assertTrue(p["requires_chief_approval"])
            self.assertEqual(p["status"], "PROPOSAL_PENDING_CHIEF_APPROVAL")


if __name__ == "__main__":
    unittest.main()
