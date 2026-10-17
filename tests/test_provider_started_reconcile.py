"""Uncertain-execution reconciliation for the durable provider scheduler.

An interrupted provider call (crash between execute and accepted evidence)
parks its task in `started`: excluded from every later wake, stop reason
EFFECT_UNKNOWN. Parking is correct (no duplicate replay), but without an
explicit reconcile entry point the wedge is permanent — the documented
\"controller/human-authority path\" has no implementation behind it.

These tests pin: the wedge, completion-by-verification, safe retry after a
proven no-effect, and rejection of unknown tasks. Pure in-process, no
provider/network/child processes.
"""
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path

from scripts.provider_hibernation import ContinuationCheckpoint
from scripts.provider_survival import CourierScheduler, Provider, TaskContext


def _checkpoint(workkey="wk-reconcile"):
    return ContinuationCheckpoint(
        repo_sha="a" * 40, branch="codex/work", pr="123", workkey=workkey,
        mutable_scope="provider-continuity", task_id="provider", attempt=3,
        dispatch_id="dispatch-3", effect_key="stable-effect",
        completed_fingerprints=[], latest_tests="exact-head proof",
        source_refs=[], next_units=["job-1"], next_action="go",
        open_provider_units=["job-1"], provider_connection_id="codex")


class StartedReconcileTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = str(Path(self.tmp.name) / "continuation.json")
        self.calls = []

    def task(self, name="job-1"):
        return TaskContext(name, fingerprint="fp-" + name, authority_scope="repo")

    def scheduler(self, execute):
        providers = [Provider("codex", True, ["completion"], authority_scopes=("repo",))]

        @contextmanager
        def ownership(cp, truth):
            yield {"workkey": cp.workkey, "mutable_scope": cp.mutable_scope,
                   "next_units": ["job-1"], "next_action": "go"}

        return CourierScheduler(
            primary_provider="codex", state_path=self.path, providers=providers,
            probe_provider=lambda *_: (True, 200, "available"),
            refresh_repository=lambda cp: {"repo_sha": "b" * 40,
                                           "branch": "codex/work", "pr": "123"},
            reconcile_ownership=ownership,
            authority_check=lambda *_: True,
            execute_provider=execute, execute_local=None)

    def test_interrupted_task_stays_parked_without_reconcile(self):
        """A non-accepting execution result parks the unit: later wakes must
        not replay it, and the loop reports EFFECT_UNKNOWN, not success."""
        sched = self.scheduler(
            lambda p, t, cp: {"status": "ERROR", "evidence": []})
        tasks = [self.task()]
        self.assertEqual(sched.handle_wake("w1", tasks, checkpoint=_checkpoint()),
                         "EFFECT_UNKNOWN")
        self.assertEqual(sched.handle_wake("w2", tasks, checkpoint=_checkpoint()),
                         "EFFECT_UNKNOWN")
        self.assertEqual(self.calls, [])
        # Parked, not completed, not replayed.
        self.assertNotIn("job-1", sched.completed_tasks)

    def test_reconcile_completed_marks_done_with_evidence(self):
        """Verified external effect completes the unit with its evidence."""
        sched = self.scheduler(
            lambda p, t, cp: {"status": "ERROR", "evidence": []})
        tasks = [self.task()]
        sched.handle_wake("w1", tasks, checkpoint=_checkpoint())
        receipt = sched.reconcile_started("job-1", effect_completed=True,
                                          evidence=["ext:job-1"])
        self.assertEqual(receipt["outcome"], "COMPLETED")
        self.assertIn("job-1", sched.completed_tasks)
        self.assertEqual(sched.handle_wake("w2", tasks, checkpoint=_checkpoint()),
                         "IDLE_NO_NEW_WORK")

    def test_reconcile_no_effect_reruns_safely(self):
        """A proven no-effect releases the unit for exactly one re-execution,
        which then completes normally."""
        def execute_once_then_done(provider, task, cp):
            self.calls.append(task.task_id)
            if len(self.calls) == 1:
                return {"status": "ERROR", "evidence": []}
            return {"status": "DONE", "evidence": ["done:job-1"]}

        sched = self.scheduler(execute_once_then_done)
        tasks = [self.task()]
        sched.handle_wake("w1", tasks, checkpoint=_checkpoint())
        receipt = sched.reconcile_started("job-1", effect_completed=False)
        self.assertEqual(receipt["outcome"], "RETRY_RELEASED")
        self.assertEqual(sched.handle_wake("w2", tasks, checkpoint=_checkpoint()),
                         "CHECKPOINTED")
        self.assertEqual(self.calls, ["job-1", "job-1"])
        self.assertIn("job-1", sched.completed_tasks)

    def test_reconcile_unknown_task_raises_without_mutation(self):
        """Reconciling a task that is not parked must fail closed."""
        sched = self.scheduler(
            lambda p, t, cp: {"status": "DONE", "evidence": ["done:job-1"]})
        tasks = [self.task()]
        sched.handle_wake("w1", tasks, checkpoint=_checkpoint())
        with self.assertRaises(ValueError):
            sched.reconcile_started("job-1", effect_completed=True,
                                    evidence=["ext:job-1"])
        with self.assertRaises(ValueError):
            sched.reconcile_started("nope", effect_completed=False)


if __name__ == "__main__":
    unittest.main()
