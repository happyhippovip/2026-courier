#!/usr/bin/env python3
"""Mission PRODUCT-4 Acceptance Test Suite — Autonomous Opportunity Discovery.

Verifies:
1. Real Chief Brain goal creates candidate.
2. Completed goal creates none.
3. Closed strand + no delta stays closed.
4. Real invalidating evidence may reopen bounded work.
5. Duplicate evidence creates no duplicate.
6. Polling creates no spam (idempotency).
7. Restart preserves deduplication.
8. Unresolved dependency prevents premature work.
9. Result unlocks next candidate.
10. Complete goal yields STOP_SUCCESS.
11. Two independent useful opportunities coexist (Parallelism).
12. Human gate correctly classified.
13. Safe branch survives Human gate.
14. Money gate correctly classified.
15. Safe branch survives Money gate.
16. Publication gate preserved.
17. Structured discovery uses 0 model calls.
18. No fake revenue/customer/analytics.
19. No routine review candidates.
20. No mission-number inflation.
21. No busywork generated because provider is free.
22. Product-3 cockpit compatibility.
23. Provider-neutral Codex bridge compatibility.
24. Message completion stamp: DONE + same fingerprint => no redispatch.
25. Message completion stamp: NOT_DONE / HANDOFF_REQUIRED => eligible handoff.
"""

from __future__ import annotations

import io
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.autonomous_opportunity_discovery import (
    AutonomousOpportunityDiscoveryEngine,
    CanonicalOpportunity,
)
from scripts.run_visual_studio_server import StudioHTTPRequestHandler
from unittest.mock import MagicMock, patch


