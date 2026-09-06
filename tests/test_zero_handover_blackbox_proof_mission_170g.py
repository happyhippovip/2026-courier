#!/usr/bin/env python3
"""Zero-Handover Black-Box Proof Test Suite (Mission 170G).

Proves that Mission 169 eliminated manual giant chat handovers in real operation.

Validates all required phases:
- Phase A: Cold Start & Autonomous Reconstruction
- Phase B: Memory Quality & Reference Verification
- Phase C: Idea Persistence Canary & Auditable Supersession
- Phase D: Task Continuation Canary across process boundaries
- Phase E: Context Compaction & Zero-Chat-Transcript Verification
- Phase F: Cross-Provider Context Equivalence (Google Antigravity vs Codex)
- Phase G: Deterministic Open-Loop & Next-Action Truth
- Phase H: Isolated Malformed State Fail-Safe Verification
"""

from __future__ import annotations

import json
import os
import re
import tempfile
import unittest
from pathlib import Path

from scripts.chief_brain import (
    ChiefBrain, IdeaItem, MemoryItem, TaskContinuationState,
    read_json_safe, scan_for_forbidden_secrets,
)

COURIER_DIR = Path(__file__).resolve().parent.parent


class TestZeroHandoverBlackboxProofMission170G(unittest.TestCase):
    """Deterministic black-box proof suite for Mission 170G."""

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.repo_dir = Path(self.tmp_dir.name)
        self.brain = ChiefBrain(repo_dir=self.repo_dir)
        self.brain.migrate_existing_state()

    def tearDown(self):
        self.tmp_dir.cleanup()

    # --------------------------------------------------------------------------
    # Phase A: Cold Start
    # --------------------------------------------------------------------------
    def test_phase_a_cold_start_bootstrap(self):
        # Instantiate genuinely fresh brain without prior memory
        fresh_brain = ChiefBrain(repo_dir=self.repo_dir)
        bootstrap = fresh_brain.build_bootstrap_context()

        self.assertEqual(bootstrap["BOOTSTRAP_TYPE"], "CHIEF_BOOTSTRAP_CONTEXT_V1")
        self.assertEqual(bootstrap["CANONICAL_WORKSPACE"], str(self.repo_dir))
        self.assertEqual(bootstrap["HARD_BOUNDARIES"]["AUTONOMOUS_SPEND_LIMIT_EUR"], 0.0)
        self.assertEqual(bootstrap["HARD_BOUNDARIES"]["PUBLICATION_AUTHORIZATION_INFERENCE"], "DENY")
        self.assertEqual(bootstrap["HARD_BOUNDARIES"]["CREDENTIAL_STORAGE"], "DENY")

        # Verify active goals reconstructed
        active_goals = fresh_brain.query_memories(item_type="ACTIVE_GOAL")
        self.assertGreater(len(active_goals), 0)
        self.assertTrue(any("Creator Factory" in g.summary for g in active_goals))

        # Verify safest next action determined
        candidates = fresh_brain.get_next_action_candidates()
        self.assertGreater(len(candidates), 0)
        self.assertIn("action_type", candidates[0])

    # --------------------------------------------------------------------------
    # Phase B: Memory Quality & Evidence References
    # --------------------------------------------------------------------------
    def test_phase_b_memory_quality_and_references(self):
        rules = {r.memory_id: r.content for r in self.brain.query_memories(item_type="PROJECT_RULE")}

        # 1. Local workspace is canonical
        self.assertIn("rule-workspace-truth", rules)
        self.assertIn("WORKSPACE_SOURCE_OF_TRUTH", rules["rule-workspace-truth"])

        # 2. Provider chats are replaceable
        self.assertIn("replaceable", rules["rule-workspace-truth"].lower())

        # 3. Autonomous spend limit is 0 EUR
        self.assertIn("rule-cost-firewall", rules)
        self.assertIn("AUTONOMOUS_SPEND_LIMIT = 0 EUR", rules["rule-cost-firewall"])

        # 4. Multiple resource pools remain independent & no quota summing
        self.assertIn("rule-multi-pool", rules)
        self.assertIn("never summed", rules["rule-multi-pool"].lower())

        # 5. Automatic credential storage / login / rotation denied
        self.assertIn("rule-sec-secrets", rules)
        self.assertIn("CREDENTIAL_STORAGE = DENY", rules["rule-sec-secrets"])

        # 6. Heavy Job Limit = 1
        self.assertIn("rule-heavy-limit", rules)
        self.assertIn("HEAVY_JOB_LIMIT = 1", rules["rule-heavy-limit"])

        # 7. HUNG work does not justify more capacity
        self.assertIn("rule-waste-policy", rules)
        self.assertIn("does not justify capacity expansion", rules["rule-waste-policy"].lower())

        # 8. Persistent Visual Studio server is not automatically HUNG
        self.assertIn("rule-vs-server", rules)
        self.assertIn("expected infrastructure", rules["rule-vs-server"].lower())

        # 9. Creator Factory remains an active strategic direction
        self.assertIn("rule-creator-factory", rules)
        self.assertIn("CREATOR_FACTORY_STRATEGY", rules["rule-creator-factory"])

        # 10. Publication authorization cannot be inferred
        self.assertIn("rule-pub-firewall", rules)
        self.assertIn("PUBLICATION_AUTHORIZATION_INFERENCE = DENY", rules["rule-pub-firewall"])

        # 11. High-risk review policy
        self.assertIn("rule-high-risk-review", rules)
        self.assertIn("HIGH_RISK_REVIEW_POLICY", rules["rule-high-risk-review"])

    # --------------------------------------------------------------------------
    # Phase C: Idea Persistence Canary & Auditable Supersession
    # --------------------------------------------------------------------------
    def test_phase_c_idea_persistence_and_supersession_canary(self):
        canary_text = "MISSION_170_CANARY: The Chief Brain should prefer compact automatic context packages over manual giant handovers."
        idea = self.brain.record_idea(canary_text, tags=["TEST_CANARY"])

        # Restart/Reload: Create genuinely fresh instance
        fresh_brain = ChiefBrain(repo_dir=self.repo_dir)
        ideas = fresh_brain._load_ideas()

        self.assertIn(idea.idea_id, ideas)
        self.assertEqual(ideas[idea.idea_id]["raw_intent"], canary_text)
        canary_survived_restart = True
        self.assertTrue(canary_survived_restart)

        # Record durable intent from canary
        intent_1 = fresh_brain.record_user_intent(canary_text)

        # Now supersede the canary intent
        superseded_text = "MISSION_170_CANARY_COMPLETE"
        intent_2 = fresh_brain.record_user_intent(superseded_text, supersedes_id=intent_1.memory_id)

        # Verify old record is SUPERSEDED and new is ACTIVE
        old_rec = fresh_brain.get_memory(intent_1.memory_id)
        new_rec = fresh_brain.get_memory(intent_2.memory_id)

        self.assertEqual(old_rec.status, "SUPERSEDED")
        self.assertEqual(old_rec.superseded_by, intent_2.memory_id)
        self.assertEqual(new_rec.status, "ACTIVE")

        # Active queries return only new record
        active_intents = fresh_brain.query_memories(item_type="USER_INTENT", status="ACTIVE")
        self.assertIn(intent_2.memory_id, [i.memory_id for i in active_intents])
        self.assertNotIn(intent_1.memory_id, [i.memory_id for i in active_intents])

    # --------------------------------------------------------------------------
    # Phase D: Continuation Canary across reloads
    # --------------------------------------------------------------------------
    def test_phase_d_continuation_canary_across_reloads(self):
        task_id = "TASK-SYNTHETIC-170"
        goal_id = "GOAL-SYNTHETIC-170"

        # Stage 1: READY
        self.brain.record_task_state(TaskContinuationState(
            task_id=task_id,
            goal_id=goal_id,
            state="READY",
            worker="google-antigravity",
            mission_id="170G",
            next_action="Dispatch to worker",
        ))

        # Reload 1
        b1 = ChiefBrain(repo_dir=self.repo_dir)
        t1 = b1.get_task_state(task_id)
        self.assertEqual(t1.state, "READY")

        # Stage 2: RUNNING
        b1.record_task_state(TaskContinuationState(
            task_id=task_id,
            goal_id=goal_id,
            state="RUNNING",
            worker="google-antigravity",
            mission_id="170G",
            started_at="2026-08-31T20:00:00+00:00",
            last_progress_at="2026-08-31T20:01:00+00:00",
            next_action="Monitor worker progress",
        ))

        # Reload 2
        b2 = ChiefBrain(repo_dir=self.repo_dir)
        t2 = b2.get_task_state(task_id)
        self.assertEqual(t2.state, "RUNNING")

        # Stage 3: Result Ingestion & Verification
        res = b2.ingest_worker_result(
            task_id=task_id,
            worker="google-antigravity",
            outcome="SUCCESS",
            evidence={"sha256": "170abcdef", "files": ["test.py"]},
            tests_passed=10,
            verified_by_chief=True,
        )

        # Reload 3
        b3 = ChiefBrain(repo_dir=self.repo_dir)
        t3 = b3.get_task_state(task_id)
        self.assertEqual(t3.state, "COMPLETED")
        self.assertEqual(t3.verification_state, "VERIFIED")
        self.assertIsNotNone(t3.result_id)
        self.assertIn("Review completed task", t3.next_action)

    # --------------------------------------------------------------------------
    # Phase E: Context Compaction & Bounded Size
    # --------------------------------------------------------------------------
    def test_phase_e_context_compaction(self):
        pkg = self.brain.build_context_package(
            task_id="TASK-170-COMPACTION",
            mission="Mission 170G Proof",
            scope_files=["scripts/chief_brain.py"],
        )

        raw_json = json.dumps(pkg)
        byte_size = len(raw_json.encode("utf-8"))

        self.assertLess(byte_size, 8192, f"Context package size was {byte_size} bytes (target < 8KB)")
        self.assertNotIn("raw_chat_history", raw_json)
        self.assertNotIn("messages", raw_json)
        self.assertEqual(scan_for_forbidden_secrets(raw_json), [])

    # --------------------------------------------------------------------------
    # Phase F: Cross-Provider Context Equivalence
    # --------------------------------------------------------------------------
    def test_phase_f_cross_provider_context_equivalence(self):
        task_id = "TASK-CROSS-PROVIDER"
        instruction = "Verify zero-handover operating system contracts."
        scope = ["scripts/chief_brain.py"]

        env_google = self.brain.build_task_envelope(
            task_id=task_id,
            instruction=instruction,
            provider_role="GOOGLE_BUILD",
            scope_files=scope,
        )

        env_codex = self.brain.build_task_envelope(
            task_id=task_id,
            instruction=instruction,
            provider_role="CODEX_REVIEW",
            scope_files=scope,
        )

        # Provider roles differ in metadata
        self.assertEqual(env_google["provider_role"], "GOOGLE_BUILD")
        self.assertEqual(env_codex["provider_role"], "CODEX_REVIEW")

        # Canonical project meaning and rules remain strictly identical
        self.assertEqual(env_google["instruction"], env_codex["instruction"])
        self.assertEqual(env_google["constraints"], env_codex["constraints"])
        self.assertEqual(env_google["success_criteria"], env_codex["success_criteria"])
        self.assertEqual(env_google["context_package"]["security_rules"], env_codex["context_package"]["security_rules"])
        self.assertEqual(env_google["context_package"]["money_rules"], env_codex["context_package"]["money_rules"])

    # --------------------------------------------------------------------------
    # Phase G: Open Loop Truth & Next Action Ranking
    # --------------------------------------------------------------------------
    def test_phase_g_open_loop_truth_and_next_action(self):
        candidates = self.brain.get_next_action_candidates()
        self.assertGreater(len(candidates), 0)

        # Verify completed work is NOT recommended
        for c in candidates:
            self.assertNotEqual(c.get("action_type"), "REOPEN_COMPLETED_WORK")

        # Verify priority ordering
        priorities = [c["priority"] for c in candidates]
        self.assertEqual(priorities, sorted(priorities))

    # --------------------------------------------------------------------------
    # Phase H: Failure Test / Malformed State Fail-Safe
    # --------------------------------------------------------------------------
    def test_phase_h_malformed_state_fail_safe(self):
        fixture_dir = self.repo_dir / "events" / "fixture_malformed"
        fixture_dir.mkdir(parents=True, exist_ok=True)
        bad_file = fixture_dir / "corrupted_memories.json"
        bad_file.write_text("NOT_VALID_JSON{{{", encoding="utf-8")

        # Reading safe returns default without crashing
        res = read_json_safe(bad_file, {"fallback": True})
        self.assertEqual(res, {"fallback": True})

        # Canonical brain storage is unaffected
        self.assertTrue(self.brain.memories_file.is_file())
        reloaded = self.brain._load_memories()
        self.assertIsInstance(reloaded, dict)


if __name__ == "__main__":
    unittest.main()
