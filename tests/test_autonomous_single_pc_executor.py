#!/usr/bin/env python3
"""Tests for Single-PC Autonomous Executor (Mission: Computer-A Autonomy).

Verifies:
1. Multi-step zero-prompt task discovery and execution.
2. Output artifacts generated: inventory_summary.json and licensing_tiers.json.
3. Duplicate suppression and restart recovery.
4. Human/Money gate isolation.
5. Zero autonomous spend and zero publication.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.autonomous_single_pc_executor import (
    SinglePCAutonomousExecutor,
    COURIER_DIR,
)


class TestSinglePCAutonomousExecutor(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="test_single_pc_autonomy_"))
        # Copy minimal runtime structure for isolated testing
        (self.tmp_dir / "runtime/content").mkdir(parents=True)
        (self.tmp_dir / "events/autonomy-runtime").mkdir(parents=True)
        (self.tmp_dir / "events/opportunity-queue").mkdir(parents=True)
        (self.tmp_dir / "events/chief-brain").mkdir(parents=True)

        # Copy existing catalog and qc report
        for f in ["runtime/content/catalog_manifest.json", "runtime/content/qc_batch_report.json"]:
            src = COURIER_DIR / f
            if src.is_file():
                shutil.copy(src, self.tmp_dir / f)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_01_executor_initialization_and_handlers(self):
        """Executor initializes with all required deterministic handlers."""
        executor = SinglePCAutonomousExecutor(repo_dir=self.tmp_dir, session_id="test-init-001")
        self.assertIn("work-fruitki-catalog-enrichment", executor._handlers)
        self.assertIn("work-creator-package-qc-batch", executor._handlers)
        self.assertIn("work-fruitki-inventory-summary", executor._handlers)
        self.assertIn("work-fruitki-pricing-manifest", executor._handlers)

    def test_02_sequential_zero_prompt_execution(self):
        """Runs shift and verifies tasks execute without manual intervention."""
        executor = SinglePCAutonomousExecutor(repo_dir=self.tmp_dir, session_id="test-shift-001")
        rep = executor.execute_shift(max_steps=5)

        self.assertEqual(rep["autonomous_spend_eur"], 0.0)
        self.assertEqual(rep["publications"], 0)
        self.assertIn("work-fruitki-inventory-summary", rep["completed_tasks"])
        self.assertIn("work-fruitki-pricing-manifest", rep["completed_tasks"])

    def test_03_inventory_summary_output_validation(self):
        """Verifies inventory_summary.json generated with valid structure."""
        executor = SinglePCAutonomousExecutor(repo_dir=self.tmp_dir, session_id="test-inv-001")
        executor.execute_shift(max_steps=5)

        inv_file = self.tmp_dir / "runtime/content/inventory_summary.json"
        self.assertTrue(inv_file.is_file())
        data = json.loads(inv_file.read_text(encoding="utf-8"))
        self.assertEqual(data.get("schema_version"), "FRUITKI_INVENTORY_SUMMARY_V1")
        self.assertEqual(data.get("total_packages"), 32)
        self.assertEqual(data.get("qc_passed_count"), 20)
        self.assertEqual(data.get("qc_blocked_count"), 6)

    def test_04_pricing_manifest_output_validation(self):
        """Verifies licensing_tiers.json generated with non-empty tiers."""
        executor = SinglePCAutonomousExecutor(repo_dir=self.tmp_dir, session_id="test-price-001")
        executor.execute_shift(max_steps=5)

        price_file = self.tmp_dir / "runtime/content/licensing_tiers.json"
        self.assertTrue(price_file.is_file())
        data = json.loads(price_file.read_text(encoding="utf-8"))
        self.assertEqual(data.get("schema_version"), "FRUITKI_LICENSING_TIERS_V1")
        self.assertEqual(data.get("total_tiers_defined"), 4)
        self.assertEqual(data.get("total_packages_mapped"), 32)
        self.assertEqual(data.get("eligible_commercial_packages_count"), 20)

    def test_05_duplicate_suppression_on_repeated_runs(self):
        """Repeated execution does not duplicate already completed tasks."""
        executor1 = SinglePCAutonomousExecutor(repo_dir=self.tmp_dir, session_id="test-dup-001")
        rep1 = executor1.execute_shift(max_steps=5)
        self.assertTrue(len(rep1["executed_tasks"]) > 0)

        # Second run on same session
        executor2 = SinglePCAutonomousExecutor(repo_dir=self.tmp_dir, session_id="test-dup-001")
        rep2 = executor2.execute_shift(max_steps=5)
        self.assertEqual(len(rep2["executed_tasks"]), 0)

    def test_06_human_gate_isolation(self):
        """Human-gated release proposal is isolated without unauthorized publication."""
        executor = SinglePCAutonomousExecutor(repo_dir=self.tmp_dir, session_id="test-gate-001")
        rep = executor.execute_shift(max_steps=5)

        gate_ids = [g["task_id"] for g in rep["human_gates"]]
        self.assertIn("work-fruitki-release-proposal", gate_ids)
        self.assertEqual(rep["publications"], 0)
        self.assertEqual(rep["autonomous_spend_eur"], 0.0)


if __name__ == "__main__":
    unittest.main()
