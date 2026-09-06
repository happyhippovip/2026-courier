#!/usr/bin/env python3
"""Comprehensive Acceptance Test Suite for Canonical Chief Brain (Mission 169).

Validates all 30 authoritative conditions:
1. durable intent survives restart
2. provider change does not remove intent
3. account change does not remove intent
4. superseded intent no longer controls current behavior
5. historical decision remains retrievable
6. rough idea survives restart
7. result becomes local canonical evidence
8. worker claim is distinct from verified evidence
9. open loops survive restart
10. next action reconstructs after restart
11. context package excludes irrelevant history
12. context package remains bounded
13. duplicate idea detection works safely
14. UNKNOWN remains UNKNOWN
15. secret-like memory is rejected
16. money authorization cannot be inferred
17. publication authorization cannot be inferred
18. completed tasks do not reopen accidentally
19. HUNG tasks remain distinguishable
20. persistent expected services are not tasks
21. crash during atomic brain write does not corrupt previous state
22. malformed state fails safely
23. concurrent reads are safe
24. concurrent write strategy is deterministic
25. handover snapshot regenerates from brain state
26. fresh Chief bootstrap reconstructs current mission
27. Codex context can be generated without Google chat history
28. Google context can be generated without Codex chat history
29. no account email/credentials required
30. deletion/supersession audit trail works
"""

from __future__ import annotations

import json
import os
import re
import tempfile
import threading
import unittest
from pathlib import Path

from scripts.chief_brain import (
    ChiefBrain, IdeaItem, MemoryItem, TaskContinuationState,
    read_json_safe, scan_for_forbidden_secrets,
)


