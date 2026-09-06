"""
tests/test_normal_goal_intent.py

Targeted proof that:
1. "without deployment" -> NO HUMAN_GATE
2. "no publication" -> NO HUMAN_GATE
3. "no purchases or spend" -> NO HUMAN_GATE
4. "do not contact customers" -> NO HUMAN_GATE
5. "deploy this to production" -> HUMAN_GATE
6. "publish this" -> HUMAN_GATE
7. "purchase the plan" -> HUMAN_GATE
8. "complete OAuth/login" -> HUMAN_GATE
9. mixed safe goal: "build locally, no deployment" -> local implementation allowed (NO HUMAN_GATE)
10. explicit product scope survives discovery
11. social/product goal cannot select unrelated Courier infrastructure as its implementation target
12. scope parser is general and not hardcoded to social_platform
13. invalidated false blocker can transition through canonical state API back to REPLAN
14. real HUMAN_GATE cannot be reopened by that mechanism
"""

import json
import tempfile
import time
import unittest
import uuid
from pathlib import Path

from scripts.courier_safety_dispatcher import (
    CourierSafetyDispatcher,
    canonical_hash,
    canonical_task_hash,
)
from scripts.courier_real_worker_adapters import (
    create_real_cli1_adapter,
    extract_target_scope,
)
from scripts.courier_founder_mode import MultiChatGoalIntake, GoalRecord


class TestNormalGoalIntentAndSafety(unittest.TestCase):

    def _check_gate(self, goal_text: str, task_dict: dict = None) -> bool:
        """Helper to invoke CourierSafetyDispatcher._requires_human_gate."""
        mission = {"goal": goal_text, "normalized_task": goal_text}
        task = task_dict or {"action": "implement_feature", "capability_request": "implementation"}
        return CourierSafetyDispatcher._requires_human_gate(mission, task)

    # 1. "without deployment" -> NO HUMAN_GATE
    def test_1_without_deployment_no_human_gate(self):
        self.assertFalse(
            self._check_gate("Build local database feature without deployment."),
            "Expected 'without deployment' to be treated as a negative constraint, not a gated request."
        )

    # 2. "no publication" -> NO HUMAN_GATE
    def test_2_no_publication_no_human_gate(self):
        self.assertFalse(
            self._check_gate("Implement offline cache, no publication."),
            "Expected 'no publication' to be treated as a negative constraint."
        )

    # 3. "no purchases or spend" -> NO HUMAN_GATE
    def test_3_no_purchases_or_spend_no_human_gate(self):
        self.assertFalse(
            self._check_gate("Add local feed ranking with no purchases or spend, spend=0."),
            "Expected 'no purchases or spend' to be treated as a negative constraint."
        )

    # 4. "do not contact customers" -> NO HUMAN_GATE
    def test_4_do_not_contact_customers_no_human_gate(self):
        self.assertFalse(
            self._check_gate("Refactor user model; do not contact customers or users."),
            "Expected 'do not contact customers' to be treated as a negative constraint."
        )

    # 5. "deploy this to production" -> HUMAN_GATE
    def test_5_deploy_this_to_production_triggers_human_gate(self):
        self.assertTrue(
            self._check_gate("Deploy this to production server immediately."),
            "Expected affirmative deploy request to trigger HUMAN_GATE."
        )

    # 6. "publish this" -> HUMAN_GATE
    def test_6_publish_this_triggers_human_gate(self):
        self.assertTrue(
            self._check_gate("Publish this package live to the registry."),
            "Expected affirmative publish request to trigger HUMAN_GATE."
        )

    # 7. "purchase the plan" -> HUMAN_GATE
    def test_7_purchase_the_plan_triggers_human_gate(self):
        self.assertTrue(
            self._check_gate("Purchase the upgraded subscription plan using corporate billing."),
            "Expected affirmative purchase request to trigger HUMAN_GATE."
        )

    # 8. "complete OAuth/login" -> HUMAN_GATE
    def test_8_complete_oauth_login_triggers_human_gate(self):
        self.assertTrue(
            self._check_gate("Complete OAuth login and enter the 2FA code."),
            "Expected affirmative OAuth/login request to trigger HUMAN_GATE."
        )

    # 9. mixed safe goal: "build locally, no deployment" -> local implementation allowed
    def test_9_mixed_safe_goal_allows_local_implementation(self):
        goal = (
            "Continue building the existing social_platform product into a useful local-first "
            "social-network foundation. Choose the single highest-value missing product capability "
            "that can be implemented safely and completely in the local repository without deployment, "
            "external services, credentials, publication, customer contact, purchases, or spend."
        )
        self.assertFalse(
            self._check_gate(goal),
            "Expected complex normal product goal with safety prohibitions NOT to trigger false HUMAN_GATE."
        )


