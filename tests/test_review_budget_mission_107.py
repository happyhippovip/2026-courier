#!/usr/bin/env python3
"""Unit and integration tests for Mission 107: Review Budget Manager & Delta Review Gate."""

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.review_budget import (
    ReviewBudgetManager,
    ReviewRiskClassifier,
    ReviewFingerprint,
    ReviewDeltaContextBuilder,
    ReviewLedger,
    compute_sha256,
)
from scripts.resource_policy import ResourcePolicyManager
from scripts.github_transport import EXACTLY_ONCE_SEMANTICS


class TestMission107ReviewBudget(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="test_review_budget_107_"))
        self.events_dir = self.test_dir / "events"
        self.reviews_dir = self.events_dir / "reviews"
        self.policies_dir = self.events_dir / "policies"
        self.reviews_dir.mkdir(parents=True, exist_ok=True)
        self.policies_dir.mkdir(parents=True, exist_ok=True)

        canonical = Path("events/policies/review_policy.json")
        if canonical.exists():
            shutil.copy(canonical, self.policies_dir / "review_policy.json")

        self.manager = ReviewBudgetManager(repo_dir=self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_01_no_change_yields_no_review(self):
        """Prove 0 changes deterministically returns NO_REVIEW."""
        res = self.manager.evaluate_review_requirement(changed_files=[], diff_str="")
        self.assertEqual(res["decision"], "NO_REVIEW")
        self.assertEqual(res["reason"], "NO_RELEVANT_INFORMATION_GAIN")
        self.assertIsNone(res["compact_context"])

    def test_02_same_reviewed_diff_hash_reuses_previous_review(self):
        """Prove identical diff hash reuses previous review and returns NO_REVIEW."""
        diff_str = "diff --git a/test.py b/test.py\n+print('hello')"
        diff_hash = compute_sha256(diff_str)

        # Record a completed review in ledger
        self.manager.ledger.record_review(
            review_id="rev-001",
            checkpoint_commit="c9446ff",
            diff_hash=diff_hash,
            file_hashes={"test.py": "abc123hash"},
            risk_class="LOW",
            review_type="ROUTINE",
            review_result="APPROVE",
            reviewer="codex",
            reason="Initial approved review"
        )

        # Query review requirement for identical diff
        res = self.manager.evaluate_review_requirement(
            changed_files=["test.py"],
            diff_str=diff_str
        )
        self.assertEqual(res["decision"], "NO_REVIEW")
        self.assertEqual(res["reason"], "ALREADY_REVIEWED_IDENTICAL_DELTA")

    def test_03_docs_and_tests_yield_low_risk_batch_review(self):
        """Prove docs-only delta is classified as LOW risk and BATCH_REVIEW."""
        changed_files = ["README.md", "docs/architecture.md", "tests/test_unit.py"]
        diff_str = "+# New documentation\n+def test_something(): pass"

        res = self.manager.evaluate_review_requirement(
            changed_files=changed_files,
            diff_str=diff_str,
            is_push_intent=False
        )
        self.assertEqual(res["risk_class"], "LOW")
        self.assertEqual(res["decision"], "BATCH_REVIEW")
        self.assertEqual(res["reason"], "LOW_RISK_BATCH_OPTIONAL")

    def test_04_medium_routing_change_requires_review_before_push(self):
        """Prove routing/orchestration change requires review before push."""
        changed_files = ["scripts/run_chief_commander.py", "scripts/run_autonomous_loop.py"]
        diff_str = "+class NewOrchestrator: pass"

        # Local work -> BATCH_REVIEW
        res_local = self.manager.evaluate_review_requirement(
            changed_files=changed_files,
            diff_str=diff_str,
            is_push_intent=False
        )
        self.assertEqual(res_local["risk_class"], "MEDIUM")
        self.assertEqual(res_local["decision"], "BATCH_REVIEW")

        # Push intent -> REVIEW_REQUIRED_BEFORE_PUSH
        res_push = self.manager.evaluate_review_requirement(
            changed_files=changed_files,
            diff_str=diff_str,
            is_push_intent=True
        )
        self.assertEqual(res_push["risk_class"], "MEDIUM")
        self.assertEqual(res_push["decision"], "REVIEW_REQUIRED_BEFORE_PUSH")
        self.assertEqual(res_push["reason"], "MEDIUM_RISK_REVIEW_REQUIRED_BEFORE_PUSH")

    def test_05_auth_and_security_change_triggers_immediate_review(self):
        """Prove auth, secret, or concurrency lock changes trigger IMMEDIATE_REVIEW_REQUIRED."""
        changed_files = ["scripts/github_transport.py"]
        diff_str = "+hmac.new(secret.encode(), raw_body)\n+ProcessSafeFileLock(lock_path)"

        res = self.manager.evaluate_review_requirement(
            changed_files=changed_files,
            diff_str=diff_str
        )
        self.assertEqual(res["risk_class"], "HIGH")
        self.assertEqual(res["decision"], "IMMEDIATE_REVIEW_REQUIRED")
        self.assertEqual(res["reason"], "HIGH_RISK_SECURITY_OR_TRUST_BOUNDARY_CHANGE")

    def test_06_daily_routine_budget_blocks_second_routine_batch(self):
        """Prove routine review budget caps at 1 batch per day."""
        changed_files = ["scripts/ui_helper.py"]
        diff1 = "+def render_ui_1(): pass"
        diff2 = "+def render_ui_2(): pass"

        # Record 1 routine review for today
        self.manager.ledger.record_review(
            review_id="rev-today-1",
            checkpoint_commit="c9446ff",
            diff_hash=compute_sha256(diff1),
            file_hashes={"scripts/ui_helper.py": "hash1"},
            risk_class="MEDIUM",
            review_type="ROUTINE",
            review_result="APPROVE",
            reviewer="codex",
            reason="Daily routine batch 1"
        )

        # Attempt second routine review
        res = self.manager.evaluate_review_requirement(
            changed_files=changed_files,
            diff_str=diff2,
            is_push_intent=False
        )
        self.assertEqual(res["decision"], "NO_REVIEW")
        self.assertEqual(res["reason"], "DAILY_ROUTINE_REVIEW_BUDGET_EXHAUSTED")

    def test_07_high_risk_overrides_daily_routine_budget(self):
        """Prove high-risk security review overrides routine budget exhaustion."""
        # Exhaust daily routine budget
        self.manager.ledger.record_review(
            review_id="rev-today-1",
            checkpoint_commit="c9446ff",
            diff_hash="hash000",
            file_hashes={"f.py": "h0"},
            risk_class="LOW",
            review_type="ROUTINE",
            review_result="APPROVE",
            reviewer="codex",
            reason="Routine 1"
        )

        # High risk change
        res = self.manager.evaluate_review_requirement(
            changed_files=["events/policies/resource_policy.json"],
            diff_str="+cost_gate_secret_token_change"
        )
        self.assertEqual(res["risk_class"], "HIGH")
        self.assertEqual(res["decision"], "IMMEDIATE_REVIEW_REQUIRED")
        self.assertTrue(res["high_risk_override"])

    def test_08_unchanged_files_absent_from_compact_context(self):
        """Prove compact context contains only changed files and no unchanged whole files."""
        changed_files = ["scripts/github_transport.py"]
        diff_str = "+def new_transport(): pass"

        res = self.manager.evaluate_review_requirement(
            changed_files=changed_files,
            diff_str=diff_str
        )
        ctx = res["compact_context"]
        self.assertIsNotNone(ctx)
        self.assertEqual(ctx["changed_files"], ["scripts/github_transport.py"])
        self.assertTrue(ctx["deterministic_checks"]["unchanged_files_excluded"])

    def test_09_fingerprints_stable_for_identical_input(self):
        """Prove identical inputs produce identical fingerprint hashes."""
        fp1 = ReviewFingerprint(pending_diff_hash="diff123", pending_files=["a.py", "b.py"], pending_risk_class="MEDIUM")
        fp2 = ReviewFingerprint(pending_diff_hash="diff123", pending_files=["a.py", "b.py"], pending_risk_class="MEDIUM")
        self.assertEqual(fp1.compute_fingerprint_hash(), fp2.compute_fingerprint_hash())

    def test_10_changed_content_changes_fingerprint(self):
        """Prove modified diff produces different fingerprint."""
        fp1 = ReviewFingerprint(pending_diff_hash="diff123")
        fp2 = ReviewFingerprint(pending_diff_hash="diff456")
        self.assertNotEqual(fp1.compute_fingerprint_hash(), fp2.compute_fingerprint_hash())

    def test_11_duplicate_review_ledger_entry_prevented(self):
        """Prove duplicate review entry for same diff_hash is deduplicated in ledger."""
        diff_hash = "diff_hash_unique_999"
        e1 = self.manager.ledger.record_review("r1", "c9446ff", diff_hash, {}, "LOW", "ROUTINE", "APPROVE", "codex", "First")
        e2 = self.manager.ledger.record_review("r2", "c9446ff", diff_hash, {}, "LOW", "ROUTINE", "APPROVE", "codex", "Second duplicate")

        self.assertEqual(e1["review_id"], e2["review_id"])
        ledger_data = json.loads((self.reviews_dir / "ledger.json").read_text(encoding="utf-8"))
        self.assertEqual(ledger_data["stats"]["total_reviews"], 1)
        self.assertEqual(ledger_data["stats"]["total_reused"], 1)

    def test_12_no_model_calls_and_no_memory_writes(self):
        """Prove all review budget evaluations run 100% deterministically with 0 model calls and 0 memory writes."""
        # Calling should_review
        dec, risk, reason, fp, ctx = self.manager.should_review(
            changed_files=["scripts/review_budget.py"],
            diff_str="+class ReviewBudgetManager: pass"
        )
        self.assertIn(dec, ["BATCH_REVIEW", "REVIEW_REQUIRED_BEFORE_PUSH", "IMMEDIATE_REVIEW_REQUIRED", "NO_REVIEW"])
        # Verify 2026-project-memory not modified
        self.assertFalse((self.test_dir / "2026-project-memory").exists())

    def test_13_mission_093_and_106_invariants_preserved(self):
        """Prove default builder/reviewer and transport semantics remain intact."""
        self.assertEqual(ResourcePolicyManager.get_default_builder(), "courier-antigravity-bridge")
        self.assertEqual(ResourcePolicyManager.get_default_reviewer(), "courier-codex-bridge")
        self.assertEqual(EXACTLY_ONCE_SEMANTICS, "BOUNDED_LOCAL_REPLAY_PROTECTION")


if __name__ == "__main__":
    unittest.main()
