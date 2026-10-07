"""Small shared persistence, STOP fencing and process-ownership primitives."""
import fcntl
import hashlib
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path

CANONICAL_WORKSPACE = "/Users/user/Downloads/2026-courier"
# Captured before tests replace subprocess.Popen with a recorder.
_POPEN_TYPE = subprocess.Popen

_PS_IDENTITY_TIMEOUT_S = 0.25
_CLEANUP_MAX_ROUNDS = 3
_CLEANUP_ROUND_GRACE_S = 2.0


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


def _fingerprint(pid, pgid, extra=()):
    material = ":".join([str(int(pid)), str(int(pgid)), *map(str, extra)])
    return hashlib.sha256(material.encode()).hexdigest()


def _pgid_for_pid(pid):
    try:
        return int(os.getpgid(int(pid)))
    except (OSError, ValueError):
        return None


def _linux_start_fields(pid):
    try:
        stat = Path(f"/proc/{int(pid)}/stat").read_text().split()
        comm = Path(f"/proc/{int(pid)}/comm").read_text().strip()
    except OSError:
        return None
    if len(stat) < 22:
        return None
    return stat[21], comm


def _ps_identity(pid, timeout_s=_PS_IDENTITY_TIMEOUT_S):
    """Optional enrichment; must never be the only way to obtain pgid."""
    try:
        value = subprocess.check_output(
            ["ps", "-p", str(int(pid)), "-o", "pid=,pgid=,lstart=,comm="],
            text=True, timeout=timeout_s, stderr=subprocess.DEVNULL).strip()
        parts = value.split()
        if len(parts) < 8 or int(parts[0]) != int(pid):
            return None
        return {"pid": int(pid), "pgid": int(parts[1]),
                "fingerprint": hashlib.sha256(" ".join(parts[:7]).encode()).hexdigest(),
                "source": "ps"}
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


def capture_process_identity(proc):
    """Identity from a Popen we own. Never depends on a later ps discovery."""
    pid = int(proc.pid)
    pgid = _pgid_for_pid(pid)
    if pgid is None:
        return None
    extra = []
    if sys.platform.startswith("linux"):
        fields = _linux_start_fields(pid)
        if fields:
            extra.extend(fields)
    ident = {"pid": pid, "pgid": pgid, "fingerprint": _fingerprint(pid, pgid, extra),
             "captured_at_spawn": True, "source": "spawn"}
    enriched = _ps_identity(pid)
    if enriched and enriched.get("pgid") == pgid:
        ident["fingerprint"] = enriched["fingerprint"]
        ident["source"] = "spawn+ps"
    return ident


def process_identity(pid):
    """Best-effort identity for a live pid. OS primitives first; ps is optional."""
    pid = int(pid)
    pgid = _pgid_for_pid(pid)
    if pgid is None:
        return None
    extra = []
    if sys.platform.startswith("linux"):
        fields = _linux_start_fields(pid)
        if fields:
            extra.extend(fields)
    ident = {"pid": pid, "pgid": pgid, "fingerprint": _fingerprint(pid, pgid, extra),
             "source": "os"}
    enriched = _ps_identity(pid)
    if enriched and enriched.get("pgid") == pgid:
        return enriched
    return ident


def identity_matches(pid, identity):
    if not identity or int(identity.get("pid", -1)) != int(pid):
        return False
    try:
        os.kill(int(pid), 0)
    except ProcessLookupError:
        pgid = identity.get("pgid")
        return pgid is not None and not group_exists(pgid)
    except OSError:
        return False
    pgid = _pgid_for_pid(pid)
    if pgid is None:
        return False
    if int(identity.get("pgid", -1)) != pgid:
        return False
    current = process_identity(pid)
    if current is not None and current.get("fingerprint") == identity.get("fingerprint"):
        return True
    return bool(identity.get("captured_at_spawn"))


def same_process(pid, identity):
    return identity_matches(pid, identity)


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


def process_group_stopped(proc, identity):
    """True only when the owned session group is gone or the direct child exited."""
    pgid = identity.get("pgid") if identity else _pgid_for_pid(proc.pid)
    if pgid is None:
        return proc.poll() is not None
    if not group_exists(pgid):
        _reap_direct(proc, 0)
        return True
    return proc.poll() is not None and not group_exists(pgid)
