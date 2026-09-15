"""POSIX heavy subprocess ownership with cross-process exclusion and cleanup."""

from __future__ import annotations

import contextlib
import datetime as dt
import fcntl
import hashlib
import json
import os
import signal
import sqlite3
import subprocess
import tempfile
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


ACTIVE_STATES = (
    "CLAIMED",
    "RUNNING",
    "TERM_SENT",
    "KILL_SENT",
    "LIVE_VALID_OWNER",
    "AMBIGUOUS_OWNER",
    "PID_IDENTITY_MISMATCH",
)


class HeavyProcessError(RuntimeError):
    """Base error for a supervisor refusal or execution failure."""


class HeavyProcessBusy(HeavyProcessError):
    """A Courier process already owns the global heavy-process lock."""


class HeavyProcessIdentityError(HeavyProcessError):
    """Recorded process identity cannot be proven safe to operate on."""


@dataclass(frozen=True)
class HeavyProcessResult:
    returncode: int
    stdout: str
    stderr: str
    timed_out: bool
    attempt: int
    state: str


class WindowsHeavyProcessAdapter:
    """Future platform boundary; Windows Job Object ownership is intentionally absent."""

    def run(self, *args: object, **kwargs: object) -> HeavyProcessResult:
        raise NotImplementedError("Windows Job Object supervision is not implemented")


def _utcnow() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def _fingerprint(parts: Sequence[str]) -> str:
    return hashlib.sha256("\0".join(parts).encode("utf-8")).hexdigest()


def _ps_rows() -> list[tuple[int, int, str, str]]:
    result = subprocess.run(
        ["ps", "-axo", "pid=,pgid=,lstart=,command="],
        check=False,
        capture_output=True,
        text=True,
        timeout=2,
    )
    rows: list[tuple[int, int, str, str]] = []
    for line in result.stdout.splitlines():
        fields = line.strip().split(None, 7)
        if len(fields) != 8 or not fields[0].isdigit() or not fields[1].isdigit():
            continue
        rows.append((int(fields[0]), int(fields[1]), " ".join(fields[2:7]), fields[7]))
    return rows


class _BoundedCapture:
    def __init__(self, stream: object, limit: int) -> None:
        self._stream = stream
        self._limit = limit
        self._data = bytearray()
        self.truncated = False
        self._thread = threading.Thread(target=self._read, daemon=True)

    def start(self) -> None:
        self._thread.start()

    def join(self) -> bytes:
        self._thread.join(timeout=2)
        return bytes(self._data)

    def _read(self) -> None:
        assert hasattr(self._stream, "read")
        while True:
            chunk = self._stream.read(65536)  # type: ignore[union-attr]
            if not chunk:
                return
            remaining = self._limit - len(self._data)
            if remaining > 0:
                self._data.extend(chunk[:remaining])
            if len(chunk) > remaining:
                self.truncated = True


