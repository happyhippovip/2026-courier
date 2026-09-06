"""Focused Product-3C bridge acceptance tests; all runtime effects are temp-local."""

import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.organization_elite_policy import CentralElitePolicyRegistry, AnomalyDomain
from scripts.productivity_engine import WorkCandidate
from scripts.productivity_runtime_bridge import ProductivityRuntimeBridge


def work(task_id, capability="GOOGLE", scope="scope-a", **kwargs):
    base = dict(task_id=task_id, goal=f"Goal {task_id}", expected_useful_outcome=f"Outcome {task_id}", owner_capability=capability, scope=scope, priority_reason="TEST", decision_value="HIGH_VALUE")
    base.update(kwargs)
    return WorkCandidate(**base)


class Product3CBridgeTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="product_3c_"))
        CentralElitePolicyRegistry._instance = None
        self.bridge = ProductivityRuntimeBridge(self.root)
        self.workers = {"google": {"state": "FREE", "capabilities": ["GOOGLE"], "provider": "GOOGLE_PRO"}, "codex": {"state": "FREE", "capabilities": ["CODEX"], "provider": "OPENAI_CODEX"}}
        self.resolver = lambda task_id: (True, {"task": task_id, "ok": True})

    def tearDown(self):
        CentralElitePolicyRegistry._instance = None
        shutil.rmtree(self.root, ignore_errors=True)

    def test_queue_is_advisory_and_native_runtime_creates_envelope(self):
        self.bridge.synchronize([work("A")], self.workers)
        result = self.bridge.dispatch_one("goal", lambda task_id: (False, None))
        self.assertEqual(result["status"], "PROGRESS_MADE")
        self.assertEqual(result["transition"]["action_type"], "DISPATCH_JOB")
        self.assertIn("job_envelope", result["transition"]["details"])
        self.assertEqual(self.bridge.manual_intermediate_prompts, 0)

    def test_gates_and_scope_conflict_are_not_authorized_by_productivity_queue(self):
        candidates = [work("pub", publication_gate=True), work("money", money_gate=True), work("one", scope="same"), work("two", "CODEX", "same")]
        plan = self.bridge.synchronize(candidates, self.workers)
        states = {item["task_id"]: item["state"] for item in plan["tasks"]}
        self.assertEqual(states["pub"], "PUBLICATION_GATE")
        self.assertEqual(states["money"], "MONEY_GATE")
        self.assertEqual(len(plan["dispatch_advisory"]), 1)

    def test_result_automatically_unlocks_dependent_next_task(self):
        candidates = [work("A", scope="a"), work("B", "CODEX", "b", dependencies=("A",))]
        transitions = self.bridge.run_until_quiescent("chain", candidates, self.workers, self.resolver)
        completed = self.bridge._completed_task_ids()
        self.assertGreaterEqual(len(transitions), 2)
        self.assertTrue({"A", "B"}.issubset(completed))

    def test_parallel_advice_uses_two_workers_and_join_read_is_model_free(self):
        self.bridge.synchronize([work("A", scope="a"), work("B", "CODEX", "b")], self.workers)
        snapshot = self.bridge.join_snapshot()
        self.assertEqual(len(snapshot["parallel_jobs"]), 2)
        self.assertEqual(snapshot["model_calls_for_read"], 0)

    def test_zero_gain_idle_provider_wait_and_duplicate_are_safe(self):
        self.assertEqual(self.bridge.synchronize([work("Z", decision_value="ZERO_GAIN")], self.workers)["status"], "STOP_SUCCESS")
        self.assertEqual(self.bridge.synchronize([work("WAIT", provider_eligibility=("UNAVAILABLE",))], self.workers)["dispatch_advisory"], [])
        self.bridge.synchronize([work("DUP")], self.workers)
        self.bridge.synchronize([work("DUP")], self.workers)
        self.assertEqual(len(self.bridge.runtime.opp_queue.list_opportunities()), 1)

    def test_snitch_quarantine_isolates_affected_scope(self):
        self.bridge.runtime.snitch_manager.report_observation("auditor", AnomalyDomain.SECURITY_BOUNDARY_VIOLATION, "bad", "good", affected_scope="bad-scope", affected_branch="BAD_BRANCH")
        self.bridge.synchronize([work("bad", scope="bad-scope"), work("safe", "CODEX", "safe-scope")], self.workers)
        result = self.bridge.dispatch_one("snitch", self.resolver)
        self.assertEqual(result["transition"]["action_type"], "LOCAL_DETERMINISTIC_EXECUTION")


if __name__ == "__main__":
    unittest.main()
