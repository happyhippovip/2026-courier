"""Independent future acceptance lab; intentionally red before Chief-Brain implementation.

All tests are local and inspect schemas/contracts only.  They never dispatch a
provider, write memory, or create a publication authority.
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

def schema(name: str) -> dict:
    return json.loads((ROOT / "schemas" / name).read_text())

class Mission143CAutonomyLab(unittest.TestCase):
    def test_chief_schema_rejects_unknown_fields_and_future_versions(self):
        s = schema("chief_brain_state_v1.schema.json")
        self.assertFalse(s.get("additionalProperties", True))
        self.assertEqual(s["properties"]["schema_version"].get("const"), "CHIEF_BRAIN_STATE_V1")
        # Future implementation must also enforce timestamp, immutable id chain and no duplicate result id.
        self.assertIn("result_id", s["properties"])

    def test_context_contract_carries_non_bypassable_money_and_stop_boundaries(self):
        s = schema("chief_context_package_v1.schema.json")
        req = set(s["required"])
        self.assertTrue({"task_id", "allowed_actions", "forbidden_actions", "stop_conditions", "context_hash"} <= req)
        # Security/money rules must become mandatory semantic fields before dispatch implementation.
        self.assertIn("security_rules", req)
        self.assertIn("money_rules", req)

    def test_provider_result_requires_no_external_authority_by_prose(self):
        s = schema("provider_result_v1.schema.json")
        req = set(s["required"])
        self.assertTrue({"task_id", "correlation_id", "result_hash", "external_calls", "mutations", "money_spent_eur"} <= req)
        self.assertEqual(s["properties"]["money_spent_eur"].get("minimum"), 0)

    def test_acceptance_matrix_preserves_all_human_gates_and_141c_boundary(self):
        matrix = json.loads((ROOT / "tests" / "mission_143c_acceptance_matrix.json").read_text())
        self.assertEqual(len(matrix["human_gates"]), 10)
        publication = next(x for x in matrix["requirements"] if x["requirement"] == "publication authority")
        self.assertEqual(publication["actual"], "BLOCKED")
        self.assertTrue(publication["activation_blocking"])

    def test_no_normal_chief_transport_claim_without_real_evidence(self):
        matrix = json.loads((ROOT / "tests" / "mission_143c_acceptance_matrix.json").read_text())
        transport = next(x for x in matrix["requirements"] if x["requirement"] == "normal Chief transport")
        self.assertEqual(transport["actual"], "UNPROVEN")

if __name__ == "__main__":
    unittest.main()