class HeavyProcessSupervisor:
    """Owns exactly one POSIX process group while holding a durable Courier lock."""

    def __init__(
        self,
        runtime_dir: Path,
        owner_id: str | None = None,
        *,
        output_limit_bytes: int = 1_048_576,
        poll_interval_seconds: float = 0.05,
        term_grace_seconds: float = 1.0,
        kill_grace_seconds: float = 1.0,
    ) -> None:
        if os.name == "nt":
            raise NotImplementedError("Windows Job Object supervision is not implemented")
        self.runtime_dir = runtime_dir
        self.owner_id = owner_id or f"courier-{uuid.uuid4()}"
        self.output_limit_bytes = output_limit_bytes
        self.poll_interval_seconds = poll_interval_seconds
        self.term_grace_seconds = term_grace_seconds
        self.kill_grace_seconds = kill_grace_seconds
        self._lock_file: object | None = None
        self._conn: sqlite3.Connection | None = None

    @property
    def ledger_path(self) -> Path:
        return self.runtime_dir / "heavy_jobs.sqlite3"

    def _open(self) -> None:
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        lock_path = self.runtime_dir / "heavy.lock"
        self._lock_file = lock_path.open("a+")
        try:
            fcntl.flock(self._lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            self._lock_file.close()
            self._lock_file = None
            raise HeavyProcessBusy("RESOURCE_GUARD_BUSY") from exc
        self._conn = sqlite3.connect(self.ledger_path, timeout=2, isolation_level=None)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute(
            """CREATE TABLE IF NOT EXISTS heavy_jobs (
                job_id TEXT NOT NULL, attempt INTEGER NOT NULL, owner_id TEXT NOT NULL,
                pid INTEGER, pgid INTEGER, command_fingerprint TEXT NOT NULL,
                observed_fingerprint TEXT, process_start TEXT, started_at TEXT NOT NULL,
                heartbeat TEXT NOT NULL, state TEXT NOT NULL, metadata_json TEXT NOT NULL,
                deadline_at TEXT, term_at TEXT, kill_at TEXT, finished_at TEXT,
                exit_code INTEGER, cleanup_result TEXT, error TEXT,
                PRIMARY KEY (job_id, attempt)
            )"""
        )
        self._reconcile_stale()

    def _close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None
        if self._lock_file is not None:
            fcntl.flock(self._lock_file.fileno(), fcntl.LOCK_UN)
            self._lock_file.close()
            self._lock_file = None

    @contextlib.contextmanager
    def ownership(self) -> object:
        try:
            self._open()
        except Exception:
            self._close()
            raise
        try:
            yield self
        finally:
            self._close()

    def _reconcile_stale(self) -> None:
        assert self._conn is not None
        rows = self._conn.execute(
            f"SELECT job_id, attempt, pid, pgid, observed_fingerprint, process_start FROM heavy_jobs "
            f"WHERE state IN ({','.join('?' for _ in ACTIVE_STATES)})",
            ACTIVE_STATES,
        ).fetchall()
        for job_id, attempt, pid, pgid, fingerprint, start in rows:
            if not (
                isinstance(pid, int) and pid > 0
                and isinstance(pgid, int) and pgid > 0
                and isinstance(fingerprint, str) and fingerprint
                and isinstance(start, str) and start
            ):
                self._transition(job_id, attempt, "AMBIGUOUS_OWNER", cleanup_result="MISSING_OR_MALFORMED_IDENTITY")
                raise HeavyProcessIdentityError(f"AMBIGUOUS_OWNER:{job_id}")
            group = [row for row in _ps_rows() if row[1] == pgid]
            if not group:
                self._transition(job_id, attempt, "STALE_PROVEN_DEAD_OWNER", cleanup_result="GROUP_GONE")
                continue
            exact = next((row for row in group if row[0] == pid), None)
            if exact and exact[2] == start and _fingerprint([exact[3]]) == fingerprint:
                self._transition(job_id, attempt, "LIVE_VALID_OWNER", cleanup_result="LIVE_VALID_OWNER")
                raise HeavyProcessBusy(f"LIVE_VALID_OWNER:{job_id}")
            self._transition(job_id, attempt, "PID_IDENTITY_MISMATCH", cleanup_result="PID_IDENTITY_MISMATCH")
            raise HeavyProcessIdentityError(f"PID_IDENTITY_MISMATCH:{job_id}")

    def _transition(self, job_id: str, attempt: int, state: str, **updates: object) -> None:
        assert self._conn is not None
        columns = ["state = ?", "heartbeat = ?"]
        values: list[object] = [state, _utcnow()]
        for key, value in updates.items():
            columns.append(f"{key} = ?")
            values.append(value)
        values.extend([job_id, attempt])
        self._conn.execute("BEGIN IMMEDIATE")
        try:
            self._conn.execute(
                f"UPDATE heavy_jobs SET {', '.join(columns)} WHERE job_id = ? AND attempt = ?",
                values,
            )
            self._conn.execute("COMMIT")
        except Exception:
            self._conn.execute("ROLLBACK")
            raise

    def _claim(self, job_id: str, attempt: int, command: Sequence[str], metadata: dict[str, object], deadline: float) -> None:
        assert self._conn is not None
        now = _utcnow()
        self._conn.execute("BEGIN IMMEDIATE")
        try:
            self._conn.execute(
                """INSERT INTO heavy_jobs
                (job_id, attempt, owner_id, command_fingerprint, started_at, heartbeat, state, metadata_json, deadline_at)
                VALUES (?, ?, ?, ?, ?, ?, 'CLAIMED', ?, ?)""",
                (
                    job_id, attempt, self.owner_id, _fingerprint(command), now, now,
                    json.dumps(metadata, sort_keys=True),
                    dt.datetime.fromtimestamp(deadline, dt.timezone.utc).isoformat(),
                ),
            )
            self._conn.execute("COMMIT")
        except Exception:
            self._conn.execute("ROLLBACK")
            raise

    def _identity_is_valid(self, pid: int, pgid: int, observed_fingerprint: str, process_start: str) -> bool:
        for row_pid, row_pgid, row_start, command in _ps_rows():
            if row_pid == pid:
                return row_pgid == pgid and row_start == process_start and _fingerprint([command]) == observed_fingerprint
        return False

    def _group_exists(self, pgid: int) -> bool:
        result = subprocess.run(
            ["ps", "-axo", "pgid=,stat="],
            check=False,
            capture_output=True,
            text=True,
            timeout=2,
        )
        return any(
            parts[0] == str(pgid) and not parts[1].startswith("Z")
            for line in result.stdout.splitlines()
            if len(parts := line.split()) == 2
        )

    def _cleanup(self, job_id: str, attempt: int, pid: int, pgid: int, observed_fingerprint: str, process_start: str) -> str:
        if not self._group_exists(pgid):
            return "CLEAN"
        if not self._identity_is_valid(pid, pgid, observed_fingerprint, process_start):
            self._transition(job_id, attempt, "IDENTITY_MISMATCH", cleanup_result="FAIL_CLOSED")
            raise HeavyProcessIdentityError("PID/PGID/command/start identity cannot be proven")
        os.killpg(pgid, signal.SIGTERM)
        self._transition(job_id, attempt, "TERM_SENT", term_at=_utcnow())
        if self._wait_for_group_exit(pgid, self.term_grace_seconds):
            return "TERM_CLEAN"
        os.killpg(pgid, signal.SIGKILL)
        self._transition(job_id, attempt, "KILL_SENT", kill_at=_utcnow())
        return "KILL_CLEAN" if self._wait_for_group_exit(pgid, self.kill_grace_seconds) else "ORPHANS_REMAIN"

    def _wait_for_group_exit(self, pgid: int, grace: float) -> bool:
        deadline = time.monotonic() + grace
        while time.monotonic() < deadline:
            if not self._group_exists(pgid):
                return True
            time.sleep(self.poll_interval_seconds)
        return not self._group_exists(pgid)

    def run(
        self,
        job_id: str,
        command: Sequence[str],
        *,
        timeout_seconds: float,
        metadata: dict[str, object] | None = None,
        max_attempts: int = 1,
        wall_clock_budget_seconds: float | None = None,
    ) -> HeavyProcessResult:
        if timeout_seconds <= 0 or max_attempts <= 0:
            raise ValueError("timeout_seconds and max_attempts must be positive")
        started = time.monotonic()
        budget = wall_clock_budget_seconds if wall_clock_budget_seconds is not None else timeout_seconds * max_attempts
        if budget <= 0:
            raise ValueError("wall_clock_budget_seconds must be positive")
        with self.ownership():
            for attempt in range(1, max_attempts + 1):
                remaining = budget - (time.monotonic() - started)
                if remaining <= 0:
                    raise HeavyProcessError("WALL_CLOCK_BUDGET_EXHAUSTED")
                result = self._run_once(job_id, command, min(timeout_seconds, remaining), metadata or {}, attempt)
                if result.returncode == 0 or attempt == max_attempts:
                    return result
            raise AssertionError("unreachable")

    def _run_once(self, job_id: str, command: Sequence[str], timeout: float, metadata: dict[str, object], attempt: int) -> HeavyProcessResult:
        deadline = time.time() + timeout
        self._claim(job_id, attempt, command, metadata, deadline)
        try:
            proc = subprocess.Popen(
                list(command), stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                start_new_session=True,
            )
        except OSError as exc:
            self._transition(job_id, attempt, "SPAWN_FAILED", finished_at=_utcnow(), error=str(exc))
            raise HeavyProcessError(f"SPAWN_FAILED:{exc}") from exc
        assert proc.stdout is not None and proc.stderr is not None
        stdout, stderr = _BoundedCapture(proc.stdout, self.output_limit_bytes), _BoundedCapture(proc.stderr, self.output_limit_bytes)
        stdout.start()
        stderr.start()
        pid, pgid = proc.pid, os.getpgid(proc.pid)
        row = next((row for row in _ps_rows() if row[0] == pid), None)
        if row is None:
            proc.wait(timeout=1)
            self._transition(job_id, attempt, "SPAWN_FAILED", finished_at=_utcnow(), error="process vanished before identity capture")
            raise HeavyProcessError("SPAWN_FAILED:identity capture")
        observed_fingerprint = _fingerprint([row[3]])
        self._transition(job_id, attempt, "RUNNING", pid=pid, pgid=pgid, observed_fingerprint=observed_fingerprint, process_start=row[2])
        timed_out = False
        while proc.poll() is None and time.time() < deadline:
            self._transition(job_id, attempt, "RUNNING")
            time.sleep(self.poll_interval_seconds)
        if proc.poll() is None:
            timed_out = True
            self._transition(job_id, attempt, "TIMEOUT")
            cleanup = self._cleanup(job_id, attempt, pid, pgid, observed_fingerprint, row[2])
            if cleanup == "ORPHANS_REMAIN":
                self._transition(job_id, attempt, "ORPHANS_REMAIN", cleanup_result=cleanup)
                raise HeavyProcessError("owned descendants remain after bounded cleanup")
        else:
            cleanup = "NORMAL_COMPLETION"
        try:
            returncode = proc.wait(timeout=max(self.kill_grace_seconds, 1.0))
        except subprocess.TimeoutExpired as exc:
            raise HeavyProcessError("owned process did not reap after cleanup") from exc
        output_suffix = "\n[output truncated]" if stdout.truncated or stderr.truncated else ""
        result = HeavyProcessResult(returncode, stdout.join().decode(errors="replace"), stderr.join().decode(errors="replace") + output_suffix, timed_out, attempt, "TIMED_OUT" if timed_out else "COMPLETED")
        proc.stdout.close()
        proc.stderr.close()
        self._transition(job_id, attempt, result.state, finished_at=_utcnow(), exit_code=returncode, cleanup_result=cleanup)
        return result
