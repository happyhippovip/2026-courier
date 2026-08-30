"""Deterministic provenance tests for the Studio human-gate API contract."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.run_visual_studio_server import (
    find_active_human_gate,
    resolve_active_gate_decision,
)


class HumanGateTruthTests(unittest.TestCase):
    def test_unrelated_completed_workflow_cannot_resolve_active_gate(self):
        gate = find_active_human_gate({
            "agent-chief": {
                "id": "agent-chief",
                "state": "BLOCKED_POLICY_CONFLICT",
                "blocked": True,
                "workflow": "idea-active",
                "correlation_id": "corr-active",
            }
        })
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            decisions = root / "decisions"
            approvals = root / "approvals"
            decisions.mkdir()
            approvals.mkdir()
            (decisions / "unrelated.json").write_text(json.dumps({
                "workflow_id": "WF-completed",
                "correlation_id": "corr-completed",
                "verdict": "ACCEPTED",
            }), encoding="utf-8")
            decision = resolve_active_gate_decision(gate, decisions, approvals)

        self.assertTrue(gate["provenance_complete"])
        self.assertEqual(decision["status"], "NO_DECISION")
        self.assertIsNone(decision["source"])

    def test_exact_workflow_and_correlation_match_resolves_decision(self):
        gate = find_active_human_gate({
            "agent-chief": {
                "id": "agent-chief",
                "state": "BLOCKED_HUMAN_GATE",
                "blocked": True,
                "workflow": "idea-active",
                "correlation_id": "corr-active",
            }
        })
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            decisions = root / "decisions"
            approvals = root / "approvals"
            decisions.mkdir()
            approvals.mkdir()
            (approvals / "matching.json").write_text(json.dumps({
                "workflow_id": "idea-active",
                "correlation_id": "corr-active",
                "action": "APPROVE",
            }), encoding="utf-8")
            decision = resolve_active_gate_decision(gate, decisions, approvals)

        self.assertEqual(decision["status"], "APPROVE")
        self.assertEqual(decision["source"], "HUMAN_APPROVAL")
        self.assertEqual(decision["workflow_id"], "idea-active")
        self.assertEqual(decision["correlation_id"], "corr-active")

    def test_legacy_gate_without_correlation_stays_unknown(self):
        gate = find_active_human_gate({
            "agent-chief": {
                "id": "agent-chief",
                "state": "BLOCKED_POLICY_CONFLICT",
                "blocked": True,
                "workflow": "idea-legacy",
            }
        })
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            decision = resolve_active_gate_decision(gate, root / "decisions", root / "approvals")

        self.assertFalse(gate["provenance_complete"])
        self.assertEqual(decision["status"], "NO_DECISION")


if __name__ == "__main__":
    unittest.main()
