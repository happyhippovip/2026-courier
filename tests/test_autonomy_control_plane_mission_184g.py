#!/usr/bin/env python3
"""Targeted unit tests for Mission 184G: Autonomy Control Plane & Sleep-Runtime Foundation."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.autonomy_control_plane import (
    AdmissionDecision,
    AutonomyControlPlane,
    DecisionValueClass,
    ExecutionTier,
    ModelAdmissionRequest,
    RiskLevel,
    TaskContinuationState,
)
from scripts.evidence_provenance import check_for_secrets

REPO_ROOT = Path(__file__).resolve().parent.parent


class TestAutonomyControlPlaneMission184G(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="autonomy_184g_test_"))
        self.plane = AutonomyControlPlane(repo_dir=self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    # --------------------------------------------------------------------------
    # Phase A: Canonical State Reconstruction
    # --------------------------------------------------------------------------

    def test_01_canonical_state_reconstruction_closed_strands(self):
        snap = self.plane.reconstruct_canonical_state()
        self.assertEqual(snap["autonomy_state"], "ACTIVE_DETERMINISTIC_FIRST")
        self.assertEqual(snap["money_firewall_spend_limit_eur"], 0.0)
        self.assertIn("RESOURCE_INTEGRITY_178C", snap["closed_strands"])
        self.assertIn("CREATOR_PUBLICATION_INTEGRITY_180C_182G_183C", snap["closed_strands"])

    # --------------------------------------------------------------------------
    # Phase B: Model Call Admission Gate & Decision Value Classes
    # --------------------------------------------------------------------------

    def test_02_zero_gain_is_strictly_rejected(self):
        req = ModelAdmissionRequest(
            request_id="adm-zg-1",
            task_id="task-zg-1",
            why_model="Routine re-evaluation",
            why_not_local="N/A",
            new_information="None",
            expected_unlock="None",
            decision_value_class=DecisionValueClass.ZERO_GAIN,
        )
        res = self.plane.evaluate_admission(req)
        self.assertFalse(res.admitted)
        self.assertEqual(res.decision, AdmissionDecision.REJECTED_ZERO_GAIN)
        self.assertEqual(res.execution_tier, ExecutionTier.LOCAL_DETERMINISTIC)

    def test_03_critical_unblock_and_high_value_are_admitted(self):
        req = ModelAdmissionRequest(
            request_id="adm-crit-1",
            task_id="task-crit-1",
            why_model="Authoritative architectural conflict synthesis",
            why_not_local="Ambiguous semantic disagreement between 2 workers",
            new_information="Both worker results available with differing proposals",
            expected_unlock="Unblocks main pipeline architecture",
            decision_value_class=DecisionValueClass.CRITICAL_UNBLOCK,
            risk_level=RiskLevel.HIGH,
        )
        res = self.plane.evaluate_admission(req)
        self.assertTrue(res.admitted)
        self.assertEqual(res.decision, AdmissionDecision.ADMITTED)
        self.assertEqual(res.execution_tier, ExecutionTier.TARGETED_MODEL_JUDGMENT)
        self.assertTrue(res.context_lease_id)

    # --------------------------------------------------------------------------
    # Phase C: Deterministic-First Execution Ladder
    # --------------------------------------------------------------------------

    def test_04_deterministic_resolver_prevents_model_call(self):
        req = ModelAdmissionRequest(
            request_id="adm-det-1",
            task_id="task-validate-hashes",
            why_model="Validate hashes",
            why_not_local="Could use model",
            new_information="File updated",
            expected_unlock="Release",
            decision_value_class=DecisionValueClass.USEFUL,
        )
        # Mock local resolver returning success
        mock_resolver = lambda tid: (True, {"hash": "abc", "valid": True})

        res = self.plane.evaluate_admission(req, deterministic_resolver=mock_resolver)
        self.assertFalse(res.admitted)
        self.assertEqual(res.decision, AdmissionDecision.REJECTED_LOCAL_RESOLVABLE)
        self.assertEqual(res.execution_tier, ExecutionTier.LOCAL_DETERMINISTIC)
        self.assertEqual(res.cached_judgment["result"]["valid"], True)

    # --------------------------------------------------------------------------
    # Phase D: Result Barrier / Event Graph Engine
    # --------------------------------------------------------------------------

    def test_05_barrier_waits_for_all_required_results(self):
        b = self.plane.register_barrier(
            barrier_id="bar-101",
            task_id="task-synthesis",
            required_result_ids=["res-a", "res-b"],
            wait_policy="ALL_REQUIRED",
        )
        self.assertEqual(b.state, TaskContinuationState.WAITING_FOR_REQUIRED_RESULT)

        # Ingest res-a -> still waiting
        sat1 = self.plane.ingest_result("res-a", {"data": "output_a"})
        self.assertEqual(sat1, [])
        b_after_a = self.plane.get_barrier("bar-101")
        self.assertFalse(b_after_a.is_satisfied())
        self.assertIn("res-a", b_after_a.arrived_result_ids)

        # Ingest res-b -> satisfied exactly once
        sat2 = self.plane.ingest_result("res-b", {"data": "output_b"})
        self.assertEqual(sat2, ["bar-101"])
        b_after_b = self.plane.get_barrier("bar-101")
        self.assertTrue(b_after_b.is_satisfied())
        self.assertEqual(b_after_b.state, TaskContinuationState.READY_FOR_CHIEF_SYNTHESIS)

    def test_06_barrier_arrival_order_invariance(self):
        self.plane.register_barrier("bar-order", "task-order", ["res-1", "res-2"])
        # Arrive 2 first, then 1
        self.plane.ingest_result("res-2", {"val": 2})
        sat = self.plane.ingest_result("res-1", {"val": 1})
        self.assertEqual(sat, ["bar-order"])
        b = self.plane.get_barrier("bar-order")
        self.assertTrue(b.is_satisfied())
        self.assertEqual(b.stored_results["res-1"]["val"], 1)
        self.assertEqual(b.stored_results["res-2"]["val"], 2)

    def test_07_barrier_duplicate_arrival_protection(self):
        self.plane.register_barrier("bar-dup", "task-dup", ["res-x"])
        sat1 = self.plane.ingest_result("res-x", {"val": "first"})
        self.assertEqual(sat1, ["bar-dup"])

        # Second identical arrival ignored
        sat2 = self.plane.ingest_result("res-x", {"val": "second"})
        self.assertEqual(sat2, [])
        metrics = self.plane._load_metrics()
        self.assertGreaterEqual(metrics.duplicate_calls_avoided, 1)

    def test_08_branch_isolation_unrelated_tasks_not_frozen(self):
        # Barrier 1 waiting on human approval
        self.plane.register_barrier("bar-human", "task-human-flow", ["human-sig-1"])
        # Barrier 2 waiting on worker result
        self.plane.register_barrier("bar-worker", "task-worker-flow", ["worker-res-1"])

        # Worker result arrives -> Barrier 2 satisfied while Barrier 1 remains safely waiting
        sat = self.plane.ingest_result("worker-res-1", {"status": "SUCCESS"})
        self.assertEqual(sat, ["bar-worker"])

        b_human = self.plane.get_barrier("bar-human")
        self.assertFalse(b_human.is_satisfied())

    def test_09_barrier_state_restores_cleanly_on_restart(self):
        self.plane.register_barrier("bar-restart", "task-restart", ["res-a", "res-b"])
        self.plane.ingest_result("res-a", {"data": "persisted"})

        # Re-instantiate control plane simulating process restart
        restarted_plane = AutonomyControlPlane(repo_dir=self.test_dir)
        b = restarted_plane.get_barrier("bar-restart")
        self.assertIsNotNone(b)
        self.assertIn("res-a", b.arrived_result_ids)
        self.assertFalse(b.is_satisfied())

        # Complete second dependency on restarted plane
        sat = restarted_plane.ingest_result("res-b", {"data": "persisted_b"})
        self.assertEqual(sat, ["bar-restart"])

    # --------------------------------------------------------------------------
    # Phase E: Context Lease & Accepted Judgment Cache
    # --------------------------------------------------------------------------

    def test_10_context_lease_reuse_and_bytes_saved_tracking(self):
        summary = "Large shared analysis context for 2026 Zentrale"
        lid1 = self.plane.obtain_context_lease(scope="zentrale_core", payload_summary=summary)
        lid2 = self.plane.obtain_context_lease(scope="zentrale_core", payload_summary=summary)
        self.assertEqual(lid1, lid2)

        metrics = self.plane._load_metrics()
        self.assertGreater(metrics.context_bytes_avoided, 0)

    def test_11_accepted_judgment_cache_hit_prevents_re_review(self):
        fp = self.plane.compute_review_fingerprint(
            artifact_hash="1111" * 16,
            diff_hash="2222" * 16,
            affected_modules=["scripts/creator_package_enricher.py"],
            risk_class="LOW",
            test_hash="3333" * 16,
        )
        self.plane.record_accepted_judgment(fp, {"verdict": "PASS", "reviewer": "CODEX_180C"})

        req = ModelAdmissionRequest(
            request_id="adm-cached-review",
            task_id="task-review-enricher",
            why_model="Review changes",
            why_not_local="N/A",
            new_information="None",
            expected_unlock="Merge",
            prior_judgment_reusable=True,
            context_reference=fp,
        )
        res = self.plane.evaluate_admission(req)
        self.assertFalse(res.admitted)
        self.assertEqual(res.decision, AdmissionDecision.REJECTED_CACHE_HIT)
        self.assertEqual(res.execution_tier, ExecutionTier.CACHED_ACCEPTED_JUDGMENT)
        self.assertEqual(res.cached_judgment["verdict"], "PASS")

    # --------------------------------------------------------------------------
    # Phase F: Review Debt & Decision Coalescing
    # --------------------------------------------------------------------------

    def test_12_review_debt_accumulation_and_flush(self):
        req = ModelAdmissionRequest(
            request_id="adm-debt-1",
            task_id="task-low-risk-doc",
            why_model="Review minor doc edit",
            why_not_local="N/A",
            new_information="Minor text tweak",
            expected_unlock="None",
            decision_value_class=DecisionValueClass.OPTIONAL,
            risk_level=RiskLevel.LOW,
        )
        res = self.plane.evaluate_admission(req)
        self.assertFalse(res.admitted)
        self.assertEqual(res.decision, AdmissionDecision.DEFERRED_REVIEW_DEBT)
        self.assertEqual(self.plane.get_review_debt_count(), 1)

        flushed = self.plane.flush_review_debt()
        self.assertEqual(len(flushed), 1)
        self.assertEqual(self.plane.get_review_debt_count(), 0)

    # --------------------------------------------------------------------------
    # Phase G: Shadow-Call Firewall
    # --------------------------------------------------------------------------

    def test_13_shadow_call_firewall_blocks_worker_fan_out(self):
        req = ModelAdmissionRequest(
            request_id="adm-worker-spawn",
            task_id="task-worker-spawn",
            why_model="Worker spawned sub-agent",
            why_not_local="N/A",
            new_information="None",
            expected_unlock="None",
            is_shadow_call=True,
            caller_id="SUB_WORKER_THREAD",
        )
        res = self.plane.evaluate_admission(req)
        self.assertFalse(res.admitted)
        self.assertEqual(res.decision, AdmissionDecision.REJECTED_SHADOW_CALL)

    # --------------------------------------------------------------------------
    # Phase H: Anti-Loop Circuit Breaker
    # --------------------------------------------------------------------------

    def test_14_circuit_breaker_trips_on_consecutive_no_progress(self):
        tid = "looping-task-99"
        self.plane.record_loop_iteration(tid, new_information_delta=0, artifact_progress_delta=0)
        self.plane.record_loop_iteration(tid, new_information_delta=0, artifact_progress_delta=0)
        self.assertFalse(self.plane.get_circuit_breaker_status(tid).get("tripped"))

        # Third zero-progress call trips breaker
        st = self.plane.record_loop_iteration(tid, new_information_delta=0, artifact_progress_delta=0)
        self.assertTrue(st.get("tripped"))

        # Admission subsequently rejected
        req = ModelAdmissionRequest(
            request_id="adm-loop-call",
            task_id=tid,
            why_model="Try again without delta",
            why_not_local="N/A",
            new_information="None",
            expected_unlock="None",
            decision_value_class=DecisionValueClass.HIGH_VALUE,
        )
        res = self.plane.evaluate_admission(req)
        self.assertFalse(res.admitted)
        self.assertEqual(res.decision, AdmissionDecision.REJECTED_LOOP_DETECTED)

        # Remediation reset
        self.plane.reset_circuit_breaker(tid)
        self.assertFalse(self.plane.get_circuit_breaker_status(tid).get("tripped"))

    # --------------------------------------------------------------------------
    # Phase I: Concurrency & Scope Locking
    # --------------------------------------------------------------------------

    def test_15_scope_locking_prevents_conflicting_mutations(self):
        self.plane._acquire_scope_locks("task_owner_a", ["runtime/content/golden_trophy_short"])

        req = ModelAdmissionRequest(
            request_id="adm-conflict-1",
            task_id="task_owner_b",
            why_model="Mutate golden trophy short",
            why_not_local="N/A",
            new_information="New frames",
            expected_unlock="Render",
            target_scope=["runtime/content/golden_trophy_short/render.mp4"],
        )
        res = self.plane.evaluate_admission(req)
        self.assertFalse(res.admitted)
        self.assertEqual(res.decision, AdmissionDecision.REJECTED_SCOPE_LOCKED)

        self.plane.release_scope_locks("task_owner_a")
        res_after = self.plane.evaluate_admission(req)
        self.assertTrue(res_after.admitted)
        self.plane.release_scope_locks("task_owner_b")

    # --------------------------------------------------------------------------
    # Phase J: Hard Night Firewalls
    # --------------------------------------------------------------------------

    def test_16_hard_night_firewalls_exact_zero_and_publication_denial(self):
        self.assertEqual(self.plane.AUTONOMOUS_SPEND_LIMIT_EUR, 0.0)
        self.assertEqual(self.plane.PUBLICATION_AUTHORIZATION_INFERENCE, "DENY")
        self.assertEqual(self.plane.MODEL_HEAVY_PER_PROVIDER, 1)
        self.assertEqual(self.plane.MUTATION_SCOPE_OWNER, 1)

    # --------------------------------------------------------------------------
    # Phase L & M: Autonomous Continuation Loop & Sleep Simulator
    # --------------------------------------------------------------------------

    def test_17_continuation_loop_runs_events_and_stops_on_idle(self):
        self.plane.register_barrier("bar-loop-1", "task-loop-1", ["res-in-1"])
        feed = [
            {"event_type": "RESULT_ARRIVED", "result_id": "res-in-1", "payload": {"out": "ok"}},
        ]
        loop_res = self.plane.run_continuation_loop(max_iterations=5, event_feed=feed)
        self.assertEqual(loop_res["final_status"], "IDLE_EXPECTED")
        self.assertGreaterEqual(loop_res["iterations_executed"], 2)

    def test_18_sleep_mode_accelerated_simulation_all_pass(self):
        sim = self.plane.run_sleep_mode_simulation()
        self.assertEqual(sim["simulation_result"], "PASS")
        self.assertEqual(sim["passed_scenarios_count"], sim["total_scenarios_count"])
        self.assertGreaterEqual(sim["total_scenarios_count"], 10)


if __name__ == "__main__":
    unittest.main()
