"""Small shared persistence, STOP fencing and process-ownership primitives."""
import fcntl
import hashlib
import json
import os
import signal
import subprocess
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path

CANONICAL_WORKSPACE = "/Users/user/Downloads/2026-courier"
# Captured before tests replace subprocess.Popen with a recorder.
_POPEN_TYPE = subprocess.Popen


def read_object(path, default=None):
    try:
        value = json.loads(Path(path).read_text())
    except FileNotFoundError:
        return {} if default is None else default
    if not isinstance(value, dict):
        raise ValueError(f"Non-object state: {path}")
    return value  # Corruption/permission errors are NOT an empty installation.


def sync_directory(path):
    fd = os.open(str(path), os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as handle:
            json.dump(value, handle, sort_keys=True)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
        sync_directory(path.parent)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


@contextmanager
def control_lock(wall):
    """STOP, admission, spawn and claim use the same linearization lock."""
    wall = Path(wall)
    wall.mkdir(parents=True, exist_ok=True)
    with open(wall / "control.lock", "a") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        yield


def process_identity(pid):
    """No command arguments/secrets persisted; include OS start time, PGID, executable."""
    try:
        value = subprocess.check_output(
            ["ps", "-p", str(int(pid)), "-o", "pid=,pgid=,lstart=,comm="],
            text=True, timeout=2, stderr=subprocess.DEVNULL).strip()
        parts = value.split()
        if len(parts) < 8 or int(parts[0]) != int(pid):
            return None
        return {"pid": int(pid), "pgid": int(parts[1]),
                # exec() may change executable names without changing ownership.
                "fingerprint": hashlib.sha256(" ".join(parts[:7]).encode()).hexdigest()}
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


def same_process(pid, identity):
    return bool(identity and process_identity(pid) == identity)


def group_exists(pgid):
    try:
        os.killpg(int(pgid), 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def _owned_unreaped_session(proc):
    """True for our unreaped start_new_session child (pgid == pid).

    The PID cannot be reused until this Popen is reaped, and killpg(pid)
    reaches only that session. Recovered handles are not Popen objects.
    """
    if not isinstance(proc, _POPEN_TYPE) or proc.returncode is not None:
        return False
    getpgid = getattr(os, "getpgid", None)
    if getpgid is None:
        return False
    try:
        return getpgid(proc.pid) == proc.pid
    except OSError:
        return False


def _reap_direct(proc, timeout):
    """Collect the direct child. Recovered processes have no wait()."""
    if isinstance(proc, _POPEN_TYPE) and proc.returncode is None:
        try:
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            pass
    else:
        proc.poll()


def cleanup_group(proc, identity, grace=2.0):
    """Only an owned Popen session or a revalidated identity authorizes signals.

    If a different leader has reused the PID, do not signal it. A surviving
    child group without a leader remains ours while its PGID exists.
    A real subprocess.Popen that is still unreaped and is its own session
    leader authorizes SIGTERM then SIGKILL without a recorded identity.
    Recovered (non-Popen) processes still require identity.
    """
    pgid = proc.pid
    if proc.poll() is not None and not group_exists(pgid):
        return True
    owned_session = _owned_unreaped_session(proc)
    if identity is None:
        if not owned_session:
            return False
    elif identity.get("pgid") != pgid:
        return False
    elif not owned_session:
        current = process_identity(pgid)
        if current is not None and current != identity:
            return False
    for sig in (signal.SIGTERM, signal.SIGKILL):
        if not group_exists(pgid):
            _reap_direct(proc, 0)
            return True
        # Once the direct child is reaped, a missing identity no longer proves
        # this PGID. Do not signal a recovered group on that basis.
        if identity is None and not _owned_unreaped_session(proc):
            _reap_direct(proc, 0)
            return not group_exists(pgid)
        if identity is not None and not _owned_unreaped_session(proc):
            current = process_identity(pgid)
            if current is not None and current != identity:
                return False
        try:
            os.killpg(pgid, sig)
        except ProcessLookupError:
            _reap_direct(proc, 0)
            return True
        deadline = time.monotonic() + grace
        while time.monotonic() < deadline:
            remaining = max(0.0, deadline - time.monotonic())
            if isinstance(proc, _POPEN_TYPE) and proc.returncode is None:
                _reap_direct(proc, min(0.05, remaining))
            else:
                proc.poll()
                time.sleep(min(0.05, remaining))
            if not group_exists(pgid):
                return True
    _reap_direct(proc, 0)
    return not group_exists(pgid)
