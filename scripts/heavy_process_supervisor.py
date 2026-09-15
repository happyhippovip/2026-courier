"""POSIX heavy subprocess ownership with cross-process exclusion and cleanup."""

from __future__ import annotations

import contextlib
import datetime as dt
import fcntl
import hashlib
import json
import math
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
from typing import Callable, Sequence


ACTIVE_STATES = (
    "CLAIMED",
    "RUNNING",
    "TERM_SENT",
    "KILL_SENT",
    "LIVE_VALID_OWNER",
    "AMBIGUOUS_OWNER",
    "PID_IDENTITY_MISMATCH",
)
UNRESOLVED_STATES = ACTIVE_STATES + ("TIMEOUT", "IDLE_TIMEOUT", "ORPHANS_REMAIN")
LIVENESS_SOURCES = ("HEARTBEAT", "PROGRESS_EVENT", "OUTPUT_ACTIVITY", "NONE")


class HeavyProcessError(RuntimeError):
    """Base error for a supervisor refusal or execution failure."""


class HeavyProcessBusy(HeavyProcessError):
    """A Courier process already owns the global heavy-process lock."""


class HeavyProcessIdentityError(HeavyProcessError):
    """Recorded process identity cannot be proven safe to operate on."""


class AgentDrainBlocked(HeavyProcessError):
    """A task attempt still has unresolved durable owned work."""


class AdmissionRejected(HeavyProcessError):
    """The durable global admission policy rejected work before spawn."""


class SafeModeBlocked(HeavyProcessError):
    """Durable safe mode prevents new managed work."""


class RetryFanoutRejected(HeavyProcessError):
    """A durable retry, fanout, or circuit policy blocked work before spawn."""


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

    def join(self, timeout_seconds: float) -> bytes:
        self._thread.join(timeout=max(0.0, timeout_seconds))
        return bytes(self._data)

    @property
    def size(self) -> int:
        return len(self._data)

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


