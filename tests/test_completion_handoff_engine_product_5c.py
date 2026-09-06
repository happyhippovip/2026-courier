"""Product-5C focused completion/handoff acceptance in isolated temp state."""

import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.completion_handoff_engine import CompletionHandoffEngine
from scripts.productivity_engine import WorkCandidate


class CompletionHandoffEngineTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="product_5c_"))
        self.engine = CompletionHandoffEngine(self.root)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_open_claim_done_is_terminal_and_evidence_required(self):
        self.engine.open("M", "fp", "goal")
        self.assertTrue(self.engine.claim("M", "google")["accepted"])
        self.assertFalse(self.engine.claim("M", "codex")["accepted"])
        self.assertEqual(self.engine.record_result("M", "fp", None, True)["status"], "BLOCKED")
        self.assertEqual(self.engine.ledger["completion_stamps"]["M"]["status"], "BLOCKED")
        self.engine.open("D", "fp-d")
        self.engine.claim("D", "google")
        self.assertEqual(self.engine.record_result("D", "fp-d", "result-D", True)["status"], "DONE")
        self.assertFalse(self.engine.claim("D", "codex")["accepted"])

    def test_capability_handoff_preserves_identity_and_prevents_ping_pong(self):
        self.engine.open("M", "same", "goal")
        self.engine.claim("M", "google")
        self.assertEqual(self.engine.not_done("M", "CAPABILITY_MISMATCH")["status"], "HANDOFF_REQUIRED")
        handoff = self.engine.handoff("M", ["google", "codex"])
        self.assertTrue(handoff["accepted"])
        item = self.engine.ledger["completion_stamps"]["M"]
        self.assertEqual(item["semantic_fingerprint"], "same")
        self.assertEqual(item["claims"], ["google", "codex"])
        self.assertEqual(self.engine.not_done("M", "CAPABILITY_MISMATCH")["status"], "BLOCKED")

    def test_dependency_and_gates_wait_without_handoff_while_independent_work_can_continue(self):
        self.engine.open("dep", "d")
        self.assertEqual(self.engine.claim("dep", "google", dependencies_satisfied=False)["status"], "WAITING_DEPENDENCY")
        self.assertEqual(self.engine.ledger["completion_stamps"]["dep"]["status"], "WAITING_DEPENDENCY")
        self.engine.open("money", "m")
        self.engine.claim("money", "google")
        self.assertEqual(self.engine.not_done("money", "MONEY_GATE")["status"], "MONEY_GATE")
        self.engine.open("safe", "s")
        self.assertTrue(self.engine.claim("safe", "codex")["accepted"])

    def test_unmet_acceptance_and_restart_recovery_are_safe(self):
        self.engine.open("quality", "q")
        self.engine.claim("quality", "google")
        self.assertEqual(self.engine.record_result("quality", "q", "result", False)["status"], "HANDOFF_REQUIRED")
        self.engine.open("orphan", "o")
        self.engine.claim("orphan", "google")
        restarted = CompletionHandoffEngine(self.root)
        self.assertEqual(restarted.recover(["codex"]), ["orphan"])
        self.assertEqual(restarted.ledger["completion_stamps"]["orphan"]["status"], "HANDOFF_REQUIRED")

    def test_product_4_and_batch_compatibility_and_zero_model_bookkeeping(self):
        candidate = WorkCandidate("done", "goal", "out", "GOOGLE", "scope", semantic_fingerprint="f")
        self.engine.open("done", "f")
        self.engine.claim("done", "google")
        self.engine.record_result("done", "f", "result", True)
        self.assertEqual(self.engine.eligible_candidates([candidate]), [])
        self.assertEqual(self.engine.model_calls, 0)


if __name__ == "__main__":
    unittest.main()
