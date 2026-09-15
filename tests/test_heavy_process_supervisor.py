import multiprocessing
import os
import signal
import sqlite3
import subprocess
import sys
import time
import unittest
import uuid
from pathlib import Path
from tempfile import TemporaryDirectory

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from heavy_process_supervisor import (
    AgentDrainBarrier,
    AgentDrainBlocked,
    HeavyProcessBusy,
    HeavyProcessError,
    HeavyProcessIdentityError,
    HeavyProcessSupervisor,
)
import check_process_safety_bypass
import run_autonomous_supervisor
import run_chief_relay_cycle


def hold_lock(runtime_dir: str, ready: multiprocessing.Queue) -> None:
    with HeavyProcessSupervisor(Path(runtime_dir), owner_id="holder").ownership():
        ready.put("locked")
        time.sleep(3)


class HeavyProcessSupervisorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = TemporaryDirectory()
        self.runtime = Path(self.tmp.name) / "guard"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def supervisor(self, **kwargs: object) -> HeavyProcessSupervisor:
        return HeavyProcessSupervisor(self.runtime, poll_interval_seconds=0.02, term_grace_seconds=0.15, kill_grace_seconds=0.5, **kwargs)

    def rows(self) -> list[tuple]:
        with sqlite3.connect(self.runtime / "heavy_jobs.sqlite3") as conn:
            return conn.execute("SELECT job_id, owner_id, pid, pgid, state, metadata_json, cleanup_result FROM heavy_jobs ORDER BY attempt").fetchall()

    def test_cross_process_lock_rejects_second_owner_before_spawn(self) -> None:
        ready: multiprocessing.Queue = multiprocessing.Queue()
        holder = multiprocessing.Process(target=hold_lock, args=(str(self.runtime), ready))
        holder.start()
        self.assertEqual(ready.get(timeout=2), "locked")
        with self.assertRaises(HeavyProcessBusy):
            self.supervisor().run("same-job", [sys.executable, "-c", "raise SystemExit(0)"], timeout_seconds=1)
        holder.terminate()
        holder.join(timeout=2)
        self.assertFalse(holder.is_alive())

    def test_normal_completion_and_metadata_propagation(self) -> None:
        result = self.supervisor(owner_id="relay-1").run(
            "job-a", [sys.executable, "-c", "print('done')"], timeout_seconds=1, metadata={"relay_stage": "consume", "task_id": "a"},
        )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "done")
        row = self.rows()[0]
        self.assertEqual(row[1], "relay-1")
        self.assertEqual(row[4], "COMPLETED")
        self.assertIn('"relay_stage": "consume"', row[5])

    def test_hard_timeout_terms_owned_group(self) -> None:
        result = self.supervisor().run("timeout", [sys.executable, "-c", "import time; time.sleep(10)"], timeout_seconds=0.1)
        self.assertTrue(result.timed_out)
        self.assertEqual(result.state, "TIMED_OUT")
        self.assertIn(self.rows()[0][6], ("TERM_CLEAN", "KILL_CLEAN"))

    def test_forced_kill_after_term_ignoring_process(self) -> None:
        result = self.supervisor().run(
            "kill", [sys.executable, "-c", "import signal,time; signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(10)"],
            timeout_seconds=0.1,
        )
        self.assertTrue(result.timed_out)
        self.assertEqual(self.rows()[0][6], "KILL_CLEAN")

    def test_parent_and_child_group_are_cleaned(self) -> None:
        marker = Path(self.tmp.name) / "child.pid"
        code = (
            "import pathlib,subprocess,sys,time; "
            f"p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(10)']); pathlib.Path({str(marker)!r}).write_text(str(p.pid)); "
            "time.sleep(10)"
        )
        self.supervisor().run("tree", [sys.executable, "-c", code], timeout_seconds=0.15)
        child_pid = int(marker.read_text())
        time.sleep(0.1)
        live_pids = {line.strip() for line in subprocess.run(["ps", "-axo", "pid="], capture_output=True, text=True, check=True).stdout.splitlines()}
        self.assertNotIn(str(child_pid), live_pids)
        self.assertIn(self.rows()[0][6], ("TERM_CLEAN", "KILL_CLEAN"))

    def test_foreign_process_survives_owned_cleanup(self) -> None:
        foreign = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(5)"])
        try:
            self.supervisor().run("owned", [sys.executable, "-c", "import time; time.sleep(10)"], timeout_seconds=0.1)
            self.assertIsNone(foreign.poll())
        finally:
            foreign.terminate()
            foreign.wait(timeout=2)

    def test_spawn_failure_is_terminal_and_releases_lock(self) -> None:
        with self.assertRaises(HeavyProcessError):
            self.supervisor().run("bad-spawn", ["/definitely/not/a/courier-command"], timeout_seconds=1)
        self.assertEqual(self.rows()[0][4], "SPAWN_FAILED")
        self.assertEqual(self.supervisor().run("after-spawn-failure", [sys.executable, "-c", ""], timeout_seconds=1).returncode, 0)

    def test_stale_sqlite_record_is_recovered_when_group_is_gone(self) -> None:
        self.supervisor().run("old", [sys.executable, "-c", ""], timeout_seconds=1)
        with sqlite3.connect(self.runtime / "heavy_jobs.sqlite3") as conn:
            conn.execute("UPDATE heavy_jobs SET state = 'RUNNING' WHERE job_id = 'old'")
        self.assertEqual(self.supervisor().run("new", [sys.executable, "-c", ""], timeout_seconds=1).returncode, 0)
        self.assertEqual(self.rows()[0][4], "STALE_PROVEN_DEAD_OWNER")

    def test_running_record_without_pid_or_pgid_fails_closed_before_successor_executes(self) -> None:
        with self.supervisor().ownership() as supervisor:
            supervisor._claim("unknown", 1, ["expected"], {}, time.time() + 1)
            supervisor._transition("unknown", 1, "RUNNING")
        marker = Path(self.tmp.name) / "successor-executed"
        with self.assertRaisesRegex(HeavyProcessIdentityError, "AMBIGUOUS_OWNER"):
            self.supervisor().run("successor", [sys.executable, "-c", f"open({str(marker)!r}, 'w').close()"], timeout_seconds=1)
        self.assertFalse(marker.exists())
        self.assertEqual(self.rows()[0][4], "AMBIGUOUS_OWNER")

    def test_malformed_running_identity_fails_closed_before_successor_executes(self) -> None:
        with self.supervisor().ownership() as supervisor:
            supervisor._claim("malformed", 1, ["expected"], {}, time.time() + 1)
            supervisor._transition("malformed", 1, "RUNNING", pid=0, pgid=-1, observed_fingerprint="", process_start="")
        marker = Path(self.tmp.name) / "successor-executed"
        with self.assertRaisesRegex(HeavyProcessIdentityError, "AMBIGUOUS_OWNER"):
            self.supervisor().run("successor", [sys.executable, "-c", f"open({str(marker)!r}, 'w').close()"], timeout_seconds=1)
        self.assertFalse(marker.exists())
        self.assertEqual(self.rows()[0][4], "AMBIGUOUS_OWNER")

    def test_valid_live_owner_is_protected_before_successor_executes(self) -> None:
        owner = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(5)"], start_new_session=True)
        try:
            with self.supervisor().ownership() as supervisor:
                supervisor._claim("live", 1, ["expected"], {}, time.time() + 1)
                row = next(row for row in __import__("heavy_process_supervisor")._ps_rows() if row[0] == owner.pid)
                supervisor._transition("live", 1, "RUNNING", pid=owner.pid, pgid=os.getpgid(owner.pid), observed_fingerprint=__import__("heavy_process_supervisor")._fingerprint([row[3]]), process_start=row[2])
            marker = Path(self.tmp.name) / "successor-executed"
            with self.assertRaisesRegex(HeavyProcessBusy, "LIVE_VALID_OWNER"):
                self.supervisor().run("successor", [sys.executable, "-c", f"open({str(marker)!r}, 'w').close()"], timeout_seconds=1)
            self.assertIsNone(owner.poll())
            self.assertFalse(marker.exists())
            self.assertEqual(self.rows()[0][4], "LIVE_VALID_OWNER")
        finally:
            os.killpg(os.getpgid(owner.pid), signal.SIGTERM)
            owner.wait(timeout=2)

    def test_identity_mismatch_fails_closed_without_killing_foreign_process(self) -> None:
        foreign = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(5)"], start_new_session=True)
        try:
            with self.supervisor().ownership() as supervisor:
                supervisor._claim("unsafe", 1, ["expected"], {}, time.time() + 1)
                row = next(row for row in __import__("heavy_process_supervisor")._ps_rows() if row[0] == foreign.pid)
                supervisor._transition("unsafe", 1, "RUNNING", pid=foreign.pid, pgid=os.getpgid(foreign.pid), observed_fingerprint="not-the-process", process_start=row[2])
            with self.assertRaises(HeavyProcessIdentityError):
                self.supervisor().run("next", [sys.executable, "-c", ""], timeout_seconds=1)
            self.assertIsNone(foreign.poll())
        finally:
            os.killpg(os.getpgid(foreign.pid), signal.SIGTERM)
            foreign.wait(timeout=2)

    def test_retry_and_wall_clock_budgets_are_bounded(self) -> None:
        result = self.supervisor().run("retry", [sys.executable, "-c", "raise SystemExit(3)"], timeout_seconds=1, max_attempts=2, wall_clock_budget_seconds=11)
        self.assertEqual(result.attempt, 2)
        self.assertEqual(len(self.rows()), 2)
        with self.assertRaises(HeavyProcessError):
            self.supervisor().run("wall", [sys.executable, "-c", "import time; time.sleep(1)"], timeout_seconds=1, max_attempts=2, wall_clock_budget_seconds=0.1)

    def test_wall_clock_budget_reserves_and_contains_term_cleanup(self) -> None:
        total_budget = 5.0
        tolerance = 0.15
        marker = Path(self.tmp.name) / "term-started"
        supervisor = HeavyProcessSupervisor(
            self.runtime, poll_interval_seconds=0.01, term_grace_seconds=0.1, kill_grace_seconds=0.1,
        )
        code = (
            "import pathlib,signal,time; "
            f"signal.signal(signal.SIGTERM, lambda *_: (pathlib.Path({str(marker)!r}).write_text(str(time.monotonic())), exit())); time.sleep(10)"
        )
        started = time.monotonic()
        result = supervisor.run("term-budget", [sys.executable, "-c", code], timeout_seconds=1, wall_clock_budget_seconds=total_budget)
        duration = time.monotonic() - started
        self.assertTrue(result.timed_out)
        self.assertTrue(marker.exists())
        self.assertLess(float(marker.read_text()), started + total_budget)
        self.assertLess(duration, total_budget + tolerance)
        self.assertEqual(self.rows()[0][6], "TERM_CLEAN")

    def test_wall_clock_budget_allows_normal_process_within_total(self) -> None:
        total_budget = 5.0
        tolerance = 0.15
        supervisor = HeavyProcessSupervisor(
            self.runtime, poll_interval_seconds=0.01, term_grace_seconds=0.1, kill_grace_seconds=0.1,
        )
        started = time.monotonic()
        result = supervisor.run(
            "normal-budget", [sys.executable, "-c", "import time; time.sleep(0.05)"],
            timeout_seconds=1, wall_clock_budget_seconds=total_budget,
        )
        self.assertEqual(result.returncode, 0)
        self.assertLess(time.monotonic() - started, total_budget + tolerance)

    def test_wall_clock_budget_contains_forced_kill_and_descendant_cleanup(self) -> None:
        total_budget = 5.0
        tolerance = 0.15
        supervisor = HeavyProcessSupervisor(
            self.runtime, poll_interval_seconds=0.01, term_grace_seconds=0.1, kill_grace_seconds=0.1,
        )
        started = time.monotonic()
        result = supervisor.run(
            "kill-budget",
            [sys.executable, "-c", "import signal,time; signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(10)"],
            timeout_seconds=1, wall_clock_budget_seconds=total_budget,
        )
        duration = time.monotonic() - started
        self.assertTrue(result.timed_out)
        self.assertLess(duration, total_budget + tolerance)
        self.assertEqual(self.rows()[0][6], "KILL_CLEAN")

    def test_impossibly_small_total_budget_rejects_before_spawn(self) -> None:
        marker = Path(self.tmp.name) / "process-started"
        with self.assertRaisesRegex(HeavyProcessError, "PROCESS_STARTED=NO"):
            self.supervisor().run(
                "too-small",
                [sys.executable, "-c", f"open({str(marker)!r}, 'w').close()"],
                timeout_seconds=1, wall_clock_budget_seconds=0.1,
            )
        self.assertFalse(marker.exists())
        self.assertFalse((self.runtime / "heavy_jobs.sqlite3").exists())

    def test_idle_timeout_uses_selected_output_activity(self) -> None:
        result = self.supervisor().run(
            "idle", [sys.executable, "-c", "import time; time.sleep(10)"], timeout_seconds=2,
            idle_timeout_seconds=0.1, liveness_source="OUTPUT_ACTIVITY",
        )
        self.assertEqual(result.state, "IDLE_TIMED_OUT")

    def test_progress_liveness_callback_prevents_idle_timeout(self) -> None:
        pulses = iter([True] * 20)
        result = self.supervisor().run(
            "progress", [sys.executable, "-c", "import time; time.sleep(.15)"], timeout_seconds=1,
            idle_timeout_seconds=0.05, liveness_source="PROGRESS_EVENT",
            liveness_callback=lambda: next(pulses, True),
        )
        self.assertEqual(result.returncode, 0)

    def test_drain_barrier_blocks_only_unresolved_owned_attempt(self) -> None:
        with self.supervisor().ownership() as supervisor:
            supervisor._claim("drain", 1, ["expected"], {}, time.time() + 1)
        barrier = AgentDrainBarrier(self.runtime)
        with self.assertRaisesRegex(AgentDrainBlocked, "UNRESOLVED_OWNED_WORK"):
            barrier.require_drained("drain", 1)
        barrier.require_drained("unowned", 1)

    def test_static_bypass_guard_rejects_forbidden_fixture(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            scripts = root / "scripts"
            scripts.mkdir()
            (scripts / "unsafe.py").write_text("import subprocess\nsubprocess.Popen(['x'])\n")
            self.assertEqual(
                check_process_safety_bypass.violations(root),
                ["scripts/unsafe.py:2:subprocess.Popen"],
            )
        self.assertEqual(check_process_safety_bypass.violations(Path(__file__).resolve().parents[1]), [])

    def test_relay_wrapper_uses_supervisor_and_propagates_metadata(self) -> None:
        task_id = f"relay-task-{uuid.uuid4().hex}"
        result = run_chief_relay_cycle.run_relay_subprocess(
            Path(__file__).resolve().parents[1], task_id, "relay-test",
            [sys.executable, "-c", "print('relay')"], owner_id="night-owner",
        )
        self.assertEqual(result.stdout.strip(), "relay")
        with sqlite3.connect(Path(__file__).resolve().parents[1] / "runtime/resource_guard/heavy_jobs.sqlite3") as conn:
            metadata = conn.execute("SELECT metadata_json FROM heavy_jobs WHERE job_id = ?", (f"{task_id}:relay-test",)).fetchone()[0]
        self.assertIn('"relay_stage": "relay-test"', metadata)

    def test_night_supervisor_propagates_session_owner_to_relay(self) -> None:
        queue_dir = Path(self.tmp.name) / "queue"
        task_id = f"night-test-{uuid.uuid4().hex}"
        task = {
            "schema_version": "2.0", "task_id": task_id, "priority": 1, "instruction": "Run test",
            "project": "2026-courier", "status": "QUEUED", "created_at": "2026-01-01T00:00:00Z",
            "attempt_count": 0, "max_attempts": 1, "requires_human": False,
        }
        queue_dir.mkdir()
        (queue_dir / f"{task_id}.json").write_text(__import__("json").dumps(task))
        report = run_autonomous_supervisor.run_supervisor_session(
            repo_dir=Path(__file__).resolve().parents[1], queue_dir=queue_dir,
            reports_dir=Path(self.tmp.name) / "reports", events_dir=Path(self.tmp.name) / "events",
            memory_repo=Path(self.tmp.name) / "missing-memory", max_tasks=1,
        )
        self.assertEqual(report["tasks_completed"], 1)
        with sqlite3.connect(Path(__file__).resolve().parents[1] / "runtime/resource_guard/heavy_jobs.sqlite3") as conn:
            owner_id = conn.execute("SELECT owner_id FROM heavy_jobs WHERE job_id = ?", (f"{task_id}:build-worker-job",)).fetchone()[0]
        self.assertEqual(owner_id, report["session_id"])


if __name__ == "__main__":
    unittest.main()
