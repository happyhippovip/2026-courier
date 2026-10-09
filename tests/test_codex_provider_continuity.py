"""Bounded, offline continuity proofs; Python 3.12 stdlib unittest is sufficient.

No provider, shell, account, purchasing API, timer or child process is invoked.
The fake connector/lease hooks model the mandatory production contracts.
"""
from contextlib import contextmanager
import datetime as dt
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.provider_circuit import ProviderState
from scripts.provider_hibernation import ContinuationCheckpoint, LaneHibernator, LaneState
from scripts.provider_survival import CourierScheduler, Provider, TaskContext


class CodexContinuityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "continuation.json"
        self.trace = []
        self.held = False
        self.cp = ContinuationCheckpoint(
            repo_sha="a" * 40, branch="codex/work", pr="123", workkey="same-work",
            mutable_scope="provider-continuity", task_id="provider", attempt=3,
            dispatch_id="dispatch-3", effect_key="stable-effect",
            completed_fingerprints=["accepted-old"], latest_tests="exact-head proof",
            source_refs=["evidence:old"], next_units=["STALE_NEXT"], next_action="STALE_ACTION",
            open_provider_units=["provider"], provider_connection_id="codex")
        self.providers = [Provider("codex", True, ["completion"], authority_scopes=("repo",))]

    def task(self, name="provider", **kw):
        return TaskContext(name, fingerprint="fp-" + name, authority_scope="repo", **kw)

    def refresh(self, cp):
        self.trace.append("fetch")
        return {"repo_sha": "b" * 40, "branch": "codex/work", "pr": "123"}

    @contextmanager
    def ownership(self, cp, truth):
        self.trace.append("ownership")
        self.held = True
        try:
            yield {"workkey": cp.workkey, "mutable_scope": cp.mutable_scope,
                   "next_units": ["provider", "local", "second"], "next_action": "fresh action"}
        finally:
            self.held = False

    def execute(self, provider, task, cp):
        self.assertTrue(self.held)
        self.assertEqual(cp.repo_sha, "b" * 40)
        self.assertNotIn("STALE_NEXT", cp.next_units)
        self.trace.append("execute:" + provider.id + ":" + task.task_id)
        return {"status": "DONE", "evidence": ["accepted:" + task.task_id]}

    def local(self, task, cp):
        self.assertTrue(self.held)
        self.trace.append("local:" + task.task_id)
        return {"status": "DONE", "evidence": ["local-proof:" + task.task_id]}

    def scheduler(self, **override):
        args = dict(primary_provider="codex", state_path=self.path, providers=self.providers,
                    probe_provider=lambda *_: (True, 200, "available"),
                    refresh_repository=self.refresh, reconcile_ownership=self.ownership,
                    authority_check=lambda *_: True, execute_provider=self.execute,
                    execute_local=self.local)
        args.update(override)
        return CourierScheduler(**args)

    def block(self, sched, reset=None):
        sched.record_provider_failure(self.cp, 429, "usage limit / quota exhausted", reset_time=reset)

    def past(self):
        return dt.datetime.now(dt.timezone.utc) - dt.timedelta(seconds=1)

    def saved(self):
        return json.loads(self.path.read_text())

    def test_quota_checkpoint_is_on_disk_before_resource_release(self):
        sched = self.scheduler()
        checked = []
        def release(_):
            cp = self.saved()["lane"]["checkpoint"]
            self.assertEqual(cp["workkey"], "same-work")
            self.assertEqual(cp["branch"], "codex/work")
            self.assertEqual(cp["dispatch_id"], "dispatch-3")
            self.assertEqual(cp["completed_fingerprints"], ["accepted-old"])
            checked.append(True)
        sched.lane.register_resource("codex-pty", "pty", release_hook=release)
        sched.record_provider_failure(self.cp, 429, "quota exhausted", retry_after=3600)
        self.assertEqual(checked, [True])
        self.assertEqual(sched.lane.state, LaneState.HIBERNATED)
        self.assertIsNotNone(sched.next_wake_at())
        self.assertEqual(self.saved()["lane"]["checkpoint"]["provider_failure_class"], "QUOTA_EXHAUSTED")

    def test_restart_restores_same_work_and_never_repeats_accepted_fingerprints(self):
        sched = self.scheduler()
        self.block(sched, self.past())
        already_done = self.task("old")
        already_done.fingerprint = "accepted-old"
        sched.handle_wake("reset", [already_done, self.task()])
        self.assertEqual(sched.provider_calls, [("codex", "RECOVERY_PROBE"), ("codex", "provider")])
        restored = self.scheduler()
        for _ in range(10):
            restored.handle_wake("duplicate", [])
        self.assertEqual(restored.provider_calls, [])
        cp = restored.lane.checkpoint
        self.assertEqual(cp.workkey, self.cp.workkey)
        self.assertEqual(cp.effect_key, "stable-effect")
        self.assertEqual(cp.attempt, 3)
        self.assertIn("accepted-old", cp.completed_fingerprints)
        self.assertIn("fp-provider", cp.completed_fingerprints)

    def test_reset_probe_once_and_repository_refreshed_before_mutation(self):
        def probe(*_):
            self.trace.append("probe")
            self.assertTrue(self.saved()["circuits"]["codex|completion"]["probe_in_flight"])
            return True, 200, "ok"
        sched = self.scheduler(probe_provider=probe)
        self.block(sched, self.past())
        for _ in range(20):
            sched.handle_wake("same", [self.task()])
        self.assertEqual(self.trace, ["probe", "fetch", "ownership", "execute:codex:provider"])
        self.assertEqual(sched.lane.checkpoint.next_action, "fresh action")
        self.assertEqual(sched.breaker.get_circuit("codex", "completion").state, ProviderState.AVAILABLE)

    def test_reentrant_wake_coalesces_under_existing_runtime_lock(self):
        sched = self.scheduler()
        second = self.scheduler()
        def probe(*_):
            self.assertEqual(second.handle_wake("parallel", [self.task()]), "COALESCED")
            return True, 200, "ok"
        sched.probe_provider = probe
        self.block(sched, self.past())
        sched.handle_wake("reset", [self.task()])
        self.assertEqual(second.provider_calls, [])

    def test_failed_probe_has_no_repeat_or_invented_reset_across_restart(self):
        sched = self.scheduler(probe_provider=lambda *_: (False, 429, "quota exhausted"))
        self.block(sched, self.past())
        sched.handle_wake("reset", [self.task()])
        self.assertEqual(sched.provider_calls, [("codex", "RECOVERY_PROBE")])
        restored = self.scheduler()
        for i in range(100):
            restored.handle_wake(str(i), [])
        self.assertEqual(restored.provider_calls, [])
        self.assertIsNone(restored.next_wake_at())
        self.assertEqual(restored.lane.state, LaneState.HIBERNATED)

    def test_unknown_probe_failure_is_not_treated_as_available(self):
        sched = self.scheduler(probe_provider=lambda *_: (False, 400, "unknown"))
        self.block(sched, self.past())
        sched.handle_wake("reset", [self.task()])
        self.assertEqual(sched.provider_calls, [("codex", "RECOVERY_PROBE")])
        self.assertNotIn("provider", sched.completed_tasks)

    def test_crash_during_probe_preserves_single_probe_claim(self):
        class Crash(BaseException):
            pass
        def crash(*_):
            raise Crash()
        sched = self.scheduler(probe_provider=crash)
        self.block(sched, self.past())
        with self.assertRaises(Crash):
            sched.handle_wake("reset", [self.task()])
        restored = self.scheduler()
        restored.handle_wake("after-crash", [])
        self.assertEqual(restored.provider_calls, [])
        self.assertTrue(restored.breaker.get_circuit("codex", "completion").probe_in_flight)

    def test_unknown_reset_stays_parked(self):
        sched = self.scheduler()
        self.block(sched)
        for _ in range(10):
            sched.handle_wake("no-new-availability", [self.task()])
        self.assertEqual(sched.provider_calls, [])
        self.assertIsNone(sched.next_wake_at())

    def test_other_writer_during_outage_prevents_resume(self):
        sched = self.scheduler(reconcile_ownership=lambda *_: None)
        self.block(sched, self.past())
        result = sched.handle_wake("reset", [self.task()])
        self.assertEqual(result, "WAITING_OWNERSHIP")
        self.assertEqual(sched.provider_calls, [("codex", "RECOVERY_PROBE")])
        self.assertEqual(self.trace, ["fetch"])

    def test_fresh_plan_can_remove_stale_next_unit(self):
        @contextmanager
        def changed(cp, truth):
            yield {"workkey": cp.workkey, "mutable_scope": cp.mutable_scope, "next_units": []}
        sched = self.scheduler(reconcile_ownership=changed)
        self.block(sched, self.past())
        sched.handle_wake("reset", [self.task()])
        self.assertNotIn("provider", sched.completed_tasks)
        self.assertEqual(sched.lane.checkpoint.next_units, [])
        self.assertEqual(sched.lane.checkpoint.next_action, "")

    def test_local_ready_continues_while_codex_unavailable(self):
        sched = self.scheduler()
        self.block(sched)
        sched.handle_wake("local", [self.task(), self.task("local", is_deterministic=True)])
        self.assertEqual(sched.provider_calls, [])
        self.assertEqual(sched.completed_tasks, ["local"])
        self.assertIn("local:local", self.trace)

    def test_authorized_compatible_fallback_only(self):
        for provider in [Provider("gemini", False, ["completion"], authority_scopes=("repo",)),
                         Provider("gemini", True, ["image"], authority_scopes=("repo",)),
                         Provider("gemini", True, ["completion"], authority_scopes=("elsewhere",))]:
            sched = self.scheduler(providers=self.providers + [provider])
            self.block(sched)
            sched.handle_wake("blocked", [self.task()])
            self.assertEqual(sched.provider_calls, [])
        sched = self.scheduler(providers=self.providers + [
            Provider("gemini", True, ["completion"], authority_scopes=("repo",))])
        sched.handle_wake("authorized", [])
        self.assertEqual(sched.provider_calls, [("gemini", "provider")])
        self.assertIn("provider", sched.completed_tasks)

    def test_fresh_authority_denial_blocks_even_connected_provider(self):
        sched = self.scheduler(authority_check=lambda *_: False)
        sched.handle_wake("normal", [self.task()], checkpoint=self.cp)
        self.assertEqual(sched.provider_calls, [])

    def test_no_codex_account_rotation_or_purchase_side_effect(self):
        sched = self.scheduler(providers=self.providers + [
            Provider("second-personal-account", True, ["completion"], family="codex", authority_scopes=("repo",))])
        self.block(sched)
        with patch("subprocess.Popen", side_effect=AssertionError("no external processes")):
            sched.handle_wake("blocked", [self.task()])
        self.assertEqual(sched.provider_calls, [])
        self.assertEqual(self.trace, [])
        self.assertEqual(len(sched.providers), 2)  # no account discovery/addition

    def test_effect_uncertain_never_redispatches_even_local_or_available(self):
        sched = self.scheduler()
        tasks = [self.task(effect_uncertain=True), self.task("local", is_deterministic=True, effect_uncertain=True)]
        sched.handle_wake("normal", tasks, checkpoint=self.cp)
        self.assertEqual(sched.completed_tasks, [])
        self.assertEqual(self.trace, [])

    def test_execution_crash_is_parked_not_replayed_after_restart(self):
        def crash(*_):
            raise RuntimeError("transport lost after execution")
        sched = self.scheduler(execute_provider=crash)
        with self.assertRaises(RuntimeError):
            sched.handle_wake("first", [self.task()], checkpoint=self.cp)
        restored = self.scheduler()
        self.assertEqual(restored.handle_wake("resume", []), "EFFECT_UNKNOWN")
        self.assertEqual(restored.provider_calls, [])

    def test_quota_response_preserves_work_and_hibernates(self):
        sched = self.scheduler(execute_provider=lambda *_: {
            "status": "QUOTA_EXHAUSTED", "no_effect": True,
            "reset_time": dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=5)})
        sched.handle_wake("first", [self.task(), self.task("second")], checkpoint=self.cp)
        self.assertEqual(sched.provider_calls, [("codex", "provider")])
        self.assertEqual(sched.started, [])
        self.assertEqual(sched.completed_tasks, [])
        self.assertEqual(sched.lane.state, LaneState.HIBERNATED)
        self.assertIsNotNone(sched.next_wake_at())

    def test_missing_connector_or_truth_never_fakes_completion(self):
        sched = self.scheduler(execute_provider=None)
        sched.handle_wake("no-connector", [self.task()], checkpoint=self.cp)
        self.assertEqual(sched.completed_tasks, [])
        sched = self.scheduler(refresh_repository=None)
        self.assertEqual(sched.handle_wake("no-fetch", []), "WAITING_RECONCILIATION")
        self.assertEqual(sched.provider_calls, [])

    def test_checkpoint_write_failure_prevents_release_and_provider_calls(self):
        sched = self.scheduler()
        released = []
        sched.lane.register_resource("pty", "pty", release_hook=released.append)
        with patch("scripts.provider_survival.save_continuation", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                self.block(sched)
        self.assertEqual(released, [])
        self.assertEqual(sched.provider_calls, [])

    def test_resource_release_failure_not_reported_as_success(self):
        sched = self.scheduler()
        def fail(_):
            raise RuntimeError("ownership could not be established")
        sched.lane.register_resource("pty", "pty", release_hook=fail)
        self.block(sched)
        self.assertFalse(sched.lane.resources["pty"].released)
        self.assertEqual(sched.stop_reason, "RESOURCE_RELEASE_FAILED")

    def test_corrupt_checkpoint_fails_closed(self):
        self.path.write_text("not-json")
        sched = self.scheduler()
        with self.assertRaises(ValueError):
            sched.handle_wake("restart", [self.task()])
        self.assertEqual(sched.provider_calls, [])

    def test_codex_never_implicitly_authorized_and_requires_persistence(self):
        with self.assertRaises(ValueError):
            CourierScheduler(primary_provider="codex")
        sched = CourierScheduler(primary_provider="codex", state_path=self.path)
        self.assertFalse(next(p for p in sched.providers if p.id == "codex").is_authorized)

    def test_changed_checkpoint_is_not_silently_discarded(self):
        sched = self.scheduler()
        self.block(sched)
        latest = ContinuationCheckpoint.from_dict(self.saved()["lane"]["checkpoint"])
        latest.repo_sha = "c" * 40
        latest.next_action = "new accepted boundary"
        before = self.path.read_bytes()
        with self.assertRaisesRegex(ValueError, "expected_checkpoint"):
            sched.record_provider_failure(latest, 429, "quota exhausted")
        self.assertEqual(self.path.read_bytes(), before)

    def test_checkpoint_update_persists_latest_progress_without_losing_evidence(self):
        sched = self.scheduler()
        self.block(sched)
        expected = self.saved()["lane"]["checkpoint"]
        latest = ContinuationCheckpoint.from_dict(expected)
        latest.repo_sha = "c" * 40
        latest.pr = "456"
        latest.next_action = "continue after new accepted unit"
        latest.completed_fingerprints = ["new-accepted"]
        latest.source_refs = ["evidence:new"]
        sched.record_provider_failure(latest, 429, "quota exhausted", expected_checkpoint=expected)
        saved = self.saved()["lane"]["checkpoint"]
        self.assertEqual(saved["repo_sha"], "c" * 40)
        self.assertEqual(saved["pr"], "456")
        self.assertEqual(saved["next_action"], latest.next_action)
        self.assertEqual(saved["completed_fingerprints"], ["accepted-old", "new-accepted"])
        self.assertEqual(saved["source_refs"], ["evidence:old", "evidence:new"])
        self.assertEqual(saved["workkey"], "same-work")

    def test_delayed_checkpoint_update_cannot_overwrite_newer_progress(self):
        sched = self.scheduler()
        self.block(sched)
        old = self.saved()["lane"]["checkpoint"]
        newer = ContinuationCheckpoint.from_dict(old)
        newer.next_action = "new current action"
        sched.record_provider_failure(newer, 429, "quota exhausted", expected_checkpoint=old)
        before = self.path.read_bytes()
        delayed = ContinuationCheckpoint.from_dict(old)
        delayed.next_action = "stale action"
        with self.assertRaisesRegex(ValueError, "stale"):
            self.scheduler().record_provider_failure(delayed, 429, "quota exhausted", expected_checkpoint=old)
        self.assertEqual(self.path.read_bytes(), before)

    def test_checkpoint_update_cannot_retarget_scope_or_connection(self):
        sched = self.scheduler()
        self.block(sched)
        expected = self.saved()["lane"]["checkpoint"]
        before = self.path.read_bytes()
        for key in ("mutable_scope", "provider_connection_id", "project"):
            latest = ContinuationCheckpoint.from_dict(expected)
            setattr(latest, key, "different-owner")
            with self.subTest(field=key), self.assertRaises(ValueError):
                sched.record_provider_failure(latest, 429, "quota exhausted", expected_checkpoint=expected)
            self.assertEqual(self.path.read_bytes(), before)


    def test_durable_wake_updates_open_units_lists(self):
        sched = self.scheduler()
        self.block(sched, self.past())
        
        # Verify initial
        cp = self.saved()["lane"]["checkpoint"]
        self.assertEqual(cp["open_provider_units"], ["provider"])
        
        # Wake up and complete the provider task
        sched.handle_wake("normal", [self.task()])
        
        # Assert it's removed from open_provider_units
        cp_after = self.saved()["lane"]["checkpoint"]
        self.assertNotIn("provider", cp_after["open_provider_units"])
        self.assertIn("fp-provider", cp_after["completed_fingerprints"])

if __name__ == "__main__":
    unittest.main()