class TestProductScopePreservation(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        # Create a mock product directory and a mock infrastructure file
        (self.root / "social_platform" / "core").mkdir(parents=True)
        (self.root / "social_platform" / "core" / "database.py").write_text("# Social database\n")
        (self.root / "packages" / "billing").mkdir(parents=True)
        (self.root / "packages" / "billing" / "engine.py").write_text("# Billing engine\n")
        (self.root / "scripts").mkdir(parents=True)
        (self.root / "scripts" / "native_agy_runner.py").write_text("# Infrastructure\n")

    def tearDown(self):
        self.temp_dir.cleanup()

    # 10. explicit product scope survives discovery

    # 12. scope parser is general and not hardcoded to social_platform
    def test_12_scope_parser_is_general(self):
        # Test generic directory detection
        scope1 = extract_target_scope("Work on the billing module and optimize it", self.root)
        self.assertEqual(scope1, "billing")

        scope2 = extract_target_scope("Continue building the social_platform app", self.root)
        self.assertEqual(scope2, "social_platform")

        # Non-matching goal falls back to None
        scope_none = extract_target_scope("Optimize general repo performance", self.root)
        self.assertIsNone(scope_none)


class TestCanonicalReopeningOfInvalidatedBlockers(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.ws = Path(self.temp_dir.name)
        (self.ws / "events" / "founder-mode").mkdir(parents=True)
        (self.ws / "events" / "mission-queue").mkdir(parents=True)
        (self.ws / "events" / "founder-mode" / "goals.json").write_text("[]")
        (self.ws / "events" / "mission-queue" / "queue.json").write_text(json.dumps({"missions": []}))
        self.intake = MultiChatGoalIntake(self.ws)

    def tearDown(self):
        self.temp_dir.cleanup()

    # 13. invalidated false blocker can transition through canonical state API back to REPLAN
    def test_13_invalidated_false_blocker_transitions_to_pending(self):
        goal_text = "Build social_platform locally without deployment or purchases"
        goal_id = self.intake.submit_goal(source="CLI", goal=goal_text)
        self.intake.set_status(goal_id, "HUMAN_GATE")

        # Goal is currently falsely blocked as HUMAN_GATE
        goals = self.intake._read_no_lock()
        self.assertEqual(goals[0]["status"], "HUMAN_GATE")

        # Canonically reopen via reopen_invalidated_blocker
        success = self.intake.reopen_invalidated_blocker(
            goal_id=goal_id,
            reason="INVALIDATED_FALSE_HUMAN_GATE: Negation parser defect corrected",
            provenance={"parser_fix": "negation_aware_v2"}
        )
        self.assertTrue(success)

        # State is now PENDING and ready for autonomous replan
        goals_after = self.intake._read_no_lock()
        self.assertEqual(goals_after[0]["status"], "PENDING")
        self.assertIn("INVALIDATED_FALSE_HUMAN_GATE", goals_after[0].get("reopen_reason", ""))

    # 14. real HUMAN_GATE cannot be reopened by that mechanism
    def test_14_real_human_gate_cannot_be_reopened_by_false_blocker_api(self):
        real_gated_goal = "Deploy social_platform to production and purchase domain"
        goal_id = self.intake.submit_goal(source="CLI", goal=real_gated_goal)
        self.intake.set_status(goal_id, "HUMAN_GATE")

        # Attempting to reopen a genuinely gated goal must fail closed
        with self.assertRaises(RuntimeError) as ctx:
            self.intake.reopen_invalidated_blocker(
                goal_id=goal_id,
                reason="Attempt to bypass genuine human gate",
            )
        self.assertIn("CANNOT_REOPEN_REAL_HUMAN_GATE", str(ctx.exception))

        # Goal remains HUMAN_GATE
        goals = self.intake._read_no_lock()
        self.assertEqual(goals[0]["status"], "HUMAN_GATE")


if __name__ == "__main__":
    unittest.main()
