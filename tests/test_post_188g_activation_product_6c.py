"""Product-6C precheck/rollback fixtures; all evidence and flags are temp-local."""

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.post_188g_activation import Post188GActivationPack, REQUIRED_MODULES


class Product6CActivationPackTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="product_6c_"))
        for name in REQUIRED_MODULES:
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("shadow module\n", encoding="utf-8")
        self.runtime = self.root / "events" / "autonomy-runtime"
        self.runtime.mkdir(parents=True)
        self.pack = Post188GActivationPack(self.root)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def evidence(self, **overrides):
        data = {"session_id": "session-188g-endurance-1788216021", "status": "COMPLETED", "final_acceptance": "PASS", "elapsed_seconds": 28800, "target_seconds": 28800, "autonomous_spend": 0, "external_writes": 0}
        data.update(overrides)
        (self.runtime / "endurance_final_acceptance.json").write_text(json.dumps(data), encoding="utf-8")

    def test_running_missing_failed_and_insufficient_evidence_fail_closed(self):
        self.assertFalse(self.pack.precheck()["ready"])
        self.evidence(status="RUNNING")
        self.assertIn("188G_STILL_RUNNING", self.pack.precheck()["blockers"])
        self.evidence(final_acceptance="FAIL")
        self.assertIn("188G_FINAL_ACCEPTANCE_NOT_PASS", self.pack.precheck()["blockers"])
        self.evidence(elapsed_seconds=100)
        self.assertIn("188G_ELAPSED_PROOF_INSUFFICIENT", self.pack.precheck()["blockers"])

    def test_valid_passed_evidence_allows_precheck_and_exact_module_plan(self):
        self.evidence()
        result = self.pack.precheck()
        self.assertTrue(result["ready"])
        self.assertEqual(result["activation_files"], list(REQUIRED_MODULES))

    def test_shadow_activation_is_atomic_and_rolls_back_on_failure(self):
        self.evidence()
        failed = self.pack.shadow_activate(lambda: False)
        self.assertEqual(failed["rollback"], "COMPLETE")
        self.assertEqual(json.loads(self.pack.state_path.read_text())["PARALLEL_RUNTIME_V1"], "OFF")
        passed = self.pack.shadow_activate(lambda: True)
        self.assertTrue(passed["activated"])
        self.assertEqual(json.loads(self.pack.state_path.read_text())["PARALLEL_RUNTIME_V1"], "ON")

    def test_fingerprint_drift_fails_closed(self):
        self.evidence()
        (self.root / REQUIRED_MODULES[0]).write_text("changed", encoding="utf-8")
        self.assertFalse(self.pack.precheck()["ready"])


if __name__ == "__main__":
    unittest.main()