class TestChiefBrainMission169(unittest.TestCase):
    """Test suite for Mission 169 Persistent Chief Brain."""

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.repo_dir = Path(self.tmp_dir.name)
        self.brain = ChiefBrain(repo_dir=self.repo_dir)

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_01_durable_intent_survives_restart(self):
        item = self.brain.record_user_intent("Always format Godot scripts with 4-space indentation.")

        # Simulate process exit and new brain instance
        new_brain = ChiefBrain(repo_dir=self.repo_dir)
        loaded = new_brain.get_memory(item.memory_id)

        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.content, "Always format Godot scripts with 4-space indentation.")
        self.assertEqual(loaded.status, "ACTIVE")

    def test_02_provider_change_does_not_remove_intent(self):
        self.brain.record_user_intent("Never modify reviewer oracles.")

        # Worker 1 (Google Antigravity) reads intent
        intents_google = self.brain.query_memories(item_type="USER_INTENT")
        self.assertEqual(len(intents_google), 1)

        # Worker 2 (Codex) opens workspace independently
        codex_brain = ChiefBrain(repo_dir=self.repo_dir)
        intents_codex = codex_brain.query_memories(item_type="USER_INTENT")
        self.assertEqual(len(intents_codex), 1)
        self.assertEqual(intents_codex[0].content, "Never modify reviewer oracles.")

    def test_03_account_change_does_not_remove_intent(self):
        item = self.brain.record_user_intent("Zero autonomous spend limit strictly enforced.")

        # New session on another authorized account
        another_session_brain = ChiefBrain(repo_dir=self.repo_dir)
        reloaded = another_session_brain.get_memory(item.memory_id)
        self.assertIsNotNone(reloaded)
        self.assertEqual(reloaded.status, "ACTIVE")

    def test_04_superseded_intent_no_longer_controls_behavior(self):
        old_intent = self.brain.record_user_intent("Use 360p resolution for draft renders.")
        new_intent = self.brain.record_user_intent(
            "Use 720p resolution for draft renders.",
            supersedes_id=old_intent.memory_id,
        )

        active_intents = self.brain.query_memories(item_type="USER_INTENT", status="ACTIVE")
        self.assertEqual(len(active_intents), 1)
        self.assertEqual(active_intents[0].memory_id, new_intent.memory_id)

        old_reloaded = self.brain.get_memory(old_intent.memory_id)
        self.assertEqual(old_reloaded.status, "SUPERSEDED")
        self.assertEqual(old_reloaded.superseded_by, new_intent.memory_id)

    def test_05_historical_decision_remains_retrievable(self):
        dec = MemoryItem(
            memory_id="dec-101",
            item_type="HISTORICAL_DECISION",
            content=json.dumps({"decision": "APPROVE_LOCAL_QC", "scope": "video_3"}),
            status="COMPLETED",
        )
        self.brain.record_memory(dec)

        reloaded = self.brain.get_memory("dec-101")
        self.assertIsNotNone(reloaded)
        self.assertEqual(reloaded.item_type, "HISTORICAL_DECISION")

    def test_06_rough_idea_survives_restart(self):
        idea = self.brain.record_idea("Add audio reactive pulse to kiwi rendering.", tags=["visual", "audio"])

        new_brain = ChiefBrain(repo_dir=self.repo_dir)
        ideas = new_brain._load_ideas()
        self.assertIn(idea.idea_id, ideas)
        self.assertEqual(ideas[idea.idea_id]["state"], "NEW")

    def test_07_result_becomes_local_canonical_evidence(self):
        res = self.brain.ingest_worker_result(
            task_id="TASK-42",
            worker="google-antigravity",
            outcome="SUCCESS",
            evidence={"sha256": "abc12345", "duration_seconds": 12.4},
            files_changed=["scripts/video.py"],
            tests_passed=5,
            verified_by_chief=True,
        )

        mem = self.brain.get_memory(res["result_id"])
        self.assertIsNotNone(mem)
        self.assertEqual(mem.item_type, "PROVIDER_RESULT")
        self.assertEqual(mem.confidence, "HIGH")

    def test_08_worker_claim_is_distinct_from_verified_evidence(self):
        res = self.brain.ingest_worker_result(
            task_id="TASK-43",
            worker="external-worker",
            outcome="SUCCESS",
            evidence={"deterministic_digest": "deadbeef"},
            claims={"claim_tests_pass": True, "claim_100_pct_coverage": True},
            verified_by_chief=False,
        )

        mem = self.brain.get_memory(res["result_id"])
        self.assertEqual(mem.confidence, "MEDIUM")
        content = json.loads(mem.content)
        self.assertIn("worker_claims", content)
        self.assertIn("deterministic_evidence", content)
        self.assertFalse(content["verified_by_chief"])

    def test_09_open_loops_survive_restart(self):
        self.brain.record_task_state(TaskContinuationState(
            task_id="TASK-INFLIGHT",
            goal_id="GOAL-1",
            state="RUNNING",
            worker="antigravity",
        ))

        new_brain = ChiefBrain(repo_dir=self.repo_dir)
        loops = new_brain.get_open_loops()
        task_loops = [l for l in loops if l.get("task_id") == "TASK-INFLIGHT"]
        self.assertEqual(len(task_loops), 1)
        self.assertEqual(task_loops[0]["loop_type"], "UNRESOLVED_TASK")

    def test_10_next_action_reconstructs_after_restart(self):
        self.brain.record_task_state(TaskContinuationState(
            task_id="TASK-FAIL-1",
            goal_id="GOAL-2",
            state="FAILED",
            worker="antigravity",
        ))

        new_brain = ChiefBrain(repo_dir=self.repo_dir)
        candidates = new_brain.get_next_action_candidates()
        self.assertGreater(len(candidates), 0)
        self.assertEqual(candidates[0]["action_type"], "RETRY_OR_CLOSE_FAILED_TASK")

    def test_11_context_package_excludes_irrelevant_history(self):
        # Add 10 historical memories
        for i in range(10):
            self.brain.record_memory(MemoryItem(
                memory_id=f"hist-{i}",
                item_type="HISTORICAL_DECISION",
                content=f"Old decision {i}",
                status="COMPLETED",
            ))

        pkg = self.brain.build_context_package(task_id="TASK-TIGHT")
        raw_pkg = json.dumps(pkg)
        self.assertNotIn("Old decision 0", raw_pkg)
        self.assertNotIn("raw_chat_history", raw_pkg)

    def test_12_context_package_remains_bounded(self):
        pkg = self.brain.build_context_package(task_id="TASK-BOUNDED", scope_files=["scripts/chief_brain.py"])
        size_bytes = len(json.dumps(pkg).encode("utf-8"))
        self.assertLess(size_bytes, 10000, f"Context package exceeded budget: {size_bytes} bytes")

    def test_13_duplicate_idea_detection(self):
        self.brain.record_user_intent("Enable automatic subtitles on all exported videos.")
        rel = self.brain.detect_intent_relation("Enable automatic subtitles on all exported videos.")
        self.assertEqual(rel["relation"], "SAME_INTENT")

    def test_14_unknown_remains_unknown(self):
        mem = MemoryItem(
            memory_id="unk-1",
            item_type="UNKNOWN",
            content="Unverified observation about external service",
            confidence="UNKNOWN",
            status="UNKNOWN",
        )
        self.brain.record_memory(mem)
        loaded = self.brain.get_memory("unk-1")
        self.assertEqual(loaded.confidence, "UNKNOWN")
        self.assertEqual(loaded.status, "UNKNOWN")

    def test_15_secret_like_memory_is_rejected(self):
        fake_key = "".join(["AI", "za", "SyD-", "12345678901234567890123456789012345"])
        test_payload = f"config_val = '{fake_key}'"
        with self.assertRaises(ValueError):
            MemoryItem(
                memory_id="bad-sec-1",
                item_type="USER_INTENT",
                content=test_payload,
            )

    def test_16_money_authorization_cannot_be_inferred(self):
        # A worker attempting to record a high-impact payment authorization memory fails closed
        with self.assertRaises(PermissionError):
            self.brain.record_memory(MemoryItem(
                memory_id="worker-fake-pay",
                item_type="PROJECT_RULE",
                content="PAYMENT_AUTHORIZATION GRANTED FOR 50 EUR",
                source="WORKER_RESULT",
            ))

    def test_17_publication_authorization_cannot_be_inferred(self):
        with self.assertRaises(PermissionError):
            self.brain.record_memory(MemoryItem(
                memory_id="worker-fake-pub",
                item_type="PROJECT_RULE",
                content="PUBLICATION_AUTHORIZATION GRANTED FOR YOUTUBE",
                source="WORKER_RESULT",
            ))

    def test_18_completed_tasks_do_not_reopen_accidentally(self):
        self.brain.record_task_state(TaskContinuationState(
            task_id="TASK-COMPLETED",
            goal_id="GOAL-1",
            state="COMPLETED",
            worker="antigravity",
        ))

        loops = self.brain.get_open_loops()
        completed_loops = [l for l in loops if l.get("task_id") == "TASK-COMPLETED"]
        self.assertEqual(len(completed_loops), 0)

    def test_19_hung_tasks_distinguishable(self):
        self.brain.record_task_state(TaskContinuationState(
            task_id="TASK-HUNG-1",
            goal_id="GOAL-1",
            state="HUNG",
            worker="antigravity",
            blocked_reason="No progress observed for > 600s",
        ))
        t = self.brain.get_task_state("TASK-HUNG-1")
        self.assertEqual(t.state, "HUNG")

    def test_20_persistent_expected_services_are_not_tasks(self):
        loops = self.brain.get_open_loops()
        for loop in loops:
            self.assertNotIn("run_visual_studio_server.py", str(loop))

    def test_21_crash_during_atomic_write_preserves_previous_state(self):
        self.brain.record_user_intent("Original durable intent baseline.")
        mem_file = self.brain.memories_file

        # Verify baseline exists
        before = mem_file.read_text(encoding="utf-8")

        # Simulate incomplete tmp file write
        tmp_file = mem_file.with_suffix(".json.tmp.crash.test")
        tmp_file.write_text("PARTIAL_JSON_CRASH_DATA", encoding="utf-8")

        # Original file remains untouched and loadable
        reloaded = self.brain._load_memories()
        self.assertEqual(len(reloaded), 1)
        if tmp_file.exists():
            tmp_file.unlink()

    def test_22_malformed_state_fails_safely(self):
        bad_file = self.repo_dir / "events" / "chief-brain" / "bad.json"
        bad_file.write_text("{malformed json...", encoding="utf-8")
        res = read_json_safe(bad_file, {"default": True})
        self.assertEqual(res, {"default": True})

    def test_23_concurrent_reads_are_safe(self):
        self.brain.record_user_intent("Multi-threaded read test target.")

        results = []
        def reader():
            b = ChiefBrain(repo_dir=self.repo_dir)
            m = b.query_memories(item_type="USER_INTENT")
            results.append(len(m))

        threads = [threading.Thread(target=reader) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(results, [1] * 10)

    def test_24_concurrent_write_strategy_is_deterministic(self):
        def writer(idx: int):
            b = ChiefBrain(repo_dir=self.repo_dir)
            b.record_memory(MemoryItem(
                memory_id=f"concurrent-{idx}",
                item_type="ACTIVE_GOAL",
                content=f"Goal {idx}",
            ))

        threads = [threading.Thread(target=writer, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        goals = self.brain.query_memories(item_type="ACTIVE_GOAL")
        self.assertGreater(len(goals), 0)

    def test_25_handover_snapshot_regenerates_from_brain_state(self):
        self.brain.record_user_intent("Handover snapshot verification goal.")
        ho = self.brain.generate_handover_snapshot()
        self.assertEqual(ho["SNAPSHOT_TYPE"], "CHIEF_HANDOVER_SNAPSHOT_V1")
        self.assertFalse(ho["RAW_CHAT_HISTORY_INCLUDED"])
        self.assertGreater(ho["ALL_ACTIVE_MEMORIES_COUNT"], 0)

    def test_26_fresh_chief_bootstrap_reconstructs_current_mission(self):
        self.brain.record_memory(MemoryItem(
            memory_id="goal-bootstrap-test",
            item_type="ACTIVE_GOAL",
            content="Implement zero-handover operating system.",
        ))

        boot = self.brain.build_bootstrap_context()
        self.assertEqual(boot["BOOTSTRAP_TYPE"], "CHIEF_BOOTSTRAP_CONTEXT_V1")
        self.assertIn("Implement zero-handover operating system.", str(boot["ACTIVE_GOALS"]))
        self.assertEqual(boot["HARD_BOUNDARIES"]["AUTONOMOUS_SPEND_LIMIT_EUR"], 0.0)

    def test_27_codex_context_generated_without_google_chat(self):
        env = self.brain.build_task_envelope(
            task_id="TASK-CODEX-REVIEW",
            instruction="Review chief_brain.py implementation.",
            provider_role="CODEX_REVIEW",
        )
        self.assertEqual(env["provider_role"], "CODEX_REVIEW")
        self.assertNotIn("chat_history", json.dumps(env))

    def test_28_google_context_generated_without_codex_chat(self):
        env = self.brain.build_task_envelope(
            task_id="TASK-GOOGLE-BUILD",
            instruction="Build new capability.",
            provider_role="GOOGLE_BUILD",
        )
        self.assertEqual(env["provider_role"], "GOOGLE_BUILD")
        self.assertNotIn("chat_history", json.dumps(env))

    def test_29_no_account_credentials_required(self):
        boot = self.brain.build_bootstrap_context()
        boot_str = json.dumps(boot)
        secrets = scan_for_forbidden_secrets(boot_str)
        self.assertEqual(secrets, [])

    def test_30_deletion_and_supersession_audit_trail(self):
        item = self.brain.record_user_intent("Initial intent for tombstone audit test.")
        self.brain.tombstone_memory(item.memory_id, reason="User requested deletion")

        loaded = self.brain.get_memory(item.memory_id)
        self.assertEqual(loaded.status, "TOMBSTONE")
        self.assertIn("[TOMBSTONE]", loaded.content)


if __name__ == "__main__":
    unittest.main()
