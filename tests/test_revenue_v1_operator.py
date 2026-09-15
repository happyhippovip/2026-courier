"""Focused tests for the bounded operator-to-Revenue-V1 closure."""

from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "scripts" / "run_revenue_v1_operator.py"
SHA = "a" * 40


class RevenueV1OperatorTests(unittest.TestCase):
    def command(self, root: Path, *args: str) -> dict:
        completed = subprocess.run(
            ["python3", str(SCRIPT), "--root", str(root), "--no-git", *args],
            check=True, text=True, capture_output=True,
        )
        return json.loads(completed.stdout)

    def test_admitted_packet_is_durable_and_retry_dispatches_zero_times(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            args = (
                "start", "--dry-run", "--target-owner", "octo", "--target-repo", "public",
                "--target-sha", SHA, "--customer-reference", "TEST-001",
                "--delivery-destination", "operator@example.test",
            )
            first = self.command(root, *args)
            second = self.command(root, *args)
            packet = json.loads(next((root / "revenue_v1/inbox").glob("*.json")).read_text())
            self.assertEqual(first["state"], "PRE_DISPATCH_ADMITTED")
            self.assertEqual(first, second)
            self.assertEqual(packet["execution_lane"], "github-actions-revenue-v1")
            self.assertEqual(packet["worker_adapter_ref"], "revenue_v1/worker_adapters/github-actions-revenue-v1.json")
            self.assertEqual(packet["proposal_mode"], "PR_ONLY")

    def test_only_reconciled_human_gate_can_complete_the_automatic_path(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            state = self.command(
                root, "start", "--dry-run", "--target-owner", "octo", "--target-repo", "public",
                "--target-sha", SHA, "--customer-reference", "TEST-002",
                "--delivery-destination", "operator@example.test",
            )
            reconciliation = root / "reconciliation.json"
            reconciliation.write_text(json.dumps({
                "status": "HANDOFF_RECONCILED", "task_id": state["task_id"],
                "attempt_id": state["attempt_id"], "proposal_pr": "9",
                "proposal_head": "revenue/result-proposal-9",
                "next_safe_state": "HUMAN_REVIEW_REQUIRED",
            }))
            completed = self.command(
                root, "reconcile", "--reconciliation", str(reconciliation),
                "--result-ref", "revenue_v1/results/test.json",
            )
            self.assertEqual(completed["state"], "HUMAN_REQUIRED")
            self.assertEqual(completed["worker_id"], "github-actions-revenue-v1")
            self.assertEqual(completed["result_ref"], "revenue_v1/results/test.json")
            self.assertEqual(completed["next_explicit_transition"], "HUMAN_REVIEW_REQUIRED")
            self.assertIn("HUMAN_REVIEW_REQUIRED", completed["real_wall"])


if __name__ == "__main__":
    unittest.main()
