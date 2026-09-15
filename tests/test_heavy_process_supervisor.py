import multiprocessing
import os
import signal
import sqlite3
import subprocess
import sys
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from heavy_process_supervisor import (
    HeavyProcessBusy,
    HeavyProcessError,
    HeavyProcessIdentityError,
    HeavyProcessSupervisor,
)


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
        self.assertEqual(self.rows()[0][4], "STALE_OWNER_RECOVERED")

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
        result = self.supervisor().run("retry", [sys.executable, "-c", "raise SystemExit(3)"], timeout_seconds=1, max_attempts=2, wall_clock_budget_seconds=2)
        self.assertEqual(result.attempt, 2)
        self.assertEqual(len(self.rows()), 2)
        with self.assertRaises(HeavyProcessError):
            self.supervisor().run("wall", [sys.executable, "-c", "import time; time.sleep(1)"], timeout_seconds=1, max_attempts=2, wall_clock_budget_seconds=0.1)


if __name__ == "__main__":
    unittest.main()