class GlobalAdmissionRecovery:
    """Admission, pending backpressure, startup quarantine, and safe mode in one ledger."""

    def __init__(
        self, ledger_path: Path, *, max_running: int = 1, max_pending: int = 10,
        min_available_memory_bytes: int = 0, resource_probe: Callable[[], int | None] | None = None,
        min_available_disk_bytes: int = 0, disk_probe: Callable[[], int | None] | None = None,
    ) -> None:
        self.ledger_path = ledger_path
        self.max_running = max_running
        self.max_pending = max_pending
        self.min_available_memory_bytes = min_available_memory_bytes
        self.resource_probe = resource_probe
        self.min_available_disk_bytes = min_available_disk_bytes
        self.disk_probe = disk_probe or self._available_memory
        if max_running < 1 or max_pending < 0 or min_available_memory_bytes < 0:
            raise ValueError("admission limits must be non-negative and max_running positive")

    @staticmethod
    def _available_memory() -> int | None:
        try:
            page_size = os.sysconf("SC_PAGE_SIZE")
            available_pages = os.sysconf("SC_AVPHYS_PAGES")
            return page_size * available_pages if page_size > 0 and available_pages >= 0 else None
        except (AttributeError, OSError, ValueError):
            return None

    def initialize(self, conn: sqlite3.Connection) -> None:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS admission_work (
                job_id TEXT NOT NULL, attempt INTEGER NOT NULL, owner_id TEXT NOT NULL,
                state TEXT NOT NULL, evidence TEXT NOT NULL, PRIMARY KEY(job_id, attempt)
            )"""
        )
        conn.execute(
            """CREATE TABLE IF NOT EXISTS safety_mode (
                singleton INTEGER PRIMARY KEY CHECK(singleton = 1), enabled INTEGER NOT NULL,
                reason TEXT NOT NULL, owner_context TEXT NOT NULL, updated_at TEXT NOT NULL
            )"""
        )
        conn.execute(
            "INSERT OR IGNORE INTO safety_mode VALUES (1, 0, '', '', ?)", (_utcnow(),)
        )

    def admit(self, conn: sqlite3.Connection, job_id: str, attempt: int, owner_id: str) -> str:
        safe_mode = conn.execute("SELECT enabled FROM safety_mode WHERE singleton=1").fetchone()[0]
        if safe_mode:
            raise SafeModeBlocked("SAFE_MODE_PROCESS_STARTED=NO")
        available_disk = self.disk_probe() if self.min_available_disk_bytes else None
        if self.min_available_disk_bytes:
            if not isinstance(available_disk, int) or available_disk < 0:
                raise AdmissionRejected("AMBIGUOUS_DISK_STATE_PROCESS_STARTED=NO")
            if available_disk < self.min_available_disk_bytes:
                raise AdmissionRejected("DISK_PRESSURE_PROCESS_STARTED=NO")
        available = self.resource_probe() if self.min_available_memory_bytes else None
        if self.min_available_memory_bytes:
            if not isinstance(available, int) or available < 0:
                self._enter_safe_mode(conn, "AMBIGUOUS_RESOURCE_STATE", owner_id)
                raise AdmissionRejected("AMBIGUOUS_RESOURCE_STATE_PROCESS_STARTED=NO")
            if available < self.min_available_memory_bytes:
                raise AdmissionRejected("MEMORY_PRESSURE_PROCESS_STARTED=NO")
        conn.execute("BEGIN IMMEDIATE")
        try:
            existing = conn.execute(
                "SELECT state FROM admission_work WHERE job_id=? AND attempt=?", (job_id, attempt)
            ).fetchone()
            if existing:
                if existing[0] == "ADMITTED":
                    conn.execute("COMMIT")
                    return "ADMITTED"
                if existing[0] == "PENDING":
                    running = conn.execute("SELECT COUNT(*) FROM admission_work WHERE state='ADMITTED'").fetchone()[0]
                    if running < self.max_running:
                        conn.execute(
                            "UPDATE admission_work SET state='ADMITTED', evidence=? WHERE job_id=? AND attempt=?",
                            (f"available_memory={available if available is not None else 'not-required'}", job_id, attempt),
                        )
                        conn.execute("COMMIT")
                        return "ADMITTED"
                conn.execute("COMMIT")
                return existing[0]
            running = conn.execute("SELECT COUNT(*) FROM admission_work WHERE state='ADMITTED'").fetchone()[0]
            if running < self.max_running:
                conn.execute(
                    "INSERT INTO admission_work VALUES (?, ?, ?, 'ADMITTED', ?)",
                    (job_id, attempt, owner_id, f"available_memory={available if available is not None else 'not-required'}"),
                )
                conn.execute("COMMIT")
                return "ADMITTED"
            pending = conn.execute("SELECT COUNT(*) FROM admission_work WHERE state='PENDING'").fetchone()[0]
            if pending >= self.max_pending:
                raise AdmissionRejected("QUEUE_FULL_PROCESS_STARTED=NO")
            conn.execute(
                "INSERT INTO admission_work VALUES (?, ?, ?, 'PENDING', ?)",
                (job_id, attempt, owner_id, f"available_memory={available if available is not None else 'not-required'}"),
            )
            conn.execute("COMMIT")
            return "PENDING"
        except Exception:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            raise

    def release(self, conn: sqlite3.Connection, job_id: str, attempt: int) -> None:
        conn.execute(
            "UPDATE admission_work SET state='TERMINAL' WHERE job_id=? AND attempt=?",
            (job_id, attempt),
        )

    def reconcile_startup(self, conn: sqlite3.Connection, owner_context: str) -> None:
        nonterminal = ("ADMITTED", "STARTING", "RUNNING", "CANCELLING", "TIMEOUT", "IDLE_TIMEOUT", "UNKNOWN", "AMBIGUOUS", "RECOVERY_REQUIRED")
        placeholders = ",".join("?" for _ in nonterminal)
        rows = conn.execute(
            f"SELECT job_id, attempt FROM admission_work WHERE state IN ({placeholders})", nonterminal
        ).fetchall()
        if rows:
            conn.execute(
                f"UPDATE admission_work SET state='RECOVERY_REQUIRED' WHERE state IN ({placeholders})", nonterminal
            )
            self._enter_safe_mode(conn, "STARTUP_UNRESOLVED_OWNERSHIP", owner_context)

    def _enter_safe_mode(self, conn: sqlite3.Connection, reason: str, owner_context: str) -> None:
        conn.execute(
            "UPDATE safety_mode SET enabled=1, reason=?, owner_context=?, updated_at=? WHERE singleton=1",
            (reason, owner_context, _utcnow()),
        )

    def clear_safe_mode(self, conn: sqlite3.Connection) -> None:
        unresolved = conn.execute(
            "SELECT COUNT(*) FROM admission_work WHERE state='RECOVERY_REQUIRED'"
        ).fetchone()[0]
        if unresolved:
            raise SafeModeBlocked("SAFE_MODE_CLEAR_BLOCKED_UNRESOLVED_WORK")
        conn.execute("UPDATE safety_mode SET enabled=0, reason='', owner_context='', updated_at=? WHERE singleton=1", (_utcnow(),))


class RetryFanoutGuard:
    """Persistent retry/fanout circuit controls in the canonical ownership ledger."""

    def __init__(self, ledger_path: Path, *, max_fanout: int = 1, circuit_threshold: int = 3) -> None:
        self.ledger_path = ledger_path
        self.max_fanout = max_fanout
        self.circuit_threshold = circuit_threshold

    def initialize(self, conn: sqlite3.Connection) -> None:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS retry_fanout (
                job_id TEXT PRIMARY KEY, starts INTEGER NOT NULL, failures INTEGER NOT NULL,
                circuit_open INTEGER NOT NULL, evidence TEXT NOT NULL
            )"""
        )

    def before_spawn(self, conn: sqlite3.Connection, job_id: str) -> None:
        conn.execute("BEGIN IMMEDIATE")
        try:
            row = conn.execute("SELECT starts, circuit_open FROM retry_fanout WHERE job_id=?", (job_id,)).fetchone()
            if row and row[1]:
                raise RetryFanoutRejected("CIRCUIT_OPEN_PROCESS_STARTED=NO")
            if (row[0] if row else 0) >= self.max_fanout:
                raise RetryFanoutRejected("FANOUT_LIMIT_PROCESS_STARTED=NO")
            if row:
                conn.execute("UPDATE retry_fanout SET starts=starts+1 WHERE job_id=?", (job_id,))
            else:
                conn.execute("INSERT INTO retry_fanout VALUES (?, 1, 0, 0, '')", (job_id,))
            conn.execute("COMMIT")
        except Exception:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            raise

    def record_failure(self, conn: sqlite3.Connection, job_id: str, retryable: bool) -> None:
        if not retryable:
            return
        conn.execute(
            "UPDATE retry_fanout SET failures=failures+1, circuit_open=CASE WHEN failures+1>=? THEN 1 ELSE 0 END, evidence='retryable_failure' WHERE job_id=?",
            (self.circuit_threshold, job_id),
        )


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
        cleanup_reserve_seconds: float | None = None,
        max_running: int = 1,
        max_pending: int = 10,
        min_available_memory_bytes: int = 0,
        resource_probe: Callable[[], int | None] | None = None,
        min_available_disk_bytes: int = 0,
        disk_probe: Callable[[], int | None] | None = None,
        max_fanout: int = 10,
        circuit_threshold: int = 3,
    ) -> None:
        if os.name == "nt":
            raise NotImplementedError("Windows Job Object supervision is not implemented")
        self.runtime_dir = runtime_dir
        self.owner_id = owner_id or f"courier-{uuid.uuid4()}"
        self.output_limit_bytes = output_limit_bytes
        self.poll_interval_seconds = poll_interval_seconds
        self.term_grace_seconds = term_grace_seconds
        self.kill_grace_seconds = kill_grace_seconds
        minimum_cleanup_reserve = term_grace_seconds + kill_grace_seconds + 4.25
        self.cleanup_reserve_seconds = (
            minimum_cleanup_reserve if cleanup_reserve_seconds is None else cleanup_reserve_seconds
        )
        if self.cleanup_reserve_seconds < minimum_cleanup_reserve:
            raise ValueError("cleanup_reserve_seconds cannot be less than TERM/KILL/proof reserve")
        self._lock_file: object | None = None
        self._conn: sqlite3.Connection | None = None
        self.admission = GlobalAdmissionRecovery(
            self.ledger_path, max_running=max_running, max_pending=max_pending,
            min_available_memory_bytes=min_available_memory_bytes, resource_probe=resource_probe,
            min_available_disk_bytes=min_available_disk_bytes, disk_probe=disk_probe,
        )
        self.retry_fanout = RetryFanoutGuard(
            self.ledger_path, max_fanout=max_fanout, circuit_threshold=circuit_threshold
        )

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
        self._conn = sqlite3.connect(self.ledger_path, timeout=5, isolation_level=None)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("BEGIN EXCLUSIVE")
        try:
            version = self._conn.execute("PRAGMA user_version").fetchone()[0]
            if version == 0:
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
                self.admission.initialize(self._conn)
                self.retry_fanout.initialize(self._conn)
                self._conn.execute(
                    """CREATE TABLE IF NOT EXISTS event_log (
                        id INTEGER PRIMARY KEY AUTOINCREMENT, job_id TEXT, attempt INTEGER,
                        owner_context TEXT, state TEXT, timestamp TEXT, evidence TEXT
                    )"""
                )
                version = 1
            if version == 1:
                self._conn.execute(
                    """CREATE TABLE IF NOT EXISTS managed_services (
                        service_id TEXT PRIMARY KEY,
                        owner_id TEXT NOT NULL,
                        pid INTEGER,
                        pgid INTEGER,
                        state TEXT NOT NULL
                    )"""
                )
                self._conn.execute(
                    """CREATE TABLE IF NOT EXISTS managed_listeners (
                        listener_id TEXT PRIMARY KEY,
                        service_id TEXT NOT NULL,
                        owner_id TEXT NOT NULL,
                        state TEXT NOT NULL
                    )"""
                )
                self._conn.execute("PRAGMA user_version = 2")
            elif version == 2:
                pass
            else:
                raise HeavyProcessError(f"UNSUPPORTED_SCHEMA_VERSION_PROCESS_STARTED=NO:{version}")
            self._conn.execute("COMMIT")
        except Exception:
            self._conn.execute("ROLLBACK")
            raise
        self.admission.reconcile_startup(self._conn, self.owner_id)
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
            evidence = json.dumps(updates) if updates else ""
            self._conn.execute(
                "INSERT INTO event_log (job_id, attempt, owner_context, state, timestamp, evidence) VALUES (?, ?, ?, ?, ?, ?)",
                (job_id, attempt, self.owner_id, state, _utcnow(), evidence)
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
            self._conn.execute(
                "INSERT INTO event_log (job_id, attempt, owner_context, state, timestamp, evidence) VALUES (?, ?, ?, ?, ?, ?)",
                (job_id, attempt, self.owner_id, 'CLAIMED', now, "")
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
        try:
            os.killpg(pgid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        return True

    def _cleanup(
        self, job_id: str, attempt: int, proc: subprocess.Popen[bytes], pid: int, pgid: int,
        observed_fingerprint: str, process_start: str, cleanup_deadline: float,
    ) -> str:
        open_listeners = self._conn.execute("SELECT listener_id FROM managed_listeners WHERE service_id = ? AND state = 'OPEN'", (job_id,)).fetchall()
        if open_listeners:
            self._transition(job_id, attempt, "UNRESOLVED_LISTENER_BLOCKS_DRAIN", cleanup_result="FAIL_CLOSED")
            raise HeavyProcessError(f"unresolved listener blocks drain for {job_id}")
            
        if not self._group_exists(pgid):
            return "CLEAN"
        if not self._identity_is_valid(pid, pgid, observed_fingerprint, process_start):
            self._transition(job_id, attempt, "IDENTITY_MISMATCH", cleanup_result="FAIL_CLOSED")
            raise HeavyProcessIdentityError("PID/PGID/command/start identity cannot be proven")
        os.killpg(pgid, signal.SIGTERM)
        self._transition(job_id, attempt, "TERM_SENT", term_at=_utcnow())
        if self._wait_for_group_exit(
            proc, pgid, min(self.term_grace_seconds, max(0.0, cleanup_deadline - time.monotonic()))
        ):
            return "TERM_CLEAN"
        os.killpg(pgid, signal.SIGKILL)
        self._transition(job_id, attempt, "KILL_SENT", kill_at=_utcnow())
        return "KILL_CLEAN" if self._wait_for_group_exit(
            proc, pgid, min(self.kill_grace_seconds, max(0.0, cleanup_deadline - time.monotonic()))
        ) else "ORPHANS_REMAIN"

    def _wait_for_group_exit(self, proc: subprocess.Popen[bytes], pgid: int, grace: float) -> bool:
        deadline = time.monotonic() + grace
        while time.monotonic() < deadline:
            proc.poll()
            if not self._group_exists(pgid):
                return True
            time.sleep(self.poll_interval_seconds)
        proc.poll()
        return not self._group_exists(pgid)

    def run(
        self,
        job_id: str,
        command: Sequence[str],
        *,
        timeout_seconds: float,
        metadata: dict[str, object] | None = None,
        env: dict[str, str] | None = None,
        run_as_uid: int | None = None,
        max_attempts: int = 1,
        wall_clock_budget_seconds: float | None = None,
        idle_timeout_seconds: float | None = None,
        liveness_source: str = "NONE",
        liveness_callback: Callable[[], bool] | None = None,
        retryable_returncodes: set[int] | None = None,
        backoff_seconds: float = 0.0,
        jitter: Callable[[], float] | None = None,
        max_jitter_seconds: float = 60.0,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> HeavyProcessResult:
        if timeout_seconds <= 0 or max_attempts <= 0:
            raise ValueError("timeout_seconds and max_attempts must be positive")
        if not isinstance(backoff_seconds, (int, float)) or not math.isfinite(backoff_seconds) or backoff_seconds < 0:
            raise ValueError("backoff_seconds must be a finite non-negative number")
        if not isinstance(max_jitter_seconds, (int, float)) or not math.isfinite(max_jitter_seconds) or max_jitter_seconds < 0:
            raise ValueError("max_jitter_seconds must be a finite non-negative number")
        if liveness_source not in LIVENESS_SOURCES:
            raise ValueError(f"unsupported liveness_source: {liveness_source}")
        if idle_timeout_seconds is not None and idle_timeout_seconds <= 0:
            raise ValueError("idle_timeout_seconds must be positive")
        started = time.monotonic()
        budget = (
            wall_clock_budget_seconds
            if wall_clock_budget_seconds is not None
            else (timeout_seconds + self.cleanup_reserve_seconds) * max_attempts
        )
        if budget <= 0:
            raise ValueError("wall_clock_budget_seconds must be positive")
        if budget < self.cleanup_reserve_seconds * max_attempts:
            raise HeavyProcessError("WALL_CLOCK_BUDGET_TOO_SMALL_PROCESS_STARTED=NO")
        total_deadline = started + budget
        with self.ownership():
            for attempt in range(1, max_attempts + 1):
                assert self._conn is not None
                admission = self.admission.admit(self._conn, job_id, attempt, self.owner_id)
                if admission == "PENDING":
                    raise AdmissionRejected("ADMISSION_BACKPRESSURE_PROCESS_STARTED=NO")
                try:
                    self.retry_fanout.before_spawn(self._conn, job_id)
                    cleanup_reserve = self.cleanup_reserve_seconds * (max_attempts - attempt + 1)
                    execution_deadline = total_deadline - cleanup_reserve
                    remaining = execution_deadline - time.monotonic()
                    if remaining <= 0:
                        raise HeavyProcessError("WALL_CLOCK_BUDGET_EXHAUSTED")
                    result = self._run_once(
                        job_id, command, min(timeout_seconds, remaining), metadata or {}, attempt,
                        execution_deadline, total_deadline, idle_timeout_seconds, liveness_source, liveness_callback, env=env, run_as_uid=run_as_uid
                    )
                finally:
                    self.admission.release(self._conn, job_id, attempt)
                if result.returncode == 0 or attempt == max_attempts:
                    return result
                retryable = result.returncode in (retryable_returncodes or set())
                self.retry_fanout.record_failure(self._conn, job_id, retryable)
                if not retryable:
                    return result
                jitter_seconds = jitter() if jitter else 0.0
                if (
                    not isinstance(jitter_seconds, (int, float))
                    or not math.isfinite(jitter_seconds)
                    or jitter_seconds < 0
                    or jitter_seconds > max_jitter_seconds
                ):
                    raise RetryFanoutRejected("INVALID_RETRY_JITTER_PROCESS_STARTED=NO")
                delay = backoff_seconds + jitter_seconds
                next_reserve = self.cleanup_reserve_seconds * (max_attempts - attempt)
                if time.monotonic() + delay + next_reserve >= total_deadline:
                    raise RetryFanoutRejected("RETRY_BUDGET_EXHAUSTED_PROCESS_STARTED=NO")
                sleeper(delay)
            raise AssertionError("unreachable")

    def _run_once(
        self, job_id: str, command: Sequence[str], timeout: float, metadata: dict[str, object],
        attempt: int, execution_deadline: float, total_deadline: float,
        idle_timeout_seconds: float | None, liveness_source: str, liveness_callback: Callable[[], bool] | None,
        env: dict[str, str] | None = None, run_as_uid: int | None = None,
    ) -> HeavyProcessResult:
        if time.monotonic() >= execution_deadline:
            raise HeavyProcessError("WALL_CLOCK_BUDGET_TOO_SMALL_PROCESS_STARTED=NO")
        self._claim(
            job_id, attempt, command, metadata,
            time.time() + max(0.0, execution_deadline - time.monotonic()),
        )
        try:

            safe_keys = {"PATH", "LANG", "TZ", "USER", "HOME", "LOGNAME"}
            merged_env = {k: v for k, v in os.environ.items() if k in safe_keys}
            if env:
                for k, v in env.items():
                    k_up = k.upper()
                    if "SECRET" in k_up or "TOKEN" in k_up or "KEY" in k_up or "PASS" in k_up or "CRED" in k_up:
                        self._transition(job_id, attempt, "SPAWN_FAILED", finished_at=_utcnow(), error=f"forbidden env key: {k}")
                        raise HeavyProcessError(f"FORBIDDEN_ENV_KEY_PROCESS_STARTED=NO:{k}")
                    merged_env[k] = v
            
            preexec_fn = None
            if run_as_uid is not None:
                if hasattr(os, "setresuid"):
                    def demote():
                        os.setresuid(run_as_uid, run_as_uid, run_as_uid)
                    preexec_fn = demote
                else:
                    self._transition(job_id, attempt, "SPAWN_FAILED", finished_at=_utcnow(), error="uid demotion not supported")
                    raise HeavyProcessError("UID_DEMOTION_UNSUPPORTED_PROCESS_STARTED=NO")
            self._transition(job_id, attempt, 'STARTING')
            proc = subprocess.Popen(
                list(command), stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                start_new_session=True, env=merged_env, preexec_fn=preexec_fn
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
        idle_timed_out = False
        last_liveness = time.monotonic()
        output_size = stdout.size + stderr.size
        while proc.poll() is None and time.monotonic() < execution_deadline:
            now = time.monotonic()
            if liveness_source == "OUTPUT_ACTIVITY":
                current_output_size = stdout.size + stderr.size
                if current_output_size != output_size:
                    last_liveness = now
                    output_size = current_output_size
            elif liveness_source in ("HEARTBEAT", "PROGRESS_EVENT") and liveness_callback and liveness_callback():
                last_liveness = now
            if idle_timeout_seconds is not None and now - last_liveness >= idle_timeout_seconds:
                idle_timed_out = True
                break
            self._transition(job_id, attempt, "RUNNING")
            time.sleep(self.poll_interval_seconds)
        if proc.poll() is None:
            timed_out = True
            self._transition(job_id, attempt, "IDLE_TIMEOUT" if idle_timed_out else "TIMEOUT")
            cleanup = self._cleanup(job_id, attempt, proc, pid, pgid, observed_fingerprint, row[2], total_deadline)
            if cleanup == "ORPHANS_REMAIN":
                self._transition(job_id, attempt, "ORPHANS_REMAIN", cleanup_result=cleanup)
                raise HeavyProcessError("owned descendants remain after bounded cleanup")
        else:
            open_listeners = self._conn.execute("SELECT listener_id FROM managed_listeners WHERE service_id = ? AND state = 'OPEN'", (job_id,)).fetchall()
            if open_listeners:
                self._transition(job_id, attempt, "UNRESOLVED_LISTENER_BLOCKS_DRAIN", cleanup_result="FAIL_CLOSED")
                raise HeavyProcessError(f"unresolved listener blocks drain for {job_id}")
            cleanup = "NORMAL_COMPLETION"
        try:
            returncode = proc.wait(timeout=max(0.0, total_deadline - time.monotonic()))
        except subprocess.TimeoutExpired as exc:
            raise HeavyProcessError("owned process did not reap after cleanup") from exc
        output_suffix = "\n[output truncated]" if stdout.truncated or stderr.truncated else ""
        remaining = max(0.0, total_deadline - time.monotonic())
        result = HeavyProcessResult(
            returncode,
            stdout.join(remaining).decode(errors="replace"),
            stderr.join(remaining).decode(errors="replace") + output_suffix,
            timed_out,
            attempt,
            "IDLE_TIMED_OUT" if idle_timed_out else ("TIMED_OUT" if timed_out else "COMPLETED"),
        )
        proc.stdout.close()
        proc.stderr.close()
        self._transition(job_id, attempt, result.state, finished_at=_utcnow(), exit_code=returncode, cleanup_result=cleanup)
        return result



    def register_service(self, service_id: str, pid: int, pgid: int) -> None:
        self._conn.execute("BEGIN IMMEDIATE")
        try:
            self._conn.execute("INSERT OR IGNORE INTO managed_services (service_id, owner_id, pid, pgid, state) VALUES (?, ?, ?, ?, 'REGISTERED')", (service_id, self.owner_id, pid, pgid))
            self._conn.execute("COMMIT")
        except Exception:
            self._conn.execute("ROLLBACK")
            raise

    def register_listener(self, listener_id: str, service_id: str) -> None:
        self._conn.execute("BEGIN IMMEDIATE")
        try:
            self._conn.execute("INSERT OR REPLACE INTO managed_listeners (listener_id, service_id, owner_id, state) VALUES (?, ?, ?, 'OPEN')", (listener_id, service_id, self.owner_id))
            self._conn.execute("COMMIT")
        except Exception:
            self._conn.execute("ROLLBACK")
            raise

    def release_listener(self, listener_id: str) -> None:
        if self._conn is None:
            raise RuntimeError("release_listener called but self._conn is None")
        self._conn.execute("BEGIN IMMEDIATE")
        try:
            self._conn.execute("UPDATE managed_listeners SET state = 'CLOSED' WHERE listener_id = ?", (listener_id,))
            self._conn.execute("COMMIT")
        except Exception:
            self._conn.execute("ROLLBACK")
            raise

class AgentDrainBarrier:
    """Blocks terminal success only from unresolved work owned by one task attempt."""

    def __init__(self, runtime_dir: Path) -> None:
        self.ledger_path = runtime_dir / "heavy_jobs.sqlite3"

    def require_drained(self, job_id: str, attempt: int) -> None:
        if not self.ledger_path.exists():
            return
        with sqlite3.connect(f"file:{self.ledger_path}?mode=ro", uri=True) as conn:
            row = conn.execute(
                "SELECT state FROM heavy_jobs WHERE job_id = ? AND attempt = ?",
                (job_id, attempt),
            ).fetchone()
        if row and row[0] in UNRESOLVED_STATES:
            raise AgentDrainBlocked(f"UNRESOLVED_OWNED_WORK:{job_id}:{attempt}:{row[0]}")
