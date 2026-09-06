from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.courier_founder_mode import ExperienceMemory, MultiChatGoalIntake
from scripts.courier_self_repair import CourierSelfRepair


class TestCourierSelfRepair(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.ws = Path(self.tmp.name)
        self.intake = MultiChatGoalIntake(self.ws)
        self.goal_id = self.intake.submit_goal("test", "Create a safe local result")
        self.brain = CourierSelfRepair(self.ws, max_repair_attempts=1)
        self.descriptor = {
            "local_internal": True, "verifiable": True, "requires_write": True,
            "target_files": ["repair_target.txt"],
            "acceptance_criteria": {"file_exists": "repair_target.txt"},
            "summary": "Repair a bounded local contract", "spend_eur": 0,
        }

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_internal_defect_creates_one_gemini_repair_mission(self) -> None:
        result = self.brain.handle_failure(
            goal_id=self.goal_id, original_goal="Create a safe local result",
            failure="EMPTY_WRITE_CRITERIA_FAIL_CLOSED", descriptor=self.descriptor,
        )
        self.assertEqual(result["status"], "REPAIR_QUEUED")
        from scripts.courier_safety_dispatcher import MissionQueue
        mission = MissionQueue(self.ws).get(result["mission_id"])
        self.assertEqual(mission["preferred_agent"], "GEMINI")
        self.assertTrue(mission["requires_write"])

    def test_gates_and_ambiguous_failures_never_create_repair(self) -> None:
        for kwargs in ({"human_gate": True}, {"safety_gate": True}, {"external_required": True}):
            fresh = CourierSelfRepair(self.ws)
            result = fresh.handle_failure(goal_id=f"g-{len(kwargs)}-{list(kwargs)[0]}", original_goal="x",
                                          failure="opaque", descriptor=self.descriptor, **kwargs)
            self.assertNotEqual(result["status"], "REPAIR_QUEUED")
        self.assertEqual(CourierSelfRepair.classify_failure(""), "AMBIGUOUS_HIGH_RISK")
        self.assertEqual(CourierSelfRepair.classify_failure("goal_id=oauth-looking"), "AMBIGUOUS_HIGH_RISK")

    def test_failure_classes_are_explicit_and_non_repairable_classes_wait_or_stop(self) -> None:
        cases = {
            "INTERNAL_DEFECT": "REPAIRABLE_INTERNAL_DEFECT",
            "WORKER_FAILURE": "WORKER_FAILURE",
            "EXECUTABLE_NOT_FOUND": "CAPACITY_UNAVAILABLE",
            "VERIFY_EFFECT_FRESHNESS": "VERIFICATION_FAILURE",
            "TEMPORARY_TIMEOUT": "TRANSIENT_LOCAL_FAILURE",
            "OAuth authentication required": "HUMAN_GATE",
            "unclassified permanent error": "TERMINAL_FAILURE",
        }
        for text, expected in cases.items():
            self.assertEqual(CourierSelfRepair.classify_failure(text), expected)
        waited = self.brain.handle_failure(goal_id="worker-failure", original_goal="x",
                                           failure="WORKER_FAILURE", descriptor=self.descriptor)
        self.assertEqual(waited["status"], "WAIT")

    def test_budget_and_writer_conflict_fail_closed(self) -> None:
        first = self.brain.handle_failure(goal_id=self.goal_id, original_goal="x",
                                          failure="EMPTY_WRITE_CRITERIA_FAIL_CLOSED", descriptor=self.descriptor)
        self.assertEqual(first["status"], "REPAIR_QUEUED")
        second = self.brain.handle_failure(goal_id=self.goal_id, original_goal="x",
                                           failure="EMPTY_WRITE_CRITERIA_FAIL_CLOSED", descriptor=self.descriptor)
        self.assertEqual(second["status"], "REPAIR_BUDGET_EXHAUSTED")
        unsafe = dict(self.descriptor, writer_conflict=True)
        result = CourierSelfRepair(self.ws).handle_failure(goal_id="conflict", original_goal="x",
                                                           failure="EMPTY_WRITE_CRITERIA_FAIL_CLOSED", descriptor=unsafe)
        self.assertEqual(result["status"], "WAIT")

    def test_repair_resume_then_only_original_acceptance_satisfies(self) -> None:
        queued = self.brain.handle_failure(goal_id=self.goal_id, original_goal="x",
                                           failure="EMPTY_WRITE_CRITERIA_FAIL_CLOSED", descriptor=self.descriptor)
        memory = ExperienceMemory(self.ws)
        resumed = self.brain.complete_repair(self.goal_id, queued["mission_id"], verified=True,
                                             intake=self.intake, lesson_recorder=memory.record_lesson)
        self.assertEqual(resumed["status"], "REPLAN_ORIGINAL_GOAL")
        self.assertEqual(self.intake._read_no_lock()[0]["status"], "PENDING")
        self.assertEqual(self.brain.mark_original_goal_satisfied(self.goal_id, original_acceptance_verified=False)["status"],
                         "ORIGINAL_ACCEPTANCE_NOT_VERIFIED")
        self.assertEqual(self.brain.mark_original_goal_satisfied(self.goal_id, original_acceptance_verified=True,
                                                                  intake=self.intake)["status"], "SATISFIED")
        self.assertTrue(memory._read())

    def test_restart_preserves_repair_state(self) -> None:
        queued = self.brain.handle_failure(goal_id=self.goal_id, original_goal="x",
                                           failure="EMPTY_WRITE_CRITERIA_FAIL_CLOSED", descriptor=self.descriptor)
        restored = CourierSelfRepair(self.ws)
        self.assertEqual(restored.state_for(self.goal_id)["repair_mission_id"], queued["mission_id"])
        self.assertEqual(restored.state_for(self.goal_id)["next_safe_action"], "REPAIR")

    def test_verification_economics_cache_and_independence(self) -> None:
        facts = {"input_fingerprint": "i", "workspace_fingerprint": "w", "acceptance_context": "a",
                 "method": "local", "result_fingerprint": "r", "low_risk_deterministic": True}
        self.assertEqual(self.brain.verification_policy(facts), "ONE_CHEAP_VERIFY")
        self.brain.record_proof(facts, "CLI1", "source-a")
        self.assertEqual(self.brain.verification_policy(facts), "NO_NEW_VERIFY")
        changed = dict(facts, workspace_fingerprint="changed")
        self.assertEqual(self.brain.verification_policy(changed), "ONE_CHEAP_VERIFY")
        two = dict(changed, low_risk_deterministic=False, two_cheap_cost=2, specialist_cost=5,
                   independent_verifiers=["CLI1", "VERIFIER_2"], proof_sources=["a", "b"])
        self.assertEqual(self.brain.verification_policy(two), "TWO_CHEAP_INDEPENDENT_VERIFIERS")
        duplicate = dict(two, independent_verifiers=["CLI1", "CLI1"], proof_sources=["a", "a"])
        self.assertNotEqual(self.brain.verification_policy(duplicate), "TWO_CHEAP_INDEPENDENT_VERIFIERS")

    def test_specialist_only_for_information_gain_not_elapsed_time(self) -> None:
        base = {"input_fingerprint": "i", "workspace_fingerprint": "w", "acceptance_context": "a",
                "method": "local", "result_fingerprint": "r", "elapsed_seconds": 999999}
        self.assertEqual(self.brain.verification_policy(base), "TARGETED_PRIMARY_VERIFY")
        self.assertEqual(self.brain.verification_policy(dict(base, ambiguity=True)), "EXPENSIVE_SPECIALIST_REVIEW")


if __name__ == "__main__":
    unittest.main()
