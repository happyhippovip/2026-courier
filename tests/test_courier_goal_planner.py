from unittest.mock import patch
from scripts.worker_availability import WorkerState, AvailabilityEvidence
class MockResolver:
    def resolve_gemini(self):
        return AvailabilityEvidence(worker='GEMINI', state=WorkerState.AVAILABLE, executable='/agy', resolution_method='MOCK', detail='mock')

"""Unit tests for CourierGoalPlanner and CourierExperienceMemory verifying unscripted autonomous planning.

Guarantees:
- UNIT_TEST_MODEL_CALLS = 0
- UNIT_TEST_NETWORK_REQUESTS = 0
"""
import tempfile
import unittest
import uuid
from pathlib import Path
from typing import Any, Dict

from scripts.courier_goal_planner import CourierGoalPlanner, PlannerDecision
from scripts.courier_experience_memory import CourierExperienceMemory
from scripts.courier_safety_dispatcher import (
    CourierSafetyDispatcher,
    LocalWorkerAdapterBoundary,
    canonical_hash,
)


@patch('scripts.worker_availability.WorkerAvailabilityResolver', new=MockResolver)
class TestCourierGoalPlanner(unittest.TestCase):
    def setUp(self) -> None:
        self.planner = CourierGoalPlanner(max_missions=4, max_write_missions=1)
        self.root_goal = (
            "Improve Courier's operational readiness by autonomously finding one small, safe, "
            "locally verifiable weakness in its own dispatcher/worker infrastructure, improving it if "
            "justified, verifying the result, and stopping when the goal is satisfied."
        )

    def test_abstract_goal_generates_initial_discovery_mission(self) -> None:
        """Verify abstract goal without prior history generates open discovery mission."""
        decision = self.planner.plan_next_step(self.root_goal, verified_history=[])
        self.assertEqual(decision.decision, "CONTINUE")
        self.assertIsNotNone(decision.next_mission)
        self.assertEqual(decision.next_mission["task"]["action"], "discover_improvement_opportunities")
        self.assertFalse(decision.next_mission["requires_write"])
        self.assertEqual(decision.next_mission["preferred_agent"], "CLI1")

    def test_missing_or_empty_root_goal_fails_closed(self) -> None:
        """Verify missing or empty root goal returns BLOCKED with no mission."""
        decision = self.planner.plan_next_step("", verified_history=[])
        self.assertEqual(decision.decision, "BLOCKED")
        self.assertIsNone(decision.next_mission)

    def test_different_discovery_evidence_produces_different_tasks(self) -> None:
        """Verify task derivation strictly uses discovered evidence, producing different tasks for different evidence."""
        hist = [{"mission_id": "m1", "status": "VERIFIED", "requires_write": False}]

        res_a = {
            "status": "COMPLETED",
            "payload": {
                "action": "discover_improvement_opportunities",
                "weakness_id": "WEAKNESS_ALPHA",
                "description": "Alpha weakness in foo",
                "suggested_files": ["scripts/alpha.py"],
                "verification_strategy": "run_alpha_tests",
                "verdict": "PASS",
            },
        }
        dec_a = self.planner.plan_next_step(self.root_goal, hist, latest_result=res_a)
        self.assertEqual(dec_a.decision, "CONTINUE")
        self.assertEqual(dec_a.next_mission["task"]["weakness_id"], "WEAKNESS_ALPHA")
        self.assertEqual(dec_a.next_mission["task"]["target_files"], ["scripts/alpha.py"])

        res_b = {
            "status": "COMPLETED",
            "payload": {
                "action": "discover_improvement_opportunities",
                "weakness_id": "WEAKNESS_BETA",
                "description": "Beta weakness in bar",
                "suggested_files": ["scripts/beta.py", "tests/test_beta.py"],
                "verification_strategy": "run_beta_tests",
                "verdict": "PASS",
            },
        }
        dec_b = self.planner.plan_next_step(self.root_goal, hist, latest_result=res_b)
        self.assertEqual(dec_b.decision, "CONTINUE")
        self.assertEqual(dec_b.next_mission["task"]["weakness_id"], "WEAKNESS_BETA")
        self.assertEqual(dec_b.next_mission["task"]["target_files"], ["scripts/beta.py", "tests/test_beta.py"])

    def test_missing_discovery_evidence_fails_closed_blocked(self) -> None:
        """Verify missing weakness_id or suggested_files returns BLOCKED without guessing."""
        hist = [{"mission_id": "m1", "status": "VERIFIED", "requires_write": False}]
        incomplete_res = {
            "status": "COMPLETED",
            "payload": {
                "action": "discover_improvement_opportunities",
                "verdict": "PASS",
            },
        }
        decision = self.planner.plan_next_step(self.root_goal, hist, latest_result=incomplete_res)
        self.assertEqual(decision.decision, "BLOCKED")
        self.assertIsNone(decision.next_mission)
        self.assertIn("DISCOVERY_EVIDENCE_INSUFFICIENT", decision.reason)

    def test_missing_implementation_evidence_fails_closed_blocked(self) -> None:
        """Verify missing files_modified from implementation result returns BLOCKED."""
        hist = [
            {"mission_id": "m1", "status": "VERIFIED", "requires_write": False},
            {"mission_id": "m2", "status": "VERIFIED", "requires_write": True},
        ]
        incomplete_imp = {
            "status": "COMPLETED",
            "payload": {
                "action": "implement_bounded_improvement",
                "verdict": "PASS",
            },
        }
        decision = self.planner.plan_next_step(self.root_goal, hist, latest_result=incomplete_imp)
        self.assertEqual(decision.decision, "BLOCKED")
        self.assertIsNone(decision.next_mission)
        self.assertIn("IMPLEMENTATION_EVIDENCE_INSUFFICIENT", decision.reason)

    def test_human_gate_verdict_produces_zero_successors(self) -> None:
        """Verify HUMAN_APPROVAL_REQUIRED or HUMAN_GATE results in decision HUMAN_GATE and zero successors."""
        history = [{"mission_id": "m1", "status": "VERIFIED", "requires_write": False}]
        latest_res = {
            "status": "HUMAN_GATE",
            "payload": {
                "verdict": "HUMAN_APPROVAL_REQUIRED",
                "summary": "OAuth login required",
            },
        }
        decision = self.planner.plan_next_step(self.root_goal, history, latest_result=latest_res)
        self.assertEqual(decision.decision, "HUMAN_GATE")
        self.assertIsNone(decision.next_mission)

    def test_failed_task_produces_zero_successors(self) -> None:
        """Verify FAILED task results in decision BLOCKED and zero successors."""
        history = [{"mission_id": "m1", "status": "VERIFIED", "requires_write": False}]
        latest_res = {
            "status": "FAILED",
            "payload": {
                "verdict": "FAILED",
                "error": "Execution crashed",
            },
        }
        decision = self.planner.plan_next_step(self.root_goal, history, latest_result=latest_res)
        self.assertEqual(decision.decision, "BLOCKED")
        self.assertIsNone(decision.next_mission)

    def test_goal_satisfied_produces_zero_successors(self) -> None:
        """Verify passed verification produces GOAL_SATISFIED and exactly 0 successors."""
        history = [
            {"mission_id": "m1", "status": "VERIFIED", "requires_write": False},
            {"mission_id": "m2", "status": "VERIFIED", "requires_write": True},
            {"mission_id": "m3", "status": "VERIFIED", "requires_write": False},
        ]
        latest_res = {
            "status": "COMPLETED",
            "payload": {
                "action": "verify_improvement_tests",
                "verdict": "PASS",
                "summary": "All tests passed successfully",
            },
        }
        decision = self.planner.plan_next_step(self.root_goal, history, latest_result=latest_res)
        self.assertEqual(decision.decision, "GOAL_SATISFIED")
        self.assertIsNone(decision.next_mission)

    def test_max_write_missions_limit_enforced(self) -> None:
        """Verify planner stops if max_write_missions is exceeded."""
        history = [
            {"mission_id": "m1", "status": "VERIFIED", "requires_write": True},
        ]
        latest_res = {
            "status": "COMPLETED",
            "payload": {
                "action": "discover_improvement_opportunities",
                "weakness_id": "WEAKNESS_2",
                "description": "Desc 2",
                "suggested_files": ["scripts/foo.py"],
                "verdict": "PASS",
            },
        }
        decision = self.planner.plan_next_step(self.root_goal, history, latest_result=latest_res)
        self.assertEqual(decision.decision, "GOAL_SATISFIED")
        self.assertIsNone(decision.next_mission)

    def test_experience_memory_lifecycle(self) -> None:
        """Verify CourierExperienceMemory persists and retrieves sanitized memories."""
        temp_dir = tempfile.TemporaryDirectory()
        workspace = Path(temp_dir.name)
        mem = CourierExperienceMemory(workspace)

        rec = mem.record_learning(
            goal=self.root_goal,
            task={"action": "verify_improvement_tests"},
            result={"verdict": "PASS", "secret_token": "SANITIZE_ME"},
            root_cause="Path configurability was missing in helper functions",
            lesson="Configurable parameters in helper functions prevent tight coupling",
            reusable_pattern="Optional path parameter with default fallback",
        )

        self.assertNotIn("secret_token", rec["result"])
        self.assertIsNotNone(rec["fingerprint"])

        listed = mem.list_memories()
        self.assertEqual(len(listed), 1)
        self.assertEqual(listed[0]["memory_id"], rec["memory_id"])
        temp_dir.cleanup()

    def test_integration_with_safety_dispatcher_full_lifecycle(self) -> None:
        """Verify autonomous planning integration with CourierSafetyDispatcher end-to-end."""
        temp_dir = tempfile.TemporaryDirectory()
        workspace = Path(temp_dir.name)
        boundary = LocalWorkerAdapterBoundary(workspace)

        def test_consumer(env: Dict[str, Any]) -> Dict[str, Any]:
            task = env.get("payload", {})
            action = task.get("action")
            corr_id = env.get("correlation_id", "")
            t_id = env.get("task_id", "")
            t_hash = env["task_hash"]
            w_id = env["worker_id"]
            target = env["target_agent"]
            m_id = env.get("mission_id", "")

            if action == "discover_improvement_opportunities":
                payload = {
                    "action": action,
                    "weakness_id": "PATH_CONFIG",
                    "description": "Configurable path support",
                    "suggested_files": ["scripts/native_agy_runner.py"],
                    "verification_strategy": "run_unit_tests",
                    "verdict": "PASS",
                    "summary": "Discovery complete",
                    "status": "COMPLETED",
                    "correlation_id": corr_id,
                    "task_id": t_id,
                    "task_hash": t_hash,
                    "target_agent": target,
                }
            elif action == "implement_bounded_improvement":
                payload = {
                    "action": action,
                    "files_modified": ["scripts/native_agy_runner.py"],
                    "verification_strategy": "run_unit_tests",
                    "verdict": "PASS",
                    "summary": "Code improved",
                    "status": "COMPLETED",
                    "correlation_id": corr_id,
                    "task_id": t_id,
                    "task_hash": t_hash,
                    "target_agent": target,
                }
            elif action == "verify_improvement_tests":
                payload = {
                    "action": action,
                    "verdict": "PASS",
                    "summary": "Verification tests passed",
                    "status": "COMPLETED",
                    "correlation_id": corr_id,
                    "task_id": t_id,
                    "task_hash": t_hash,
                    "target_agent": target,
                }
            else:
                payload = {"action": action, "verdict": "PASS", "status": "COMPLETED"}

            return {
                "ack": {"schema_version": "1.0", "type": "ACK", "status": "ACCEPTED", "task_hash": t_hash, "worker_id": w_id, "mission_id": m_id, "target_agent": target, "correlation_id": corr_id, "task_id": t_id},
                "result": {"schema_version": "1.0", "type": "RESULT", "status": "COMPLETED", "task_hash": t_hash, "worker_id": w_id, "mission_id": m_id, "target_agent": target, "correlation_id": corr_id, "task_id": t_id, "payload": payload, "result_fingerprint": canonical_hash(payload)},
            }

        boundary.register_consumer("CLI1", test_consumer)
        boundary.register_consumer("GEMINI", test_consumer)
        dispatcher = CourierSafetyDispatcher(workspace, adapter_boundary=boundary)

        # Seed initial mission from planner
        init_decision = self.planner.plan_next_step(self.root_goal, verified_history=[])
        self.assertEqual(init_decision.decision, "CONTINUE")
        dispatcher.mission_queue.enqueue(init_decision.next_mission)

        # Adapter deriver wrapping CourierGoalPlanner
        def deriver_fn(verified_parent: Dict[str, Any]) -> Any:
            all_verified = [m for m in dispatcher.mission_queue.read_all() if m.get("status") == "VERIFIED"]
            latest_res = None
            if verified_parent.get("result_reference"):
                res_path = Path(verified_parent["result_reference"])
                if res_path.exists():
                    import json
                    latest_res = json.loads(res_path.read_text(encoding="utf-8"))
            d = self.planner.plan_next_step(self.root_goal, all_verified, latest_result=latest_res)
            return d.next_mission

        executed = 0
        while True:
            res = dispatcher.process_next_mission("worker-canary", successor_deriver=deriver_fn)
            if res.get("status") == "NO_PENDING_MISSION":
                break
            self.assertEqual(res["status"], "VERIFIED")
            executed += 1

        self.assertEqual(executed, 3)
        missions = dispatcher.mission_queue.read_all()
        self.assertEqual(len(missions), 3)
        self.assertTrue(all(m["status"] == "VERIFIED" for m in missions))
        temp_dir.cleanup()


if __name__ == "__main__":
    unittest.main()
