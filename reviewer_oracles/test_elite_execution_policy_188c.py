"""Independent contract oracle for future Mission 189 integration."""

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent
MATRIX = ROOT / "elite_execution_adversarial_matrix_188c.json"
POLICY = ROOT / "elite_execution_policy_188c.md"


class EliteExecutionPolicyContractTests(unittest.TestCase):
    def setUp(self):
        self.matrix = json.loads(MATRIX.read_text(encoding="utf-8"))
        self.policy = POLICY.read_text(encoding="utf-8")

    def test_contract_has_all_required_fields(self):
        self.assertEqual(len(self.matrix["required_fields"]), 15)
        for field in self.matrix["required_fields"]:
            self.assertIn(f"`{field}`", self.policy)

    def test_semantic_and_opportunity_vocabularies_are_fail_closed(self):
        self.assertEqual(
            self.matrix["semantic_states"],
            [
                "NO_RELEVANT_CHANGE", "RELEVANT_LOW_RISK_DELTA",
                "RELEVANT_DECISION_DELTA", "RELEVANT_HIGH_RISK_DELTA",
                "UNKNOWN_REQUIRES_CLASSIFICATION",
            ],
        )
        self.assertEqual(
            self.matrix["opportunity_outcomes"],
            ["RUN_NOW", "DEFER_FOR_HIGHER_VALUE", "LOCALIZE", "COALESCE",
             "WAIT_FOR_DEPENDENCY", "DROP_ZERO_GAIN"],
        )

    def test_all_eighteen_adversarial_cases_are_unique(self):
        cases = self.matrix["cases"]
        self.assertEqual(len(cases), 18)
        self.assertEqual(len({case["id"] for case in cases}), 18)
        self.assertTrue(all(case["expected"] for case in cases))

    def test_policy_covers_quality_gates_and_no_swarm_rules(self):
        for phrase in (
            "MONEY", "PUBLICATION", "IDENTITY_LEGAL", "human gate",
            "at most one necessary", "perfection loop", "does not poll a model",
            "quality-adjusted useful-state", "RELEVANT_HIGH_RISK_DELTA",
        ):
            self.assertIn(phrase, self.policy)


if __name__ == "__main__":
    unittest.main()