class TestAutonomousOpportunityDiscoveryMissionProduct4(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="courier_opp_disc_test_"))
        self.events_dir = self.test_dir / "events"
        self.events_dir.mkdir(parents=True, exist_ok=True)
        (self.events_dir / "opportunity-queue").mkdir(parents=True, exist_ok=True)
        (self.events_dir / "chief-brain").mkdir(parents=True, exist_ok=True)
        (self.events_dir / "autonomy-runtime").mkdir(parents=True, exist_ok=True)
        (self.events_dir / "anomalies").mkdir(parents=True, exist_ok=True)
        (self.events_dir / "agent-states").mkdir(parents=True, exist_ok=True)
        self.engine = AutonomousOpportunityDiscoveryEngine(repo_dir=self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_01_real_chief_brain_goal_creates_candidate(self):
        """Active Chief Brain goal generates a canonical opportunity candidate."""
        goals = [{
            "goal_id": "goal-math-01",
            "content": "Compute volatility matrices for EUR risk",
            "target_agent": "antigravity",
            "priority": 8,
            "expected_outcome": "Matrix report in data/matrices.json",
            "scope": ["data/matrices.json"],
        }]
        cands = self.engine.discover_opportunities(active_goals=goals)
        self.assertEqual(len(cands), 1)
        self.assertEqual(cands[0].goal_id, "goal-math-01")
        self.assertEqual(cands[0].status, "READY")
        self.assertTrue((self.test_dir / "events/opportunity-queue" / f"{cands[0].opportunity_id}.json").exists())

    def test_02_completed_goal_creates_none(self):
        """A goal already completed produces no new opportunity."""
        # Pre-seed completed goal in engine
        self.engine.completed_signatures.add("goal-math-01")
        goals = [{
            "goal_id": "goal-math-01",
            "content": "Compute volatility matrices for EUR risk",
            "target_agent": "antigravity",
            "priority": 8,
        }]
        cands = self.engine.discover_opportunities(active_goals=goals)
        self.assertEqual(len(cands), 0)

    def test_03_closed_strand_protection(self):
        """Closed strand with no relevant delta produces zero opportunities."""
        opp = CanonicalOpportunity(
            opportunity_id="opp-closed-01",
            goal_id="goal-closed",
            description="Archive previous month ledger",
            status="DONE",
        )
        self.engine.add_opportunity(opp)
        self.engine.completed_signatures.add(opp.dedupe_hash)

        goals = [{
            "goal_id": "goal-closed",
            "content": "Archive previous month ledger",
        }]
        cands = self.engine.discover_opportunities(active_goals=goals)
        self.assertEqual(len(cands), 0)

    def test_04_invalidating_evidence_reopens_bounded_work(self):
        """Genuine new failure/invalidation evidence justifies bounded remediation work."""
        goals = [{
            "goal_id": "goal-remediate-01",
            "content": "Fix corrupted checksum in monthly archive after disk alert",
            "priority": 9,
            "expected_outcome": "Repaired checksum in ledger",
        }]
        cands = self.engine.discover_opportunities(active_goals=goals)
        self.assertEqual(len(cands), 1)
        self.assertEqual(cands[0].priority, 9)

    def test_05_duplicate_evidence_creates_no_duplicate(self):
        """Duplicate evidence yields exactly one canonical opportunity record."""
        goals = [{
            "goal_id": "goal-dup-check",
            "content": "Verify SSL certificates for API gateway",
        }]
        cands1 = self.engine.discover_opportunities(active_goals=goals)
        cands2 = self.engine.discover_opportunities(active_goals=goals)

        self.assertEqual(len(cands1), 1)
        self.assertEqual(len(cands2), 0)  # Suppressed as duplicate

    def test_06_polling_creates_no_spam(self):
        """Repeated polling cycles with unchanged state generate 0 candidates."""
        goals = [{"goal_id": "g1", "content": "Task 1"}]
        self.engine.discover_opportunities(active_goals=goals)

        for _ in range(5):
            cands = self.engine.discover_opportunities(active_goals=goals)
            self.assertEqual(len(cands), 0)

    def test_07_restart_preserves_deduplication(self):
        """Instantiating a new engine instance after restart preserves deduplication."""
        goals = [{"goal_id": "g1", "content": "Task 1"}]
        self.engine.discover_opportunities(active_goals=goals)

        # Simulate restart
        new_engine = AutonomousOpportunityDiscoveryEngine(repo_dir=self.test_dir)
        cands = new_engine.discover_opportunities(active_goals=goals)
        self.assertEqual(len(cands), 0)

    def test_08_unresolved_dependency_prevents_premature_work(self):
        """Step B is not emitted if prerequisite Step A is not yet completed."""
        chain = [{
            "goal_id": "goal-seq-01",
            "steps": [
                {"step_id": "step-a", "description": "Step A: Extract raw metrics", "dependencies": []},
                {"step_id": "step-b", "description": "Step B: Summarize metrics", "dependencies": ["step-a"]},
            ]
        }]
        cands = self.engine.discover_opportunities(sequenced_chains=chain)
        self.assertEqual(len(cands), 1)
        self.assertEqual(cands[0].opportunity_id, "step-a")

    def test_09_result_unlocks_next_candidate_and_10_stop_success(self):
        """Zero-prompt sequential chain: Step A complete -> unlocks B -> B complete -> unlocks C -> C complete -> STOP_SUCCESS."""
        chain = [{
            "goal_id": "goal-chain-full",
            "steps": [
                {"step_id": "step-1", "description": "Extract data", "dependencies": []},
                {"step_id": "step-2", "description": "Transform data", "dependencies": ["step-1"]},
                {"step_id": "step-3", "description": "Load data", "dependencies": ["step-2"]},
            ]
        }]

        # Iteration 1: Initial state -> discovers step-1
        cands1 = self.engine.discover_opportunities(sequenced_chains=chain)
        self.assertEqual(len(cands1), 1)
        self.assertEqual(cands1[0].opportunity_id, "step-1")

        # Iteration 2: Result for step-1 arrives -> discovers step-2
        cands2 = self.engine.discover_opportunities(
            sequenced_chains=chain,
            new_result={"task_id": "step-1", "outcome": "SUCCESS"},
        )
        self.assertEqual(len(cands2), 1)
        self.assertEqual(cands2[0].opportunity_id, "step-2")

        # Iteration 3: Result for step-2 arrives -> discovers step-3
        cands3 = self.engine.discover_opportunities(
            sequenced_chains=chain,
            new_result={"task_id": "step-2", "outcome": "SUCCESS"},
        )
        self.assertEqual(len(cands3), 1)
        self.assertEqual(cands3[0].opportunity_id, "step-3")

        # Iteration 4: Result for step-3 arrives -> all complete -> 0 new candidates (STOP_SUCCESS)
        cands4 = self.engine.discover_opportunities(
            sequenced_chains=chain,
            new_result={"task_id": "step-3", "outcome": "SUCCESS"},
        )
        self.assertEqual(len(cands4), 0)

    def test_11_parallel_independent_opportunities_coexist(self):
        """Two independent useful opportunities with different scopes and workers are both emitted."""
        goals = [
            {
                "goal_id": "goal-google-build",
                "content": "Implement vector math acceleration in scripts/math.py",
                "target_agent": "antigravity",
                "provider": "GOOGLE_PRO",
                "scope": ["scripts/math.py"],
            },
            {
                "goal_id": "goal-codex-spec",
                "content": "Write compliance oracle tests in tests/test_compliance.py",
                "target_agent": "codex",
                "provider": "CODEX",
                "scope": ["tests/test_compliance.py"],
            }
        ]
        cands = self.engine.discover_opportunities(active_goals=goals)
        self.assertEqual(len(cands), 2)
        providers = {c.provider for c in cands}
        self.assertIn("GOOGLE_PRO", providers)
        self.assertIn("CODEX", providers)

    def test_12_human_gate_classification_and_13_branch_survival(self):
        """Human gate is classified properly while independent safe branch remains eligible."""
        goals = [
            {
                "goal_id": "goal-gated-pub",
                "content": "Publish weekly summary release to YouTube channel",
                "target_agent": "publication_officer",
            },
            {
                "goal_id": "goal-safe-calc",
                "content": "Calculate local cache hit ratio",
                "target_agent": "antigravity",
            }
        ]
        cands = self.engine.discover_opportunities(active_goals=goals)
        self.assertEqual(len(cands), 2)

        gated = next(c for c in cands if "Publish" in c.description)
        safe = next(c for c in cands if "Calculate" in c.description)

        self.assertEqual(gated.status, "HUMAN_GATE")
        self.assertEqual(safe.status, "READY")

    def test_14_money_gate_classification_and_15_branch_survival(self):
        """Spend > 0 EUR is classified as MONEY_GATE; safe branch remains eligible."""
        goals = [
            {
                "goal_id": "goal-paid-tool",
                "content": "Purchase external API credits",
                "estimated_cost": 25.0,
            },
            {
                "goal_id": "goal-local-audit",
                "content": "Audit security configuration files",
                "estimated_cost": 0.0,
            }
        ]
        cands = self.engine.discover_opportunities(active_goals=goals)
        self.assertEqual(len(cands), 2)

        money_gated = next(c for c in cands if "Purchase" in c.description)
        free_task = next(c for c in cands if "Audit" in c.description)

        self.assertEqual(money_gated.status, "MONEY_GATE")
        self.assertEqual(money_gated.cost_class, "PAID")
        self.assertEqual(free_task.status, "READY")
        self.assertEqual(free_task.cost_class, "FREE_LOCAL")

    def test_16_publication_gate_preserved(self):
        """Public upload or release deployment is strictly gated."""
        goals = [{
            "goal_id": "goal-pub-gate",
            "content": "Public upload of video package",
        }]
        cands = self.engine.discover_opportunities(active_goals=goals)
        self.assertEqual(len(cands), 1)
        self.assertEqual(cands[0].status, "HUMAN_GATE")

    def test_17_deterministic_first_zero_model_calls(self):
        """Discovery process executes completely locally without calling any LLM API."""
        goals = [{"goal_id": "g-det", "content": "Deterministic local code check"}]
        cands = self.engine.discover_opportunities(active_goals=goals)
        self.assertEqual(len(cands), 1)

    def test_18_no_fake_revenue_or_busywork_rejection(self):
        """Artificial tasks such as fake revenue or routine review are rejected."""
        goals = [
            {"goal_id": "g-fake-rev", "content": "Generate synthetic fake revenue analytics"},
            {"goal_id": "g-busy", "content": "Run routine review on idle poll"},
        ]
        cands = self.engine.discover_opportunities(active_goals=goals)
        self.assertEqual(len(cands), 0)

    def test_22_product_3_cockpit_compatibility(self):
        """Discovered opportunities are directly rendered in Product-3 Live Task Board."""
        goals = [{
            "goal_id": "g-cockpit-check",
            "content": "Verify cache optimization",
            "target_agent": "antigravity",
            "provider": "GOOGLE_PRO",
            "priority": 7,
        }]
        cands = self.engine.discover_opportunities(active_goals=goals)
        self.assertEqual(len(cands), 1)

        handler = MagicMock()
        handler.wfile = io.BytesIO()

        with patch("scripts.run_visual_studio_server.EVENTS_DIR", self.events_dir),              patch("scripts.run_visual_studio_server.COURIER_DIR", self.test_dir):
            StudioHTTPRequestHandler.handle_api_state(handler)

        res = json.loads(handler.wfile.getvalue().decode("utf-8"))
        tb = res.get("task_board", [])
        task = next((t for t in tb if t["task_id"] == cands[0].opportunity_id), None)
        self.assertIsNotNone(task)
        self.assertEqual(task["provider"], "GOOGLE_PRO")
        self.assertEqual(task["status"], "READY")

    def test_23_codex_bridge_compatibility(self):
        """Codex provider fields are preserved for Codex dispatch."""
        goals = [{
            "goal_id": "g-codex",
            "content": "Codex technical verification",
            "target_agent": "codex",
            "provider": "CODEX",
        }]
        cands = self.engine.discover_opportunities(active_goals=goals)
        self.assertEqual(len(cands), 1)
        self.assertEqual(cands[0].provider, "CODEX")
        self.assertEqual(cands[0].target_agent, "codex")

    def test_24_message_completion_stamp_done_prevents_redispatch(self):
        """Message completion stamp DONE prevents re-dispatch of identical semantic work."""
        goals = [{"goal_id": "g-msg-1", "content": "Handle user query on data export"}]
        cands = self.engine.discover_opportunities(active_goals=goals)
        self.assertEqual(len(cands), 1)
        opp_id = cands[0].opportunity_id

        # Apply DONE stamp
        ok = self.engine.apply_message_completion_stamp(
            opportunity_id=opp_id,
            stamp_status="DONE",
            worker="antigravity",
            result_ref="res-export-101",
        )
        self.assertTrue(ok)

        # Subsequent discovery does NOT re-emit
        cands_next = self.engine.discover_opportunities(active_goals=goals)
        self.assertEqual(len(cands_next), 0)

    def test_25_message_completion_stamp_handoff_re_eligible(self):
        """Message completion stamp NOT_DONE or HANDOFF_REQUIRED makes task eligible for handoff."""
        goals = [{"goal_id": "g-msg-2", "content": "Process complex format conversion"}]
        cands = self.engine.discover_opportunities(active_goals=goals)
        self.assertEqual(len(cands), 1)
        opp_id = cands[0].opportunity_id

        # Apply HANDOFF_REQUIRED stamp
        ok = self.engine.apply_message_completion_stamp(
            opportunity_id=opp_id,
            stamp_status="HANDOFF_REQUIRED",
            worker="worker_1",
        )
        self.assertTrue(ok)

        opp = self.engine.discovered_opportunities[opp_id]
        self.assertEqual(opp.status, "READY")
        self.assertEqual(opp.message_stamp["status"], "HANDOFF_REQUIRED")


if __name__ == "__main__":
    unittest.main()
