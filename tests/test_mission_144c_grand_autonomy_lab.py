"""Independent contract lab for a future Chief-Brain implementation.

This file intentionally tests only local schemas/matrices and makes no claim
that provider or normal-chat transport exists today.
"""
from __future__ import annotations
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

class Mission144CGrandAutonomyLab(unittest.TestCase):
    def setUp(self):
        self.matrix = json.loads((ROOT / "tests" / "mission_144c_grand_autonomy_matrix.json").read_text())

    def test_proof_levels_are_ordered_and_keep_normal_chat_unproven(self):
        self.assertEqual(self.matrix["proof_levels"][-1], "UNPROVEN")
        transport = next(x for x in self.matrix["requirements"] if x["requirement"] == "transport proof")
        self.assertEqual(transport["status"], "UNPROVEN")

    def test_high_risk_contracts_are_activation_blocking(self):
        blocking = {x["requirement"] for x in self.matrix["requirements"] if x["activation_blocker"]}
        self.assertTrue({"state and lineage", "result ingestion", "money and human authority", "publication boundary"} <= blocking)

    def test_post_build_plan_requires_141c_before_acceptance(self):
        commands = "\n".join(self.matrix["post_build_commands"])
        self.assertIn("test_mission_141c_acceptance_oracle", commands)
        self.assertIn("git fetch origin", commands)

    def test_transport_evidence_requires_real_machine_boundaries(self):
        evidence = self.matrix["transport_evidence"]
        for item in evidence.values():
            self.assertTrue(item)
        self.assertTrue(any("durable" in item.lower() for item in evidence.values()))
        self.assertTrue(any("persisted" in item.lower() for item in evidence.values()))

if __name__ == "__main__":
    unittest.main()
