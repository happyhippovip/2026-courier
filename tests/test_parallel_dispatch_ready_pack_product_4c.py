"""Product-4C isolated shadow-pack acceptance; no live runtime is touched."""

import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.organization_elite_policy import AnomalyDomain, CentralElitePolicyRegistry
from scripts.parallel_dispatch_ready_pack import ParallelDispatchReadyPack
from scripts.productivity_engine import WorkCandidate


def task(task_id, capability="GOOGLE", scope="scope-a", **kwargs):
    base = dict(task_id=task_id, goal=task_id, expected_useful_outcome="useful", owner_capability=capability, scope=scope, priority_reason="TEST", decision_value="HIGH_VALUE")
    base.update(kwargs)
    return WorkCandidate(**base)


class ParallelDispatchReadyPackTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="product_4c_"))
        CentralElitePolicyRegistry._instance = None
        self.pack = ParallelDispatchReadyPack(self.root)
        self.workers = {"google": {"state": "FREE", "capabilities": ["GOOGLE"], "provider": "GOOGLE_PRO"}, "codex": {"state": "FREE", "capabilities": ["CODEX"], "provider": "OPENAI_CODEX"}}
        self.local = lambda task_id: (True, {"task": task_id})

    def tearDown(self):
        CentralElitePolicyRegistry._instance = None
        shutil.rmtree(self.root, ignore_errors=True)

    def test_two_independent_providers_form_two_item_batch(self):
        batch = self.pack.select_dispatch_batch([task("g", scope="x"), task("c", "CODEX", "y")], self.workers, deterministic_resolver=self.local)
        self.assertEqual(len(batch["selected_jobs"]), 2)
        self.assertEqual({entry["provider"] for entry in batch["selected_jobs"]}, {"GOOGLE_PRO", "OPENAI_CODEX"})
        self.assertFalse(batch["creates_runtime_jobs"])

    def test_scope_overlap_dependency_and_gates_are_withheld(self):
        batch = self.pack.select_dispatch_batch([
            task("one", scope="project/a"), task("overlap", "CODEX", "project/a/sub"),
            task("dep", "CODEX", "z", dependencies=("one",)), task("human", human_gate=True),
            task("money", money_gate=True), task("pub", publication_gate=True),
        ], self.workers, deterministic_resolver=self.local)
        self.assertEqual(len(batch["selected_jobs"]), 1)
        self.assertEqual(batch["withheld"]["dep"], "WAITING_DEPENDENCY")
        self.assertEqual(batch["withheld"]["human"], "HUMAN_GATE")
        self.assertEqual(batch["withheld"]["money"], "MONEY_GATE")
        self.assertEqual(batch["withheld"]["pub"], "PUBLICATION_GATE")

    def test_quarantine_duplicate_and_provider_unavailability_fail_closed(self):
        self.pack.registry.snitch_manager.report_observation("audit", AnomalyDomain.SECURITY_BOUNDARY_VIOLATION, "bad", "good", affected_scope="bad", affected_branch="BAD")
        batch = self.pack.select_dispatch_batch([task("bad", scope="bad"), task("unavailable", "CODEX", "free", provider_eligibility=("MISSING",))], self.workers, deterministic_resolver=self.local)
        self.assertEqual(batch["selected_jobs"], [])
        self.assertIn(batch["withheld"]["bad"], {"QUARANTINED_BY_SNITCH", "AUTHORITATIVE_DENIAL"})
        self.assertEqual(batch["withheld"]["unavailable"], "WAITING_DEPENDENCY")

    def test_stable_batch_identity_and_completion_stamp_prevent_redispatch(self):
        candidate = task("once", scope="x", semantic_fingerprint="same")
        first = self.pack.select_dispatch_batch([candidate], self.workers, deterministic_resolver=self.local)
        stamp = self.pack.completion_stamp("once", "same", "result-ref")
        second = self.pack.select_dispatch_batch([candidate], self.workers, deterministic_resolver=self.local)
        self.assertEqual(stamp["status"], "DONE")
        self.assertEqual(second["selected_jobs"], [])
        self.assertEqual(second["withheld"]["once"], "DONE")
        self.assertTrue(first["decision_fingerprint"])

    def test_zero_gain_one_useful_and_read_snapshot_are_model_free(self):
        batch = self.pack.select_dispatch_batch([task("useful"), task("zero", "CODEX", "y", decision_value="ZERO_GAIN")], self.workers, deterministic_resolver=self.local)
        view = self.pack.cockpit_snapshot(batch)
        self.assertEqual(len(batch["selected_jobs"]), 1)
        self.assertEqual(batch["withheld"]["zero"], "NO_GAIN")
        self.assertEqual(view["model_calls_for_read"], 0)

    def test_twenty_five_agents_do_not_fan_out(self):
        workers = {f"agent-{i}": {"state": "FREE", "capabilities": ["NONE"], "provider": "NONE"} for i in range(25)}
        batch = self.pack.select_dispatch_batch([task("only")], workers, deterministic_resolver=self.local)
        self.assertEqual(batch["selected_jobs"], [])
        self.assertEqual(batch["model_calls_for_read"], 0)


if __name__ == "__main__":
    unittest.main()
