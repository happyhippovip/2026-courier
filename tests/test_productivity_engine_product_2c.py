"""Focused Product-2C deterministic scheduler acceptance tests."""

import tempfile
import unittest
from pathlib import Path

from scripts.productivity_engine import ProductivityEngine, WorkCandidate


def candidate(task_id, capability="GOOGLE", scope="scope", **kwargs):
    base = dict(task_id=task_id, goal=task_id, expected_useful_outcome="useful", owner_capability=capability, scope=scope, priority_reason="TEST")
    base.update(kwargs)
    return WorkCandidate(**base)


class ProductivityEngineProduct2CTests(unittest.TestCase):
    def setUp(self):
        self.engine = ProductivityEngine(Path(tempfile.mkdtemp(prefix="product_2c_")))
        self.workers = {"google": {"state": "FREE", "capabilities": ["GOOGLE"]}, "codex": {"state": "FREE", "capabilities": ["CODEX"]}}

    def test_two_independent_valuable_tasks_parallelize(self):
        plan = self.engine.plan([candidate("A", scope="a", decision_value="HIGH_VALUE"), candidate("B", "CODEX", "b", decision_value="HIGH_VALUE")], self.workers)
        self.assertEqual(len(plan["dispatch_advisory"]), 2)
        self.assertEqual(plan["metrics"]["parallel_independent_jobs"], 1)

    def test_scope_conflict_and_zero_gain_idle(self):
        plan = self.engine.plan([candidate("A", scope="same"), candidate("B", "CODEX", "same")], self.workers)
        self.assertEqual(len(plan["dispatch_advisory"]), 1)
        idle = self.engine.plan([candidate("Z", decision_value="ZERO_GAIN")], self.workers)
        self.assertEqual(idle["status"], "STOP_SUCCESS")

    def test_dependencies_and_gates_are_branch_local(self):
        plan = self.engine.plan([
            candidate("wait", dependencies=("missing",)), candidate("human", human_gate=True),
            candidate("money", money_gate=True), candidate("publish", publication_gate=True),
            candidate("safe", "CODEX", "safe"),
        ], self.workers)
        states = {x["task_id"]: x["state"] for x in plan["tasks"]}
        self.assertEqual(states["wait"], "WAITING_DEPENDENCY")
        self.assertEqual(states["human"], "HUMAN_GATE")
        self.assertEqual(states["money"], "MONEY_GATE")
        self.assertEqual(states["publish"], "PUBLICATION_GATE")
        self.assertEqual(states["safe"], "READY")

    def test_duplicate_review_and_completed_work_never_dispatch(self):
        plan = self.engine.plan([candidate("done", completed=True), candidate("cached", semantic_fingerprint="fp")], self.workers, accepted_fingerprints=["fp"])
        self.assertEqual(plan["status"], "STOP_SUCCESS")
        self.assertEqual(plan["metrics"]["model_calls_avoided_when_provable"], 1)

    def test_critical_product_work_beats_cosmetic_infrastructure(self):
        plan = self.engine.plan([
            candidate("cosmetic", "GOOGLE", "x", decision_value="OPTIONAL", product_value=False, infrastructure_only=True),
            candidate("critical", "GOOGLE", "y", decision_value="CRITICAL_UNBLOCK", critical_path=True),
        ], {"google": self.workers["google"]})
        self.assertEqual(plan["dispatch_advisory"][0]["task_id"], "critical")

    def test_unavailable_provider_waits_without_fake_dispatch_or_purchase(self):
        plan = self.engine.plan([candidate("need-google")], {"codex": self.workers["codex"]})
        self.assertEqual(plan["dispatch_advisory"], [])
        self.assertIsNone(plan["capacity_purchase_candidate"])
        self.assertEqual(plan["model_calls"], 0)

    def test_provider_eligibility_is_evidence_bound(self):
        worker = {"google": {"state": "FREE", "capabilities": ["GOOGLE"], "provider": "UNVERIFIED"}}
        plan = self.engine.plan([candidate("verified-only", provider_eligibility=("GOOGLE_PRO",))], worker)
        self.assertEqual(plan["dispatch_advisory"], [])

    def test_twenty_five_logical_agents_do_not_create_model_jobs(self):
        workers = {f"agent-{i}": {"state": "FREE", "capabilities": ["NONE"]} for i in range(25)}
        plan = self.engine.plan([candidate("task")], workers)
        self.assertEqual(plan["model_calls"], 0)
        self.assertEqual(plan["dispatch_advisory"], [])


if __name__ == "__main__":
    unittest.main()
