"""Single-flight bounded execution engine (lane L3).

Ownership model: a :class:`WorkerHost` holds at most one live dispatch. A
dispatch is the exact triple ``(task_id, attempt, dispatch_id)`` plus the
``worker_id`` that claimed it. The child process tree belongs to exactly that
dispatch; termination addresses only the recorded tree, never the system.

Every wait is a blocking wait with a deadline. The number of loop wakes for
one run is bounded by ``ceil(total_s / quantum_s) + slack``; there is no
busy poll and no retry anywhere in this module. A resource problem
(pressure, EMFILE/ENFILE) raises :class:`ResourcePaused` exactly once per
call instead of spinning.

Adapter constraint (recorded for L4): the child must not double-fork out of
its process group (POSIX) or job (Windows). Grandchildren that stay in the
owned tree are reaped; session escapees are not reachable by owned-tree
cleanup on any platform.
"""

from __future__ import annotations

import errno
import hashlib
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

# -- bounds (all of them are load-bearing contracts) --------------------------
MAX_TIMEOUT_S = 3600.0
DEFAULT_TIMEOUT_S = 300.0
KILL_GRACE_S = 2.0
MIN_HEARTBEAT_S = 0.2
MAX_HEARTBEAT_S = 30.0
MAX_ARGV = 256
MAX_ARGV_BYTES = 64 * 1024
MAX_ARTIFACTS = 64
MAX_ARTIFACT_BYTES = 16 * 1024 * 1024
MAX_STDIO_TAIL = 64 * 1024
OUTBOX_CAP = 32
ORPHAN_TERM_GRACE_S = 2.0
LOAD_PRESSURE_FACTOR = 4.0

CLAIM_RECORD_GLOB = "dispatch-*.json"
CRASH_REPORT_NAME = "crash.json"


class SpecError(ValueError):
    """The execution spec is malformed; the host refuses it fail-closed."""


class HostBusy(RuntimeError):
    """The host already owns a live dispatch; single-flight only."""


class ContainmentError(RuntimeError):
    """The host cannot contain or reap the tree it owns."""


class ResourcePaused(RuntimeError):
    """The host must pause (pressure or FD exhaustion), not retry.

    ``reason`` is a short machine-readable tag such as ``"fd-exhaustion"``
    or ``"cpu-pressure"``. Raised exactly once per call; the caller (lane
    L2's serve, via the service layer) decides what happens to the lease.
    """

    def __init__(self, reason: str):
        super().__init__(f"RESOURCE_PAUSE: {reason}")
        self.reason = reason


class OutboxFull(RuntimeError):
    """The durable outbox reached its cap; the controller must drain it."""


class Outcome:
    COMPLETED = "completed"
    CRASH = "crash"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"
    LEASE_LOST = "lease-lost"
    SPAWN_FAILED = "spawn-failed"


class LivenessState:
    DELIVERED = "delivered"
    ACCEPTED = "accepted"
    WORKING = "working"
    QUIET = "quiet"
    SLOW = "slow"
    PROBING = "probing"
    FAILED = "failed"
    RESULT_DURABLE = "result_durable"
    RETIRED = "retired"


