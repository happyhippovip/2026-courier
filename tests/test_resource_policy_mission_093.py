#!/usr/bin/env python3
"""Unit and integration tests for Mission 093, 095 & 097 Hardened Resource Policy & Dedupe Engine."""

import concurrent.futures
import hashlib
import json
import os
import shutil
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.resource_policy import (
    ResourcePolicyManager,
    CostGate,
    TaskLeaseManager,
    TaskDedupeEngine,
    FileManifestTracker,
    ChiefContextPackageBuilder,
    ReviewDedupeTracker,
    save_json,
)
from scripts.run_chief_commander import SmartResourceRouter
from scripts.run_autonomous_loop import AutonomousLevel6Loop


def _concurrency_worker(repo_dir_str: str, task_id: str, task_hash: str, owner_id: str) -> tuple[bool, str, str]:
    """Worker function executed in separate OS processes for atomic lease testing."""
    mgr = TaskLeaseManager(repo_dir=Path(repo_dir_str))
    success, reason, data = mgr.acquire_lease(task_id, task_hash, owner_id=owner_id, duration_sec=60)
    return success, reason, owner_id


class TestMission093And095And097HardenedPolicy(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="test_mission_097_"))
        self.events_dir = self.test_dir / "events"
        self.locks_dir = self.events_dir / "locks"
        self.processed_dir = self.events_dir / "processed"
        self.policies_dir = self.events_dir / "policies"
        self.locks_dir.mkdir(parents=True, exist_ok=True)
        self.processed_dir.mkdir(parents=True, exist_ok=True)
        self.policies_dir.mkdir(parents=True, exist_ok=True)

        canonical = Path("events/policies/resource_policy.json")
        if canonical.exists():
            shutil.copy(canonical, self.policies_dir / "resource_policy.json")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_01_canonical_policy_defaults(self):
        """Prove Antigravity is default builder and Codex is default reviewer."""
        builder = ResourcePolicyManager.get_default_builder()
        reviewer = ResourcePolicyManager.get_default_reviewer()
        self.assertEqual(builder, "courier-antigravity-bridge")
        self.assertEqual(reviewer, "courier-codex-bridge")

        target, reason, exec_class = SmartResourceRouter.classify_and_route("Build new UI component", [])
        self.assertEqual(target, "antigravity")
        self.assertEqual(exec_class, "DETERMINISTIC_ANTIGRAVITY")

        target_qa, reason_qa, exec_class_qa = SmartResourceRouter.classify_and_route("Run unit test verification and QA audit", [])
        self.assertEqual(target_qa, "codex")
        self.assertEqual(exec_class_qa, "DETERMINISTIC_CODEX")

    def test_02_cost_gate_blocks_unauthorized_resources_and_spend(self):
        """Prove unauthorized or on-demand tiers and spend requests are blocked."""
        eval_ag = CostGate.evaluate_spend_request("google_antigravity_plus", estimated_cost_eur=0.0, repo_dir=self.test_dir)
        self.assertTrue(eval_ag["allowed"])

        eval_planned = CostGate.evaluate_spend_request("future_google_upgrade", estimated_cost_eur=0.0, repo_dir=self.test_dir)
        self.assertFalse(eval_planned["allowed"])
        self.assertEqual(eval_planned["reason"], "RESOURCE_PLANNED_NOT_ACTIVE")

        eval_unauth = CostGate.evaluate_spend_request("on_demand_api_tiers", estimated_cost_eur=0.0, repo_dir=self.test_dir)
        self.assertFalse(eval_unauth["allowed"])
        self.assertEqual(eval_unauth["reason"], "UNAUTHORIZED_RESOURCE_TIER")

        eval_spend = CostGate.evaluate_spend_request("google_antigravity_plus", estimated_cost_eur=25.0, requested_action="PURCHASE_TIER", repo_dir=self.test_dir)
        self.assertFalse(eval_spend["allowed"])
        self.assertEqual(eval_spend["reason"], "SPEND_NOT_ALLOWED_BY_POLICY")

    def test_03_atomic_multiprocess_new_lease(self):
        """Prove genuine process-level atomicity on new claim: exactly 1 success and 1 blocked when 2 processes race."""
        task_id = "TASK-CONCURRENCY-NEW-001"
        task_hash = "hash_new_123"

        with concurrent.futures.ProcessPoolExecutor(max_workers=2) as executor:
            fut1 = executor.submit(_concurrency_worker, str(self.test_dir), task_id, task_hash, "builder-process-alpha")
            fut2 = executor.submit(_concurrency_worker, str(self.test_dir), task_id, task_hash, "builder-process-beta")
            res1 = fut1.result()
            res2 = fut2.result()

        results = [res1, res2]
        successes = [r for r in results if r[0] is True]
        blocked = [r for r in results if r[0] is False]

        self.assertEqual(len(successes), 1, "Exactly one process must acquire the lease")
        self.assertEqual(len(blocked), 1, "Exactly one competing process must be blocked")
        self.assertEqual(successes[0][1], "LEASE_ACQUIRED")
        self.assertEqual(blocked[0][1], "TASK_ALREADY_CLAIMED_BY_ANOTHER_BUILDER")

    def test_03b_atomic_expired_lease_reclaim_single_winner(self):
        """Prove genuine single-winner reclaim on expired lease: exactly 1 success and 1 blocked when 2 processes race."""
        task_id = "TASK-CONCURRENCY-EXPIRED-001"
        task_hash = "hash_expired_456"
        mgr = TaskLeaseManager(repo_dir=self.test_dir)
        lease_path = mgr._get_lease_path(task_id)

        # Seed an expired lease
        now_ts = time.time()
        expired_seed = {
            "task_id": task_id,
            "task_hash": "seed_old_hash",
            "owner_id": "old-expired-owner",
            "acquired_at": now_ts - 1000,
            "expires_at": now_ts - 500, # expired
            "acquired_iso": "2026-01-01T00:00:00Z"
        }
        with open(lease_path, "w", encoding="utf-8") as f:
            json.dump(expired_seed, f)

        # Two competing processes race to reclaim the expired lease
        with concurrent.futures.ProcessPoolExecutor(max_workers=2) as executor:
            fut1 = executor.submit(_concurrency_worker, str(self.test_dir), task_id, task_hash, "reclaimer-alpha")
            fut2 = executor.submit(_concurrency_worker, str(self.test_dir), task_id, task_hash, "reclaimer-beta")
            res1 = fut1.result()
            res2 = fut2.result()

        results = [res1, res2]
        successes = [r for r in results if r[0] is True]
        blocked = [r for r in results if r[0] is False]

        self.assertEqual(len(successes), 1, "Exactly one process must reclaim the expired lease")
        self.assertEqual(len(blocked), 1, "Competing reclaimer must be blocked")
        self.assertEqual(successes[0][1], "LEASE_RECLAIMED_EXPIRED")
        self.assertEqual(blocked[0][1], "TASK_ALREADY_CLAIMED_BY_ANOTHER_BUILDER")

        # Verify final lease file on disk contains exactly the winning owner
        winner_owner = successes[0][2]
        with open(lease_path, "r", encoding="utf-8") as f:
            final_data = json.load(f)
        self.assertEqual(final_data.get("owner_id"), winner_owner, "Final lease file must contain winner as owner")

    def test_03c_corrupt_existing_lease_fails_closed_without_overwrite(self):
        task_id = "TASK-CORRUPT-LEASE-001"
        mgr = TaskLeaseManager(repo_dir=self.test_dir)
        lease_path = mgr._get_lease_path(task_id)
        lease_path.write_text('{"owner_id":', encoding="utf-8")
        original = lease_path.read_bytes()

        acquired, reason, lease = mgr.acquire_lease(
            task_id, "new-hash", owner_id="new-owner", duration_sec=60
        )

        self.assertFalse(acquired)
        self.assertEqual(reason, "TASK_LEASE_CORRUPT_FAIL_CLOSED")
        self.assertEqual(lease, {})
        self.assertTrue(mgr.is_task_claimed(task_id))
        self.assertFalse(mgr.release_lease(task_id, "new-owner"))
        self.assertEqual(lease_path.read_bytes(), original)

    def test_03d_atomic_save_failure_preserves_canonical_file_and_cleans_temp(self):
        target = self.events_dir / "atomic-state.json"
        target.write_text('{"state":"old"}', encoding="utf-8")

        with patch("scripts.resource_policy.os.replace", side_effect=OSError("injected replace failure")):
            with self.assertRaisesRegex(OSError, "injected replace failure"):
                save_json(target, {"state": "new"})

        self.assertEqual(target.read_text(encoding="utf-8"), '{"state":"old"}')
        self.assertEqual(list(target.parent.glob(f"{target.name}.tmp.*")), [])

    def test_03e_initial_lease_publish_failure_never_exposes_partial_canonical_state(self):
        task_id = "TASK-LEASE-PUBLISH-FAILURE"
        mgr = TaskLeaseManager(repo_dir=self.test_dir)
        lease_path = mgr._get_lease_path(task_id)

        with patch("scripts.resource_policy.os.link", side_effect=OSError("injected publish failure")):
            with self.assertRaisesRegex(OSError, "injected publish failure"):
                mgr.acquire_lease(task_id, "hash", "owner", duration_sec=60)

        self.assertFalse(lease_path.exists())
        self.assertEqual(list(lease_path.parent.glob(f"{lease_path.name}.claim.*")), [])

    def test_04_cached_result_integrity_and_fail_closed_checks(self):
        """Prove untampered result is reused, while tampered, missing, or empty hash is blocked."""
        dedupe = TaskDedupeEngine(repo_dir=self.test_dir)
        task_hash = dedupe.compute_task_hash(
            task_type="BUILD",
            instruction="Implement secure component",
            target_agent="courier-antigravity-bridge",
            input_files=[],
            parameters={"env": "prod"},
        )

        res_file = self.processed_dir / "TASK-SEC-result.json"
        valid_payload = {"verdict": "ACCEPTED", "summary": "Cryptographically clean output"}
        with open(res_file, "w", encoding="utf-8") as f:
            json.dump({"task_id": "TASK-SEC", "payload": valid_payload}, f)

        valid_res_hash = hashlib.sha256(json.dumps(valid_payload, sort_keys=True).encode("utf-8")).hexdigest()
        dedupe.register_task_result(task_hash, "TASK-SEC", "TASK-SEC-result.json", valid_res_hash)

        # 1. Clean file with valid hash -> reuse allowed
        cached = dedupe.get_cached_result(task_hash)
        self.assertIsNotNone(cached)
        self.assertTrue(cached.get("reused_from_cache"))
        self.assertEqual(cached.get("result_hash"), valid_res_hash)

        # 2. Tamper with result file on disk -> reuse BLOCKED
        tampered_payload = {"verdict": "ACCEPTED", "summary": "MALICIOUSLY TAMPERED PAYLOAD"}
        with open(res_file, "w", encoding="utf-8") as f:
            json.dump({"task_id": "TASK-SEC", "payload": tampered_payload}, f)

        cached_tampered = dedupe.get_cached_result(task_hash)
        self.assertIsNone(cached_tampered, "Tampered result must be blocked by integrity verification")

        # 3. Restore valid file, but simulate missing result_hash in registry -> reuse BLOCKED (fail-closed)
        with open(res_file, "w", encoding="utf-8") as f:
            json.dump({"task_id": "TASK-SEC", "payload": valid_payload}, f)

        registry_file = self.processed_dir / "task_dedupe_registry.json"
        with open(registry_file, "r", encoding="utf-8") as f:
            reg_data = json.load(f)
        reg_data[task_hash]["result_hash"] = None
        with open(registry_file, "w", encoding="utf-8") as f:
            json.dump(reg_data, f)

        cached_missing_hash = dedupe.get_cached_result(task_hash)
        self.assertIsNone(cached_missing_hash, "Missing result_hash must fail closed")

        # 4. Simulate empty string result_hash -> reuse BLOCKED (fail-closed)
        reg_data[task_hash]["result_hash"] = "   "
        with open(registry_file, "w", encoding="utf-8") as f:
            json.dump(reg_data, f)

        cached_empty_hash = dedupe.get_cached_result(task_hash)
        self.assertIsNone(cached_empty_hash, "Empty result_hash must fail closed")

    def test_05_cost_safe_iteration_limits_and_fallback(self):
        """Prove default iterations is 1, missing policy falls back to 1, and explicit policy can set > 1."""
        self.assertEqual(ResourcePolicyManager.get_default_iterations(repo_dir=self.test_dir), 1)

        loop = AutonomousLevel6Loop(repo_dir=self.test_dir)
        self.assertEqual(loop.max_iterations, 1)

        empty_dir = Path(tempfile.mkdtemp(prefix="test_empty_policy_"))
        try:
            self.assertEqual(ResourcePolicyManager.get_default_iterations(repo_dir=empty_dir), 1)
            loop_empty = AutonomousLevel6Loop(repo_dir=empty_dir)
            self.assertEqual(loop_empty.max_iterations, 1)
        finally:
            shutil.rmtree(empty_dir, ignore_errors=True)

        loop_custom = AutonomousLevel6Loop(repo_dir=self.test_dir, max_iterations=3)
        self.assertEqual(loop_custom.max_iterations, 3)

    def test_06_file_manifest_hash_tracking(self):
        """Prove file unchanged reuses hash, file changed requires reread."""
        test_file = self.test_dir / "sample.py"
        test_file.write_text("print('hello v1')", encoding="utf-8")

        h1 = FileManifestTracker.get_file_hash(test_file)
        self.assertTrue(FileManifestTracker.is_file_unchanged(test_file, h1))

        test_file.write_text("print('hello v2')", encoding="utf-8")
        self.assertFalse(FileManifestTracker.is_file_unchanged(test_file, h1))

        h2 = FileManifestTracker.get_file_hash(test_file)
        self.assertNotEqual(h1, h2)
        self.assertTrue(FileManifestTracker.is_file_unchanged(test_file, h2))

    def test_07_compact_chief_context_package(self):
        """Prove large chat history is omitted and delta context is packaged compactly."""
        pkg = ChiefContextPackageBuilder.build_compact_package(
            workflow_id="WF-001",
            task_id="TASK-001",
            instruction="Execute step 1",
            scope_files=[],
            context_version=73,
            context_delta={"idea_id": "idea-123", "action": "NEW"},
            repo_dir=self.test_dir,
        )

        self.assertFalse(pkg["raw_chat_history_included"])
        self.assertEqual(pkg["context_version"], "v73")
        self.assertEqual(pkg["context_delta"]["idea_id"], "idea-123")
        self.assertIn("file_manifest", pkg)

    def test_08_review_dedupe_tracker(self):
        """Prove unchanged result hash skips redundant review."""
        res_hash = "sha256_result_abc"
        should_rev, reason = ReviewDedupeTracker.should_review(res_hash, res_hash)
        self.assertFalse(should_rev)
        self.assertEqual(reason, "RESULT_HASH_UNCHANGED_SKIP_REDUNDANT_REVIEW")

        should_rev2, reason2 = ReviewDedupeTracker.should_review("sha256_old", res_hash)
        self.assertTrue(should_rev2)
        self.assertEqual(reason2, "NEW_OR_MODIFIED_RESULT_REVIEW_REQUIRED")

    def test_09_academy_audit_evidence_not_ignored(self):
        """Prove Academy lessons, evaluations, deliveries, and adoptions are NOT ignored in .gitignore."""
        gitignore_path = Path(".gitignore")
        if gitignore_path.exists():
            content = gitignore_path.read_text(encoding="utf-8")
            self.assertNotIn("events/academy/lessons/*.json", content)
            self.assertNotIn("events/academy/evaluations/*.json", content)
            self.assertNotIn("events/academy/adoptions/*.json", content)
            self.assertNotIn("events/academy/deliveries/*.json", content)


if __name__ == "__main__":
    unittest.main()