@dataclass(frozen=True)
class ExecutionSpec:
    """Everything the host needs to run one dispatch, nothing more."""

    task_id: str
    attempt: int
    dispatch_id: str
    worker_id: str
    result_id: str
    argv: tuple
    timeout_s: float
    lease_ttl_s: float
    artifact_dir: str
    heartbeat_s: float = 1.0
    # Set when the spec came from a declarative claim through the adapter
    # bridge (courier_worker.adapter_bridge); argv then names Courier's own
    # runner, never a command supplied by the task.
    adapter: Optional[str] = None
    params: Optional[dict] = field(default=None, compare=False)
    effect_key: Optional[str] = None

    def __post_init__(self):
        for name in ("task_id", "dispatch_id", "worker_id", "result_id"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value or len(value) > 200:
                raise SpecError(f"{name} must be a non-empty string of at most 200 chars")
        if isinstance(self.attempt, bool) or not isinstance(self.attempt, int) or self.attempt < 1:
            raise SpecError("attempt must be an integer >= 1")
        if (not isinstance(self.argv, (list, tuple)) or not self.argv
                or len(self.argv) > MAX_ARGV):
            raise SpecError("argv must be a non-empty argument list")
        if any(not isinstance(a, str) or not a for a in self.argv):
            raise SpecError("argv entries must be non-empty strings")
        if sum(len(a) for a in self.argv) > MAX_ARGV_BYTES:
            raise SpecError("argv exceeds size bound")
        if not isinstance(self.timeout_s, (int, float)) or not 0 < self.timeout_s <= MAX_TIMEOUT_S:
            raise SpecError(f"timeout_s must be within (0, {MAX_TIMEOUT_S}]")
        if not isinstance(self.lease_ttl_s, (int, float)) or self.lease_ttl_s < 1:
            raise SpecError("lease_ttl_s must be >= 1")
        if not isinstance(self.heartbeat_s, (int, float)) \
                or not MIN_HEARTBEAT_S <= self.heartbeat_s <= MAX_HEARTBEAT_S:
            raise SpecError(f"heartbeat_s must be within [{MIN_HEARTBEAT_S}, {MAX_HEARTBEAT_S}]")
        if not isinstance(self.artifact_dir, str) or not self.artifact_dir:
            raise SpecError("artifact_dir must be a non-empty path")


@dataclass(frozen=True)
class ArtifactRef:
    path: str
    sha256: str


@dataclass
class ExecutionResult:
    """The durable truth of one finished dispatch, delivered exactly once."""

    spec: ExecutionSpec
    outcome: str
    returncode: Optional[int] = None
    was_signal: bool = False
    artifacts: tuple = ()
    crash_report_path: Optional[str] = None
    duration_s: float = 0.0
    wakes: int = 0
    stale: bool = False

    @property
    def l2_outcome(self) -> str:
        return "success" if self.outcome == Outcome.COMPLETED else "failure"

    @property
    def retryable(self) -> bool:
        # Only environment-shaped ends are worth a blind retry. A crash or a
        # cancellation is evidence, not a transient: the controller (and the
        # non-idempotent BLOCK rule) must see retryable=false.
        return self.outcome in (Outcome.TIMEOUT, Outcome.LEASE_LOST)


def default_pressure_probe() -> Optional[str]:
    """Return None when the host may spawn, else a short reason.

    Fail-closed: any probe error pauses the host. The FD check opens and
    closes a real pipe, so descriptor exhaustion is observed, not assumed.
    """
    try:
        r, w = os.pipe()
        try:
            pass
        finally:
            os.close(r)
            os.close(w)
    except OSError as exc:
        return f"fd-exhaustion: {exc.strerror or exc}"
        
    try:
        load = _one_minute_load()
    except OSError as exc:
        return f"load-probe-failed: {exc.strerror or exc}"
        
    if load is not None:
        cpus = os.cpu_count() or 1
        if load > cpus * LOAD_PRESSURE_FACTOR:
            return f"cpu-pressure: load1 {load:.1f} over {cpus} cpu(s)"
    return None


def _one_minute_load() -> Optional[float]:
    getter = getattr(os, "getloadavg", None)
    if getter is None:
        return None
    return float(getter()[0])


# -- owned-tree containment ---------------------------------------------------
#
# POSIX: the child starts a new session, so its process group id equals its
# pid and signalling the group reaches every non-escaping descendant.
# Windows: the child joins a Job Object created with KILL_ON_JOB_CLOSE, so
# the OS itself kills the whole tree when the job closes -- including after
# a hard kill of the host, which cannot run any cleanup of its own.

if os.name == "nt":
    import ctypes
    from ctypes import wintypes

    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    _kernel32.CreateJobObjectW.restype = wintypes.HANDLE
    _kernel32.CreateJobObjectW.argtypes = [wintypes.LPVOID, wintypes.LPCWSTR]
    _kernel32.SetInformationJobObject.restype = wintypes.BOOL
    _kernel32.SetInformationJobObject.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPVOID, wintypes.DWORD]
    _kernel32.AssignProcessToJobObject.restype = wintypes.BOOL
    _kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    _kernel32.OpenProcess.restype = wintypes.HANDLE
    _kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    _kernel32.CloseHandle.restype = wintypes.BOOL
    _kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    _kernel32.TerminateJobObject.restype = wintypes.BOOL
    _kernel32.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]

    _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000
    _JobObjectExtendedLimitInformation = 9

    class _JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", wintypes.LARGE_INTEGER),
            ("PerJobUserTimeLimit", wintypes.LARGE_INTEGER),
            ("LimitFlags", wintypes.DWORD),
            ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessCount", wintypes.DWORD),
            ("Affinity", ctypes.c_size_t),
            ("PriorityClass", wintypes.DWORD),
            ("SchedulingClass", wintypes.DWORD),
        ]

    class _IO_COUNTERS(ctypes.Structure):
        _fields_ = [(n, ctypes.c_ulonglong) for n in
                    ("ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
                     "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]

    class _JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
        _fields_ = [("BasicLimitInformation", _JOBOBJECT_BASIC_LIMIT_INFORMATION),
                    ("IoInfo", _IO_COUNTERS),
                    ("ProcessMemoryLimit", ctypes.c_size_t),
                    ("JobMemoryLimit", ctypes.c_size_t),
                    ("PeakProcessMemoryUsed", ctypes.c_size_t),
                    ("PeakJobMemoryUsed", ctypes.c_size_t)]

    def _job_for_child() -> object:
        job = _kernel32.CreateJobObjectW(None, None)
        if not job:
            raise ContainmentError("CreateJobObjectW failed; child would run uncontained")
        info = _JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        info.BasicLimitInformation.LimitFlags = _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        ok = _kernel32.SetInformationJobObject(
            job, _JobObjectExtendedLimitInformation,
            ctypes.byref(info), ctypes.sizeof(info))
        if not ok:
            _kernel32.CloseHandle(job)
            raise ContainmentError("SetInformationJobObject(KILL_ON_JOB_CLOSE) failed")
        return job

    def _assign_to_job(job: object, pid: int) -> None:
        proc = _kernel32.OpenProcess(0x001F0FFF, False, pid)
        if not proc:
            raise ContainmentError(f"cannot open child pid {pid} for job assignment")
        try:
            if not _kernel32.AssignProcessToJobObject(job, proc):
                raise ContainmentError(f"child pid {pid} escapes the job object")
        finally:
            _kernel32.CloseHandle(proc)

    def _close_job(job: object) -> None:
        _kernel32.CloseHandle(job)

    def _terminate_job(job: object) -> None:
        _kernel32.TerminateJobObject(job, 1)

    # NtResumeProcess resumes all threads in a process given its handle.
    # This replaces the psutil dependency for the CREATE_SUSPENDED pattern.
    _ntdll = ctypes.WinDLL("ntdll", use_last_error=True)
    _ntdll.NtResumeProcess.restype = wintypes.LONG  # NTSTATUS
    _ntdll.NtResumeProcess.argtypes = [wintypes.HANDLE]

    def _resume_process(proc: subprocess.Popen) -> None:
        """Resume a process created with CREATE_SUSPENDED."""
        # subprocess.Popen on Windows stores the process handle as _handle
        handle = getattr(proc, "_handle", None)
        if handle is None:
            raise ContainmentError("cannot resume: no process handle")
        status = _ntdll.NtResumeProcess(handle)
        if status < 0:
            raise ContainmentError(f"NtResumeProcess failed: NTSTATUS 0x{status & 0xFFFFFFFF:08X}")
else:
    def _job_for_child() -> object:
        return None

    def _assign_to_job(job: object, pid: int) -> None:
        pass

    def _close_job(job: object) -> None:
        pass

    def _terminate_job(job: object) -> None:
        pass


class ContainedRun:
    """One spawned child plus the only handle allowed to signal its tree."""

    def __init__(self, proc: subprocess.Popen, job: object, stdout_path: str, stderr_path: str):
        self.proc = proc
        self.job = job
        self.stdout_path = stdout_path
        self.stderr_path = stderr_path

    @property
    def pid(self) -> int:
        return self.proc.pid

    def group_id(self) -> Optional[int]:
        if os.name == "nt":
            return None
        return self.proc.pid

    def poll(self) -> Optional[int]:
        return self.proc.poll()

    def wait(self, timeout: Optional[float] = None) -> Optional[int]:
        try:
            return self.proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            return None

    def tree_alive(self) -> bool:
        """True if any member of the owned tree may still run."""
        if os.name == "nt":
            return self.proc.poll() is None  # the job kills the rest on close
        pgid = self.proc.pid
        try:
            os.killpg(pgid, 0)
            return True
        except ProcessLookupError:
            return False
        except PermissionError:
            return True  # someone else's group with our id: assume alive

    def terminate_tree(self, grace: float = KILL_GRACE_S) -> None:
        """SIGTERM, then SIGKILL, then reap. Addresses the owned tree only."""
        if os.name == "nt":
            if self.job is not None:
                _terminate_job(self.job)
            if self.proc.poll() is None:
                self.proc.wait()
            self._close()
            return

        pgid = self.proc.pid
        try:
            os.killpg(pgid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        except PermissionError as exc:
            raise ContainmentError(f"cannot signal owned group {pgid}: {exc}") from exc

        if self.proc.poll() is None:
            try:
                self.proc.wait(timeout=grace)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(pgid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                except PermissionError as exc:
                    raise ContainmentError(f"cannot kill owned group {pgid}: {exc}") from exc
                self.proc.wait()
        else:
            # Root is already dead. Wait grace period for the group to empty.
            deadline = time.monotonic() + grace
            while time.monotonic() < deadline:
                try:
                    os.killpg(pgid, 0)
                except (OSError, ProcessLookupError):
                    break
                time.sleep(0.05)
            else:
                try:
                    os.killpg(pgid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                except PermissionError as exc:
                    raise ContainmentError(f"cannot kill owned group {pgid}: {exc}") from exc

        self._close()

    def _close(self) -> None:
        if self.job is not None:
            _close_job(self.job)
            self.job = None


def _spawn_contained(argv: list, run_dir: str, tag: str) -> ContainedRun:
    """Spawn argv contained. EMFILE/ENFILE becomes ResourcePaused, once."""
    stdout_path = os.path.join(run_dir, f"{tag}.out")
    stderr_path = os.path.join(run_dir, f"{tag}.err")
    stdout_f = open(stdout_path, "wb")
    try:
        stderr_f = open(stderr_path, "wb")
    except OSError:
        stdout_f.close()
        raise
    popen_kwargs: dict = {"stdout": stdout_f, "stderr": stderr_f,
                           "stdin": subprocess.DEVNULL, "close_fds": True}
    job = None
    if os.name == "nt":
        job = _job_for_child()
        popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | 0x00000004
    else:
        popen_kwargs["start_new_session"] = True
    try:
        proc = subprocess.Popen(argv, **popen_kwargs)
    except OSError as exc:
        _close_job(job)
        stdout_f.close()
        stderr_f.close()
        if exc.errno in (errno.EMFILE, errno.ENFILE):
            raise ResourcePaused(f"fd-exhaustion at spawn: {exc.strerror or exc}") from exc
        raise ContainmentError(f"spawn failed: {exc.strerror or exc}") from exc
    finally:
        stdout_f.close()
        stderr_f.close()
    if os.name == "nt":
        try:
            _assign_to_job(job, proc.pid)
            _resume_process(proc)
        except BaseException:
            try:
                proc.kill()
            except OSError:
                pass
            proc.wait()
            _close_job(job)
            raise
    return ContainedRun(proc, job, stdout_path, stderr_path)


# -- claim records, orphan gate, home lock ------------------------------------
#
# `<home>/run/claims/dispatch-<dispatch_id>.json` names the live tree of one
# dispatch: the host pid that owns it, the child root pid and, on POSIX, the
# process group. A new host runs the orphan gate before claiming anything:
# records whose owner is dead name trees no host will reap, so the gate
# reaps them. This is how no child of a hard-killed host survives on POSIX;
# on Windows the Job Object already guarantees it and the gate only drops
# the stale record.

def _run_dir(home: str) -> Path:
    return Path(home) / "run"


def _claims_dir(home: str) -> Path:
    return _run_dir(home) / "claims"


def _claim_path(home: str, dispatch_id: str) -> Path:
    safe = "".join(c if (c.isalnum() or c in "-_.") else "_" for c in dispatch_id)
    return _claims_dir(home) / f"dispatch-{safe or 'unnamed'}.json"


def _owner_alive(owner_pid: int, owner_create_time: float | None = None) -> bool:
    if owner_pid <= 0:
        return False
    if owner_create_time and owner_create_time > 0.0:
        try:
            import psutil
            proc = psutil.Process(owner_pid)
            if proc.status() == psutil.STATUS_ZOMBIE:
                return False
            if abs(proc.create_time() - owner_create_time) > 0.1:
                return False
            return True
        except (Exception,):
            return False
    try:
        if os.name == "nt":
            import ctypes
            handle = ctypes.windll.kernel32.OpenProcess(0x100000, False, owner_pid)
            if not handle:
                return False
            ctypes.windll.kernel32.CloseHandle(handle)
            return True
        os.kill(owner_pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


def _write_claim_record(home: str, spec: ExecutionSpec, run: ContainedRun) -> Path:
    _claims_dir(home).mkdir(parents=True, exist_ok=True)
    owner_create_time = 0.0
    try:
        import psutil
        owner_create_time = psutil.Process(os.getpid()).create_time()
    except Exception:
        pass
    record = {"task_id": spec.task_id, "attempt": spec.attempt, "dispatch_id": spec.dispatch_id,
              "worker_id": spec.worker_id, "owner_pid": os.getpid(), "owner_create_time": owner_create_time,
              "child_pid": run.pid, "pgid": run.group_id()}
    path = _claim_path(home, spec.dispatch_id)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".claim-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(record, fh, sort_keys=True)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    return path


def run_orphan_gate(home: str) -> int:
    """Reap trees of dead owners. Returns the number of records handled."""
    claims = _claims_dir(home)
    if not claims.is_dir():
        return 0
    handled = 0
    for path in sorted(claims.glob(CLAIM_RECORD_GLOB)):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
            owner_pid = int(record.get("owner_pid", 0) or 0)
            owner_create_time = float(record.get("owner_create_time", 0.0) or 0.0)
        except (OSError, ValueError, TypeError):
            try:
                path.rename(path.with_suffix('.json.corrupt'))
            except OSError:
                pass
            continue
        if _owner_alive(owner_pid, owner_create_time):
            continue  # another live host owns this tree; hands off
        _reap_orphan(record)
        try:
            path.unlink()
        except OSError:
            pass
        handled += 1
    return handled


def _reap_orphan(record: dict) -> None:
    child_pid = int(record.get("child_pid", 0) or 0)
    pgid = record.get("pgid")
    if os.name == "nt":
        return  # KILL_ON_JOB_CLOSE already reaped the tree at host death
    if pgid is None and child_pid:
        pgid = child_pid
    if not pgid:
        return
    if child_pid:
        try:
            alive_pgid = os.getpgid(child_pid)
        except (OSError, ProcessLookupError):
            alive_pgid = None
        if alive_pgid is not None and alive_pgid != pgid:
            return  # pid reused by an unrelated group; not ours
    try:
        os.killpg(pgid, signal.SIGTERM)
    except (OSError, ProcessLookupError):
        return
    deadline = time.monotonic() + ORPHAN_TERM_GRACE_S
    while time.monotonic() < deadline:
        try:
            os.killpg(pgid, 0)
        except (OSError, ProcessLookupError):
            return
        time.sleep(0.05)
    try:
        os.killpg(pgid, signal.SIGKILL)
    except (OSError, ProcessLookupError):
        pass


def acquire_home_lock(home: str):
    """Fail-closed single ownership of one home directory.

    Returns an open lock handle the caller must keep (and pass to
    :func:`release_home_lock`). A second live host for the same home gets
    :class:`HostBusy`, never a shared home.
    """
    _run_dir(home).mkdir(parents=True, exist_ok=True)
    path = _run_dir(home) / "worker.lock"
    fd = os.open(str(path), os.O_RDWR | os.O_CREAT, 0o600)
    try:
        if os.name == "nt":
            import msvcrt
            try:
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            except OSError:
                os.close(fd)
                raise HostBusy(f"home {home} is already owned by a live host")
        else:
            import fcntl
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                os.close(fd)
                raise HostBusy(f"home {home} is already owned by a live host")
        os.ftruncate(fd, 0)
        os.write(fd, str(os.getpid()).encode("ascii"))
        return fd
    except BaseException:
        try:
            os.close(fd)
        except OSError:
            pass
        raise


def release_home_lock(lock_fd) -> None:
    try:
        if os.name == "nt":
            import msvcrt
            try:
                msvcrt.locking(lock_fd, msvcrt.LK_UNLCK, 1)
            except OSError:
                pass
        else:
            import fcntl
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_UN)
            except OSError:
                pass
    finally:
        os.close(lock_fd)


# -- artifacts and crash truth -------------------------------------------------

def _sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def collect_artifacts(artifact_dir: str) -> tuple:
    """Hash every file under artifact_dir, bounded in count and bytes."""
    root = Path(artifact_dir)
    if not root.is_dir():
        return ()
    found = []
    total = 0
    for dirpath, _dirnames, filenames in os.walk(artifact_dir):
        for name in sorted(filenames):
            full = os.path.join(dirpath, name)
            try:
                size = os.path.getsize(full)
            except OSError:
                continue
            total += size
            if len(found) >= MAX_ARTIFACTS or total > MAX_ARTIFACT_BYTES:
                raise ContainmentError("artifact set exceeds bounds; refusing an unbounded result")
            rel = os.path.relpath(full, artifact_dir)
            found.append((rel, _sha256_file(full)))
    return tuple(ArtifactRef(path=rel, sha256=sha) for rel, sha in found)


def _tail(path: str, limit: int = MAX_STDIO_TAIL) -> str:
    try:
        size = os.path.getsize(path)
    except OSError:
        return ""
    try:
        with open(path, "rb") as fh:
            fh.seek(max(0, size - limit))
            return fh.read().decode("utf-8", errors="replace")
    except OSError:
        return ""


def write_crash_report(artifact_dir: str, spec: ExecutionSpec, outcome: str,
                       returncode: Optional[int], duration_s: float, stderr_path: str) -> str:
    """Persist the abnormal end as evidence; the report itself is an artifact."""
    os.makedirs(artifact_dir, exist_ok=True)
    report = {"dispatch_id": spec.dispatch_id, "task_id": spec.task_id, "attempt": spec.attempt,
              "worker_id": spec.worker_id, "outcome": outcome, "returncode": returncode,
              "duration_s": round(duration_s, 3),
              "stderr_tail": _tail(stderr_path)[-8000:]}
    path = os.path.join(artifact_dir, CRASH_REPORT_NAME)
    fd, tmp = tempfile.mkstemp(dir=artifact_dir, prefix=".crash-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(report, fh, sort_keys=True)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    return path


# -- durable outbox ------------------------------------------------------------
#
# `<home>/outbox/<dispatch_id>.json` holds one undelivered result. The host
# writes it before the first delivery attempt and removes it once the
# controller answers ACCEPTED_FOR_VERIFY, ACK_DUPLICATE, or 409-stale. A
# crash between run and delivery therefore loses nothing: the next host on
# the same home redelivers the identical bytes, and the journal dedupes them.

def _outbox_dir(home: str) -> Path:
    return Path(home) / "outbox"


def outbox_write(home: str, payload: dict) -> Path:
    outbox = _outbox_dir(home)
    outbox.mkdir(parents=True, exist_ok=True)
    existing = list(outbox.glob("*.json"))
    if len(existing) >= OUTBOX_CAP and not any(
            p.name == f"{payload['dispatch_id']}.json" for p in existing):
        raise OutboxFull(f"outbox holds {len(existing)} results; controller must drain it")
    path = outbox / f"{payload['dispatch_id']}.json"
    fd, tmp = tempfile.mkstemp(dir=str(outbox), prefix=".outbox-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, sort_keys=True)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    return path


def outbox_read_all(home: str) -> list:
    outbox = _outbox_dir(home)
    if not outbox.is_dir():
        return []
    payloads = []
    for path in sorted(outbox.glob("*.json")):
        try:
            payloads.append((path, json.loads(path.read_text(encoding="utf-8"))))
        except (OSError, ValueError):
            continue
    return payloads


def outbox_remove(home: str, dispatch_id: str) -> None:
    try:
        (_outbox_dir(home) / f"{dispatch_id}.json").unlink()
    except OSError:
        pass


# -- the single-flight host ----------------------------------------------------

class WorkerHost:
    """Owns at most one live dispatch and runs it bounded.

    ``on_heartbeat`` is called with the elapsed seconds about once per
    quantum; its exceptions never kill the run (no storm: called, not
    retried). ``is_cancelled`` is polled once per quantum; when it turns
    true the owned tree is terminated and the end is reported as
    ``cancelled`` truth.
    """

    def __init__(self, home: str, pressure_probe: Optional[Callable[[], Optional[str]]] = None):
        self.home = home
        self._pressure_probe = pressure_probe or default_pressure_probe
        self._active: Optional[str] = None

    @property
    def busy(self) -> bool:
        return self._active is not None

    def run_once(self, spec: ExecutionSpec,
                 on_heartbeat: Optional[Callable[[float], None]] = None,
                 is_cancelled: Optional[Callable[[], bool]] = None) -> ExecutionResult:
        if self._active is not None:
            raise HostBusy(f"host already owns dispatch {self._active}; single-flight only")
        reason = self._pressure_probe()
        if reason is not None:
            raise ResourcePaused(reason)
        run_dir = str(_run_dir(self.home))
        os.makedirs(run_dir, exist_ok=True)
        os.makedirs(spec.artifact_dir, exist_ok=True)
        run = _spawn_contained(list(spec.argv), run_dir, f"task-{spec.dispatch_id}")
        self._active = spec.dispatch_id
        claim_record = _write_claim_record(self.home, spec, run)
        try:
            return self._wait(spec, run, on_heartbeat, is_cancelled)
        finally:
            run.terminate_tree()
            self._active = None
            try:
                claim_record.unlink()
            except OSError:
                pass

    def _wait(self, spec: ExecutionSpec, run: ContainedRun,
              on_heartbeat: Optional[Callable[[float], None]],
              is_cancelled: Optional[Callable[[], bool]]) -> ExecutionResult:
        start = time.monotonic()
        timeout_at = start + spec.timeout_s
        lease_at = start + spec.lease_ttl_s
        quantum = min(spec.heartbeat_s, 1.0)
        outcome: Optional[str] = None
        returncode: Optional[int] = None
        wakes = 0
        while outcome is None:
            now = time.monotonic()
            remaining = min(timeout_at, lease_at) - now
            if remaining <= 0:
                # spec.timeout_s is the task's declared hard bound, not a silence
                # heuristic: when it passes, the owned tree is stopped and the
                # attempt is a retryable TIMEOUT. (Session liveness - QUIET/SLOW/
                # PROBING - applies to surfaces and sessions, not to this bound.)
                outcome = Outcome.TIMEOUT if timeout_at <= lease_at else Outcome.LEASE_LOST
                run.terminate_tree()
                returncode = run.poll()
                break
            if is_cancelled is not None:
                try:
                    cancelled = is_cancelled()
                except Exception:
                    cancelled = False
                if cancelled:
                    outcome = Outcome.CANCELLED
                    run.terminate_tree()
                    returncode = run.poll()
                    break
            returncode = run.wait(timeout=min(quantum, remaining))
            wakes += 1
            if returncode is not None:
                outcome = Outcome.COMPLETED if returncode == 0 else Outcome.CRASH
                run.terminate_tree()
                break
            if on_heartbeat is not None:
                try:
                    if on_heartbeat(time.monotonic() - start) is not False:
                        lease_at = time.monotonic() + spec.lease_ttl_s
                except Exception:
                    pass  # a failed heartbeat never kills a healthy run
        duration_s = time.monotonic() - start
        crash_report_path = None
        if outcome != Outcome.COMPLETED:
            crash_report_path = write_crash_report(
                spec.artifact_dir, spec, outcome, returncode, duration_s, run.stderr_path)
        artifacts = collect_artifacts(spec.artifact_dir)
        return ExecutionResult(
            spec=spec, outcome=outcome, returncode=returncode,
            was_signal=returncode is not None and returncode < 0,
            artifacts=artifacts, crash_report_path=crash_report_path,
            duration_s=duration_s, wakes=wakes)


if __name__ == "__main__":  # `python -m courier_worker.host`
    import sys as _sys

    from courier_worker.service import main as _main

    _sys.exit(_main())
